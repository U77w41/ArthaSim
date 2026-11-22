import polars as pl
from arthasim import Config, World
from helpers import P


def cfg(tmp_path, **kw):
    base = dict(persons=5_000, out_dir=str(tmp_path))
    base.update(kw)
    return Config.tier("S", **base)


def test_population_world_runs_on_the_new_modules(tmp_path):
    world = World.build(cfg(tmp_path), seed=7)
    assert [m.name for m in world.modules] == ["lifecourse", "income", "remittances", "dbt", "budget", "allowance", "consumption",
                                                "cash"]
    run = world.run(until="2025-05-20")
    pay = run.table("payments").collect()
    purposes, rails = set(pay["purpose"].unique()), set(pay["rail"].unique())
    assert run.manifest["days"] == 50 and "UNSPECIFIED" not in purposes
    wd = pay.filter(pl.col("purpose") == "CASH_WITHDRAWAL")["amount_paise"]
    assert (wd % P.get("cash.withdrawal_note_paise") == 0).all() and (wd != P.get("spike.cash_withdrawal_paise")).any()
    assert {"SALARY", "EARNINGS", "PENSION", "EMPLOYER_REVENUE", "REMITTANCE", "GROCERY", "TRANSPORT",
            "UTILITIES", "TELECOM", "CASH_WITHDRAWAL", "CASH_DEPOSIT"} <= purposes
    assert {"UPI_P2M", "UPI_P2P", "DEBIT_CARD", "CASH", "NACH_CR", "NEFT", "ATM", "AEPS", "BRANCH"} <= rails
    s = world.state
    assert int(s.book.balance[s.merchant_cash].sum()) < 10 * len(s.merchant_cash) * P.get("cash.merchant_float_paise")
    monthly = run.table("truth_household_monthly").collect()
    assert monthly.columns == ["household_id", "month", "income_paise", "balance_paise", "buffer_months",
                               "stress", "budget_paise", "medical_due_paise"]
    assert monthly["month"].unique().sort().to_list() == ["2025-04", "2025-05"]
    assert monthly.height == 2 * len(s.population.households.adults)


def test_unbanked_earners_are_paid_in_cash(tmp_path):
    world = World.build(cfg(tmp_path), seed=7)
    s = world.state
    pay = world.run(until="2025-04-30").table("payments").collect()
    unbanked_cash = s.person_cash[s.person_deposit == -1].tolist()
    income = pay.filter(pl.col("payee_account_id").is_in(unbanked_cash)
                        & pl.col("purpose").is_in(["EARNINGS", "PENSION"]))
    assert income.height > 0 and (income["rail"] == "CASH").all() and (income["status"] == "SUCCESS").all()


def test_mid_month_start_split_run_and_determinism(tmp_path):
    one = World.build(cfg(tmp_path / "one", start="2025-04-20"), seed=7).run(until="2025-05-05")
    assert one.table("truth_household_monthly").collect()["month"].unique().sort().to_list() == ["2025-04", "2025-05"]
    world = World.build(cfg(tmp_path / "two", start="2025-04-20"), seed=7)
    world.step(5)
    two = world.run(until="2025-05-05")
    assert one.manifest["content_hash"] == two.manifest["content_hash"]
    other = World.build(cfg(tmp_path / "three", start="2025-04-20"), seed=8).run(until="2025-05-05")
    assert other.manifest["content_hash"]["payments"] != one.manifest["content_hash"]["payments"]


def test_spike_world_is_unchanged(tmp_path):
    spike = World.build(Config.tier("XS", persons=500, employers=10, merchants=30, out_dir=str(tmp_path)), seed=7)
    run = spike.run(until="2025-04-03")
    assert [m.name for m in spike.modules] == ["spike_income", "spike_consumption"]
    assert "truth_household_monthly" not in run.tables()
    assert set(run.table("payments").collect()["purpose"].unique()) <= {"SALARY", "EMPLOYER_REVENUE", "OTHER",
                                                                         "CASH_WITHDRAWAL"}
