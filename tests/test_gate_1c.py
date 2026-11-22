import json

import duckdb
from pathlib import Path

import polars as pl
import pytest

from arthasim import Config, World
from arthasim.export import is_id
from arthasim.store.hashing import content_hash
from arthasim.views import Source, asof_us, lines_sql


@pytest.mark.slow
def test_plan_1c_gate(tmp_path):
    world = World.build(Config.tier("S", out_dir=str(tmp_path)), seed=7)
    world.step(85)
    s = world.state
    eid = int(s.person_ids[(s.person_employer >= 0) & (s.person_deposit >= 0)][0])
    calls = []
    world.watch(eid, calls.append)
    run = world.run(until="2025-06-29")
    assert run.manifest["days"] == 90

    for t in run.tables():
        assert run.manifest["content_hash"][t] == content_hash(run.path, t), t
    assert not Path(run.path, ".spool").exists() and not list(world._store.spool_dir.glob("*2025-05*"))

    cut = run.view("truth", asof="2025-06-10")
    first, second = cut.table("postings").collect(), cut.table("postings").collect()
    keep = cut.table("journal").select("journal_id").collect()["journal_id"]
    assert first.equals(second) and first.equals(
        run.table("postings").filter(pl.col("journal_id").is_in(keep.implode())).collect())

    v = run.view("bank", bank="SYNB03")
    last = v.sql("""select account_id, month, arg_max(balance_after_paise, line_seq) as b
                    from (select *, strftime(date, '%Y-%m') as month from statement_lines) group by 1, 2""")
    bal = v.table("balances_monthly").collect()
    joined = last.join(bal, on=["account_id", "month"])
    assert joined.height > 0 and (joined["b"] == joined["balance_paise"]).all()
    assert set(bal["month"].to_list()) == {"2025-04", "2025-05"}

    upi = run.view("switch").sql("select count(*) n, count(distinct payment_id) d from payments")
    truth = run.sql("select count(*) n from payments where rail in ('UPI_P2M', 'UPI_P2P')")
    assert upi["n"][0] == upi["d"][0] == truth["n"][0]

    dest = tmp_path / "export"
    run.export(dest, view="bank", bank="SYNB03")
    m = json.loads((dest / "manifest.json").read_text())
    for t, meta in m["tables"].items():
        got = pl.scan_parquet(dest / t, hive_partitioning=True) if meta["layout"] == "month" \
            else pl.scan_parquet(dest / f"{t}.parquet")
        assert not [c for c in got.collect_schema().names() if is_id(c)], t
        assert got.select(pl.len()).collect().item() == meta["rows"] == \
            v.table(t).select(pl.len()).collect().item(), t

    # One person's statement lines fit in 300 MB without spilling (they join only their own payments).
    src = Source(run.path)
    capped = duckdb.connect(config={"memory_limit": "300MB", "max_temp_directory_size": "0B"})
    mine = f"select account_id from {src('accounts')} where holder_entity_id = {eid}"
    assert capped.sql(lines_sql(src, mine, None, truth=True)).pl().height > 0

    accounts = ", ".join(map(str, run.sql(f"select account_id from accounts where holder_entity_id = {eid}")
                                ["account_id"].to_list()))
    window = run.sql(f"""select payment_id from payments where settle_ts >= {asof_us('2025-06-24')}
                         and (payer_account_id in ({accounts}) or payee_account_id in ({accounts}))""")
    watched = sorted(p["payment_id"] for c in calls for p in c["payments"])
    assert watched and watched == sorted(window["payment_id"].to_list())
    assert {c["date"].isoformat() for c in calls} <= {f"2025-06-{d}" for d in range(25, 30)}
