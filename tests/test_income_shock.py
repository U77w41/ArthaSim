"""Income shocks: layoffs held against alignment, pay cuts restored (plan 1d-2, Task 7)."""
import functools
import tempfile
from collections import Counter
from datetime import date
from pathlib import Path

import numpy as np
import pytest

from arthasim import Config, World
from arthasim.build import categories as c
from arthasim.interventions import IncomeShock, ParamOverride
from arthasim.life.state import month_index

METRO = "district == 'metro_archetype'"
DISTRICT = {"metro_archetype": 0, "rural_archetype": 1}


def config(path):
    return Config.tier("S", persons=5_000, out_dir=str(path))


def build(path):
    return World.build(config(path), 7, path=Path(path) / "run", checkpoints=False)


@functools.lru_cache(maxsize=None)
def plain_run():
    """No intervention, to 2025-07-01. Read-only."""
    return build(tempfile.mkdtemp(prefix="arthasim-plain-")).run("2025-07-01")


def salaried_by_cell(run, month):
    rows = run.sql(f"""select p.district, p.sex, e.age from entity_state_monthly e join persons p using (entity_id)
                       where e.month = '{month}' and e.life_stage = 'salaried'""")
    return Counter((DISTRICT[d] * 2 + c.SEX.index(s)) * c.N_AGE_GROUPS + int(c.age_group(a))
                   for d, s, a in rows.iter_rows())


def events(run, event, day):
    return set(run.sql(f"select entity_id from life_events where event = '{event}' and date = '{day}'")["entity_id"])


def shock_layoffs(run):
    """People the shock laid off on 1 May: the run's LAID_OFF events that day, less the life course's own."""
    return events(run, "LAID_OFF", "2025-05-01") - events(plain_run(), "LAID_OFF", "2025-05-01")


def cells_of(run, people, month):
    rows = run.sql(f"""select p.district, p.sex, e.age from entity_state_monthly e join persons p using (entity_id)
                       where e.month = '{month}' and e.entity_id in ({', '.join(map(str, people)) or 'null'})""")
    return Counter((DISTRICT[d] * 2 + c.SEX.index(s)) * c.N_AGE_GROUPS + int(c.age_group(a))
                   for d, s, a in rows.iter_rows())


def assert_shifted(run, month, shift):
    plain, got = salaried_by_cell(plain_run(), month), salaried_by_cell(run, month)
    for cell in set(plain) | set(got) | set(shift):
        assert got.get(cell, 0) == plain.get(cell, 0) - min(shift.get(cell, 0), plain.get(cell, 0)), cell


def test_layoff_and_alignment(tmp_path):
    world = build(tmp_path)
    world.apply(IncomeShock("2025-05-01", METRO, "layoff", 0.5, months=2))
    run = world.run("2025-07-01")
    laid = shock_layoffs(run)
    pool = set(plain_run().sql("""select e.entity_id from entity_state_monthly e join persons p using (entity_id)
                                  where e.month = '2025-05' and e.life_stage = 'salaried'
                                  and p.district = 'metro_archetype'""")["entity_id"])
    assert laid <= pool and 0.4 < len(laid) / len(pool) < 0.6
    may = run.sql(f"""select life_stage, monthly_income_paise, employer_entity_id from entity_state_monthly
                      where month = '2025-05' and entity_id in ({', '.join(map(str, laid))})""")
    assert set(may["life_stage"]) == {"seeking"} and set(may["monthly_income_paise"]) == {0}
    assert may["employer_entity_id"].null_count() == may.height
    shift = cells_of(plain_run(), laid, "2025-05")
    assert_shifted(run, "2025-06", shift)
    assert salaried_by_cell(run, "2025-07") == salaried_by_cell(plain_run(), "2025-07")
    log = run.table("interventions_log").collect()
    assert log["affected"].to_list() == [len(laid)] and log["ends"].to_list() == [date(2025, 7, 1)]
    ids = run.table("life_events").collect()["event_id"].to_list()
    assert ids == list(range(len(ids)))                   # event ids continue the counter, rows in id order


def test_layoff_shift_is_clamped(tmp_path):
    world = build(tmp_path)
    world.apply(IncomeShock("2025-05-01", METRO, "layoff", 1.0))
    run = world.run("2025-07-01")
    laid = shock_layoffs(run)
    assert laid
    shift = cells_of(plain_run(), laid, "2025-05")
    june = salaried_by_cell(plain_run(), "2025-06")
    assert any(n > june.get(cell, 0) for cell, n in shift.items())      # some cell's shift exceeds its target
    assert_shifted(run, "2025-06", shift)
    assert_shifted(run, "2025-07", shift)


