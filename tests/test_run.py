import polars as pl
import pytest
from arthasim import Config, World, Run


def cfg(tmp_path, **kw):
    base = dict(persons=500, employers=10, merchants=30, out_dir=str(tmp_path))
    base.update(kw)
    return Config.tier("XS", **base)


def test_three_day_run_tables_and_manifest(tmp_path):
    run = World.build(cfg(tmp_path), seed=7).run(until="2025-04-03")
    assert set(run.tables()) == {"payments", "journal", "postings", "persons", "orgs", "banks", "accounts"}
    pay = run.table("payments").collect()
    assert pay.columns == ["payment_id", "intent_ts", "settle_ts", "rail", "status", "amount_paise",
                           "payer_account_id", "payee_account_id", "payer_bank", "payee_bank",
                           "journal_id", "purpose"]
    ok = pay.filter(pl.col("status") == "SUCCESS")
    assert ok["journal_id"].null_count() == 0
    assert pay.filter(pl.col("status") != "SUCCESS")["journal_id"].null_count() == pay.height - ok.height
    assert pay["payment_id"].n_unique() == pay.height and pay["settle_ts"].is_sorted()
    sums = run.sql("select journal_id, sum(delta_paise) s from postings group by 1 having sum(delta_paise) <> 0 "
                   "and journal_id not in (select journal_id from journal where kind = 3)")
    assert sums.height == 0
    m = run.manifest
    assert m["seed"] == 7 and m["days"] == 3 and m["payments"] == pay.height and m["end"] == "2025-04-03"
    assert Run.open(run.path).manifest == m


def test_same_seed_same_content_other_seed_differs(tmp_path):
    a = World.build(cfg(tmp_path / "a"), seed=7).run(until="2025-04-05").manifest["content_hash"]
    b = World.build(cfg(tmp_path / "b"), seed=7).run(until="2025-04-05").manifest["content_hash"]
    c = World.build(cfg(tmp_path / "c"), seed=8).run(until="2025-04-05").manifest["content_hash"]
    assert a == b and a["payments"] != c["payments"]


def test_split_run_equals_single_run_across_month_boundary(tmp_path):
    one = World.build(cfg(tmp_path / "one", start="2025-04-25"), seed=7).run(until="2025-05-05")
    w = World.build(cfg(tmp_path / "two", start="2025-04-25"), seed=7)
    w.step(4)
    two = w.run(until="2025-05-05")
    for t in ("payments", "journal", "postings"):
        assert one.table(t).collect().equals(two.table(t).collect())
    months = one.table("payments").select(pl.col("settle_ts").cast(pl.Datetime("us", "Asia/Kolkata"))
                                          .dt.strftime("%Y-%m").unique()).collect()
    assert sorted(months.to_series().to_list()) == ["2025-04", "2025-05"]
    assert one.manifest["days"] == 11


def test_existing_run_directory_is_not_overwritten(tmp_path):
    World.build(cfg(tmp_path), seed=7).run(until="2025-04-02")
    with pytest.raises(FileExistsError):
        World.build(cfg(tmp_path), seed=7)


@pytest.mark.parametrize("kw", [{"banks": 1}, {"employers": 0}])
def test_degenerate_configs_run(tmp_path, kw):
    run = World.build(cfg(tmp_path, **kw), seed=7).run(until="2025-04-04")
    assert run.manifest["days"] == 4 and run.table("payments").collect().height > 0
