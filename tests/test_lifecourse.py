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


def test_small_world_runs_a_full_year(tmp_path):
    # Tiny cells make raking converge slowly near the floor; that must not stop the run.
    run = World.build(cfg(tmp_path, persons=300), seed=7).run(until="2026-03-31")
    assert run.manifest["days"] == 365


def test_helper_flips_never_reverse_in_the_same_month(tmp_path):
    rates = {"life.within.helper_to_own": 0.5, "life.within.own_to_helper": 0.5}
    run = World.build(cfg(tmp_path).with_params(**rates), seed=7).run(until="2025-06-30")
    ev = run.table("life_events").collect()
    own = ev.filter(pl.col("event") == "BECAME_OWN_ACCOUNT").select("entity_id", "date")
    helper = ev.filter(pl.col("event") == "BECAME_HELPER").select("entity_id", "date")
    assert own.height > 0 and helper.height > 0
    assert own.join(helper, on=["entity_id", "date"]).height == 0


def test_raises_come_once_a_year_and_not_soon_after_joining(tmp_path):
    run = World.build(cfg(tmp_path).with_params(**{"life.switch.monthly_prob": 0.2}), seed=7).run(until="2025-12-31")
    ev = (run.table("life_events").collect()
          .with_columns((pl.col("date").dt.year() * 12 + pl.col("date").dt.month()).alias("m")))
    raises = ev.filter(pl.col("event") == "RAISE").sort(["entity_id", "m"])
    gaps = raises.with_columns((pl.col("m") - pl.col("m").shift(1).over("entity_id")).alias("gap"))["gap"].drop_nulls()
    assert raises.height > 0 and (gaps >= 12).all()
    joined = ev.filter(pl.col("event").is_in(["HIRED", "JOB_SWITCH"])).select("entity_id", pl.col("m").alias("j"))
    after = raises.join(joined, on="entity_id").filter((pl.col("m") >= pl.col("j")) & (pl.col("m") - pl.col("j") < 6))
    assert joined.height > 0 and after.height == 0
