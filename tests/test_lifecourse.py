import datetime as dt
import numpy as np
import polars as pl
from arthasim import Config, World
from arthasim.build import categories as c
from arthasim.life.helpers import orphaned


def cfg(tmp_path, **kw):
    return Config.tier("S", **{"persons": 5_000, "out_dir": str(tmp_path), **kw})


def test_three_months_on_target_with_consistent_events(tmp_path):
    world = World.build(cfg(tmp_path), seed=7)
    assert [m.name for m in world.modules][0] == "lifecourse"
    run = world.run(until="2025-06-30")
    esm = run.table("entity_state_monthly").collect()
    assert esm["month"].unique().sort().to_list() == ["2025-04", "2025-05", "2025-06"]
    s, t = world.state, world.state.life.targets
    p = s.population.persons
    for month in ("2025-05", "2025-06"):
        m = esm.filter(pl.col("month") == month).sort("entity_id")
        stage = np.array([c.LIFE_STAGE.index(x) for x in m["life_stage"].to_list()])
        age = m["age"].to_numpy()
        for d in (0, 1):
            for sex in (c.F, c.M):
                sel = (p.district == d) & (p.sex == sex)
                cell, want = t.counts(dt.date.fromisoformat(month + "-01"), d, sex, age[sel])
                got = np.zeros_like(want)
                np.add.at(got, (cell, stage[sel]), 1)
                assert np.array_equal(got, want), (month, d, sex)
    ev = run.table("life_events").collect()
    changes = (esm.sort(["entity_id", "month"])
               .with_columns(pl.col("life_stage").shift(1).over("entity_id").alias("prev"))
               .filter(pl.col("prev").is_not_null() & (pl.col("prev") != pl.col("life_stage"))))
    stage_events = ev.filter(pl.col("from_stage").is_not_null())
    assert stage_events.height == changes.height > 0
    assert {"HIRED", "LAID_OFF", "RAISE"} <= set(ev["event"].unique())
    sal = esm.filter((pl.col("month") == "2025-06") & (pl.col("life_stage") == "salaried"))
    assert sal["employer_entity_id"].null_count() == 0 and sal["has_account"].all()
    payroll = np.zeros(len(s.employer_ids), dtype=np.int64)
    np.add.at(payroll, s.person_employer[s.person_employer >= 0], s.person_salary[s.person_employer >= 0])
    assert np.array_equal(payroll, s.employer_payroll)
    live, inc, helper = p.life_stage, s.population.attributes.monthly_income_paise, s.life.helper
    assert not orphaned(live, s.population.households.household_of_person, helper).any()
    assert (inc[helper] == 0).all() and (inc[np.isin(live, [c.FARM, c.SELF_EMPLOYED]) & ~helper] > 0).all()
    assert ((s.person_employer >= 0) == (live == c.SALARIED)).all()


def test_hire_without_account_gets_paid_into_the_new_account(tmp_path):
    run = World.build(cfg(tmp_path), seed=7).run(until="2025-06-30")
    ev = run.table("life_events").collect()
    opened = ev.filter(pl.col("event") == "ACCOUNT_OPENED").select("entity_id", "account_id", "date")
    hired = ev.filter(pl.col("event") == "HIRED").select("entity_id", "date")
    both = opened.join(hired, on=["entity_id", "date"])
    assert both.height > 0
    pay = run.table("payments").collect().filter(pl.col("purpose") == "SALARY")
    paid = both.join(pay, left_on="account_id", right_on="payee_account_id")
    assert paid.select("entity_id").n_unique() == both.height


def test_mid_month_start_split_run_and_outside_window(tmp_path):
    one = World.build(cfg(tmp_path / "a", start="2025-04-20"), seed=7).run(until="2025-05-05")
    assert one.table("life_events").filter(pl.col("from_stage").is_not_null()).collect()["date"].min() == dt.date(2025, 5, 1)
    w = World.build(cfg(tmp_path / "b", start="2025-04-20"), seed=7)
    w.step(5)
    two = w.run(until="2025-05-05")
    assert one.manifest["content_hash"] == two.manifest["content_hash"]
    late = World.build(cfg(tmp_path / "c", start="2026-03-20"), seed=7).run(until="2026-05-05")
    assert late.table("entity_state_monthly").collect()["month"].unique().sort().to_list() == ["2026-03", "2026-04", "2026-05"]
