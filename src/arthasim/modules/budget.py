"""Household budgets: a buffer-stock rule, financial stress and medical shocks."""
from __future__ import annotations

import datetime as dt

import numpy as np

from arthasim.engine import rng
from arthasim.modules.base import BehaviourModule
from arthasim.params import ParamRegistry


def household_budget(income: np.ndarray, balance: np.ndarray, adults: np.ndarray, dependants: np.ndarray,
                     params: ParamRegistry) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Monthly budget, buffer in months of need, and stress (0 to 1)."""
    income = np.asarray(income, dtype=np.float64)
    floor = params.get("consumption.floor_per_adult_paise") * (
        np.asarray(adults, dtype=np.float64) + params.get("consumption.dependant_weight") * np.asarray(dependants))
    spend = params.get("consumption.spend_share") * income
    need = np.maximum(spend, floor)
    buffer_months = np.asarray(balance, dtype=np.float64) / need
    target = params.get("consumption.buffer_target_months")
    lo, hi = params.get("consumption.adjust_min"), params.get("consumption.adjust_max")
    adjust = np.clip(lo + (1 - lo) * buffer_months / target, lo, hi)
    budget = np.rint(np.maximum(floor, spend * adjust)).astype(np.int64)
    stress = np.clip(1 - buffer_months / target, 0.0, 1.0)
    return budget, buffer_months, stress


class Budget(BehaviourModule):
    name = "budget"

    def monthly(self, world, month: dt.date) -> None:
        s, params, seed = world.state, world.params, world.seed
        pop, beh = s.population, s.behaviour
        hh = pop.households.household_of_person
        n = pop.households.adults.size
        income = np.zeros(n, dtype=np.int64)
        np.add.at(income, hh, pop.attributes.monthly_income_paise)
        transfer = np.zeros(n, dtype=np.int64)          # DBT, counted at its monthly value
        np.add.at(transfer, hh, beh.person_transfer)
        balance = np.zeros(n, dtype=np.int64)
        np.add.at(balance, hh, s.book.balance[s.person_cash])
        banked = s.person_deposit >= 0
        np.add.at(balance, hh[banked], s.book.balance[s.person_deposit[banked]])
        budget, buffer_months, stress = household_budget(income + transfer, balance, pop.households.adults,
                                                         pop.households.dependants, params)

        # Medical shocks: keyed on the calendar month, so a mid-month start draws the same shocks.
        ids = np.arange(n, dtype=np.int64)
        key_day = month.replace(day=1).toordinal()
        elderly = np.zeros(n, dtype=bool)
        elderly[hh[pop.persons.age >= 60]] = True
        prob = params.get("shock.medical_monthly_prob") * np.where(elderly, 2.0, 1.0)
        hit = rng.uniform(seed, rng.stream_id("budget.medical"), ids, key_day) < prob
        cost = rng.lognormal(seed, rng.stream_id("budget.medical_cost"), ids, key_day,
                             params.get("shock.medical_median_paise"), params.get("shock.medical_sigma"))
        medical_due = np.where(hit, np.maximum(100, np.rint(cost)), 0).astype(np.int64)
        stress = np.where(hit, np.minimum(1.0, stress + params.get("shock.stress_bonus")), stress)

        beh.income[:], beh.transfer_income[:], beh.balance[:], beh.budget[:] = income, transfer, balance, budget
        beh.buffer_months[:], beh.stress[:], beh.medical_due[:] = buffer_months, stress, medical_due
        beh.person_budget[:] = budget[hh] // pop.households.adults[hh]
