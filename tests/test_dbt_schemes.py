import datetime as dt
import numpy as np
from arthasim.build import categories as c
from arthasim.dbt.schemes import (OLD_AGE_PENSION, PM_KISAN, WOMEN, DbtInputs, bpl_households, default_schemes,
                                  enrolled_payees, old_age_pension, pm_kisan, women)
from arthasim.engine.intents import Purpose
from helpers import P

ALL = P.override("dbt.pm_kisan.coverage", 1.0).override("dbt.old_age.coverage", 1.0).override(
    "dbt.women.coverage", 1.0)


def inputs(people, bpl=None):
    """people: (household, stage, age, sex, income, helper, sector) per person."""
    cols = list(zip(*people))
    hh = np.array(cols[0], dtype=np.int64)
    n_h = int(hh.max()) + 1
    return DbtInputs(stage=np.array(cols[1]), helper=np.array(cols[5], dtype=bool), age=np.array(cols[2]),
                     sex=np.array(cols[3]), sector=np.array(cols[6]), income=np.array(cols[4], dtype=np.int64),
                     household=hh, is_metro=np.zeros(hh.size, dtype=bool),
                     hh_members=np.bincount(hh, minlength=n_h),
                     bpl=np.ones(n_h, dtype=bool) if bpl is None else np.array(bpl, dtype=bool))


def person(hh, stage, age=40, sex=c.F, income=0, helper=False, sector=-1):
    return (hh, stage, age, sex, income, helper, sector)


def test_registry_rows_and_count():
    assert P.table().height == 184 and P.get("dbt.pm_kisan.amount_paise") == 200_000
    assert P.get("dbt.bpl.headcount") == {"metro": 0.264, "rural": 0.309}
    assert [str(d) for d in P.get("dbt.pm_kisan.dates")] == ["2025-08-02", "2025-11-19", "2026-03-13", "2026-06-20"]
    dbt = P.table().filter(P.table()["id"].str.starts_with("dbt.") & (P.table()["role"] == "input"))
    assert dbt.height == 17 and set(dbt["status"].to_list()) == {"verified", "unverified", "assumption"}
    assert P.get("dbt.cashout_lag")["d0_5"] == 0.179            # plan 1e's holdout row


def test_bpl_takes_the_poorest_persons_up_to_the_headcount():
    head = {"metro": 0.264, "rural": 0.309}
    got = bpl_households(np.array([0, 100, 200, 300]), np.ones(4, dtype=np.int64), np.zeros(4, dtype=bool), head)
    assert got.tolist() == [True, True, False, False]          # 0 and 1 members before the cut of 1.236
    # Ranked within district kind; ties go to the lower household index.
    got = bpl_households(np.array([5, 5, 0, 9, 1]), np.array([1, 1, 1, 1, 6]),
                         np.array([True, True, True, True, False]), head)
    assert got.tolist() == [True, False, True, False, True]    # metro cut 1.056: households 2 then 0


def test_pm_kisan_one_payee_per_household_and_exclusions():
    farmer = lambda hh, age=40: person(hh, c.FARM, age=age, sex=c.M, income=1_000_000)
    people = [farmer(0, 50), farmer(0, 60),
              farmer(1), person(1, c.SALARIED, income=3_000_000, sector=c.PUBLIC_ADMIN),
              farmer(2), person(2, c.SALARIED, income=6_000_000, sector=3),
              farmer(3), person(3, c.SALARIED, income=5_800_000, sector=3),
              farmer(4), person(4, c.RETIRED, age=70, income=1_000_000),
              farmer(5), person(5, c.RETIRED, age=70, income=999_900),
              person(6, c.FARM, helper=True)]
    r = pm_kisan(inputs(people), ALL, 7)
    assert r.scheme == PM_KISAN and r.payee.tolist() == [1, 6, 10] and r.enrolled.all()
    assert r.amount.tolist() == [200_000] * 3 and r.monthly_value.tolist() == [50_000] * 3


