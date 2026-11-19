import datetime as dt
import numpy as np
from arthasim.modules.budget import Budget, household_budget
from helpers import P
from world_fixture import small_world


def test_budget_formula():
    income = np.array([3_000_000, 3_000_000, 0, 3_000_000])
    balance = np.array([9_000_000, 0, 1_000_000, 90_000_000])
    budget, buffer_months, stress = household_budget(income, balance, np.array([2, 2, 1, 2]),
                                                     np.array([0, 2, 0, 0]), P)
    assert budget.dtype == np.int64 and budget.tolist() == [2_730_000, 1_530_000, 250_000, 2_932_500]
    assert np.allclose(buffer_months, [9 / 2.55, 0.0, 4.0, 90 / 2.55])
    assert stress.tolist() == [0.0, 1.0, 0.0, 0.0]


def test_monthly_hook_fills_state():
    w = small_world()
    s, b = w.state, w.state.population
    hh, n = b.households.household_of_person, len(b.households.adults)
    Budget().monthly(w, dt.date(2025, 4, 1))
    beh = s.behaviour
    income = np.zeros(n, dtype=np.int64)
    np.add.at(income, hh, b.attributes.monthly_income_paise)
    balance = np.zeros(n, dtype=np.int64)
    np.add.at(balance, hh, s.book.balance[s.person_cash])
    banked = s.person_deposit >= 0
    np.add.at(balance, hh[banked], s.book.balance[s.person_deposit[banked]])
    assert np.array_equal(beh.income, income) and np.array_equal(beh.balance, balance)
    assert np.array_equal(beh.person_budget, beh.budget[hh] // b.households.adults[hh])
    assert (beh.budget > 0).all() and ((beh.stress >= 0) & (beh.stress <= 1)).all()
    assert np.isfinite(beh.buffer_months).all() and (beh.medical_due >= 0).all()


def test_medical_shocks_rate_stress_and_determinism():
    w = small_world()
    beh = w.state.behaviour
    rates = []
    for mon in range(4, 10):
        Budget().monthly(w, dt.date(2025, mon, 1))
        rates.append((beh.medical_due > 0).mean())
    assert 0.005 < np.mean(rates) < 0.03
    hit = beh.medical_due > 0
    assert hit.any() and (beh.stress[hit] >= 0.3 - 1e-9).all() and (beh.medical_due[hit] >= 100).all()
    snapshot = beh.medical_due.copy()
    Budget().monthly(w, dt.date(2025, 9, 1))
    assert np.array_equal(beh.medical_due, snapshot)
