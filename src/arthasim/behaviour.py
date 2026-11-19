"""Mutable behavioural state that modules share: household budgets, buffers and stress."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class BehaviourState:
    income: np.ndarray            # per household, paise per month
    balance: np.ndarray           # per household: members' cash and primary deposits
    budget: np.ndarray            # per household, paise per month
    medical_due: np.ndarray       # per household, paise due this month
    buffer_months: np.ndarray     # per household
    stress: np.ndarray            # per household, 0 to 1
    person_budget: np.ndarray     # per person, paise per month

    @classmethod
    def zeros(cls, n_households: int, n_persons: int) -> "BehaviourState":
        i = lambda n: np.zeros(n, dtype=np.int64)
        f = lambda n: np.zeros(n, dtype=np.float64)
        return cls(income=i(n_households), balance=i(n_households), budget=i(n_households),
                   medical_due=i(n_households), buffer_months=f(n_households), stress=f(n_households),
                   person_budget=i(n_persons))
