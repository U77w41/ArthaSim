"""Interventions: dated changes applied to a world (architecture section 14.2; plan 1d-2).

Each is a frozen dataclass. Construction normalises dates and checks what needs no world (kinds, rates, the month-start
rule); `World.apply` checks the rest against the world. An intervention's random draws use its own stream,
`stream()`, so two arms with the same intervention draw the same numbers and the baseline's streams are untouched."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
from dataclasses import dataclass, fields
from typing import Any, Mapping, Sequence

from arthasim import macro

Date = str | dt.date

RAIL_RULES = {("UPI", "per_txn_limit"): "rail.upi.limit_paise"}
HOOK_PHASES = {"fraud_control": 2, "credit_policy": 3, "card_policy": 3, "recommender": 4}
INCOME_KINDS = ("layoff", "pay_cut")
EXPENSE_KINDS = ("medical",)


def _date(value: Date) -> dt.date:
    return value if isinstance(value, dt.date) else dt.date.fromisoformat(str(value))


def _month_start(day: dt.date, what: str) -> None:
    if day.day != 1:
        raise ValueError(f"{what} takes effect at a month start; {day.isoformat()} is not the 1st")


def add_months(day: dt.date, months: int) -> dt.date:
    """The 1st of the month `months` after `day`'s month."""
    y, m = divmod(day.month - 1 + months, 12)
    return dt.date(day.year + y, m + 1, 1)


def _json(value: Any) -> Any:
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(_json(k)): _json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json(v) for v in value]
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if hasattr(value, "item"):                       # numpy scalars
        return value.item()
    return str(value)


class Intervention:
    """Base of the interventions below."""

    def effective(self, start: dt.date) -> dt.date:
        """When it takes effect; `start` is the run's first day (for interventions whose date may be None)."""
        raise NotImplementedError

    def ends(self) -> dt.date | None:
        """The first month it no longer applies, for shocks with a duration."""
        return None

    def details(self) -> dict[str, Any]:
        """The fields, as JSON-safe values."""
        return {f.name: _json(getattr(self, f.name)) for f in fields(self)}

    def stream(self) -> str:
        digest = hashlib.sha256(json.dumps(self.details(), sort_keys=True).encode()).hexdigest()[:12]
        return f"iv.{type(self).__name__}.{digest}"


def _set(obj, name: str, value: Any) -> None:
    object.__setattr__(obj, name, value)


@dataclass(frozen=True)
class ParamOverride(Intervention):
    """A registry parameter takes `value` from the start of `date` (None: the run's first day)."""
    param_id: str
    value: Any
    date: Date | None = None

    def __post_init__(self) -> None:
        if self.date is not None:
            _set(self, "date", _date(self.date))

    def effective(self, start: dt.date) -> dt.date:
        return self.date or start


@dataclass(frozen=True)
class ChangeRailRule(Intervention):
    """A rail rule from the start of `date`. Phase 1 has one: the UPI per-transaction limit, in paise."""
    date: Date
    rail: str
    rule: str
    value: Any

    def __post_init__(self) -> None:
        _set(self, "date", _date(self.date))
        if (self.rail, self.rule) not in RAIL_RULES:
            pairs = ", ".join(f"({r!r}, {u!r})" for r, u in RAIL_RULES)
            raise ValueError(f"no rail rule ({self.rail!r}, {self.rule!r}); supported: {pairs}")

    @property
    def param_id(self) -> str:
        return RAIL_RULES[(self.rail, self.rule)]

    def effective(self, start: dt.date) -> dt.date:
        return self.date


@dataclass(frozen=True)
class MacroPath(Intervention):
    """Replace a macro series (`policy_rate`, `cpi_inflation`) from its earliest date on."""
    name: str
    series: Mapping[Date, float]

    def __post_init__(self) -> None:
        macro.param_id(self.name)
        items = self.series.items() if isinstance(self.series, Mapping) else self.series
        steps = tuple(sorted((_date(d), float(v)) for d, v in items))
        if not steps:
            raise ValueError("a macro path needs at least one dated value")
        _set(self, "series", steps)

    def effective(self, start: dt.date) -> dt.date:
        return self.series[0][0]

    def details(self) -> dict[str, Any]:
        return {"name": self.name, "series": {d.isoformat(): v for d, v in self.series}}


@dataclass(frozen=True)
class SetPolicyRate(Intervention):
    """Add `change_bp` basis points to the repo rate in force from `date` on."""
    date: Date
    change_bp: float

    def __post_init__(self) -> None:
        _set(self, "date", _date(self.date))

    def effective(self, start: dt.date) -> dt.date:
        return self.date


