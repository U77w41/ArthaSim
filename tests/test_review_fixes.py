"""Tests for the final review's findings (plan 1c)."""
import gc
import json
from pathlib import Path

import polars as pl
import pytest

from arthasim import Config, World, Run


def _cfg(tmp_path, name, start="2025-04-20", persons=2_000):
    return Config.tier("S", persons=persons, start=start, out_dir=str(tmp_path / name))


def _salaried(world):
    s = world.state
    return int(s.person_ids[(s.person_employer >= 0) & (s.person_deposit >= 0)][0])


def test_raising_callback_leaves_world_ready_to_continue(tmp_path):
    """I1: a callback that raises must not leave the day half-done; continuing gives the clean run."""
    w = World.build(_cfg(tmp_path, "w"), seed=7)
    eid = _salaried(w)

    def boom(payload):
        if payload["date"].isoformat() == "2025-04-22":
            raise RuntimeError("stop")

    w.watch(eid, boom)
    with pytest.raises(RuntimeError):
        w.run(until="2025-04-25")
    assert w.date.isoformat() == "2025-04-23"                 # the 22nd is done
    w.unwatch(eid)
    resumed = w.run(until="2025-04-25")
    clean = World.build(_cfg(tmp_path, "c"), seed=7).run(until="2025-04-25")
    assert resumed.manifest["content_hash"] == clean.manifest["content_hash"]


def test_run_is_readable_while_running_and_after_an_error(tmp_path):
    """I2: files still being written are not visible under their final names; an error closes them."""
    w = World.build(_cfg(tmp_path, "r"), seed=7)
    w._store.row_group_rows = 1_000                          # so open files hold row groups mid-month
    w.step(1)
    seen = []

    def read_during(payload):
        if payload["date"].isoformat() == "2025-04-25":
            run = Run.open(w.path)
            seen.append(run.table("payments").select(pl.len()).collect().item())
            seen.append(run.view("bank", bank="SYNB03").table("payments").select(pl.len()).collect().item())
        if payload["date"].isoformat() == "2025-04-27":
            raise RuntimeError("stop")

    w.watch(_salaried(w), read_during)
    with pytest.raises(RuntimeError):
        w.run(until="2025-04-30")
    assert len(seen) == 2 and seen[0] > 0
    after = Run.open(w.path)
    assert after.table("payments").select(pl.len()).collect().item() > seen[0]
    assert not list(Path(w.path).rglob("part-*.parquet.tmp"))


def test_truth_view_asof_cut_keeps_file_order():
    """I3: a cut through a semi-join must still come back in file order, the same every time."""
    from run_fixture import small_run
    run = small_run()
    v = run.view("truth", asof="2025-05-10")
    a = v.table("postings").collect()
    b = v.table("postings").collect()
    assert a.equals(b)
    keep = set(v.table("journal").collect()["journal_id"].to_list())
    want = run.table("postings").filter(pl.col("journal_id").is_in(list(keep))).collect()
    assert a.equals(want)
    inst = v.table("instruments").collect()
    assert inst.equals(v.table("instruments").collect())
    assert inst["instrument_id"].is_sorted()


class _Counting:
    """A DuckDB connection that records every statement it runs."""

    def __init__(self, con):
        self._con, self.statements = con, []

    def sql(self, q, *a, **kw):
        self.statements.append(q)
        return self._con.sql(q, *a, **kw)

    def execute(self, q, *a, **kw):
        self.statements.append(q)
        return self._con.execute(q, *a, **kw)

    def __getattr__(self, name):
        return getattr(self._con, name)


def test_export_reads_each_table_once(tmp_path, monkeypatch):
    """I4: each view table's query runs once; months are copied from that one result."""
    import duckdb
    import arthasim.export as export
    from run_fixture import small_run
    made = []
    real = duckdb.connect

    def connect(*a, **kw):
        made.append(_Counting(real(*a, **kw)))
        return made[-1]

    monkeypatch.setattr(export.duckdb, "connect", connect)
    small_run().export(tmp_path / "x", view="bank", bank="SYNB03")
    reads = [q for c in made for q in c.statements if "read_parquet(" in q]
    assert len(reads) == 6                                     # one per bank-view table


def test_finished_runs_keep_no_spool(tmp_path):
    """I5: the open month's spool lives outside the run folder and goes when the world does."""
    w = World.build(_cfg(tmp_path, "s", start="2025-04-28"), seed=7)
    run = w.run(until="2025-05-03")                            # ends mid-May
    assert not Path(run.path, ".spool").exists()
    spool = w._store.spool_dir
    assert spool.exists() and any(spool.iterdir())             # May's spool, kept while the world can continue
    assert not [f for f in spool.iterdir() if "2025-04" in f.name]
    del w
    gc.collect()
    assert not spool.exists()


def _blake(seed, stream, i):
    import hashlib
    key = hashlib.blake2b(f"arthasim.ids/{seed}/{stream}".encode(), digest_size=32).digest()
    return int.from_bytes(hashlib.blake2b(int(i).to_bytes(8, "little", signed=True), key=key,
                                          digest_size=8).digest(), "little")


def test_identifier_tokens_are_keyed_one_way_hashes():
    """I6: tokens are keyed BLAKE2b digests, not an invertible mix of (seed, stream, id)."""
    import numpy as np
    from arthasim.build.identifiers import account_no, customer_no, token
    from arthasim.engine import rng
    ids = np.array([0, 1, 32, 41872], dtype=np.int64)
    assert token("u", 7, 99, ids).tolist() == [f"u_{_blake(7, 99, i):016x}" for i in ids]
    s = rng.stream_id("id.account_no")
    assert account_no(7, ids, ["SYNB03"] * 4).tolist() == [f"SYNB03-{_blake(7, s, i):016x}" for i in ids]
    s = rng.stream_id("id.customer_no")
    assert customer_no(7, ids, np.full(4, 2), ["SYNB03"] * 4).tolist() == \
        [f"CIFSYNB03-{_blake(7, s, i * 64 + 2):016x}" for i in ids]


def test_export_carries_no_seed_and_says_what_it_protects(tmp_path):
    from run_fixture import small_run
    run = small_run()
    dest = run.export(tmp_path / "b", view="bank", bank="SYNB03")
    text = (dest / "manifest.json").read_text() + (dest / "README.md").read_text()
    assert "seed" not in text.lower() and run.manifest["run_id"] not in text
    m = json.loads((dest / "manifest.json").read_text())
    assert "source_run_id" not in m and len(m["source_run"]) == 16
    readme = (dest / "README.md").read_text()
    assert "not anonymised" in readme and "pan_like" in readme and "ref" in readme


def test_deposit_balance_before_any_month_has_closed(tmp_path):
    """Minor 1, re-graded: a run with no closed month gives an empty frame, like net_worth, not an error."""
    run = World.build(_cfg(tmp_path, "d", start="2025-04-20"), seed=7).run(until="2025-04-25")
    assert "balances_monthly" not in run.tables()
    db = run.metric("deposit_balance", by="bank")
    assert db.columns == ["month", "bank", "value"] and db.height == 0
