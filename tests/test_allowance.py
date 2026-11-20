import numpy as np
from arthasim.engine.intents import Purpose
from arthasim.ledger.journal import FlowType
from arthasim.modules.allowance import allowance_pairs, person_need


def test_enum_values():
    assert Purpose.ALLOWANCE == 6 and FlowType.HOUSEHOLD_TRANSFER == 9


def test_person_need():
    need = person_need(person_budget=np.array([30_000, 30_000, 30_000]), budget=np.array([90_000]),
                       medical_due=np.array([5_000]), head=np.array([0]),
                       utilities_share=np.array([0.1, 0.1, 0.1]))
    assert np.allclose(need, [41_000, 27_000, 27_000])    # head: 27,000 + 9,000 utilities + 5,000 medical


def test_pairs_cover_shortfall():
    # Earner, homemaker, pensioner with a small pension: the pension is topped up, not replaced.
    p, r, a = allowance_pairs(np.array([0, 0, 0]), np.array([100_000, 0, 7_000]),
                              np.array([41_000.0, 27_000.0, 27_000.0]))
    assert list(zip(p.tolist(), r.tolist(), a.tolist())) == [(0, 1, 27_000), (0, 2, 20_000)]


def test_pairs_scaled_when_short():
    # Surplus 10,000 + 5,000; shortfall 20,000 + 10,000; scale 0.5, split 2:1 between payers.
    p, r, a = allowance_pairs(np.array([0, 0, 0, 0]), np.array([30_000, 10_000, 0, 0]),
                              np.array([20_000.0, 5_000.0, 20_000.0, 10_000.0]))
    assert list(zip(p.tolist(), r.tolist(), a.tolist())) == [(0, 2, 6_667), (0, 3, 3_333), (1, 2, 3_333), (1, 3, 1_667)]
    assert a[p == 0].sum() == 10_000 and a[p == 1].sum() == 5_000


def test_no_surplus_no_pairs():
    # Household 0: two non-earners. Household 1: one adult short of need.
    p, r, a = allowance_pairs(np.array([0, 0, 1]), np.array([0, 0, 0]), np.array([10_000.0, 10_000.0, 10_000.0]))
    assert p.size == r.size == a.size == 0 and p.dtype == np.int64


import calendar
import datetime as dt
from dataclasses import fields
from arthasim.engine.intents import Intents, Rail
from arthasim.ledger.journal import Kind
from arthasim.modules.allowance import Allowance, allowance_day
from arthasim.modules.budget import Budget
from helpers import P
from world_fixture import small_world

W = small_world()
S, B = W.state, W.state.population
FIELDS = [f.name for f in fields(Intents)]


def _month(year, mon, withdrawals=False):
    Budget().monthly(W, dt.date(year, mon, 1))
    mod = Allowance()
    mod.monthly(W, dt.date(year, mon, 1))
    days = range(1, calendar.monthrange(year, mon)[1] + 1)
    parts = [(d, mod.intents(W, dt.date(year, mon, d))) for d in days]
    it, day = Intents.concat([it for _, it in parts]), np.concatenate([np.full(len(it), d) for d, it in parts])
    if not withdrawals:
        keep = it.purpose == Purpose.ALLOWANCE
        it, day = Intents(*[getattr(it, f)[keep] for f in FIELDS]), day[keep]
    return it, day


def _owner():
    owner = np.full(len(S.book), -1, dtype=np.int64)
    banked = np.flatnonzero(S.person_deposit >= 0)
    owner[S.person_deposit[banked]] = banked
    owner[S.person_cash] = np.arange(len(S.person_cash))
    return owner


def test_allowance_day():
    assert allowance_day(np.array([28, 5, -1]), np.array([3, 3, 17]), 28).tolist() == [28, 6, 17]
    assert allowance_day(np.array([28, 5, -1]), np.array([3, 3, 17]), 31).tolist() == [29, 6, 17]


def test_no_monthly_no_intents():
    assert len(Allowance().intents(W, dt.date(2025, 4, 5))) == 0


