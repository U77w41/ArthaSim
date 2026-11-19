import datetime as dt
import numpy as np
from arthasim.build import categories as c
from arthasim.engine.intents import Intents, Purpose, Rail
from arthasim.ledger.journal import FlowType, Kind
from arthasim.modules.budget import Budget
from arthasim.modules.spending import Consumption, choose_rail
from helpers import P
from world_fixture import small_world

W = small_world()
S, B = W.state, W.state.population
O, K, H = B.orgs, B.banking, B.households
Budget().monthly(W, dt.date(2025, 4, 1))
BEH = S.behaviour
PBUD, MED = BEH.person_budget.copy(), BEH.medical_due.copy()     # other test files reuse this world
DAYS = [dt.date(2025, 4, d) for d in range(1, 31)]
IT = Intents.concat([Consumption().intents(W, d) for d in DAYS])
BANKED = S.person_deposit >= 0
ACCT_PERSON = np.full(len(S.book), -1, dtype=np.int64)
ACCT_PERSON[S.person_cash] = S.person_ids
ACCT_PERSON[S.person_deposit[BANKED]] = S.person_ids[BANKED]
PAYER = ACCT_PERSON[IT.payer_acct]
M = len(S.merchant_ids)
ACCT_MERCHANT = np.full(len(S.book), -1, dtype=np.int64)
ACCT_MERCHANT[S.merchant_deposit] = np.arange(M)
ACCT_MERCHANT[S.merchant_cash] = np.arange(M)
MERCHANT = ACCT_MERCHANT[IT.payee_acct]
AT_MERCHANT = MERCHANT >= 0
CAT = IT.purpose - Purpose.GROCERY
METRO = np.array([d.kind for d in B.districts])[B.persons.district] == "metro"
LIMIT = P.get("rail.upi.limit_paise")


def test_choose_rail():
    t, f = np.array([True]), np.array([False])
    amt = np.array([5_000])
    assert choose_rail(amt, t, t, t, t, np.array([0.5]), np.array([0.1]), P).tolist() == [Rail.UPI_P2M]
    assert choose_rail(amt, t, t, t, t, np.array([0.9]), np.array([0.1]), P).tolist() == [Rail.DEBIT_CARD]
    assert choose_rail(amt, t, t, t, t, np.array([0.9]), np.array([0.9]), P).tolist() == [Rail.CASH]
    assert choose_rail(amt, t, f, f, t, np.array([0.1]), np.array([0.1]), P).tolist() == [Rail.CASH]
    assert choose_rail(np.array([LIMIT + 1]), t, f, t, f, np.array([0.1]), np.array([0.1]), P).tolist() == [Rail.CASH]


def test_spend_follows_the_budget():
    IT.validate()
    assert (PAYER >= 0).all() and (IT.flow_type == FlowType.CONSUMPTION).all()
    for metro, key in ((True, "metro"), (False, "rural")):
        rows = METRO[PAYER] == metro
        shares = np.asarray(P.get(f"consumption.category_shares.{key}"))
        budget = PBUD[METRO == metro].sum()
        for k in (0, 1, 6):
            assert abs(IT.amount[rows & (CAT == k)].sum() / (budget * shares[k]) - 1.0) < 0.06
        ordinary = rows & (IT.purpose != Purpose.MEDICAL)
        assert abs(IT.amount[ordinary].sum() / budget - 1.0) < 0.06


def test_merchant_is_in_district_category_and_usually_local():
    assert np.array_equal(O.merchant_district[MERCHANT[AT_MERCHANT]], B.persons.district[PAYER[AT_MERCHANT]])
    shop = AT_MERCHANT & (CAT <= 8)
    assert np.array_equal(O.merchant_category[MERCHANT[shop]], CAT[shop])
    medical = IT.purpose == Purpose.MEDICAL
    assert AT_MERCHANT[medical].all() and (O.merchant_category[MERCHANT[medical]] == 3).all()
    locality = H.locality[H.household_of_person]
    grocery = AT_MERCHANT & (CAT == 0)
    local = (O.merchant_locality[MERCHANT[grocery]] == locality[PAYER[grocery]]).mean()
    assert abs(local - (0.7 + 0.3 / 20)) < 0.04


def test_rails_respect_instruments_and_acceptance():
    upi, card, cash = IT.rail == Rail.UPI_P2M, IT.rail == Rail.DEBIT_CARD, IT.rail == Rail.CASH
    assert (upi | card | cash).all()
    assert K.person_upi[PAYER[upi]].all() and K.person_has_card[PAYER[card]].all()
    assert O.merchant_accepts_upi[MERCHANT[upi & AT_MERCHANT]].all()
    assert O.merchant_accepts_card[MERCHANT[card & AT_MERCHANT]].all() and AT_MERCHANT[card].all()
    assert (IT.kind[cash] == Kind.CASH_PAYMENT).all() and (IT.kind[~cash] == Kind.PAYMENT).all()
    assert cash[~BANKED[PAYER]].all()
    assert np.isin(IT.payer_acct[cash], S.person_cash).all() and np.isin(IT.payer_acct[~cash], S.person_deposit).all()
    can = AT_MERCHANT & K.person_upi[PAYER] & O.merchant_accepts_upi[np.maximum(MERCHANT, 0)] & (IT.amount <= LIMIT)
    assert abs(upi[can].mean() - 0.85) < 0.03


def test_bills_medical_and_online():
    util, tel = IT.purpose == Purpose.UTILITIES, IT.purpose == Purpose.TELECOM
    assert util.sum() == len(H.head) and set(PAYER[util].tolist()) == set(H.head.tolist())
    assert tel.sum() == K.person_has_mobile.sum() and K.person_has_mobile[PAYER[tel]].all()
    assert np.isin(IT.payee_acct[util], [S.biller_deposit[1], S.biller_cash[1]]).all()
    assert np.isin(IT.payee_acct[tel], [S.biller_deposit[0], S.biller_cash[0]]).all()
    assert (IT.purpose == Purpose.MEDICAL).sum() == (MED > 0).sum()
    online = IT.payee_acct == S.biller_deposit[2]
    assert online.any() and K.person_upi[PAYER[online]].all() and (IT.rail[online] == Rail.UPI_P2M).all()
    assert np.isin(CAT[online], [4, 5, 8]).all()
    could = K.person_upi[PAYER] & np.isin(CAT, [4, 5, 8])
    assert abs(online[could].mean() - 0.25) < 0.04


def test_habit_subset_and_determinism():
    grocery = AT_MERCHANT & (CAT == 0) & (B.attributes.habit_strength[PAYER] > 0.9)
    pairs, counts = np.unique(np.stack([PAYER[grocery], MERCHANT[grocery]]), axis=1, return_counts=True)
    total = np.bincount(pairs[0], weights=counts)
    top = np.zeros_like(total)
    np.maximum.at(top, pairs[0], counts)
    regular = total >= 8
    assert regular.sum() > 20 and (top[regular] / total[regular]).mean() > 0.8
    day = DAYS[9]
    full, part = Consumption().intents(W, day), Consumption().intents(W, day, persons=np.arange(200))
    mine = ACCT_PERSON[full.payer_acct] < 200
    for field in ("payee_acct", "amount", "rail", "slot", "purpose"):
        assert np.array_equal(np.sort(getattr(full, field)[mine]), np.sort(getattr(part, field)))
    assert np.array_equal(Consumption().intents(W, day).amount, full.amount)
