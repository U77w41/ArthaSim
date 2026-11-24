"""A world's applied interventions and their state, pickled with the world.

Within a day: parameter, rail and macro interventions take effect first (`start_of_day`), then module swaps on a
month start; income shocks act after the life course's monthly hook and expense shocks after the budget's
(`after_module`); scenario DBT schemes run inside the `dbt` module; `end_of_day` notes which parameters were read."""
from __future__ import annotations

import dataclasses
import datetime as dt
import json
import pickle
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np
import polars as pl

from arthasim import macro, where
from arthasim.build import categories as c
from arthasim.dbt.schemes import OLD_AGE_PENSION, PM_KISAN, WOMEN, ScenarioScheme
from arthasim.engine import rng
from arthasim.interventions import (ChangeRailRule, DBTTransfer, ExpenseShock, IncomeShock, Intervention,
                                    MacroPath, ParamOverride, SetHook, SetPolicyRate)
from arthasim.life.events import EventLog
from arthasim.life.jobs import recompute_payroll
from arthasim.life.state import month_index
from arthasim.modules.base import BehaviourModule
from arthasim.store.parquet import LOG_SCHEMA

if TYPE_CHECKING:
    from arthasim.world import World

PARAM_KINDS = (ParamOverride, ChangeRailRule, MacroPath, SetPolicyRate)
POPULATION_ONLY = (IncomeShock, ExpenseShock, DBTTransfer)


def target_param(iv: Intervention) -> str:
    """The registry id a parameter, rail or macro intervention changes."""
    if isinstance(iv, ParamOverride):
        return iv.param_id
    if isinstance(iv, ChangeRailRule):
        return iv.param_id
    if isinstance(iv, MacroPath):
        return macro.param_id(iv.name)
    return macro.param_id("policy_rate")


def check_module(impl: Any, names: list[str]) -> bytes:
    """A module swapped in must be a BehaviourModule named like an existing module, and must pickle. Returns its
    pickled bytes."""
    if not isinstance(impl, BehaviourModule):
        raise TypeError(f"a module swap needs a BehaviourModule; got {type(impl).__name__}")
    if impl.name not in names:
        raise ValueError(f"no module named {impl.name!r} to replace; modules are {', '.join(names)}")
    try:
        return pickle.dumps(impl, protocol=5)
    except Exception as e:                      # noqa: BLE001 - any failure to pickle
        raise ValueError(f"a module swapped in must pickle (for checkpoints and workers): {e}") from None


def match_key(iv: Intervention) -> Any:
    """What makes two interventions the same one. A module swap compares by its module's pickled state, not by
    object identity, so it still matches after a fork or a load (which copy the module)."""
    if isinstance(iv, SetHook):
        return ("SetHook", iv.kind, iv.bank, iv.date, pickle.dumps(iv.impl, protocol=5))
    return iv


@dataclass
class _Row:
    seq: int
    iv: Intervention
    effective: dt.date
    ends: dt.date | None
    key: Any = None
    extra: dict[str, Any] = field(default_factory=dict)
    affected: int | None = None
    read_after: bool | None = None
    done: bool = False             # parameter changes made, swaps made


@dataclass
class _Shift:
    """Laid-off counts per target cell, held off the cells' salaried targets from month `first` to `last`."""
    counts: np.ndarray
    first: int                     # month index
    last: int | None               # inclusive; None for the rest of the run


@dataclass
class _Cut:
    """People whose pay an income shock cut, with what must still hold for the cut to be reversed."""
    rate: float
    who: np.ndarray
    stage: np.ndarray
    entry: np.ndarray              # month index the person entered the stage
    pay_set: np.ndarray            # `life.pay_set` at the cut
    restore: int | None            # month index of the restore; None for never


def _set_income(state, who: np.ndarray, income: np.ndarray) -> None:
    """Income, and salary for the salaried (the model keeps the two equal)."""
    state.population.attributes.monthly_income_paise[who] = income
    state.person_salary[who] = np.where(state.population.persons.life_stage[who] == c.SALARIED, income, 0)


