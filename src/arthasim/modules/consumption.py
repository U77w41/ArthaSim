"""Consumption: daily purchases by UPI or cash."""
from __future__ import annotations

import datetime as dt

import numpy as np

from arthasim.build.world import WorldState
from arthasim.engine import rng
from arthasim.engine.intents import Intents, Purpose, Rail
from arthasim.ledger.journal import FlowType, Kind
from arthasim.params import ParamRegistry


def intents(state: WorldState, params: ParamRegistry, seed: int, day: dt.date,
            persons: np.ndarray | None = None) -> Intents:
    idx = np.arange(len(state.person_ids)) if persons is None else np.asarray(persons, dtype=np.int64)
    d = day.toordinal()
    S = rng.stream_id
    n_merchants = len(state.merchant_ids)
    median = params.get("spike.purchase.median_paise")
    sigma = params.get("spike.purchase.sigma")
    count = rng.poisson(seed, S("cons.count"), state.person_ids[idx], d, params.get("spike.purchases_per_day"))

    parts: list[Intents] = []
    for k in range(int(count.max()) if count.size else 0):
        sel = idx[count > k]
        ents = state.person_ids[sel]
        merchant = np.minimum((rng.uniform(seed, S("cons.merchant"), ents, d, k) * n_merchants).astype(np.int64),
                              n_merchants - 1)
        amount = np.maximum(100, np.rint(rng.lognormal(seed, S("cons.amount"), ents, d, median, sigma, k)))
        slot = 28 + np.minimum((rng.uniform(seed, S("cons.slot"), ents, d, k) * 60).astype(np.int64), 59)
        offset = np.minimum((rng.uniform(seed, S("cons.offset"), ents, d, k) * 900).astype(np.int64), 899)
        digital = state.person_digital[sel]
        n = sel.size
        parts.append(Intents(
            np.where(digital, Kind.PAYMENT, Kind.CASH_PAYMENT), np.full(n, FlowType.CONSUMPTION),
            np.where(digital, state.person_deposit[sel], state.person_cash[sel]),
            np.where(digital, state.merchant_deposit[merchant], state.merchant_cash[merchant]),
            amount, np.where(digital, Rail.UPI_P2M, Rail.CASH), slot, offset, np.full(n, Purpose.OTHER)))
    return Intents.concat(parts)
