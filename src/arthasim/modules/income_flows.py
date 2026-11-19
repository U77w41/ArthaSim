"""Income for every earning group: salaries, other earnings, pensions and employer revenue."""
from __future__ import annotations

import calendar
import datetime as dt

import numpy as np

from arthasim.build import categories as c
from arthasim.engine import rng
from arthasim.engine.intents import Intents, Purpose, Rail
from arthasim.ledger.journal import FlowType, Kind
from arthasim.modules.base import BehaviourModule

_OTHER_EARNERS = (c.SELF_EMPLOYED, c.GIG, c.FARM, c.CASUAL)


def _rows(kind, flow, payer, payee, amount, rail, slot, offset, purpose) -> Intents:
    n = len(np.atleast_1d(payee))
    full = lambda v: np.broadcast_to(np.asarray(v, dtype=np.int64), (n,))
    return Intents(full(kind), full(flow), full(payer), full(payee), full(amount), full(rail), full(slot),
                   full(offset), full(purpose))


class Income(BehaviourModule):
    name = "income"

    def intents(self, world, day: dt.date) -> Intents:
        s, params, seed = world.state, world.params, world.seed
        pop = s.population
        stage = pop.persons.life_stage
        income = pop.attributes.monthly_income_paise
        banked = s.person_deposit >= 0
        d = day.toordinal()
        S = rng.stream_id

        def slot_offset(ids, lo, width):
            slot = lo + np.minimum((rng.uniform(seed, S("income.slot"), ids, d) * width).astype(np.int64), width - 1)
            off = np.minimum((rng.uniform(seed, S("income.offset"), ids, d) * 900).astype(np.int64), 899)
            return slot, off

        parts: list[Intents] = []

        # Employer revenue from outside the sample, on the 1st.
        if day.day == 1:
            amount = np.rint(params.get("spike.employer_revenue_multiple") * s.employer_payroll).astype(np.int64)
            m = amount > 0
            parts.append(_rows(Kind.PAYMENT, FlowType.TRANSFER, s.boundary_deposit, s.employer_deposit[m], amount[m],
                               Rail.NEFT, 32, 0, Purpose.EMPLOYER_REVENUE))

        # Salaries on each employer's payday.
        if len(s.employer_ids):
            paying = s.employer_payday == day.day
            staff = np.flatnonzero((s.person_employer >= 0) & paying[np.maximum(s.person_employer, 0)])
            if staff.size:
                slot, off = slot_offset(staff, 36, 12)
                parts.append(_rows(Kind.PAYMENT, FlowType.WAGE, s.employer_deposit[s.person_employer[staff]],
                                   s.person_deposit[staff], s.person_salary[staff], Rail.NACH_CR, slot, off,
                                   Purpose.SALARY))

        # Pensions from outside the sample: by NACH if banked, else in cash.
        if day.day == int(params.get("income.pension_day")):
            retired = np.flatnonzero((stage == c.RETIRED) & (income > 0))
            slot, off = slot_offset(retired, 36, 12)
            b = banked[retired]
            parts.append(_rows(Kind.PAYMENT, FlowType.PENSION, s.boundary_deposit, s.person_deposit[retired[b]],
                               income[retired[b]], Rail.NACH_CR, slot[b], off[b], Purpose.PENSION))
            parts.append(_rows(Kind.CASH_PAYMENT, FlowType.PENSION, s.boundary_cash, s.person_cash[retired[~b]],
                               income[retired[~b]], Rail.CASH, slot[~b], off[~b], Purpose.PENSION))

        # Other earners: exactly f pay days a month, spread by a per-person phase.
        days_in_month = calendar.monthrange(day.year, day.month)[1]
        events = params.get("income.pay_events_per_month")
        cash_share = params.get("income.cash_share")
        sigma = params.get("income.event_sigma")
        for st in _OTHER_EARNERS:
            name = c.LIFE_STAGE[st]
            f = int(events[name])
            who = np.flatnonzero((stage == st) & (income > 0))
            if who.size == 0:
                continue
            phi = rng.uniform(seed, S("income.phase"), who, 0) * days_in_month
            pays = (np.floor((day.day + phi) * f / days_in_month)
                    > np.floor((day.day - 1 + phi) * f / days_in_month))
            who = who[pays]
            if who.size == 0:
                continue
            z = rng.normal(seed, S("income.noise"), who, d)
            amount = np.maximum(100, np.rint(income[who] / f * np.exp(sigma * z - sigma ** 2 / 2))).astype(np.int64)
            in_cash = ~banked[who] | (rng.uniform(seed, S("income.cash"), who, d) < cash_share[name])
            slot, off = slot_offset(who, 40, 40)
            parts.append(_rows(Kind.CASH_PAYMENT, FlowType.EARNINGS, s.boundary_cash, s.person_cash[who[in_cash]],
                               amount[in_cash], Rail.CASH, slot[in_cash], off[in_cash], Purpose.EARNINGS))
            dig = ~in_cash
            rail = np.where(pop.banking.person_upi[who[dig]], Rail.UPI_P2P, Rail.NEFT)
            parts.append(_rows(Kind.PAYMENT, FlowType.EARNINGS, s.boundary_deposit, s.person_deposit[who[dig]],
                               amount[dig], rail, slot[dig], off[dig], Purpose.EARNINGS))
        return Intents.concat(parts)
