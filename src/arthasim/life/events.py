"""Life events and the monthly person-state table."""
from __future__ import annotations

import datetime as dt

import numpy as np
import polars as pl

from arthasim.build import categories as c

EVENT_NAMES = ("HIRED", "LAID_OFF", "LEFT_JOB", "RETIRED", "JOB_SWITCH", "STARTED_WORK", "STOPPED_WORK",
               "CHANGED_WORK", "STARTED_STUDY", "LEFT_STUDY", "STARTED_SEEKING", "STOPPED_SEEKING",
               "LEFT_RETIREMENT", "RAISE", "ACCOUNT_OPENED", "BECAME_OWN_ACCOUNT", "BECAME_HELPER", "PAY_CUT",
               "PAY_RESTORED")
_W = set(c.WORK)


def _stage_event(src: int, dst: int) -> str | None:
    """The one event a stage change writes (row: from, column: to)."""
    if src == dst:
        return None
    if dst == c.RETIRED:
        return "RETIRED"
    if dst == c.SALARIED:
        return "HIRED"
    if src == c.STUDYING:
        return "STARTED_WORK" if dst in _W else "LEFT_STUDY"
    if src == c.SEEKING:
        return {c.STUDYING: "STARTED_STUDY", c.HOMEMAKER: "STOPPED_SEEKING"}.get(dst, "STARTED_WORK")
    if src == c.SALARIED:
        return {c.SEEKING: "LAID_OFF"}.get(dst, "CHANGED_WORK" if dst in _W else "LEFT_JOB")
    if src in _W:
        return "CHANGED_WORK" if dst in _W else "STOPPED_WORK"
    if src == c.HOMEMAKER:
        return {c.STUDYING: "STARTED_STUDY", c.SEEKING: "STARTED_SEEKING"}.get(dst, "STARTED_WORK")
    # retired
    return {c.STUDYING: "STARTED_STUDY", c.SEEKING: "STARTED_SEEKING", c.HOMEMAKER: "LEFT_RETIREMENT"}.get(
        dst, "STARTED_WORK")


STAGE_EVENT = [[_stage_event(i, j) for j in range(9)] for i in range(9)]

EVENT_SCHEMA = {"event_id": pl.Int64, "date": pl.Date, "entity_id": pl.Int64, "event": pl.String,
                "from_stage": pl.String, "to_stage": pl.String, "employer_from": pl.Int64, "employer_to": pl.Int64,
                "income_before_paise": pl.Int64, "income_after_paise": pl.Int64, "account_id": pl.Int64}
STATE_SCHEMA = {"entity_id": pl.Int64, "month": pl.String, "age": pl.Int64, "life_stage": pl.String,
                "months_in_stage": pl.Int64, "helper": pl.Boolean, "sector": pl.String,
                "employer_entity_id": pl.Int64, "monthly_income_paise": pl.Int64, "has_account": pl.Boolean,
                "primary_bank": pl.String, "has_upi": pl.Boolean, "has_card": pl.Boolean}


def _ints(values, n: int) -> np.ndarray:
    """Int64 array of length n; None becomes -1 (written as null)."""
    if values is None:
        return np.full(n, -1, dtype=np.int64)
    return np.broadcast_to(np.asarray(values, dtype=np.int64), (n,)).copy()


def _names(labels: list[str], index: np.ndarray) -> list[str | None]:
    return [labels[i] if i >= 0 else None for i in index.tolist()]


def _nullable(values: np.ndarray) -> list[int | None]:
    return [v if v >= 0 else None for v in values.tolist()]


class EventLog:
    """Events collected during one monthly hook."""

    def __init__(self) -> None:
        self._parts: list[tuple] = []

    def add(self, entity, event, *, from_stage=None, to_stage=None, employer_from=None, employer_to=None,
            income_before, income_after, account_id=None) -> None:
        entity = np.asarray(entity, dtype=np.int64)
        n = entity.size
        if n == 0:
            return
        names = np.broadcast_to(np.asarray(event, dtype=object), (n,)).copy()
        self._parts.append((entity, names, _ints(from_stage, n), _ints(to_stage, n), _ints(employer_from, n),
                            _ints(employer_to, n), _ints(income_before, n), _ints(income_after, n),
                            _ints(account_id, n)))

    def __len__(self) -> int:
        return sum(p[0].size for p in self._parts)

    def frame(self, date: dt.date, first_id: int) -> pl.DataFrame:
        if not self._parts:
            return pl.DataFrame(schema=EVENT_SCHEMA)
        cols = [np.concatenate([p[i] for p in self._parts]) for i in range(9)]
        entity, event, src, dst, e_from, e_to, before, after, account = cols
        n = entity.size
        return pl.DataFrame({
            "event_id": np.arange(first_id, first_id + n, dtype=np.int64),
            "date": pl.Series([date] * n, dtype=pl.Date), "entity_id": entity,
            "event": pl.Series(event.tolist(), dtype=pl.String),
            "from_stage": pl.Series(_names(c.LIFE_STAGE, src), dtype=pl.String),
            "to_stage": pl.Series(_names(c.LIFE_STAGE, dst), dtype=pl.String),
            "employer_from": pl.Series(_nullable(e_from), dtype=pl.Int64),
            "employer_to": pl.Series(_nullable(e_to), dtype=pl.Int64),
            "income_before_paise": before, "income_after_paise": after,
            "account_id": pl.Series(_nullable(account), dtype=pl.Int64)}, schema=EVENT_SCHEMA)


def state_frame(state, month: str) -> pl.DataFrame:
    """One row per person: their state at the start of the month, after the life course has run."""
    pop, life = state.population, state.life
    p, k = pop.persons, pop.banking
    n = len(p)
    emp = state.person_employer
    employer = np.where(emp >= 0, state.employer_ids[np.maximum(emp, 0)] if len(state.employer_ids) else -1, -1)
    codes = k.bank_codes.tolist()
    return pl.DataFrame({
        "entity_id": state.person_ids, "month": pl.Series([month] * n, dtype=pl.String),
        "age": p.age.astype(np.int64), "life_stage": pl.Series(_names(c.LIFE_STAGE, p.life_stage), dtype=pl.String),
        "months_in_stage": life.months_in_stage.astype(np.int64), "helper": life.helper,
        "sector": pl.Series(_names(c.SECTORS, pop.attributes.sector.astype(np.int64)), dtype=pl.String),
        "employer_entity_id": pl.Series(_nullable(employer), dtype=pl.Int64),
        "monthly_income_paise": pop.attributes.monthly_income_paise.astype(np.int64),
        "has_account": k.person_has_account,
        "primary_bank": pl.Series(_names(codes, k.person_primary_bank.astype(np.int64)), dtype=pl.String),
        "has_upi": k.person_upi, "has_card": k.person_has_card}, schema=STATE_SCHEMA)
