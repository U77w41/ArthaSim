import datetime as dt

import duckdb
import polars as pl
import pytest

from arthasim import Config, World
from arthasim.views import asof_us, month_end
from run_fixture import small_run


def test_asof_helpers():
    assert asof_us("2025-04-30") == asof_us(dt.date(2025, 4, 30))
    assert asof_us("2025-04-30") - asof_us("2025-04-29") == 86_400_000_000
    assert month_end("2025-04-30") == "2025-04" and month_end("2025-05-10") == "2025-04"
    assert month_end("2025-05-31") == "2025-05" and month_end("2025-01-15") == "2024-12"


def test_truth_view_matches_run_tables():
    run = small_run()
    v = run.view("truth")
    assert v.tables() == sorted(run.tables())
    assert v.table("payments").collect().equals(run.table("payments").collect())
    assert v.table("persons").collect().equals(run.table("persons").collect())
    assert v.sql("select count(*) n from postings")["n"][0] == run.table("postings").collect().height


def test_asof_cuts_fact_tables():
    run = small_run()
    v = run.view("truth", asof="2025-05-01")
    pay = v.table("payments").collect()
    assert 0 < pay.height < run.table("payments").collect().height
    assert pay["settle_ts"].max() < asof_us("2025-05-01") <= run.table("payments").collect()["settle_ts"].max()
    jids = set(v.table("journal").collect()["journal_id"].to_list())
    assert set(v.table("postings").collect()["journal_id"].to_list()) == jids
    assert v.table("entity_state_monthly").collect()["month"].unique().sort().to_list() == ["2025-04", "2025-05"]
    assert v.table("balances_monthly").collect()["month"].unique().to_list() == ["2025-04"]
    assert v.table("payments", asof="2025-04-19").collect().height == 0                # before the start: empty
    assert v.table("balances_monthly", asof="2025-04-29").collect().height == 0
    assert v.table("payments", asof="2026-01-01").collect().height == run.table("payments").collect().height
    late = run.table("accounts").filter(pl.col("opened_on") > dt.date(2025, 5, 1)).collect().height
    assert v.table("accounts").collect().height == run.table("accounts").collect().height - late


def test_view_sql_cannot_name_other_tables():
    bank = small_run().view("bank", bank="SYNB01")
    assert "persons" not in bank.tables()
    with pytest.raises(duckdb.CatalogException):
        bank.sql("select * from persons")


def test_view_errors(tmp_path):
    with pytest.raises(ValueError, match="bank, switch, bureau, truth"):
        small_run().view("aa")
    spike = World.build(Config.tier("XS", persons=300, employers=5, merchants=20, out_dir=str(tmp_path)),
                        seed=7).run(until="2025-04-02")
    with pytest.raises(ValueError, match="population-built"):
        spike.view("truth")