class Active:
    def __init__(self) -> None:
        self.rows: list[_Row] = []
        self._events: list[pl.DataFrame] = []
        self._shifts: list[_Shift] = []
        self._cuts: list[_Cut] = []

    @property
    def applied(self) -> list[Intervention]:
        return [r.iv for r in self.rows]

    # -- applying -----------------------------------------------------------------------------------------------
    def apply(self, world: "World", iv: Intervention) -> int:
        if not isinstance(iv, Intervention):
            raise TypeError(f"not an intervention: {iv!r}")
        effective = iv.effective(world.config.start)
        if effective < world.date:
            raise ValueError(f"{type(iv).__name__} takes effect on {effective.isoformat()}, before the world's "
                             f"next day {world.date.isoformat()}")
        if isinstance(iv, ParamOverride) and iv.param_id not in world.params:
            raise KeyError(iv.param_id)
        if isinstance(iv, POPULATION_ONLY):
            if world.state.population is None:
                raise ValueError(f"{type(iv).__name__} needs a population world (tier S and above); "
                                 "this is a spike world")
            where.check(iv.where)
        key = match_key(iv) if not isinstance(iv, SetHook) else None
        if isinstance(iv, SetHook):
            # The world runs its own copy, so no state passes between worlds (or seeds) through the caller's object.
            blob = check_module(iv.impl, [m.name for m in world.modules])
            key = ("SetHook", iv.kind, iv.bank, iv.date, blob)
            iv = dataclasses.replace(iv, impl=pickle.loads(blob))
        self._check_more(world, iv)
        row = _Row(len(self.rows), iv, effective, iv.ends(), key=key,
                   read_after=False if isinstance(iv, PARAM_KINDS) else None)
        self.rows.append(row)
        return row.seq

    def _check_more(self, world: "World", iv: Intervention) -> None:
        if isinstance(iv, DBTTransfer):
            taken = {PM_KISAN, OLD_AGE_PENSION, WOMEN}
            taken |= {s.name for s in getattr(_module(world, "dbt"), "schemes", [])}
            taken |= {r.iv.scheme for r in self.rows if isinstance(r.iv, DBTTransfer)}
            if iv.scheme in taken:
                raise ValueError(f"scheme name {iv.scheme!r} is taken; names in use are {', '.join(sorted(taken))}")

    def unapplied(self, wanted: tuple[Intervention, ...]) -> list[Intervention]:
        """The interventions of `wanted` not matched one for one, in order, by one already applied."""
        return unapplied([r.key for r in self.rows], wanted)

    # -- the day ------------------------------------------------------------------------------------------------
    def start_of_day(self, world: "World", day: dt.date) -> None:
        for row in self.rows:
            if row.done or row.effective > day or not isinstance(row.iv, PARAM_KINDS):
                continue
            world.set_params(world.params.override(target_param(row.iv), self._new_value(world, row.iv)))
            row.done = True
        if day.day == 1 or world.days_simulated == 0:
            for row in self.rows:
                if row.done or row.effective > day or not isinstance(row.iv, SetHook):
                    continue
                self._swap(world, row.iv.impl)
                row.done = True

    @staticmethod
    def _new_value(world: "World", iv: Intervention) -> Any:
        if isinstance(iv, (ParamOverride, ChangeRailRule)):
            return iv.value
        if isinstance(iv, MacroPath):
            return macro.replace_from(macro.steps(world.params, iv.name), iv.series)
        return macro.add_from(macro.steps(world.params, "policy_rate"), iv.date, iv.change_bp / 100)

    @staticmethod
    def _swap(world: "World", impl: BehaviourModule) -> None:
        i = [m.name for m in world.modules].index(impl.name)
        pending = world.modules[i].tables()
        if any(frame.height for frame in pending.values()):
            raise RuntimeError(f"module {impl.name!r} still has rows to write at a month start")
        world.modules[i] = impl

    def after_module(self, world: "World", name: str, day: dt.date) -> None:
        """Called after each module's monthly hook: income shocks act after the life course."""
        first = day.replace(day=1)
        if name == "lifecourse":
            self._income_shocks(world, first)
        elif name == "budget":
            self._expense_shocks(world, first)
        elif name == "dbt":
            self._dbt_affected(world, first)

    def dbt_schemes(self, first: dt.date) -> list[ScenarioScheme]:
        """Scenario DBT schemes enrolling in the month starting `first`, in the order applied."""
        out = []
        for row in self.rows:
            if isinstance(row.iv, DBTTransfer):
                sch = ScenarioScheme(row.iv.scheme, row.iv.amount_paise, row.iv.where, tuple(row.iv.dates), row.seq)
                if sch.active(first):
                    out.append(sch)
        return out

    def _dbt_affected(self, world: "World", first: dt.date) -> None:
        results = getattr(_module(world, "dbt"), "_results", [])
        for row in self.rows:
            if isinstance(row.iv, DBTTransfer) and row.affected is None and row.effective == first:
                for scheme, r in results:
                    if isinstance(scheme, ScenarioScheme) and scheme.seq == row.seq:
                        row.affected = int(r.enrolled.sum())
                        row.extra = {"selected": int(r.payee.size)}

    def _expense_shocks(self, world: "World", first: dt.date) -> None:
        """Extra medical shocks, after the budget has drawn the month's own (so those stay paired)."""
        s, params = world.state, world.params
        beh, hh_of = s.behaviour, s.population.households.household_of_person
        key = first.toordinal()
        for row in self.rows:
            iv = row.iv
            if not isinstance(iv, ExpenseShock) or row.effective > first or (row.ends and first >= row.ends):
                continue
            hh = np.unique(hh_of[where.select(world, iv.where)]).astype(np.int64)
            hit = rng.uniform(world.seed, rng.stream_id(iv.stream()), hh, key) < iv.rate
            cost = rng.lognormal(world.seed, rng.stream_id(iv.stream() + ".cost"), hh, key,
                                 params.get("shock.medical_median_paise"), params.get("shock.medical_sigma"))
            h = hh[hit]
            beh.medical_due[h] += np.maximum(100, np.rint(cost[hit])).astype(np.int64)
            beh.stress[h] = np.minimum(1.0, beh.stress[h] + params.get("shock.stress_bonus"))
            if row.effective == first:
                row.affected = int(hh.size)
                row.extra = {"selected": int(hh.size)}

    def target_shift(self, month: dt.date, n_cells: int) -> np.ndarray:
        """Per target cell, the people active layoff shocks hold off its salaried target this month."""
        m = month_index(month)
        out = np.zeros(n_cells, dtype=np.int64)
        for sh in self._shifts:
            if sh.first <= m and (sh.last is None or m <= sh.last):
                out += sh.counts[:n_cells]
        return out

    # -- income shocks ------------------------------------------------------------------------------------------
    def _income_shocks(self, world: "World", first: dt.date) -> None:
        s = world.state
        m = month_index(first)
        log = EventLog()
        for cut in self._cuts:
            if cut.restore == m:
                self._restore(s, cut, m, log)
        for row in self.rows:
            if isinstance(row.iv, IncomeShock) and not row.done and row.effective == first:
                if row.iv.kind == "layoff":
                    self._layoff(world, row, first, log)
                else:
                    self._pay_cut(world, row, first, log)
                row.done = True
        if len(log):
            events = log.frame(first, s.life.next_event_id)
            s.life.next_event_id += events.height
            self._events.append(events)

    def _layoff(self, world: "World", row: _Row, first: dt.date, log: EventLog) -> None:
        from arthasim.modules.lifecourse import cell_of, lay_off
        s, iv = world.state, row.iv
        sel = where.select(world, iv.where)
        sal = sel[s.population.persons.life_stage[sel] == c.SALARIED]
        u = rng.uniform(world.seed, rng.stream_id(iv.stream()), s.person_ids[sal], first.toordinal())
        who = sal[u < iv.rate]
        n_cells = s.life.targets.n_cells
        counts = np.bincount(cell_of(s)[who], minlength=n_cells).astype(np.int64)
        lay_off(world, who, first, log)
        m = month_index(first)
        if iv.months != 1 and who.size:
            self._shifts.append(_Shift(counts, m + 1, m + iv.months - 1 if iv.months else None))
        row.affected = int(who.size)
        row.extra = {"selected": int(sel.size), "not_salaried": int(sel.size - sal.size)}

    def _pay_cut(self, world: "World", row: _Row, first: dt.date, log: EventLog) -> None:
        s, iv = world.state, row.iv
        p, life = s.population.persons, s.life
        sel = where.select(world, iv.where)
        who = sel[np.isin(p.life_stage[sel], c.EARNING) & ~life.helper[sel]]
        before = s.population.attributes.monthly_income_paise[who].astype(np.int64)
        new = np.where(before > 0, np.maximum(1, np.rint(before * (1 - iv.rate))), 0).astype(np.int64)
        _set_income(s, who, new)
        recompute_payroll(s)
        log.add(s.person_ids[who], "PAY_CUT", income_before=before, income_after=new)
        m = month_index(first)
        self._cuts.append(_Cut(float(iv.rate), who, p.life_stage[who].copy(),
                               (m - life.months_in_stage[who]).astype(np.int64), life.pay_set[who].copy(),
                               m + iv.months if iv.months else None))
        row.affected = int(who.size)
        row.extra = {"selected": int(sel.size), "not_earning": int(sel.size - who.size)}

    @staticmethod
    def _restore(s, cut: _Cut, m: int, log: EventLog) -> None:
        """Reverse a cut for those still in the same stage whose pay has not been reset since (raises kept)."""
        p, life = s.population.persons, s.life
        who = cut.who
        keep = ((p.life_stage[who] == cut.stage) & ~life.helper[who] & (life.pay_set[who] == cut.pay_set)
                & ((m - life.months_in_stage[who]) == cut.entry))
        back = who[keep]
        before = s.population.attributes.monthly_income_paise[back].astype(np.int64)
        new = np.rint(before / (1 - cut.rate)).astype(np.int64)
        _set_income(s, back, new)
        recompute_payroll(s)
        log.add(s.person_ids[back], "PAY_RESTORED", income_before=before, income_after=new)

    def end_of_day(self, world: "World", day: dt.date, reads: set[str]) -> None:
        for row in self.rows:
            if row.read_after is False and row.effective <= day and target_param(row.iv) in reads:
                row.read_after = True

    def tables(self) -> dict[str, pl.DataFrame]:
        """Life events written by interventions since the last call."""
        if not self._events:
            return {}
        out = pl.concat(self._events)
        self._events = []
        return {"life_events": out}

    # -- records ------------------------------------------------------------------------------------------------
    def _details(self, row: _Row) -> dict[str, Any]:
        return {**row.iv.details(), **row.extra}

    def log_frame(self) -> pl.DataFrame:
        return pl.DataFrame({
            "seq": [r.seq for r in self.rows], "kind": [type(r.iv).__name__ for r in self.rows],
            "effective": [r.effective for r in self.rows], "ends": [r.ends for r in self.rows],
            "details": [json.dumps(self._details(r), sort_keys=True) for r in self.rows],
            "affected": [r.affected for r in self.rows], "read_after": [r.read_after for r in self.rows]},
            schema=LOG_SCHEMA)

    def details(self) -> list[dict[str, Any]]:
        return [{"kind": type(r.iv).__name__, **r.iv.details()} for r in self.rows]


def _module(world: "World", name: str):
    for m in world.modules:
        if m.name == name:
            return m
    return None


def unapplied(applied_keys: list[Any], wanted: tuple[Intervention, ...]) -> list[Intervention]:
    """The interventions of `wanted` not matched one for one, in order, by one already applied (by `match_key`)."""
    used = [False] * len(applied_keys)
    out = []
    for iv in wanted:
        key = match_key(iv)
        for i, done in enumerate(applied_keys):
            if not used[i] and done == key:
                used[i] = True
                break
        else:
            out.append(iv)
    return out
