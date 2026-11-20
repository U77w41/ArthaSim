"""Household allowances: earners pass money to members whose own income falls short of their need."""
from __future__ import annotations

import calendar
import datetime as dt

import numpy as np

from arthasim.engine import rng
from arthasim.engine.intents import Intents, Purpose, Rail
from arthasim.ledger.journal import FlowType, Kind
from arthasim.modules.base import BehaviourModule
from arthasim.modules.spending import UTILITIES

_EMPTY = np.empty(0, dtype=np.int64)
_NOTE = 10_000                     # withdrawals are rounded up to whole hundreds of rupees


def person_need(person_budget: np.ndarray, budget: np.ndarray, medical_due: np.ndarray, head: np.ndarray,
                utilities_share: np.ndarray) -> np.ndarray:
    """Each adult's monthly outgoings: their spending share less utilities, plus, for the head,
    the household's utilities bill and medical costs. Per-household arrays are indexed by household."""
    u = np.asarray(utilities_share, dtype=np.float64)
    need = np.asarray(person_budget, dtype=np.float64) * (1.0 - u)
    head = np.asarray(head, dtype=np.int64)
    need[head] += np.asarray(budget, dtype=np.float64) * u[head] + np.asarray(medical_due, dtype=np.float64)
    return need


def _balance(hh: np.ndarray, income, need):
    """Per person shortfall and surplus, and their totals per household."""
    income, need = np.asarray(income, dtype=np.float64), np.asarray(need, dtype=np.float64)
    shortfall, surplus = np.maximum(0.0, need - income), np.maximum(0.0, income - need)
    n_h = int(hh.max()) + 1 if hh.size else 0
    return (shortfall, surplus, np.bincount(hh, weights=surplus, minlength=n_h),
            np.bincount(hh, weights=shortfall, minlength=n_h))


def _scale(total_surplus: np.ndarray, total_short: np.ndarray) -> np.ndarray:
    return np.minimum(1.0, np.divide(total_surplus, total_short, out=np.ones(total_short.size),
                                     where=total_short > 0))


def _margin_scale(total_surplus: np.ndarray, total_short: np.ndarray, total_request: np.ndarray) -> np.ndarray:
    """Share of each household's margin requests that the surplus left after every shortfall can pay."""
    leftover = np.maximum(0.0, total_surplus - total_short)
    full = leftover >= total_request              # divide only where the result is below 1: no overflow
    return np.divide(leftover, total_request, out=np.ones(total_request.size), where=~full)


def margin_scale(household_of_person: np.ndarray, income: np.ndarray, need: np.ndarray,
                 margin: float) -> np.ndarray:
    """Per household, the share of every recipient's margin that leftover surplus pays: at most 1,
    and 1 with no request."""
    hh = np.asarray(household_of_person, dtype=np.int64)
    shortfall, _, total_surplus, total_short = _balance(hh, income, need)
    request = np.where(shortfall > 0, margin * np.asarray(need, dtype=np.float64), 0.0)
    return _margin_scale(total_surplus, total_short, np.bincount(hh, weights=request, minlength=total_short.size))


def household_scale(household_of_person: np.ndarray, income: np.ndarray, need: np.ndarray) -> np.ndarray:
    """Per household, the share of every shortfall that surplus covers: at most 1, and 1 with no shortfall."""
    _, _, total_surplus, total_short = _balance(np.asarray(household_of_person, dtype=np.int64), income, need)
    return _scale(total_surplus, total_short)


