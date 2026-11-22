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
