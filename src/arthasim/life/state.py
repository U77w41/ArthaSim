"""Per-person life-course state carried from month to month."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import numpy as np

from arthasim.build import categories as c
from arthasim.engine import rng
from arthasim.life.rates import flow_row, monthly_flows, quarterly_flows
from arthasim.life.targets import Targets
from arthasim.params import ParamRegistry

NO_STAGE = -1
NEVER_LEFT = 9999
NO_MONTH = -9999


def month_index(month: dt.date) -> int:
    return month.year * 12 + month.month - 1


@dataclass
class LifeState:
    birth_month: np.ndarray        # int8, 1-12
    months_in_stage: np.ndarray    # int32
    last_stage: np.ndarray         # int8, -1 none
    months_since_left: np.ndarray  # int32, 9999 none
    last_income: np.ndarray        # int64
    last_sector: np.ndarray        # int8, -1 none
    helper: np.ndarray             # bool
    raise_month: np.ndarray        # int8 per employer, 1-12
    targets: Targets
    last_raise: np.ndarray = None  # int32 month index (year * 12 + month - 1) of the last raise, -9999 none
    pay_set: np.ndarray = None     # int32 month index pay was last set (hire, switch, helper flip), -9999 none
    next_event_id: int = 0


def initial_life_state(persons, households, attributes, orgs, targets: Targets, params: ParamRegistry, seed: int,
                       start: dt.date, helper: np.ndarray) -> LifeState:
    n = len(persons)
    ids = np.arange(n, dtype=np.int64)
    S = rng.stream_id
    birth = 1 + np.minimum((rng.uniform(seed, S("life.birth_month"), ids, 0) * 12).astype(np.int64), 11)

    E = orgs.employer_capacity.size
    employer_ids = n + np.arange(E, dtype=np.int64)
    april = rng.uniform(seed, S("life.raise_month"), employer_ids, 0) < float(params.get("life.raise.april_share"))
    others = np.array([m for m in range(1, 13) if m != 4], dtype=np.int64)
    pick = np.minimum((rng.uniform(seed, S("life.raise_month"), employer_ids, 0, 1) * 11).astype(np.int64), 10)
    raise_month = np.where(april, 4, others[pick])

    # Months in the current stage: geometric with the stage's monthly base exit rate, capped by age.
    neg = float(params.get("life.flows.negligible_pct"))
    exit_rate = np.stack([1 - np.diag(monthly_flows(quarterly_flows(targets.src, s, neg))) for s in (c.F, c.M)])
    stage, age = persons.life_stage, persons.age
    e = np.clip(exit_rate[persons.sex, flow_row(stage, helper)], 1e-6, 1 - 1e-9)
    u = rng.uniform(seed, S("life.months_in_stage"), ids, 0)
    months = 1 + np.floor(np.log1p(-u) / np.log1p(-e)).astype(np.int64)
    cap = np.where(stage == c.STUDYING, (age - 15) * 12, (age - 18) * 12 + 1)
    months = np.maximum(1, np.minimum(months, cap))
    return LifeState(birth_month=birth.astype(np.int8), months_in_stage=months.astype(np.int32),
                     last_stage=np.full(n, NO_STAGE, dtype=np.int8),
                     months_since_left=np.full(n, NEVER_LEFT, dtype=np.int32),
                     last_income=np.zeros(n, dtype=np.int64), last_sector=np.full(n, -1, dtype=np.int8),
                     helper=np.asarray(helper, dtype=bool).copy(), raise_month=raise_month.astype(np.int8),
                     targets=targets, last_raise=np.full(n, NO_MONTH, dtype=np.int32),
                     pay_set=np.full(n, NO_MONTH, dtype=np.int32))