def _months(value: Any) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"months must be a whole number of months, 0 or more; got {value!r}")


@dataclass(frozen=True)
class IncomeShock(Intervention):
    """`layoff`: selected salaried people lose their jobs with probability `rate` (in (0, 1]). `pay_cut`: selected
    earners' pay falls by `rate` (in (0, 1)), restored after `months`. From the month start `date`; `months=0`
    lasts the rest of the run."""
    date: Date
    where: str
    kind: str
    rate: float
    months: int = 0

    def __post_init__(self) -> None:
        _set(self, "date", _date(self.date))
        _month_start(self.date, "an income shock")
        if self.kind not in INCOME_KINDS:
            raise ValueError(f"income shock kind must be one of {', '.join(INCOME_KINDS)}; got {self.kind!r}")
        if self.kind == "layoff" and not 0 < self.rate <= 1:
            raise ValueError(f"a layoff rate must be in (0, 1]; got {self.rate!r}")
        if self.kind == "pay_cut" and not 0 < self.rate < 1:
            raise ValueError(f"a pay cut rate must be in (0, 1) (a 100% cut is a layoff); got {self.rate!r}")
        _months(self.months)

    def effective(self, start: dt.date) -> dt.date:
        return self.date

    def ends(self) -> dt.date | None:
        return add_months(self.date, self.months) if self.months else None


@dataclass(frozen=True)
class ExpenseShock(Intervention):
    """`medical`: each selected household has an extra medical shock with probability `rate` (in [0, 1]) in each month
    from the month start `date`, for `months` months (0: the rest of the run)."""
    date: Date
    where: str
    kind: str
    rate: float
    months: int = 0

    def __post_init__(self) -> None:
        _set(self, "date", _date(self.date))
        _month_start(self.date, "an expense shock")
        if self.kind not in EXPENSE_KINDS:
            raise ValueError(f"expense shock kind must be one of {', '.join(EXPENSE_KINDS)}; got {self.kind!r}")
        if not 0 <= self.rate <= 1:
            raise ValueError(f"an expense shock rate must be in [0, 1]; got {self.rate!r}")
        _months(self.months)

    def effective(self, start: dt.date) -> dt.date:
        return self.date

    def ends(self) -> dt.date | None:
        return add_months(self.date, self.months) if self.months else None


@dataclass(frozen=True)
class DBTTransfer(Intervention):
    """A transfer scheme: everyone `where` selects is credited `amount` rupees by APBS on each of `dates`."""
    scheme: str
    amount: float
    where: str
    dates: Sequence[Date]

    def __post_init__(self) -> None:
        if not isinstance(self.scheme, str) or not self.scheme:
            raise ValueError("a DBT transfer needs a scheme name")
        _set(self, "dates", tuple(sorted({_date(d) for d in self.dates})))
        if not self.dates:
            raise ValueError("a DBT transfer needs at least one date")
        paise = float(self.amount) * 100
        if not math.isfinite(paise) or paise <= 0 or abs(paise - round(paise)) > 1e-6:
            raise ValueError(f"amount must be a positive number of rupees in whole paise; got {self.amount!r}")

    @property
    def amount_paise(self) -> int:
        return int(round(float(self.amount) * 100))

    def effective(self, start: dt.date) -> dt.date:
        return self.dates[0].replace(day=1)


@dataclass(frozen=True)
class SetHook(Intervention):
    """`kind="module"`: `impl`, a behaviour module, replaces the module of the same name from the month start
    `date` (None: the run's first day). Section 11's hook kinds arrive in later phases."""
    kind: str
    impl: Any
    bank: str | None = None
    date: Date | None = None

    def __post_init__(self) -> None:
        if self.kind in HOOK_PHASES:
            raise NotImplementedError(f"SetHook kind {self.kind!r} arrives in phase {HOOK_PHASES[self.kind]}; "
                                      "phase 1 supports kind='module'")
        if self.kind != "module":
            raise ValueError(f"unknown hook kind {self.kind!r}; phase 1 supports 'module'")
        if self.bank is not None:
            raise ValueError("a module swap applies to the whole world; bank must be None")
        if self.date is not None:
            _set(self, "date", _date(self.date))
            _month_start(self.date, "a module swap")

    def effective(self, start: dt.date) -> dt.date:
        return self.date or start

    def details(self) -> dict[str, Any]:
        impl = type(self.impl)
        return {"kind": self.kind, "impl": f"{impl.__module__}.{impl.__qualname__}", "bank": self.bank,
                "date": _json(self.date)}
