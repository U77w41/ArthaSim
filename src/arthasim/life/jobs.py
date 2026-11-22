"""Employer choice, pay on entry, job switches, raises and payroll."""
from __future__ import annotations

import datetime as dt

import numpy as np

from arthasim.build.earnings import income_for
from arthasim.engine import rng
from arthasim.params import ParamRegistry


def _staff(state) -> np.ndarray:
    emp = state.person_employer
    return np.bincount(emp[emp >= 0], minlength=len(state.employer_ids))


def choose_employers(state, persons: np.ndarray, sector: np.ndarray, u: np.ndarray) -> np.ndarray:
    """Employer index for each person: among employers of their (district, sector), weighted by vacancies
    (capacity minus staff) plus one; if the district has none in that sector, among all its employers."""
    o = state.population.orgs
    persons, sector, u = np.asarray(persons), np.asarray(sector), np.asarray(u, dtype=np.float64)
    district = state.population.persons.district[persons]
    weight = (np.maximum(0, o.employer_capacity - _staff(state)) + 1).astype(np.float64)
    out = np.full(persons.size, -1, dtype=np.int64)
    for d, s in {(int(a), int(b)) for a, b in zip(district, sector)}:
        m = (district == d) & (sector == s)
        group = np.flatnonzero((o.employer_district == d) & (o.employer_sector == s))
        if group.size == 0:
            group = np.flatnonzero(o.employer_district == d)
        if group.size == 0:
            raise ValueError(f"district {d} has no employers")
        cum = np.cumsum(weight[group])
        pick = np.minimum(np.searchsorted(cum / cum[-1], u[m], side="right"), group.size - 1)
        out[m] = group[pick]
    return out


def entry_income(state, params: ParamRegistry, persons: np.ndarray, stage: np.ndarray, sector: np.ndarray,
                 z: np.ndarray) -> np.ndarray:
    """Pay on entering a stage: the build's income rule at the person's current age."""
    p = state.population.persons
    kinds = np.array([d.kind for d in state.population.districts])
    is_metro = kinds[p.district[persons]] == "metro"
    return income_for(np.asarray(stage), p.education[persons], p.age[persons], is_metro, np.asarray(sector),
                      np.asarray(z, dtype=np.float64), params)


def switch_pay(old: np.ndarray, z: np.ndarray, params: ParamRegistry) -> np.ndarray:
    f = params.get("life.switch.pay_factor")
    factor = np.exp(np.log(f["median"]) + f["sigma"] * np.asarray(z, dtype=np.float64))
    return np.maximum(100, np.rint(np.asarray(old) * factor)).astype(np.int64)


def raise_due(state, month: dt.date) -> np.ndarray:
    """Salaried persons whose employer's raise month is this month."""
    emp = state.person_employer
    sal = np.flatnonzero(emp >= 0)
    return sal[state.life.raise_month[emp[sal]] == month.month]


def raised_pay(old: np.ndarray, z: np.ndarray, params: ParamRegistry) -> np.ndarray:
    rate = np.maximum(0.0, params.get("life.raise.mean") + params.get("life.raise.sd") * np.asarray(z, dtype=np.float64))
    return np.rint(np.asarray(old) * (1 + rate)).astype(np.int64)


def recompute_payroll(state) -> None:
    """Each employer's payroll is the sum of its staff's salaries (updated in place)."""
    emp = state.person_employer
    on = emp >= 0
    payroll = np.zeros(len(state.employer_ids), dtype=np.int64)
    np.add.at(payroll, emp[on], state.person_salary[on])
    state.employer_payroll[:] = payroll


def firm_shock(state, seed: int, key_day: int) -> np.ndarray:
    """Per employer, a monthly multiplier on its staff's moves out: lognormal with mean 1
    (median exp(-sigma^2 / 2)), sigma `life.layoff.employer_shock_sigma` from the run's registry."""
    sigma = float(state.life.targets.params.get("life.layoff.employer_shock_sigma"))
    return rng.lognormal(seed, rng.stream_id("life.firm_shock"), state.employer_ids, key_day,
                         float(np.exp(-sigma ** 2 / 2)), sigma)
