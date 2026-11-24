"""Spending: category purchases at nearby merchants, online orders, bills and medical costs."""
from __future__ import annotations

import calendar
import datetime as dt
from dataclasses import dataclass

import numpy as np

from arthasim.build import categories as c
from arthasim.engine import rng
from arthasim.engine.intents import Intents, Purpose, Rail
from arthasim.ledger.journal import FlowType, Kind
from arthasim.modules.base import BehaviourModule
from arthasim.params import ParamRegistry

N_CAT = len(c.MERCHANT_CATEGORIES)
UTILITIES, TELECOM = N_CAT, N_CAT + 1          # positions in the category-share lists
ONLINE_CATEGORIES = (4, 5, 8)                    # apparel, electronics, other
PHARMACY = 3
TELECOM_BILLER, ELECTRICITY_BILLER, ECOMMERCE_BILLER = 0, 1, 2
_KEY = 16                                        # entity key = person * 16 + slot for draws


def choose_rail(amount, payer_upi, payer_card, merchant_upi, merchant_card, u_upi, u_card,
                params: ParamRegistry) -> np.ndarray:
    """UPI if both sides can and the payer prefers it; else card if both sides can; else cash."""
    upi = (np.asarray(payer_upi) & np.asarray(merchant_upi) & (np.asarray(amount) <= params.get("rail.upi.limit_paise"))
           & (np.asarray(u_upi) < params.get("rail.choice.upi_preference")))
    card = (~upi & np.asarray(payer_card) & np.asarray(merchant_card)
            & (np.asarray(u_card) < params.get("rail.choice.card_preference")))
    return np.where(upi, int(Rail.UPI_P2M), np.where(card, int(Rail.DEBIT_CARD), int(Rail.CASH))).astype(np.int64)


@dataclass
class _Static:
    district: np.ndarray
    locality: np.ndarray
    is_metro: np.ndarray
    shares: np.ndarray            # per person: 11 category shares for the district kind
    order_dc: np.ndarray
    start_dc: np.ndarray
    count_dc: np.ndarray
    order_dlc: np.ndarray
    start_dlc: np.ndarray
    count_dlc: np.ndarray
    n_localities: int


def _lookup(key: np.ndarray, size: int):
    order = np.argsort(key, kind="stable")
    count = np.bincount(key, minlength=size)
    return order, np.cumsum(count) - count, count