def test_old_age_pension_amounts_and_rules():
    people = [person(0, c.HOMEMAKER, age=79), person(1, c.HOMEMAKER, age=80), person(2, c.RETIRED, age=65, income=500_000),
              person(3, c.HOMEMAKER, age=65), person(4, c.HOMEMAKER, age=59)]
    r = old_age_pension(inputs(people, bpl=[True, True, True, False, True]), ALL, 7)
    assert r.scheme == OLD_AGE_PENSION and r.payee.tolist() == [0, 1]
    assert r.amount.tolist() == [100_000, 130_000] and r.monthly_value.tolist() == [100_000, 130_000]


def test_women_rules():
    people = [person(0, c.HOMEMAKER, age=21), person(1, c.HOMEMAKER, age=60), person(2, c.STUDYING, age=20),
              person(3, c.HOMEMAKER, age=61), person(4, c.SEEKING, age=30, sex=c.M),
              person(5, c.HOMEMAKER, age=30), person(5, c.SELF_EMPLOYED, sex=c.M, income=2_083_333, sector=3),
              person(6, c.HOMEMAKER, age=30), person(6, c.SELF_EMPLOYED, sex=c.M, income=2_083_334, sector=3),
              person(7, c.HOMEMAKER, age=30), person(7, c.SALARIED, sex=c.M, income=500_000, sector=c.PUBLIC_ADMIN)]
    r = women(inputs(people), ALL, 7)
    assert r.scheme == WOMEN and r.payee.tolist() == [0, 1, 5]
    tiers = {a for a, _ in P.get("dbt.women.amount_tiers")}
    assert set(r.amount.tolist()) <= tiers and (r.monthly_value == r.amount).all()


def _many_women(n=20_000):
    return inputs([person(i, c.HOMEMAKER, age=30) for i in range(n)])


def test_women_tiers_follow_the_weights():
    r = women(_many_women(), ALL, 7)
    tiers = P.get("dbt.women.amount_tiers")
    total = sum(w for _, w in tiers)
    for amount, weight in tiers:
        assert abs((r.amount == amount).mean() - weight / total) < 0.01, amount


def test_coverage_is_fixed_per_entity_and_respects_0_and_1():
    inp = _many_women()
    a, b = women(inp, P, 7), women(inp, P, 7)
    assert np.array_equal(a.enrolled, b.enrolled) and np.array_equal(a.amount, b.amount)
    assert abs(a.enrolled.mean() - 0.4) < 0.02
    assert (a.amount[~a.enrolled] == 0).all() and (a.monthly_value[~a.enrolled] == 0).all()
    assert not women(inp, P.override("dbt.women.coverage", 0.0), 7).enrolled.any()
    assert women(inp, ALL, 7).enrolled.all()
    assert not np.array_equal(women(inp, P, 8).enrolled, a.enrolled)


def test_enrolled_payees_and_default_schemes():
    people = [person(0, c.FARM, sex=c.M, income=1_000_000), person(0, c.HOMEMAKER, age=30),
              person(1, c.HOMEMAKER, age=70), person(2, c.SALARIED, sex=c.M, income=9_000_000, sector=3)]
    mask = enrolled_payees(inputs(people), ALL, 7)
    assert mask.tolist() == [True, True, True, False]
    schemes = default_schemes()
    assert [s.name for s in schemes] == [PM_KISAN, OLD_AGE_PENSION, WOMEN]
    assert [s.purpose for s in schemes] == [Purpose.DBT_PM_KISAN, Purpose.DBT_OLD_AGE_PENSION, Purpose.DBT_WOMEN]
    pk, old, wm = schemes
    assert pk.pays_on(dt.date(2025, 8, 2), P) and not pk.pays_on(dt.date(2025, 8, 3), P)
    assert old.pays_on(dt.date(2025, 4, 5), P) and not old.pays_on(dt.date(2025, 4, 10), P)
    assert wm.pays_on(dt.date(2025, 4, 10), P) and not wm.pays_on(dt.date(2025, 4, 5), P)
