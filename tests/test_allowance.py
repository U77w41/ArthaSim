import numpy as np
from arthasim.engine.intents import Purpose
from arthasim.ledger.journal import FlowType
from arthasim.modules.allowance import allowance_need, allowance_pairs, household_scale, margin_scale, person_need


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
    h = B.households
    need = allowance_need(W)
    p, r, a = allowance_pairs(h.household_of_person, B.attributes.monthly_income_paise, need,
                              P.get("transfer.allowance_margin"))
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


from arthasim import Config, World


def test_world_runs_allowance(tmp_path):
    world = World.build(Config.tier("S", persons=5_000, out_dir=str(tmp_path)), seed=7)
    assert [m.name for m in world.modules] == ["income", "remittances", "budget", "allowance", "consumption", "cash"]
    run = world.run(until="2025-05-31")       # every invariant is checked daily
    rows = run.sql("""
        select pa.household_id as payer_hh, pb.household_id as payee_hh, y.status
        from payments y
        join accounts a on a.account_id = y.payer_account_id join persons pa on pa.entity_id = a.holder_entity_id
        join accounts b on b.account_id = y.payee_account_id join persons pb on pb.entity_id = b.holder_entity_id
        where y.purpose = 'ALLOWANCE'""")
    assert rows.height > 0 and (rows["payer_hh"] == rows["payee_hh"]).all()
    assert (rows["status"] == "SUCCESS").mean() > 0.9


import polars as pl
import pytest
from hypothesis import given, settings, strategies as st


def test_margin_parameter():
    row = P.table().filter(pl.col("id") == "transfer.allowance_margin")
    assert row.height == 1 and P.get("transfer.allowance_margin") == 0.15 and row["status"][0] == "assumption"


def test_household_scale():
    scale = household_scale(np.array([0, 0, 1, 1, 2, 3]), np.array([30_000, 0, 10_000, 0, 0, 10_000]),
                            np.array([10_000.0, 10_000.0, 5_000.0, 10_000.0, 5_000.0, 5_000.0]))
    assert scale.tolist() == [1.0, 0.5, 0.0, 1.0]


def test_nobody_gives_and_receives():
    # Income 105 against need 100: a payer of a little, never a recipient of the margin.
    p, r, a = allowance_pairs(np.array([0, 0, 0]), np.array([1_000, 105, 0]), np.array([100.0, 100.0, 100.0]), 0.15)
    assert list(zip(p.tolist(), r.tolist(), a.tolist())) == [(0, 2, 114), (1, 2, 1)]


def test_allowance_need_is_unpadded():
    Budget().monthly(W, dt.date(2025, 4, 1))
    beh, h = S.behaviour, B.households
    kinds = np.array([d.kind for d in B.districts])
    u = np.where(kinds[B.persons.district] == "metro", P.get("consumption.category_shares.metro")[9],
                 P.get("consumption.category_shares.rural")[9])
    plain = person_need(beh.person_budget, beh.budget, beh.medical_due, h.head, u)
    assert np.allclose(allowance_need(W), plain)


def test_margin_paid_from_leftover():
    # Surplus 60,000 covers shortfalls of 40,000 and 10,000; the 10,000 left pays 10/12 of two 6,000 margins.
    p, r, a = allowance_pairs(np.array([0, 0, 0]), np.array([100_000, 0, 30_000]),
                              np.array([40_000.0, 40_000.0, 40_000.0]), 0.15)
    assert list(zip(p.tolist(), r.tolist(), a.tolist())) == [(0, 1, 45_000), (0, 2, 15_000)]


def test_stretched_household_gets_no_margin():
    args = (np.array([0, 0, 0, 0]), np.array([30_000, 10_000, 0, 0]), np.array([20_000.0, 5_000.0, 20_000.0, 10_000.0]))
    plain, padded = allowance_pairs(*args), allowance_pairs(*args, 0.15)
    assert all((x == y).all() for x, y in zip(plain, padded))
    assert list(zip(*(x.tolist() for x in padded))) == [(0, 2, 6_667), (0, 3, 3_333), (1, 2, 3_333), (1, 3, 1_667)]


def test_margin_scale():
    scale = margin_scale(np.array([0, 0, 0, 1]), np.array([100_000, 0, 30_000, 50_000]),
                         np.array([40_000.0, 40_000.0, 40_000.0, 10_000.0]), 0.15)
    assert np.allclose(scale, [10 / 12, 1.0])


