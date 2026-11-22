import datetime as dt
import numpy as np
from arthasim.build import categories as c
from arthasim.life.jobs import (choose_employers, entry_income, firm_shock, raise_due, raised_pay,
                                recompute_payroll, switch_pay)
from helpers import P
from world_fixture import small_world


def test_choose_employers_stays_in_district_and_sector():
    s = small_world().state
    o = s.population.orgs
    who = np.flatnonzero(s.population.persons.life_stage == c.SEEKING)[:200]
    sector = np.full(who.size, 3)
    e = choose_employers(s, who, sector, np.linspace(0, 0.999, who.size))
    assert (o.employer_district[e] == s.population.persons.district[who]).all()
    has_group = [((o.employer_district == d) & (o.employer_sector == 3)).any() for d in s.population.persons.district[who]]
    assert (o.employer_sector[e][has_group] == 3).all()


def test_pay_rules():
    assert switch_pay(np.array([1_000_000]), np.array([0.0]), P).tolist() == [1_150_000]
    assert raised_pay(np.array([1_000_000]), np.array([0.0]), P).tolist() == [1_089_000]
    assert raised_pay(np.array([1_000_000]), np.array([-5.0]), P).tolist() == [1_000_000]
    s = small_world().state
    who = np.flatnonzero(s.population.persons.life_stage == c.SEEKING)[:5]
    pay = entry_income(s, P, who, np.full(5, c.SALARIED), np.full(5, 3), np.zeros(5))
    assert (pay > 0).all()


def test_raise_due_and_payroll():
    s = small_world().state
    due = raise_due(s, dt.date(2025, 4, 1))
    assert (s.life.raise_month[s.person_employer[due]] == 4).all() and (s.person_salary[due] > 0).all()
    before = s.employer_payroll.copy()
    recompute_payroll(s)
    assert np.array_equal(before, s.employer_payroll)
    shock = firm_shock(s, 7, dt.date(2025, 5, 1).toordinal())
    assert shock.shape == (len(s.employer_ids),) and 0.8 < shock.mean() < 1.2
