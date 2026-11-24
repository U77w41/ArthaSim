"""The eight phase 1 interventions, Scenario and the where evaluator (plan 1d-2, Task 5)."""
import json
from datetime import date

import numpy as np
import pytest

from arthasim import where
from arthasim.build import categories as c
from arthasim.interventions import (ChangeRailRule, DBTTransfer, ExpenseShock, IncomeShock, MacroPath,
                                    ParamOverride, SetHook, SetPolicyRate)
from arthasim.modules.spending import Consumption
from arthasim.scenario import Scenario
from world_fixture import small_world


def test_dates_normalise_and_compare():
    a = IncomeShock("2025-06-01", "life_stage == 'salaried'", "layoff", 0.1)
    assert a == IncomeShock(date(2025, 6, 1), "life_stage == 'salaried'", "layoff", 0.1) and a.date == date(2025, 6, 1)
    assert MacroPath("policy_rate", {"2025-06-06": 5.75}).series == ((date(2025, 6, 6), 5.75),)
    assert DBTTransfer("X", 2000, "true", ["2025-05-15", "2025-05-01"]).dates == (date(2025, 5, 1), date(2025, 5, 15))
    assert SetPolicyRate("2025-05-15", -25).date == date(2025, 5, 15)
    assert ChangeRailRule("2025-05-15", "UPI", "per_txn_limit", 1).param_id == "rail.upi.limit_paise"


@pytest.mark.parametrize("make", [
    lambda: IncomeShock("2025-06-01", "true", "pay_cut", 1.0),
    lambda: IncomeShock("2025-06-01", "true", "layoff", 0.0),
    lambda: IncomeShock("2025-06-02", "true", "layoff", 0.1),
    lambda: IncomeShock("2025-06-01", "true", "strike", 0.1),
    lambda: IncomeShock("2025-06-01", "true", "layoff", 0.1, months=-1),
    lambda: ExpenseShock("2025-06-01", "true", "fuel", 0.1),
    lambda: ExpenseShock("2025-06-01", "true", "medical", 1.5),
    lambda: ChangeRailRule("2025-06-01", "UPI", "fee", 1),
    lambda: MacroPath("repo", {"2025-06-01": 5.0}),
    lambda: MacroPath("policy_rate", {}),
    lambda: DBTTransfer("X", 2000.555, "true", ["2025-05-15"]),
    lambda: DBTTransfer("X", 0, "true", ["2025-05-15"]),
    lambda: DBTTransfer("X", 2000, "true", []),
    lambda: SetHook("module", object(), bank="SYNB01"),
    lambda: SetHook("module", object(), date="2025-05-02"),
    lambda: SetHook("pricing", object())])
def test_static_rules(make):
    with pytest.raises(ValueError):
        make()


def test_layoff_rate_one_and_section_11_hooks():
    IncomeShock("2025-06-01", "true", "layoff", 1.0)
    for kind, phase in (("fraud_control", "phase 2"), ("credit_policy", "phase 3"), ("card_policy", "phase 3"),
                        ("recommender", "phase 4")):
        with pytest.raises(NotImplementedError, match=phase):
            SetHook(kind, object())
    assert DBTTransfer("X", 2000, "true", ["2025-05-15"]).amount_paise == 200_000
    assert DBTTransfer("X", 0.5, "true", ["2025-05-15"]).amount_paise == 50


def test_streams_effective_and_ends():
    a, b = (IncomeShock("2025-06-01", "true", "layoff", r, months=3) for r in (0.1, 0.2))
    assert a.stream().startswith("iv.IncomeShock.") and len(a.stream().split(".")[-1]) == 12
    assert a.stream() != b.stream()
    assert a.stream() == IncomeShock("2025-06-01", "true", "layoff", 0.1, months=3).stream()
    assert a.ends() == date(2025, 9, 1) and IncomeShock("2025-06-01", "true", "layoff", 0.1).ends() is None
    assert ExpenseShock("2025-11-01", "true", "medical", 0.1, months=2).ends() == date(2026, 1, 1)
    start = date(2025, 4, 1)
    assert DBTTransfer("X", 1, "true", ["2025-05-15"]).effective(start) == date(2025, 5, 1)
    assert ParamOverride("rail.upi.limit_paise", 1).effective(start) == start
    assert ParamOverride("rail.upi.limit_paise", 1, "2025-05-03").effective(start) == date(2025, 5, 3)
    assert MacroPath("cpi_inflation", {"2025-07-01": 1.0, "2025-06-01": 2.0}).effective(start) == date(2025, 6, 1)
    assert SetHook("module", Consumption()).effective(start) == start
    details = SetHook("module", Consumption(), date="2025-05-01").details()
    assert details["impl"].endswith("Consumption") and json.loads(json.dumps(details)) == details
    assert MacroPath("policy_rate", {"2025-06-06": 5.75}).details()["series"] == {"2025-06-06": 5.75}


def test_scenario_is_immutable():
    a, b = ParamOverride("x", 1), ParamOverride("y", 2)
    s = Scenario.baseline()
    t = s.add(a).add(b)
    assert s.interventions == () and t.interventions == (a, b) and t == Scenario.baseline().add(a, b)
    assert t.details()[0] == {"kind": "ParamOverride", "param_id": "x", "value": 1, "date": None}
    with pytest.raises(TypeError):
        s.add("not an intervention")


def test_where_selects_and_checks():
    world = small_world()                      # read-only
    p, life = world.state.population.persons, world.state.life
    got = where.select(world, "life_stage == 'farm' and not helper")
    assert got.dtype == np.int64 and np.array_equal(got, np.flatnonzero((p.life_stage == c.FARM) & ~life.helper))
    frame = where.person_frame(world)
    assert frame.columns == list(where.COLUMNS) and dict(frame.schema) == where.WHERE_SCHEMA
    assert frame.height == len(p)
    assert where.select(world, "age > 500").size == 0
    metro = where.select(world, "district_kind = 'metro' and sex in ('F')")
    assert metro.size and (p.sex[metro] == c.F).all()
    for bad in ("occupation == 'farmer'", "age >", "true; select 1"):
        with pytest.raises(ValueError):
            where.check(bad)
    where.check("life_stage == 'farm' and not helper and monthly_income_paise > 0 and bpl")
