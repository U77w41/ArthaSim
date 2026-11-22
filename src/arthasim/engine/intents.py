"""Payment intents: what agents want to do today, before settlement."""
from __future__ import annotations

from dataclasses import dataclass, fields
from enum import IntEnum
from typing import Sequence

import numpy as np
import polars as pl


class Rail(IntEnum):
    CASH = 1
    UPI_P2M = 2
    NACH_CR = 3
    ATM = 4
    NEFT = 5
    UPI_P2P = 6
    DEBIT_CARD = 7
    IMPS = 8
    AEPS = 9
    BRANCH = 10
    APBS = 11               # Aadhaar Payment Bridge: DBT credits


class Status(IntEnum):
    SUCCESS = 1
    DECLINED_TECH = 2
    DECLINED_FUNDS = 3
    DECLINED_LIMIT = 4


class Purpose(IntEnum):
    UNSPECIFIED = 0
    SALARY = 1
    EARNINGS = 2
    PENSION = 3
    EMPLOYER_REVENUE = 4
    REMITTANCE = 5
    ALLOWANCE = 6           # earner to a member of their own household
    DBT_PM_KISAN = 7
    DBT_OLD_AGE_PENSION = 8
    DBT_WOMEN = 9
    GROCERY = 10            # merchant category k has purpose 10 + k
    FOOD = 11
    FUEL = 12
    PHARMACY = 13
    APPAREL = 14
    ELECTRONICS = 15
    TRANSPORT = 16
    SERVICES = 17
    OTHER = 18
    UTILITIES = 19
    TELECOM = 20
    MEDICAL = 21
    CASH_WITHDRAWAL = 30
    CASH_DEPOSIT = 31


@dataclass
class Intents:
    kind: np.ndarray
    flow_type: np.ndarray
    payer_acct: np.ndarray
    payee_acct: np.ndarray
    amount: np.ndarray
    rail: np.ndarray
    slot: np.ndarray
    offset_s: np.ndarray
    purpose: np.ndarray | None = None

    def __post_init__(self) -> None:
        if self.purpose is None:
            self.purpose = np.zeros(len(np.asarray(self.kind)), dtype=np.int64)
        for f in fields(self):
            setattr(self, f.name, np.ascontiguousarray(getattr(self, f.name), dtype=np.int64))

    def __len__(self) -> int:
        return int(self.kind.shape[0])

    @classmethod
    def empty(cls) -> "Intents":
        return cls(*[np.empty(0, dtype=np.int64) for _ in fields(cls)])

    @classmethod
    def concat(cls, parts: Sequence["Intents"]) -> "Intents":
        if not parts:
            return cls.empty()
        return cls(*[np.concatenate([getattr(p, f.name) for p in parts]) for f in fields(cls)])

    @classmethod
    def from_frame(cls, frame: pl.DataFrame) -> "Intents":
        names = [f.name for f in fields(cls)]
        return cls(**{n: frame[n].to_numpy() for n in names if n in frame.columns})

    def to_frame(self) -> pl.DataFrame:
        return pl.DataFrame({f.name: getattr(self, f.name) for f in fields(self)})

    def sorted(self) -> "Intents":
        order = np.lexsort((self.offset_s, self.slot))      # stable: by slot, then offset
        return Intents(*[getattr(self, f.name)[order] for f in fields(self)])

    def validate(self) -> None:
        if (self.amount <= 0).any():
            raise ValueError("intent amounts must be positive")
        if ((self.slot < 0) | (self.slot > 95)).any():
            raise ValueError("slot must be between 0 and 95")
        if ((self.offset_s < 0) | (self.offset_s > 899)).any():
            raise ValueError("offset_s must be between 0 and 899")
