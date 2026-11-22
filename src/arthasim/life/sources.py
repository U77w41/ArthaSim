"""PLFS 2025 source values for the life course, read from params/lifecourse/plfs_2025.yaml."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, model_validator

from arthasim.build.marginals import _resolve

GROUPS = ("rural_male", "rural_female", "urban_male", "urban_female")
PLFS_COLUMNS = ["15-19", "20-24", "25-29", "30-34", "35-39", "40-44", "45-49", "50-54", "55-59", "60-64", "65+",
                "15+"]
ANNUAL_ROWS = ("own_agri", "own_secondary", "own_tertiary", "helper_agri", "helper_secondary", "helper_tertiary",
               "regular", "regular_agri", "casual_public", "casual_other", "casual_other_agri", "unemployed",
               "student", "domestic", "domestic_collect", "pensioner", "disabled", "others")
EFFECT_KEYS = ("very_young", "young", "graduate", "has_child", "married", "e_ratio", "streak2", "streak3")
MONTHS = ("2025-04", "2025-05", "2025-06", "2025-07", "2025-08", "2025-09", "2025-10", "2025-11", "2025-12",
          "2026-01", "2026-02", "2026-03")
QUARTERS = ("2025-05", "2025-08", "2025-11", "2026-02")
_DEFAULT = "params/lifecourse/plfs_2025.yaml"


def group_name(kind: str, sex: int) -> str:
    """PLFS group for a district kind ("metro" is urban India, "rural" is rural India) and sex (0 F, 1 M)."""
    area = {"metro": "urban", "rural": "rural"}[kind]
    return f"{area}_{'female' if sex == 0 else 'male'}"


@dataclass(frozen=True)
class FlowPairs:
    pairs: list[list[list[float | None]]]      # [pair][row][col], states own, helper, regular, casual, unemployed, nlf
    row_totals: list[list[float]]              # [pair][row], the row's "all" value


@dataclass(frozen=True)
class Plfs2025:
    annual: dict[str, dict[str, list[float]]]
    cws_2025: dict[str, dict[str, float]]
    monthly: dict[str, dict[str, dict[str, float]]]
    quarterly: dict[str, dict[str, dict[str, float]]]
    flows: dict[str, FlowPairs]
    effects: dict[str, dict[str, dict[str, float]]]


class _Block(BaseModel):
    source: str
    table: str
    pages: str
    status: Literal["unverified", "verified", "assumption"]


class _Rate(BaseModel):
    lfpr: float
    wpr: float


class _Quarter(BaseModel):
    regular: float
    casual: float
    agriculture: float


class _Flows(BaseModel):
    pairs: list[list[list[Optional[float]]]]
    row_totals: list[list[float]]

    @model_validator(mode="after")
    def _check(self) -> "_Flows":
        if len(self.pairs) != 4 or len(self.row_totals) != 4:
            raise ValueError("flows: four quarter pairs expected")
        for p, t in zip(self.pairs, self.row_totals):
            if len(p) != 6 or any(len(r) != 6 for r in p) or len(t) != 6:
                raise ValueError("flows: each pair is 6 rows of 6 cells with 6 row totals")
        return self


class _Annual(_Block):
    values: dict[str, dict[str, list[float]]]

    @model_validator(mode="after")
    def _check(self) -> "_Annual":
        if set(self.values) != set(GROUPS):
            raise ValueError("annual: one block per PLFS group expected")
        for g, rows in self.values.items():
            if set(rows) != set(ANNUAL_ROWS) or any(len(v) != len(PLFS_COLUMNS) or min(v) < 0 for v in rows.values()):
                raise ValueError(f"annual.{g}: rows {ANNUAL_ROWS}, each {len(PLFS_COLUMNS)} non-negative values")
        return self


class _Cws(_Block):
    values: dict[str, _Rate]


class _Monthly(_Block):
    values: dict[str, dict[str, _Rate]]

    @model_validator(mode="after")
    def _check(self) -> "_Monthly":
        if tuple(sorted(self.values)) != MONTHS or any(set(v) != set(GROUPS) for v in self.values.values()):
            raise ValueError("monthly: every group for every month from 2025-04 to 2026-03 expected")
        return self


class _Quarterly(_Block):
    values: dict[str, dict[str, _Quarter]]

    @model_validator(mode="after")
    def _check(self) -> "_Quarterly":
        if tuple(sorted(self.values)) != QUARTERS or any(set(v) != set(GROUPS) for v in self.values.values()):
            raise ValueError(f"quarterly: every group for the quarters {QUARTERS} expected")
        return self


class _FlowsBlock(_Block):
    values: dict[Literal["M", "F"], _Flows]


class _Effects(_Block):
    values: dict[Literal["M", "F"], dict[Literal["lost", "gained"], dict[str, float]]]

    @model_validator(mode="after")
    def _check(self) -> "_Effects":
        for s, kinds in self.values.items():
            if set(kinds) != {"lost", "gained"} or any(set(v) != set(EFFECT_KEYS) for v in kinds.values()):
                raise ValueError(f"effects.{s}: lost and gained with keys {EFFECT_KEYS} expected")
        return self


class _File(BaseModel):
    annual: _Annual
    cws_2025: _Cws
    monthly: _Monthly
    quarterly: _Quarterly
    flows: _FlowsBlock
    effects: _Effects


@lru_cache(maxsize=None)
def _load(path: Path) -> Plfs2025:
    f = _File(**yaml.safe_load(path.read_text()))
    return Plfs2025(
        annual=f.annual.values,
        cws_2025={g: r.model_dump() for g, r in f.cws_2025.values.items()},
        monthly={m: {g: r.model_dump() for g, r in v.items()} for m, v in f.monthly.values.items()},
        quarterly={q: {g: r.model_dump() for g, r in v.items()} for q, v in f.quarterly.values.items()},
        flows={s: FlowPairs(pairs=v.pairs, row_totals=v.row_totals) for s, v in f.flows.values.items()},
        effects={s: {k: dict(d) for k, d in v.items()} for s, v in f.effects.values.items()},
    )


def load_plfs(path: str | Path = _DEFAULT) -> Plfs2025:
    """The PLFS 2025 values; relative paths resolve against the repo root. Cached per resolved path."""
    return _load(_resolve(path).resolve())
