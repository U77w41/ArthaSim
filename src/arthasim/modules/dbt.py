"""Government transfers (DBT): each month the schemes' eligible, covered people are enrolled; on each
scheme's pay day the government credits them by APBS from its balance at the central bank."""
from __future__ import annotations

import datetime as dt

import numpy as np
import polars as pl

from arthasim.build.banking import pick_banks
from arthasim.build.pipeline import dbt_inputs
from arthasim.dbt.schemes import Scheme, SchemeResult, default_schemes
from arthasim.engine import rng
from arthasim.engine.intents import Intents, Rail
from arthasim.ledger.journal import FlowType, Kind
from arthasim.life.accounts import open_accounts
from arthasim.life.events import EventLog
from arthasim.modules.base import BehaviourModule

DBT_SCHEMA = {"entity_id": pl.Int64, "month": pl.String, "scheme": pl.String, "enrolled": pl.Boolean,
              "monthly_value_paise": pl.Int64, "opened_account": pl.Boolean}


class GovernmentTransfers(BehaviourModule):
    name = "dbt"

    def __init__(self, schemes: list[Scheme] | None = None) -> None:
        self.schemes = list(schemes) if schemes is not None else default_schemes()
        self._results: list[tuple[Scheme, SchemeResult]] = []
        self._tables: dict[str, pl.DataFrame] = {}

    def tables(self) -> dict[str, pl.DataFrame]:
        out, self._tables = self._tables, {}
        return out

    def monthly(self, world, month: dt.date) -> None:
        s, params, seed = world.state, world.params, world.seed
        if s.government is None:
            return
        first = month.replace(day=1)
        results = [(scheme, scheme.evaluate(dbt_inputs(s), params, seed)) for scheme in self.schemes]

        # Every payee is paid into a bank account: an enrolled payee without one opens it this month.
        n = len(s.person_ids)
        payee = np.zeros(n, dtype=bool)
        for _, r in results:
            payee[r.payee[r.enrolled]] = True
        unbanked = np.flatnonzero(payee & (s.person_deposit < 0))
        opened = np.zeros(n, dtype=bool)
        log = EventLog()
        if unbanked.size:
            pop = s.population
            is_metro = np.array([d.kind == "metro" for d in pop.districts])[pop.persons.district[unbanked]]
            u = rng.uniform(seed, rng.stream_id("dbt.bank"), unbanked, first.toordinal())
            banks = pick_banks(u, is_metro, params, int(world.config.banks))
            ids = open_accounts(s, params, unbanked, banks, first, seed)
            income = pop.attributes.monthly_income_paise[unbanked]
            log.add(s.person_ids[unbanked], "ACCOUNT_OPENED", income_before=income, income_after=income,
                    account_id=ids)
            opened[unbanked] = True
        events = log.frame(first, s.life.next_event_id)
        s.life.next_event_id += events.height

        transfer = np.zeros(n, dtype=np.int64)
        for _, r in results:
            np.add.at(transfer, r.payee, r.monthly_value)
        s.behaviour.person_transfer[:] = transfer

        label = f"{month:%Y-%m}"
        rows = [pl.DataFrame({"entity_id": s.person_ids[r.payee], "month": [label] * r.payee.size,
                              "scheme": [r.scheme] * r.payee.size, "enrolled": r.enrolled,
                              "monthly_value_paise": r.monthly_value,
                              "opened_account": opened[r.payee] & r.enrolled}, schema=DBT_SCHEMA)
                for _, r in results]
        self._results = results
        self._tables = {"truth_dbt_monthly": pl.concat(rows) if rows else pl.DataFrame(schema=DBT_SCHEMA),
                        "life_events": events}

    def intents(self, world, day: dt.date) -> Intents:
        s, params, seed = world.state, world.params, world.seed
        lo, hi = (int(x) for x in params.get("dbt.slots"))
        d = day.toordinal()
        parts: list[Intents] = []
        for scheme, r in self._results:
            if not scheme.pays_on(day, params):
                continue
            who, amount = r.payee[r.enrolled], r.amount[r.enrolled]
            if who.size == 0:
                continue
            deposit = s.person_deposit[who]
            if (deposit < 0).any():
                raise RuntimeError("an enrolled DBT payee has no bank account")
            slot = lo + np.minimum((rng.uniform(seed, rng.stream_id("dbt.slot"), who, d) * (hi - lo + 1))
                                   .astype(np.int64), hi - lo)
            off = np.minimum((rng.uniform(seed, rng.stream_id("dbt.offset"), who, d) * 900).astype(np.int64), 899)
            full = lambda v: np.full(who.size, int(v), dtype=np.int64)
            parts.append(Intents(full(Kind.GOVERNMENT_TRANSFER), full(FlowType.SOCIAL_BENEFIT),
                                 full(s.government.balance_account), deposit, amount, full(Rail.APBS), slot, off,
                                 full(scheme.purpose)))
        return Intents.concat(parts)
