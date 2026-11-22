import datetime as dt

import polars as pl

from arthasim import Config, World
from arthasim.engine.scheduler import day_start_us
from run_fixture import small_run


def test_closing_balance_is_last_posting_or_opening():
    run = small_run()
    bal = run.table("balances_monthly").collect()
    assert bal.columns == ["account_id", "month", "balance_paise"]
    assert bal["month"].unique().to_list() == ["2025-04"]             # May is still open: no row
    accounts = run.table("accounts").filter(pl.col("opened_on") <= dt.date(2025, 4, 30)).collect()
    assert bal.height == accounts.height and bal["account_id"].is_sorted()
    may1 = day_start_us(dt.date(2025, 5, 1))
    last = run.sql(f"""select p.account_id, arg_max(p.balance_after_paise, p.journal_id * 64 + p.line_no) b
                       from postings p join journal j using (journal_id) where j.ts < {may1} group by 1""")
    joined = bal.join(last, on="account_id", how="left").join(accounts, on="account_id")
    expect = joined.select(pl.coalesce("b", "opening_balance_paise"))["b"]
    assert (joined["balance_paise"] == expect).all()
    assert joined["b"].null_count() < joined.height                   # most accounts moved in April


def test_balances_are_written_once_per_month_in_split_runs(tmp_path):
    w = World.build(Config.tier("S", persons=2_000, start="2025-04-28", out_dir=str(tmp_path)), seed=7)
    w.step(2)                                                          # 28 and 29 April
    run = w.run(until="2025-05-02")
    bal = run.table("balances_monthly").collect()
    assert bal["month"].unique().to_list() == ["2025-04"]
    april = run.table("accounts").filter(pl.col("opened_on") <= dt.date(2025, 4, 30)).collect().height
    assert bal["account_id"].n_unique() == bal.height == april
