"""Income: employer revenue from the boundary, and salary runs."""
from __future__ import annotations

import datetime as dt

import numpy as np

from arthasim.build.world import WorldState
from arthasim.engine import rng
from arthasim.engine.intents import Intents, Purpose, Rail
from arthasim.ledger.journal import FlowType, Kind
from arthasim.params import ParamRegistry


def intents(state: WorldState, params: ParamRegistry, seed: int, day: dt.date) -> Intents:
    parts: list[Intents] = []
    if len(state.employer_ids) == 0:
        return Intents.empty()
    d = day.toordinal()

    if day.day == 1:
        amount = np.rint(params.get("spike.employer_revenue_multiple") * state.employer_payroll).astype(np.int64)
        m = amount > 0                                  # no top-up for an employer with no payroll
        n = int(m.sum())
        parts.append(Intents(np.full(n, Kind.PAYMENT), np.full(n, FlowType.TRANSFER),
                             np.full(n, state.boundary_deposit), state.employer_deposit[m], amount[m],
                             np.full(n, Rail.NEFT), np.full(n, 32), np.zeros(n), np.full(n, Purpose.EMPLOYER_REVENUE)))

    paying = state.employer_payday == day.day
    staff = np.flatnonzero((state.person_employer >= 0) & paying[np.maximum(state.person_employer, 0)])
    if staff.size:
        ents = state.person_ids[staff]
        slot = 36 + np.minimum((rng.uniform(seed, rng.stream_id("income.slot"), ents, d) * 12).astype(np.int64), 11)
        offset = np.minimum((rng.uniform(seed, rng.stream_id("income.offset"), ents, d) * 900).astype(np.int64), 899)
        n = staff.size
        parts.append(Intents(np.full(n, Kind.PAYMENT), np.full(n, FlowType.WAGE),
                             state.employer_deposit[state.person_employer[staff]],
                             state.person_deposit[staff], state.person_salary[staff],
                             np.full(n, Rail.NACH_CR), slot, offset, np.full(n, Purpose.SALARY)))
    return Intents.concat(parts)
