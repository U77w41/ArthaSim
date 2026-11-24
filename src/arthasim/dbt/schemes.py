"""Direct benefit transfer schemes: who is eligible, who is covered, and how much each payee gets.

Pure functions over person arrays, so the build (to bank every payee) and the monthly module (to pay
them) apply the same rules. Sources and derivations for every parameter: docs/sources/dbt.md."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Callable, Mapping

import numpy as np

from arthasim.build import categories as c
from arthasim.engine import rng
from arthasim.engine.intents import Purpose
from arthasim.params import ParamRegistry

PM_KISAN, OLD_AGE_PENSION, WOMEN = "PM_KISAN", "OLD_AGE_PENSION", "WOMEN"


@dataclass(frozen=True)
class DbtInputs:
    """One entry per person unless noted."""
    stage: np.ndarray       # life stage index
    helper: np.ndarray      # bool: unpaid family helper
    age: np.ndarray
    sex: np.ndarray
    sector: np.ndarray      # attributes.sector
    income: np.ndarray      # monthly_income_paise: earned income only
    household: np.ndarray   # household index
    is_metro: np.ndarray    # bool
    hh_members: np.ndarray  # per household: adults plus dependants
    bpl: np.ndarray         # per household, bool: on the BPL list

    @property
    def n_households(self) -> int:
        return int(self.hh_members.size)


@dataclass(frozen=True)
class SchemeResult:
    scheme: str
    payee: np.ndarray          # person indices of eligible payees, ascending
    enrolled: np.ndarray       # bool, aligned with payee
    amount: np.ndarray         # paise per credit; 0 where not enrolled
    monthly_value: np.ndarray  # paise per month; 0 where not enrolled


@dataclass(frozen=True)
class Scheme:
    name: str
    purpose: int
    evaluate: Callable[[DbtInputs, ParamRegistry, int], SchemeResult]
    pays_on: Callable[[dt.date, ParamRegistry], bool]


def bpl_households(per_member_income: np.ndarray, members: np.ndarray, is_metro: np.ndarray,
                   headcount: Mapping[str, float]) -> np.ndarray:
    """Per household: on the BPL list. Within each district kind, households are ranked by earned income
    per member (ties by index); a household is on the list while the members of poorer households number
    fewer than the headcount share of all members of that kind."""
    income = np.asarray(per_member_income, dtype=np.float64)
    members = np.asarray(members, dtype=np.int64)
    metro = np.asarray(is_metro, dtype=bool)
    out = np.zeros(income.size, dtype=bool)
    for kind, mask in (("metro", metro), ("rural", ~metro)):
        idx = np.flatnonzero(mask)
        if idx.size == 0:
            continue
        idx = idx[np.lexsort((idx, income[idx]))]
        before = np.cumsum(members[idx]) - members[idx]
        out[idx] = before < float(headcount[kind]) * members[idx].sum()
    return out


def _per_household(inp: DbtInputs, values) -> np.ndarray:
    return np.bincount(inp.household, weights=np.asarray(values, dtype=np.float64), minlength=inp.n_households)


def _government_employee(inp: DbtInputs) -> np.ndarray:
    """Per household: a member is salaried in public administration."""
    return _per_household(inp, (inp.stage == c.SALARIED) & (inp.sector == c.PUBLIC_ADMIN)) > 0


def _covered(seed: int, stream: str, entity: np.ndarray, coverage: float) -> np.ndarray:
    return rng.uniform(seed, rng.stream_id(stream), np.asarray(entity, dtype=np.int64), 0) < float(coverage)


def _result(name: str, payee: np.ndarray, enrolled: np.ndarray, amount: np.ndarray,
            monthly: np.ndarray) -> SchemeResult:
    amount = np.where(enrolled, amount, 0).astype(np.int64)
    return SchemeResult(name, payee.astype(np.int64), enrolled, amount,
                        np.where(enrolled, monthly, 0).astype(np.int64))


def pm_kisan(inp: DbtInputs, params: ParamRegistry, seed: int) -> SchemeResult:
    """One payee per farmer household: its eldest own-account farmer (lowest index on ties)."""
    hh = inp.household
    farmer = np.flatnonzero((inp.stage == c.FARM) & ~inp.helper)
    taxpayer = inp.income * 12 > int(params.get("dbt.taxpayer_income_paise"))
    pensioner = (inp.stage == c.RETIRED) & (inp.income >= int(params.get("dbt.pm_kisan.pension_exclusion_paise")))
    excluded = _government_employee(inp) | (_per_household(inp, taxpayer | pensioner) > 0)
    farmer = farmer[~excluded[hh[farmer]]]
    order = farmer[np.lexsort((farmer, -inp.age[farmer], hh[farmer]))]
    _, first = np.unique(hh[order], return_index=True)
    payee = np.sort(order[first])
    enrolled = _covered(seed, "dbt.pm_kisan.cover", hh[payee], params.get("dbt.pm_kisan.coverage"))
    amount = np.full(payee.size, int(params.get("dbt.pm_kisan.amount_paise")), dtype=np.int64)
    return _result(PM_KISAN, payee, enrolled, amount, amount * 3 // 12)


def old_age_pension(inp: DbtInputs, params: ParamRegistry, seed: int) -> SchemeResult:
    """Aged 60+, no contributory pension (not retired), in a BPL household: central share plus state top-up."""
    payee = np.flatnonzero((inp.age >= int(params.get("dbt.old_age.min_age"))) & (inp.stage != c.RETIRED)
                           & inp.bpl[inp.household])
    bands = sorted(params.get("dbt.old_age.central_paise"))
    ages = np.array([a for a, _ in bands])
    central = np.array([v for _, v in bands], dtype=np.int64)
    band = np.maximum(np.searchsorted(ages, inp.age[payee], side="right") - 1, 0)
    amount = central[band] + int(params.get("dbt.old_age.state_topup_paise"))
    enrolled = _covered(seed, "dbt.old_age.cover", payee, params.get("dbt.old_age.coverage"))
    return _result(OLD_AGE_PENSION, payee, enrolled, amount, amount)


def women(inp: DbtInputs, params: ParamRegistry, seed: int) -> SchemeResult:
    """Women in the age range, household earned income under the cap, no government employee at home.
    Each gets the amount of one state's scheme, drawn once with the tiers' weights."""
    lo, hi = params.get("dbt.women.ages")
    hh_income = _per_household(inp, inp.income)
    under_cap = hh_income * 12 < int(params.get("dbt.women.income_cap_paise"))
    payee = np.flatnonzero((inp.sex == c.F) & (inp.age >= lo) & (inp.age <= hi)
                           & under_cap[inp.household] & ~_government_employee(inp)[inp.household])
    tiers = params.get("dbt.women.amount_tiers")
    amounts = np.array([a for a, _ in tiers], dtype=np.int64)
    cum = np.cumsum([w for _, w in tiers], dtype=np.float64)
    u = rng.uniform(seed, rng.stream_id("dbt.women.tier"), payee, 0)
    amount = amounts[np.minimum(np.searchsorted(cum / cum[-1], u, side="right"), amounts.size - 1)]
    enrolled = _covered(seed, "dbt.women.cover", payee, params.get("dbt.women.coverage"))
    return _result(WOMEN, payee, enrolled, amount, amount)


def _on_release_date(day: dt.date, params: ParamRegistry) -> bool:
    return day.isoformat() in {str(d) for d in params.get("dbt.pm_kisan.dates")}


@dataclass(frozen=True)
class _OnDay:
    """Pays on the day of the month a parameter names. A class, not a closure, so schemes pickle."""
    param: str

    def __call__(self, day: dt.date, params: ParamRegistry) -> bool:
        return day.day == int(params.get(self.param))


def _on_day(param: str) -> Callable[[dt.date, ParamRegistry], bool]:
    return _OnDay(param)


def default_schemes() -> list[Scheme]:
    return [Scheme(PM_KISAN, int(Purpose.DBT_PM_KISAN), pm_kisan, _on_release_date),
            Scheme(OLD_AGE_PENSION, int(Purpose.DBT_OLD_AGE_PENSION), old_age_pension, _on_day("dbt.old_age.day")),
            Scheme(WOMEN, int(Purpose.DBT_WOMEN), women, _on_day("dbt.women.day"))]


def enrolled_payees(inp: DbtInputs, params: ParamRegistry, seed: int,
                    schemes: list[Scheme] | None = None) -> np.ndarray:
    """Per person: enrolled as a payee in at least one scheme."""
    out = np.zeros(inp.stage.size, dtype=bool)
    for scheme in schemes if schemes is not None else default_schemes():
        r = scheme.evaluate(inp, params, seed)
        out[r.payee[r.enrolled]] = True
    return out
