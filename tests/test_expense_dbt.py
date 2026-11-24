"""Expense shocks and scenario DBT transfers (plan 1d-2, Task 8)."""
import functools
import tempfile
from pathlib import Path

import polars as pl
import pytest

from arthasim import Config, World
from arthasim.interventions import DBTTransfer, ExpenseShock
from helpers import data_files

FARMERS = "life_stage == 'farm' and not helper"
BANKS = [f"SYNB{i:02d}" for i in range(1, 13)]
IST = "make_timestamp(y.intent_ts) + interval 330 minute"


def build(path):
    return World.build(Config.tier("S", persons=5_000, out_dir=str(path)), 7, path=Path(path) / "run",
                       checkpoints=False)


@functools.lru_cache(maxsize=None)
def plain_run():
    """No intervention, to 2025-06-01. Read-only."""
    return build(tempfile.mkdtemp(prefix="arthasim-plain-")).run("2025-06-01")


def household(run, month, column):
    return dict(run.sql(f"select household_id, {column} from truth_household_monthly where month = '{month}'")
                .iter_rows())


def test_dbt_transfer(tmp_path):
    world = build(tmp_path)
    world.apply(DBTTransfer("TEST_TRANCHE", 2000, FARMERS, ["2025-05-15"]))
    run = world.run("2025-06-01")
    farmers = set(run.sql("""select entity_id from entity_state_monthly where month = '2025-05'
                             and life_stage = 'farm' and not helper""")["entity_id"])
    dbt = run.sql("select * from truth_dbt_monthly where scheme = 'TEST_TRANCHE'")
    assert farmers and set(dbt["entity_id"]) == farmers and dbt["enrolled"].all()
    assert set(dbt["monthly_value_paise"]) == {200_000} and set(dbt["month"]) == {"2025-05"}
    pay = run.sql(f"""select y.amount_paise, y.rail, y.status, strftime({IST}, '%Y-%m-%d') as day, hour({IST}) as hour
                      from payments y where y.purpose = 'DBT_OTHER'""")
    assert pay.height == len(farmers) and set(pay["amount_paise"]) == {200_000} and set(pay["rail"]) == {"APBS"}
    assert set(pay["status"]) == {"SUCCESS"} and set(pay["day"]) == {"2025-05-15"}
    assert set(pay["hour"]) <= {6, 7, 8, 9}
    unbanked = set(plain_run().sql("""select entity_id from entity_state_monthly where month = '2025-05'
                                      and life_stage = 'farm' and not helper and not has_account""")["entity_id"])
    opened = set(run.sql("""select entity_id from life_events where event = 'ACCOUNT_OPENED'
                            and date = '2025-05-01'""")["entity_id"])
    assert unbanked and unbanked <= opened
    assert dbt.filter(pl.col("entity_id").is_in(list(unbanked)))["opened_account"].all()
    # Transfer income: May households gain 200,000 paise per payee; June is as in the plain run.
    payees = run.sql(f"""select household_id, count(*) as n from persons
                         where entity_id in ({', '.join(map(str, farmers))}) group by 1""")
    per_household = dict(payees.iter_rows())
    may, plain_may = household(run, "2025-05", "transfer_income_paise"), household(plain_run(), "2025-05",
                                                                                    "transfer_income_paise")
    assert all(may[h] - plain_may[h] == 200_000 * per_household.get(h, 0) for h in may)
    assert household(run, "2025-06", "transfer_income_paise") == household(plain_run(), "2025-06",
                                                                           "transfer_income_paise")
    assert run.table("interventions_log").collect()["affected"].to_list() == [len(farmers)]
    lines = pl.concat([run.view("bank", bank=b).table("statement_lines").filter(pl.col("rail") == "APBS").collect()
                       for b in BANKS])
    assert lines.filter(pl.col("narration").str.ends_with("/DBT_OTHER")).height == len(farmers)


def test_dbt_errors(tmp_path):
    world = build(tmp_path)
    with pytest.raises(ValueError):
        world.apply(DBTTransfer("PM_KISAN", 1, "true", ["2025-05-15"]))
    world.apply(DBTTransfer("A", 1, "true", ["2025-05-15"]))
    with pytest.raises(ValueError):
        world.apply(DBTTransfer("A", 2, "true", ["2025-06-15"]))
    world.run("2025-05-02")
    with pytest.raises(ValueError):
        world.apply(DBTTransfer("B", 1, "true", ["2025-05-20"]))          # its month has begun


def test_dbt_and_expense_that_select_nobody(tmp_path):
    world = build(tmp_path)
    world.apply(DBTTransfer("NOBODY", 2000, "age > 500", ["2025-05-15"]))
    world.apply(ExpenseShock("2025-05-01", "age > 500", "medical", 1.0, months=1))
    run = world.run("2025-05-20")
    assert run.sql("select count(*) as n from payments where purpose = 'DBT_OTHER'")["n"][0] == 0
    assert run.table("interventions_log").collect()["affected"].to_list() == [0, 0]


def test_expense_shock(tmp_path):
    world = build(tmp_path)
    world.apply(ExpenseShock("2025-05-01", "district == 'rural_archetype'", "medical", 1.0, months=1))
    run = world.run("2025-06-01")
    rural = set(run.sql("select household_id from households where district = 'rural_archetype'")["household_id"])
    got, plain = household(run, "2025-05", "medical_due_paise"), household(plain_run(), "2025-05", "medical_due_paise")
    assert rural and all(got[h] >= plain[h] + 100 for h in rural)
    assert all(got[h] == plain[h] for h in got if h not in rural)
    assert household(run, "2025-06", "medical_due_paise") == household(plain_run(), "2025-06", "medical_due_paise")
    assert run.table("interventions_log").collect()["affected"].to_list() == [len(rural)]


def test_expense_shock_at_rate_zero_changes_nothing(tmp_path):
    world = build(tmp_path)
    world.apply(ExpenseShock("2025-05-01", "true", "medical", 0.0))
    run = world.run("2025-06-01")
    assert data_files(run.path) == data_files(plain_run().path)


# -- Deferred minors tidy-up -------------------------------------------------------------------------------------------

ON_5_MAY = f"strftime({IST}, '%Y-%m-%d') = '2025-05-05'"


def test_a_scenario_credit_and_a_pension_on_one_day_have_their_own_times(tmp_path):
    """A scenario scheme draws its credit times from its own streams, so a person paid by it and by the old-age
    pension on the 5th is not credited twice at one instant."""
    world = build(tmp_path)
    world.apply(DBTTransfer("TOP_UP", 500, "age >= 60", ["2025-05-05"]))
    run = world.run("2025-05-05")
    times = run.sql(f"""select y.payee_account_id as a, y.purpose, y.intent_ts as t from payments y
                        where y.purpose in ('DBT_OTHER', 'DBT_OLD_AGE_PENSION') and {ON_5_MAY}""")
    both = (times.filter(pl.col("purpose") == "DBT_OTHER")
            .join(times.filter(pl.col("purpose") == "DBT_OLD_AGE_PENSION"), on="a", suffix="_pension"))
    assert both.height >= 20
    assert (both["t"] == both["t_pension"]).sum() <= both.height // 20
    pension = plain_run().sql(f"""select y.payee_account_id as a, y.intent_ts as t from payments y
                                  where y.purpose = 'DBT_OLD_AGE_PENSION' and {ON_5_MAY}""")
    assert pension.sort("a").equals(times.filter(pl.col("purpose") == "DBT_OLD_AGE_PENSION").select("a", "t")
                                    .sort("a"))                         # the pension's own times are unchanged