def test_month_pays_every_pair_once_inside_households():
    it, _ = _month(2025, 4)
    it.validate()
    beh, h = S.behaviour, B.households
    kinds = np.array([d.kind for d in B.districts])
    u = np.where(kinds[B.persons.district] == "metro", P.get("consumption.category_shares.metro")[9],
                 P.get("consumption.category_shares.rural")[9])
    need = person_need(beh.person_budget, beh.budget, beh.medical_due, h.head, u)
    p, r, a = allowance_pairs(h.household_of_person, B.attributes.monthly_income_paise, need)
    owner = _owner()
    got = sorted(zip(owner[it.payer_acct].tolist(), owner[it.payee_acct].tolist(), it.amount.tolist()))
    assert len(got) > 0 and got == sorted(zip(p.tolist(), r.tolist(), a.tolist()))
    assert (it.purpose == Purpose.ALLOWANCE).all() and (it.flow_type == FlowType.HOUSEHOLD_TRANSFER).all()
    assert ((it.slot >= 48) & (it.slot <= 79)).all()


def test_rails_follow_recipient():
    it, _ = _month(2025, 4)
    owner, upi = _owner(), B.banking.person_upi
    payer, rec = owner[it.payer_acct], owner[it.payee_acct]
    to_upi = upi[rec]
    p2p = to_upi & upi[payer] & (it.amount <= P.get("rail.upi.limit_paise"))
    imps = to_upi & ~p2p & (S.person_deposit[payer] >= 0)
    cash = ~(p2p | imps)
    assert (it.rail[p2p] == Rail.UPI_P2P).all() and (it.rail[imps] == Rail.IMPS).all()
    assert (it.rail[cash] == Rail.CASH).all() and (it.kind[cash] == Kind.CASH_PAYMENT).all()
    assert (it.kind[~cash] == Kind.PAYMENT).all()
    assert (it.payer_acct[cash] == S.person_cash[payer[cash]]).all()
    assert (it.payee_acct[~cash] == S.person_deposit[rec[~cash]]).all()


def test_days_salaried_and_keyed():
    it, day = _month(2025, 4)
    payer = _owner()[it.payer_acct]
    sal = S.person_employer[payer] >= 0
    assert (day[sal] == np.minimum(S.employer_payday[S.person_employer[payer[sal]]] + 1, 30)).all()
    assert ((day[~sal] >= 1) & (day[~sal] <= 28)).all()
    may, may_day = _month(2025, 5)
    may_payer = _owner()[may.payer_acct]
    april = dict(zip(payer[~sal].tolist(), day[~sal].tolist()))
    assert all(april.get(q, d) == d for q, d in zip(may_payer.tolist(), may_day.tolist()))


def test_cash_payer_withdraws_shortfall_first():
    it, day = _month(2025, 4, withdrawals=True)
    owner, bal = _owner(), S.book.balance
    wd = it.kind == Kind.CASH_WITHDRAWAL
    cash_allow = (it.purpose == Purpose.ALLOWANCE) & (it.kind == Kind.CASH_PAYMENT)
    assert wd.any() and (it.purpose[wd] == Purpose.CASH_WITHDRAWAL).all()
    assert (it.flow_type[wd] == FlowType.CASH_CONVERSION).all()
    payer = owner[it.payer_acct]
    assert (it.payer_acct[wd] == S.person_deposit[payer[wd]]).all() and (it.payee_acct[wd] == S.person_cash[payer[wd]]).all()
    assert (it.rail[wd] == S.withdraw_rail[S.person_cash[payer[wd]]]).all()
    # One withdrawal per banked payer and day whose cash on hand is short of that day's cash allowances,
    # for the shortfall rounded up to whole hundreds of rupees, at slot 48 offset 0, before any allowance.
    due = {}
    for q, d, a in zip(payer[cash_allow].tolist(), day[cash_allow].tolist(), it.amount[cash_allow].tolist()):
        due[(q, d)] = due.get((q, d), 0) + a
    expected = {}
    for (q, d), a in due.items():
        short = a - int(bal[S.person_cash[q]])
        if S.person_deposit[q] >= 0 and short > 0:
            expected[(q, d)] = -(-short // 10_000) * 10_000
    assert dict(zip(zip(payer[wd].tolist(), day[wd].tolist()), it.amount[wd].tolist())) == expected
    assert len(expected) == int(wd.sum()) and (it.slot[wd] == 48).all() and (it.offset_s[wd] == 0).all()
