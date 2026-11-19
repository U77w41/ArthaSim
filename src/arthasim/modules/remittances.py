"""Monthly transfers from migrant earners to their home households."""
from __future__ import annotations

import datetime as dt

import numpy as np
import polars as pl

from arthasim.build.graph import REMITTANCE
from arthasim.engine import rng
from arthasim.engine.intents import Intents, Purpose, Rail
from arthasim.ledger.journal import FlowType, Kind
from arthasim.modules.base import BehaviourModule


class Remittances(BehaviourModule):
    name = "remittances"

    def intents(self, world, day: dt.date) -> Intents:
        s, params, seed = world.state, world.params, world.seed
        pop = s.population
        edges = pop.edges.filter(pl.col("type") == REMITTANCE)
        src, dst = edges["src"].to_numpy(), edges["dst"].to_numpy()
        ok = (s.person_deposit[src] >= 0) & (s.person_deposit[dst] >= 0)
        src, dst = src[ok], dst[ok]
        send_day = 1 + np.minimum((rng.uniform(seed, rng.stream_id("remit.day"), src, 0) * 28).astype(np.int64), 27)
        today = send_day == day.day
        src, dst = src[today], dst[today]
        n = src.size
        if n == 0:
            return Intents.empty()
        d = day.toordinal()
        amount = np.rint(params.get("transfer.remittance_share") * pop.attributes.monthly_income_paise[src]).astype(np.int64)
        keep = amount > 0
        src, dst, amount = src[keep], dst[keep], amount[keep]
        n = src.size
        upi = pop.banking.person_upi[src] & (amount <= params.get("rail.upi.limit_paise"))
        slot = 40 + np.minimum((rng.uniform(seed, rng.stream_id("remit.slot"), src, d) * 40).astype(np.int64), 39)
        off = np.minimum((rng.uniform(seed, rng.stream_id("remit.offset"), src, d) * 900).astype(np.int64), 899)
        return Intents(np.full(n, Kind.PAYMENT), np.full(n, FlowType.REMITTANCE), s.person_deposit[src],
                       s.person_deposit[dst], amount, np.where(upi, Rail.UPI_P2P, Rail.IMPS), slot, off,
                       np.full(n, Purpose.REMITTANCE))