class Consumption(BehaviourModule):
    name = "consumption"

    def __init__(self) -> None:
        self._cache: tuple | None = None         # (state, registry, _Static), reused only for those same objects

    def __getstate__(self) -> dict:
        state = dict(self.__dict__)
        state["_cache"] = None
        return state

    def _setup(self, world) -> _Static:
        s = world.state
        cached = self._cache
        if cached is None or cached[0] is not s or cached[1] is not world.params:
            pop, params = s.population, world.params
            h, o = pop.households, pop.orgs
            L = int(h.locality.max()) + 1 if h.locality.size else 1
            L = max(L, int(o.merchant_locality.max()) + 1 if o.merchant_locality.size else 1)
            n_d = len(pop.districts)
            kinds = np.array([d.kind for d in pop.districts])
            district = pop.persons.district
            is_metro = kinds[district] == "metro"
            table = np.array([params.get("consumption.category_shares.metro"),
                              params.get("consumption.category_shares.rural")], dtype=np.float64)
            dc = o.merchant_district * N_CAT + o.merchant_category
            dlc = (o.merchant_district * L + o.merchant_locality) * N_CAT + o.merchant_category
            self._cache = (s, params, _Static(district, h.locality[h.household_of_person], is_metro,
                                              table[np.where(is_metro, 0, 1)], *_lookup(dc, n_d * N_CAT),
                                              *_lookup(dlc, n_d * L * N_CAT), L))
        return self._cache[2]

    def _merchant(self, world, st: _Static, person, cat, entity, day, index):
        """A merchant in the person's district and category, usually in their own locality.
        Returns -1 where the district has no merchant of that category."""
        seed, S = world.seed, rng.stream_id
        dc = st.district[person] * N_CAT + cat
        dlc = (st.district[person] * st.n_localities + st.locality[person]) * N_CAT + cat
        local = ((rng.uniform(seed, S("cons.local"), entity, day, index) < world.params.get("consumption.local_share"))
                 & (st.count_dlc[dlc] > 0))
        n = np.where(local, st.count_dlc[dlc], st.count_dc[dc])
        start = np.where(local, st.start_dlc[dlc], st.start_dc[dc])
        pick = np.minimum((rng.uniform(seed, S("cons.pick"), entity, day, index) * n).astype(np.int64),
                          np.maximum(n - 1, 0))
        merchant = np.where(local, st.order_dlc[np.minimum(start + pick, st.order_dlc.size - 1)],
                            st.order_dc[np.minimum(start + pick, st.order_dc.size - 1)])
        return np.where(n > 0, merchant, -1)

    def intents(self, world, day: dt.date, persons: np.ndarray | None = None) -> Intents:
        s, params, seed = world.state, world.params, world.seed
        pop, beh, st = s.population, s.behaviour, self._setup(world)
        o, k, h = pop.orgs, pop.banking, pop.households
        S = rng.stream_id
        d = day.toordinal()
        D = calendar.monthrange(day.year, day.month)[1]
        idx = np.arange(len(s.person_ids)) if persons is None else np.asarray(persons, dtype=np.int64)
        in_scope = np.zeros(len(s.person_ids), dtype=bool)
        in_scope[idx] = True
        habit = pop.attributes.habit_strength
        sigma = params.get("consumption.ticket_sigma")
        per_month = params.get("consumption.purchases_per_month")
        rows: dict[str, list[np.ndarray]] = {f: [] for f in ("person", "purpose", "amount", "payee", "rail", "entity", "index")}

        def add(person, purpose, amount, merchant_or_biller, is_biller, rail, entity, index):
            """Payee accounts follow the rail: deposits for digital rails, cash for cash."""
            digital = rail != int(Rail.CASH)
            if is_biller:
                payee = np.where(digital, s.biller_deposit[merchant_or_biller], s.biller_cash[merchant_or_biller])
            else:
                payee = np.where(digital, s.merchant_deposit[merchant_or_biller], s.merchant_cash[merchant_or_biller])
            for key, value in (("person", person), ("purpose", purpose), ("amount", amount), ("payee", payee),
                               ("rail", rail), ("entity", entity), ("index", index)):
                rows[key].append(np.broadcast_to(np.asarray(value, dtype=np.int64), person.shape))

        def funded(person, amount):
            """The payer's account covers the amount at the start of the day (UPI and card need this)."""
            dep = s.person_deposit[person]
            return (dep >= 0) & (s.book.balance[np.maximum(dep, 0)] >= amount)

        def rail_for(person, amount, m_upi, m_card, entity, index):
            ok = funded(person, amount)
            return choose_rail(amount, k.person_upi[person] & ok, k.person_has_card[person] & ok, m_upi, m_card,
                               rng.uniform(seed, S("cons.upi"), entity, d, index),
                               rng.uniform(seed, S("cons.card"), entity, d, index), params)

        # Purchases by merchant category.
        for cat in range(N_CAT):
            ent_all = idx * _KEY + cat
            count = rng.poisson(seed, S("cons.count"), ent_all, d, per_month[cat] / D)
            for i in range(int(count.max()) if count.size else 0):
                person = idx[count > i]
                entity = person * _KEY + cat
                z = rng.normal(seed, S("cons.amount"), entity, d, i)
                amount = np.maximum(100, np.rint(beh.person_budget[person] * st.shares[person, cat] / per_month[cat]
                                                 * np.exp(sigma * z - sigma ** 2 / 2))).astype(np.int64)
                online = np.zeros(person.size, dtype=bool)
                if cat in ONLINE_CATEGORIES:
                    online = (k.person_upi[person] & funded(person, amount)
                              & (rng.uniform(seed, S("cons.online"), entity, d, i) < params.get("consumption.online_share")))
                if online.any():
                    p_on = person[online]
                    add(p_on, Purpose.GROCERY + cat, amount[online], ECOMMERCE_BILLER, True,
                        np.full(p_on.size, int(Rail.UPI_P2M)), entity[online], i)
                person, entity, amount = person[~online], entity[~online], amount[~online]
                favourite = self._merchant(world, st, person, cat, entity, 0, 0)
                fresh = self._merchant(world, st, person, cat, entity, d, i)
                loyal = rng.uniform(seed, S("cons.habit"), entity, d, i) < habit[person]
                merchant = np.where(loyal, favourite, fresh)
                ok = merchant >= 0                       # no merchant of this category in the district
                person, entity, amount, merchant = person[ok], entity[ok], amount[ok], merchant[ok]
                rail = rail_for(person, amount, o.merchant_accepts_upi[merchant], o.merchant_accepts_card[merchant],
                                entity, i)
                add(person, Purpose.GROCERY + cat, amount, merchant, False, rail, entity, i)

        # Monthly bills, on a fixed day for each payer. Billers accept UPI, not cards.
        def bill_day(entity):
            return 1 + np.minimum((rng.uniform(seed, S("cons.billday"), entity, 0) * 28).astype(np.int64), 27)

        heads = h.head[in_scope[h.head]]
        hh_of_head = pop.households.household_of_person[heads]
        entity = heads * _KEY + UTILITIES
        due = bill_day(entity) == day.day
        heads, hh_of_head, entity = heads[due], hh_of_head[due], entity[due]
        amount = np.maximum(100, np.rint(beh.budget[hh_of_head] * st.shares[heads, UTILITIES])).astype(np.int64)
        rail = rail_for(heads, amount, np.ones(heads.size, bool), np.zeros(heads.size, bool), entity, 0)
        add(heads, Purpose.UTILITIES, amount, ELECTRICITY_BILLER, True, rail, entity, 0)

        mobile = idx[k.person_has_mobile[idx]]
        entity = mobile * _KEY + TELECOM
        due = bill_day(entity) == day.day
        mobile, entity = mobile[due], entity[due]
        amount = np.maximum(100, np.rint(beh.person_budget[mobile] * st.shares[mobile, TELECOM])).astype(np.int64)
        rail = rail_for(mobile, amount, np.ones(mobile.size, bool), np.zeros(mobile.size, bool), entity, 0)
        add(mobile, Purpose.TELECOM, amount, TELECOM_BILLER, True, rail, entity, 0)

        # Medical costs: the head pays a pharmacy on a fixed day of the month.
        sick = np.flatnonzero(beh.medical_due > 0)
        heads = h.head[sick]
        keep = in_scope[heads]
        sick, heads = sick[keep], heads[keep]
        entity = heads * _KEY + UTILITIES + 2
        due = bill_day(entity) == day.day
        sick, heads, entity = sick[due], heads[due], entity[due]
        pharmacy = self._merchant(world, st, heads, PHARMACY, entity, 0, 0)
        ok = pharmacy >= 0
        sick, heads, entity, pharmacy = sick[ok], heads[ok], entity[ok], pharmacy[ok]
        amount = beh.medical_due[sick]
        rail = rail_for(heads, amount, o.merchant_accepts_upi[pharmacy], o.merchant_accepts_card[pharmacy], entity, 0)
        add(heads, Purpose.MEDICAL, amount, pharmacy, False, rail, entity, 0)

        if not rows["person"]:
            return Intents.empty()
        cols = {key: np.concatenate(v) for key, v in rows.items()}
        person, rail, ent, ind = cols["person"], cols["rail"], cols["entity"], cols["index"]
        digital = rail != int(Rail.CASH)
        n = person.size
        slot = 28 + np.minimum((rng.uniform(seed, S("cons.slot"), ent * 64 + ind, d, 0) * 60).astype(np.int64), 59)
        off = np.minimum((rng.uniform(seed, S("cons.offset"), ent * 64 + ind, d, 0) * 900).astype(np.int64), 899)
        return Intents(np.where(digital, int(Kind.PAYMENT), int(Kind.CASH_PAYMENT)),
                       np.full(n, int(FlowType.CONSUMPTION)),
                       np.where(digital, s.person_deposit[person], s.person_cash[person]),
                       cols["payee"], cols["amount"], rail, slot, off, cols["purpose"])