@settings(max_examples=300, deadline=None)
@given(st.lists(st.tuples(st.integers(0, 4), st.integers(0, 200_000), st.integers(1_000, 100_000)),
                min_size=1, max_size=15),
       st.floats(0.0, 0.5))
def test_margin_never_lowers_an_allowance(people, margin):
    hh = np.array([x[0] for x in people])
    income = np.array([x[1] for x in people])
    need = np.array([x[2] for x in people], dtype=np.float64)
    plain = dict(zip(zip(*(x.tolist() for x in allowance_pairs(hh, income, need)[:2])),
                     allowance_pairs(hh, income, need)[2].tolist()))
    p, r, a = allowance_pairs(hh, income, need, margin)
    padded = dict(zip(zip(p.tolist(), r.tolist()), a.tolist()))
    assert all(padded.get(pair, 0) >= amount for pair, amount in plain.items())
    surplus = np.maximum(0.0, income - need)
    for q in np.unique(p):                                        # nobody gives more than their surplus
        assert a[p == q].sum() <= surplus[q] + 0.5 * (p == q).sum()


def test_cash_allowance_withdrawals_use_the_registry_note(tmp_path):
    world = World.build(Config.tier("S", persons=5_000, out_dir=str(tmp_path)).with_params(
        **{"cash.withdrawal_note_paise": 50_000}), seed=7)
    Budget().monthly(world, dt.date(2025, 4, 1))
    mod = Allowance()
    mod.monthly(world, dt.date(2025, 4, 1))
    it = Intents.concat([mod.intents(world, dt.date(2025, 4, d)) for d in range(1, 31)])
    wd = it.kind == Kind.CASH_WITHDRAWAL
    assert wd.any() and (it.amount[wd] % 50_000 == 0).all()


def test_allowance_over_the_upi_limit_goes_by_imps():
    upi, banked = B.banking.person_upi, S.person_deposit >= 0
    payer, rec = np.flatnonzero(upi & banked)[:2]
    mod = Allowance()
    mod._pairs = (np.array([payer]), np.array([rec]), np.array([P.get("rail.upi.limit_paise") + 1]), np.array([5]))
    it = mod.intents(W, dt.date(2025, 4, 5))
    assert it.rail.tolist() == [Rail.IMPS] and it.kind.tolist() == [Kind.PAYMENT]


def test_withdrawal_settles_before_the_allowance_it_funds():
    Budget().monthly(W, dt.date(2025, 4, 1))
    mod = Allowance()
    mod.monthly(W, dt.date(2025, 4, 1))
    owner = _owner()
    checked = ties = 0
    for d in range(1, 31):
        raw = mod.intents(W, dt.date(2025, 4, d))
        # A tie at the same slot and offset is where the order matters; natural ties are rare, so force one:
        # the first withdrawing payer's gifts move to the withdrawal's slot and offset.
        wd = np.flatnonzero(raw.kind == Kind.CASH_WITHDRAWAL)
        if wd.size:
            gifts = (owner[raw.payer_acct] == owner[raw.payer_acct[wd[0]]]) & (raw.kind == Kind.CASH_PAYMENT)
            raw.slot[gifts], raw.offset_s[gifts] = raw.slot[wd[0]], raw.offset_s[wd[0]]
        it = raw.sorted()
        payer = owner[it.payer_acct]
        for i in np.flatnonzero(it.kind == Kind.CASH_WITHDRAWAL):
            gifts = np.flatnonzero((payer == payer[i]) & (it.kind == Kind.CASH_PAYMENT))
            assert gifts.size and (gifts > i).all()
            checked += 1
            ties += int(((it.slot[gifts] == it.slot[i]) & (it.offset_s[gifts] == it.offset_s[i])).any())
    assert checked > 0 and ties > 0


def test_note_below_one_is_rejected_by_the_allowance(tmp_path):
    for note in (0, 0.5):
        world = World.build(Config.tier("S", persons=5_000, out_dir=str(tmp_path / str(note))).with_params(
            **{"cash.withdrawal_note_paise": note}), seed=7)
        Budget().monthly(world, dt.date(2025, 4, 1))
        mod = Allowance()
        mod.monthly(world, dt.date(2025, 4, 1))
        with pytest.raises(ValueError, match="withdrawal_note"):
            for d in range(1, 31):
                mod.intents(world, dt.date(2025, 4, d))