def test_pay_cut_and_restore(tmp_path):
    world = build(tmp_path)
    world.apply(IncomeShock("2025-05-01", "life_stage in ('salaried', 'farm')", "pay_cut", 0.2, months=2))
    run = world.run("2025-05-01")
    cut = run.sql("select entity_id, income_before_paise as b, income_after_paise as a from life_events "
                  "where event = 'PAY_CUT'")
    b = cut["b"].to_numpy()
    assert cut.height > 0 and (cut["a"].to_numpy() == np.where(b > 0, np.maximum(1, np.rint(b * 0.8)), 0)).all()
    plain_may = dict(plain_run().sql("""select entity_id, monthly_income_paise from entity_state_monthly
                                        where month = '2025-05'""").iter_rows())
    assert all(plain_may[e] == b for e, b in zip(cut["entity_id"], cut["b"]))
    eligible = set(plain_run().sql("""select entity_id from entity_state_monthly where month = '2025-05'
                                      and life_stage in ('salaried', 'farm') and not helper""")["entity_id"])
    assert set(cut["entity_id"]) == eligible
    # Two cut salaried people with no life events in June or on 1 July (so nothing else changes their pay).
    quiet = run.sql("""select e.entity_id from entity_state_monthly e where e.month = '2025-05'
                       and e.life_stage = 'salaried' order by e.entity_id""")["entity_id"].to_list()
    busy = set(plain_run().sql("""select entity_id from life_events where date >= '2025-06-01'""")["entity_id"])
    i, j = [e for e in quiet if e not in busy][:2]
    s = world.state
    a = s.population.attributes
    raise_i = int(round(a.monthly_income_paise[i] * 1.1))                 # a raise in between
    a.monthly_income_paise[i] = s.person_salary[i] = raise_i
    s.life.pay_set[j] = month_index(date(2025, 6, 1))                     # j's pay was reset by a switch
    run = world.run("2025-07-01")
    back = run.sql("select entity_id, income_before_paise as b, income_after_paise as a from life_events "
                   "where event = 'PAY_RESTORED' and date = '2025-07-01'")
    restored = dict(zip(back["entity_id"], back["a"]))
    assert restored[i] == int(np.rint(raise_i / 0.8)) and j not in restored
    assert (back["a"].to_numpy() == np.rint(back["b"].to_numpy() / 0.8)).all()
    assert run.table("interventions_log").collect()["affected"].to_list() == [cut.height]


def test_permanent_cut_is_never_restored(tmp_path):
    world = build(tmp_path)
    world.apply(IncomeShock("2025-05-01", "life_stage == 'farm'", "pay_cut", 0.2))
    run = world.run("2025-07-01")
    assert run.sql("select count(*) as n from life_events where event = 'PAY_CUT'")["n"][0] > 0
    assert run.sql("select count(*) as n from life_events where event = 'PAY_RESTORED'")["n"][0] == 0


def test_shocks_that_select_nobody(tmp_path):
    world = build(tmp_path)
    world.apply(IncomeShock("2025-05-01", "age > 500", "layoff", 0.5))
    world.apply(IncomeShock("2025-05-01", "age > 500", "pay_cut", 0.5, months=1))
    run = world.run("2025-05-02")
    assert run.table("interventions_log").collect()["affected"].to_list() == [0, 0]
    assert events(run, "LAID_OFF", "2025-05-01") == events(plain_run(), "LAID_OFF", "2025-05-01")


def test_watchers_see_life_course_and_shock_events(tmp_path):
    plain = plain_run()
    retired = plain.sql("""select entity_id from life_events where date = '2025-05-01' and event = 'RETIRED'
                           order by entity_id limit 1""")["entity_id"][0]
    salaried = plain.sql("""select entity_id from entity_state_monthly where month = '2025-05'
                            and life_stage = 'salaried' order by entity_id limit 1""")["entity_id"][0]
    world = build(tmp_path)
    world.apply(IncomeShock("2025-05-01", f"entity_id = {salaried}", "layoff", 1.0))
    seen = {retired: [], salaried: []}
    for eid, calls in seen.items():
        world.watch(eid, calls.append)
    world.run("2025-05-01")
    events = {eid: [e["event"] for c in calls if c["date"] == date(2025, 5, 1) for e in c["events"]]
              for eid, calls in seen.items()}
    assert "RETIRED" in events[retired] and "LAID_OFF" in events[salaried]


# -- Deferred minors tidy-up -------------------------------------------------------------------------------------------

def test_a_pay_cut_is_not_restored_after_a_helper_round_trip(tmp_path):
    """Own-account earners cut in May, made helpers in June and own-account again in July: their July pay is fresh, so
    the restore must leave it alone (it used to divide it by 1 - rate)."""
    world = build(tmp_path)
    world.apply(IncomeShock("2025-05-01", "life_stage in ('farm', 'self_employed')", "pay_cut", 0.2, months=2))
    world.apply(ParamOverride("life.within.own_to_helper", 1.0, "2025-06-01"))
    world.apply(ParamOverride("life.within.helper_to_own", 1.0, "2025-07-01"))
    run = world.run("2025-07-01")
    cut = set(run.sql("select entity_id from life_events where event = 'PAY_CUT'")["entity_id"])
    trip = cut & events(run, "BECAME_HELPER", "2025-06-01") & events(run, "BECAME_OWN_ACCOUNT", "2025-07-01")
    restored = events(run, "PAY_RESTORED", "2025-07-01")
    assert trip and restored                                       # both cases met
    assert not trip & restored
    fresh = dict(run.sql("""select entity_id, income_after_paise from life_events where date = '2025-07-01'
                            and event = 'BECAME_OWN_ACCOUNT'""").iter_rows())
    july = dict(run.sql("""select entity_id, monthly_income_paise from entity_state_monthly
                           where month = '2025-07'""").iter_rows())
    assert all(july[e] == fresh[e] for e in trip)
