"""Macro paths: the RBI repo rate and CPI inflation, each a registry row mapping an effective date to a value that
holds until the next date and carries forward past the last. Phase 1 records them; nothing reads them yet.
Sources: docs/sources/macro.md."""
from __future__ import annotations

import datetime as dt
from typing import Sequence

import polars as pl

from arthasim.params import ParamRegistry

SERIES = {"policy_rate": "macro.policy_rate", "cpi_inflation": "macro.cpi_inflation"}
MACRO_SCHEMA = {"series": pl.String, "date": pl.Date, "value": pl.Float64}

Steps = list[tuple[dt.date, float]]


def _date(value) -> dt.date:
    return value if isinstance(value, dt.date) else dt.date.fromisoformat(str(value))


def param_id(series: str) -> str:
    if series not in SERIES:
        raise ValueError(f"unknown macro series {series!r}; series are {', '.join(SERIES)}")
    return SERIES[series]


def steps(params: ParamRegistry, series: str) -> Steps:
    """The series' steps, ascending by date."""
    return sorted((_date(k), float(v)) for k, v in params.get(param_id(series)).items())


def value_on(steps: Steps, day: dt.date) -> float | None:
    """The value in force on `day`: the last step on or before it, or None before the first."""
    value = None
    for date, v in steps:
        if date > day:
            break
        value = v
    return value


def _as_registry(steps: Steps) -> dict[str, float]:
    return {d.isoformat(): v for d, v in sorted(steps)}


def replace_from(steps: Steps, new: Sequence[tuple[dt.date, float]]) -> dict[str, float]:
    """The steps before `new`'s earliest date, then `new`."""
    new = sorted((_date(d), float(v)) for d, v in new)
    start = new[0][0]
    return _as_registry([s for s in steps if s[0] < start] + new)


def add_from(steps: Steps, date: dt.date, change_pp: float) -> dict[str, float]:
    """`change_pp` added to every step on or after `date`, with a step at `date` if there was none."""
    out = [(d, round(v + change_pp, 6) if d >= date else v) for d, v in steps]
    if date not in {d for d, _ in steps}:
        current = value_on(steps, date)
        if current is None:
            raise ValueError(f"no value in force on {date} to change")
        out.append((date, round(current + change_pp, 6)))
    return _as_registry(out)


def frame(params: ParamRegistry) -> pl.DataFrame:
    """Both series, one row per step, sorted by series then date."""
    rows = [(name, d, v) for name in sorted(SERIES) for d, v in steps(params, name)]
    return pl.DataFrame({"series": [r[0] for r in rows], "date": [r[1] for r in rows],
                         "value": [r[2] for r in rows]}, schema=MACRO_SCHEMA)