def allowance_pairs(household_of_person: np.ndarray, income: np.ndarray, need: np.ndarray,
                    margin: float = 0.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(payer, recipient, amount) inside each household. Members with surplus cover members with
    shortfall, pro rata to surplus; if shortfall exceeds surplus, every shortfall is scaled down alike."""
    hh = np.asarray(household_of_person, dtype=np.int64)
    shortfall, surplus, total_surplus, total_short = _balance(hh, income, need)
    n_h = total_surplus.size
    scale = _scale(total_surplus, total_short)
    # Second stage: surplus left after every shortfall pays each recipient a margin on their need.
    request = np.where(shortfall > 0, margin * np.asarray(need, dtype=np.float64), 0.0)
    scale2 = _margin_scale(total_surplus, total_short, np.bincount(hh, weights=request, minlength=n_h))

    # Pair members by position within their household (households are small).
    order = np.argsort(hh, kind="stable")
    count = np.bincount(hh, minlength=n_h)
    start = np.cumsum(count) - count
    payers, recipients = [_EMPTY], [_EMPTY]
    for a in range(int(count.max()) if n_h else 0):
        for b in range(int(count.max())):
            if a == b:
                continue
            rows = start[count > max(a, b)]
            p, r = order[rows + a], order[rows + b]
            keep = (surplus[p] > 0) & (shortfall[r] > 0)
            payers.append(p[keep])
            recipients.append(r[keep])
    p, r = np.concatenate(payers), np.concatenate(recipients)
    h = hh[p]
    amount = np.rint((shortfall[r] * scale[h] + request[r] * scale2[h]) * surplus[p] / total_surplus[h]).astype(np.int64)
    keep = amount > 0
    p, r, amount = p[keep], r[keep], amount[keep]
    order = np.lexsort((r, p))
    return p[order], r[order], amount[order]


def allowance_day(payday: np.ndarray, keyed_day: np.ndarray, days_in_month: int) -> np.ndarray:
    """Day of the month a payer gives allowances: the day after their salary (capped at the month's
    last day) for salaried payers (payday >= 1), else their own keyed day."""
    payday = np.asarray(payday, dtype=np.int64)
    return np.where(payday >= 1, np.minimum(payday + 1, days_in_month), np.asarray(keyed_day, dtype=np.int64))


def allowance_need(world) -> np.ndarray:
    """Each adult's need this month (the margin is paid separately, from leftover surplus)."""
    s, params = world.state, world.params
    pop, beh = s.population, s.behaviour
    kinds = np.array([d.kind for d in pop.districts])
    u = np.where(kinds[pop.persons.district] == "metro",
                 params.get("consumption.category_shares.metro")[UTILITIES],
                 params.get("consumption.category_shares.rural")[UTILITIES])
    return person_need(beh.person_budget, beh.budget, beh.medical_due, pop.households.head, u)


class Allowance(BehaviourModule):
    """Monthly allowances inside households, paid where the recipient spends from."""

    name = "allowance"

    def __init__(self) -> None:
        self._pairs: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray] | None = None

    def monthly(self, world, month: dt.date) -> None:
        s, seed = world.state, world.seed
        pop = s.population
        payer, recipient, amount = allowance_pairs(pop.households.household_of_person,
                                                   pop.attributes.monthly_income_paise, allowance_need(world),
                                                   world.params.get("transfer.allowance_margin"))
        employer = s.person_employer[payer]
        payday = np.full(payer.size, -1, dtype=np.int64)
        payday[employer >= 0] = s.employer_payday[employer[employer >= 0]]
        keyed = 1 + np.minimum((rng.uniform(seed, rng.stream_id("allow.day"), payer, 0) * 28).astype(np.int64), 27)
        days = calendar.monthrange(month.year, month.month)[1]
        self._pairs = (payer, recipient, amount, allowance_day(payday, keyed, days))

    def intents(self, world, day: dt.date) -> Intents:
        if self._pairs is None:
            return Intents.empty()
        payer, rec, amount, pay_day = self._pairs
        today = pay_day == day.day
        payer, rec, amount = payer[today], rec[today], amount[today]
        n = payer.size
        if n == 0:
            return Intents.empty()
        s, params, seed = world.state, world.params, world.seed
        upi, d, S = s.population.banking.person_upi, day.toordinal(), rng.stream_id

        # Rail follows the recipient: digital to someone who pays by UPI, else cash in hand.
        p2p = upi[rec] & upi[payer] & (amount <= params.get("rail.upi.limit_paise"))
        imps = upi[rec] & ~p2p & (s.person_deposit[payer] >= 0)
        cash = ~(p2p | imps)
        rail = np.where(p2p, int(Rail.UPI_P2P), np.where(imps, int(Rail.IMPS), int(Rail.CASH)))
        pair = payer * len(s.person_ids) + rec
        slot = 48 + np.minimum((rng.uniform(seed, S("allow.slot"), pair, d) * 32).astype(np.int64), 31)
        off = np.minimum((rng.uniform(seed, S("allow.offset"), pair, d) * 900).astype(np.int64), 899)
        transfers = Intents(np.where(cash, int(Kind.CASH_PAYMENT), int(Kind.PAYMENT)),
                            np.full(n, int(FlowType.HOUSEHOLD_TRANSFER)),
                            np.where(cash, s.person_cash[payer], s.person_deposit[payer]),
                            np.where(cash, s.person_cash[rec], s.person_deposit[rec]),
                            amount, rail, slot, off, np.full(n, int(Purpose.ALLOWANCE)))

        # A banked payer short of cash for today's cash allowances withdraws the shortfall first.
        who, due = np.unique(payer[cash], return_inverse=True)
        total = np.bincount(due, weights=amount[cash], minlength=who.size).astype(np.int64)
        short = total - s.book.balance[s.person_cash[who]]
        go = (short > 0) & (s.person_deposit[who] >= 0)
        who, short = who[go], short[go]
        m = who.size
        wd_rail = (s.withdraw_rail[s.person_cash[who]] if s.withdraw_rail is not None
                   else np.full(m, int(Rail.ATM)))
        withdrawals = Intents(np.full(m, int(Kind.CASH_WITHDRAWAL)), np.full(m, int(FlowType.CASH_CONVERSION)),
                              s.person_deposit[who], s.person_cash[who], -(-short // _NOTE) * _NOTE, wd_rail,
                              np.full(m, 48), np.zeros(m), np.full(m, int(Purpose.CASH_WITHDRAWAL)))
        return Intents.concat([withdrawals, transfers])
