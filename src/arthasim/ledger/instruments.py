"""Financial instruments: one record per balance, with a holder and an issuer."""
from __future__ import annotations

from enum import IntEnum

import numpy as np


class InstrumentType(IntEnum):
    DEPOSIT = 1
    CASH = 2
    RESERVE = 3


class InstrumentBook:
    """All instruments in the world. Build with add/add_many, then freeze()."""

    def __init__(self) -> None:
        self._parts: list[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]] = []
        self._count = 0
        self._frozen = False

    def add(self, type: int, holder: int, issuer: int, opening_paise: int) -> int:
        return int(self.add_many(type, [holder], [issuer], [opening_paise])[0])

    def add_many(self, type: int, holders, issuers, openings) -> np.ndarray:
        if self._frozen:
            raise RuntimeError("book is frozen")
        holders = np.asarray(holders, dtype=np.int64)
        n = holders.shape[0]
        issuers = np.broadcast_to(np.asarray(issuers, dtype=np.int64), (n,))
        openings = np.broadcast_to(np.asarray(openings, dtype=np.int64), (n,))
        types = np.full(n, int(type), dtype=np.int64)
        self._parts.append((types, holders, issuers.copy(), openings.copy()))
        ids = np.arange(self._count, self._count + n, dtype=np.int64)
        self._count += n
        return ids

    def freeze(self) -> None:
        cols = [np.concatenate([p[i] for p in self._parts]) if self._parts
                else np.empty(0, dtype=np.int64) for i in range(4)]
        self.type, self.holder, self.issuer, self.opening = cols
        self.balance = self.opening.copy()
        self._frozen = True

    def __len__(self) -> int:
        return self._count
