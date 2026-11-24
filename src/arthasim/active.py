"""A world's applied interventions and their state, pickled with the world.

Within a day: parameter, rail and macro interventions take effect first (`start_of_day`), then module swaps on a
month start; income shocks act after the life course's monthly hook and expense shocks after the budget's
(`after_module`); scenario DBT schemes run inside the `dbt` module; `end_of_day` notes which parameters were read."""
from __future__ import annotations

import datetime as dt
import json
import pickle
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np
import polars as pl

from arthasim import macro, where
from arthasim.interventions import (ChangeRailRule, DBTTransfer, ExpenseShock, IncomeShock, Intervention,
                                    MacroPath, ParamOverride, SetHook, SetPolicyRate)
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


@dataclass
class _Row:
    seq: int
    iv: Intervention
    effective: dt.date
    ends: dt.date | None
    extra: dict[str, Any] = field(default_factory=dict)
    affected: int | None = None
    read_after: bool | None = None
    done: bool = False             # parameter changes made, swaps made


class Active:
    def __init__(self) -> None:
        self.rows: list[_Row] = []
        self._events: list[pl.DataFrame] = []

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
        if isinstance(iv, SetHook):
            self._check_module(world, iv.impl)
        self._check_more(world, iv)
        row = _Row(len(self.rows), iv, effective, iv.ends(),
                   read_after=False if isinstance(iv, PARAM_KINDS) else None)
        self.rows.append(row)
        return row.seq

    def _check_more(self, world: "World", iv: Intervention) -> None:
        """Checks of later kinds (Tasks 7 and 8)."""

    @staticmethod
    def _check_module(world: "World", impl: Any) -> None:
        if not isinstance(impl, BehaviourModule):
            raise TypeError(f"a module swap needs a BehaviourModule; got {type(impl).__name__}")
        names = [m.name for m in world.modules]
        if impl.name not in names:
            raise ValueError(f"no module named {impl.name!r} to replace; modules are {', '.join(names)}")
        try:
            pickle.dumps(impl)
        except Exception as e:                      # noqa: BLE001 - any failure to pickle
            raise ValueError(f"a module swapped in must pickle (for checkpoints and workers): {e}") from None

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
        """Called after each module's monthly hook (Tasks 7 and 8 act here)."""

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


def unapplied(applied: list[Intervention], wanted: tuple[Intervention, ...]) -> list[Intervention]:
    """The interventions of `wanted` not matched one for one, in order, by an equal one already applied."""
    used = [False] * len(applied)
    out = []
    for iv in wanted:
        for i, done in enumerate(applied):
            if not used[i] and done == iv:
                used[i] = True
                break
        else:
            out.append(iv)
    return out
