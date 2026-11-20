import numpy as np
import pytest
from hypothesis import given, settings, strategies as st
from arthasim.engine.intents import Intents, Rail, Status
from arthasim.engine.settlement import settle_day
from arthasim.ledger.journal import Kind, FlowType

# accounts: 0,1,2 deposits of persons A,B,C; 3 cash of A; 4 vault cash; 5 cash of merchant
TYPE = np.array([1, 1, 1, 2, 2, 2], dtype=np.int64)
DEP_FOR_CASH = np.array([-1, -1, -1, 0, -1, -1], dtype=np.int64)
VAULT_FOR_DEP = np.array([4, 4, 4, -1, -1, -1], dtype=np.int64)


def run(balance, rows, limit=10_000_000, tech=None, rate=0.0, wd=2000, note=1):
    cols = list(zip(*rows))
    it = Intents(*[np.array(c, dtype=np.int64) for c in cols]).sorted()
    it.validate()
    tech_u = np.ones(len(rows)) if tech is None else np.array(tech, dtype=np.float64)
    bal = np.array(balance, dtype=np.int64)
    return bal, settle_day(bal, TYPE, DEP_FOR_CASH, VAULT_FOR_DEP, it, limit, tech_u, rate, wd, 0, 0,
                           withdrawal_note=note)


def pay(payer, payee, amt, slot, rail=Rail.UPI_P2M, off=0):
    return (Kind.PAYMENT, FlowType.CONSUMPTION, payer, payee, amt, rail, slot, off)


def test_slot_order_decides_who_has_funds():
    bal, s = run([100, 0, 0, 0, 0, 0], [pay(1, 2, 50, slot=2), pay(0, 1, 80, slot=1)])
    assert s.payments["status"].tolist() == [Status.SUCCESS, Status.SUCCESS] and bal.tolist()[:3] == [20, 30, 50]
    bal, s = run([100, 0, 0, 0, 0, 0], [pay(1, 2, 50, slot=1), pay(0, 1, 80, slot=2)])
    assert s.payments["status"].tolist() == [Status.DECLINED_FUNDS, Status.SUCCESS]
    assert s.payments["journal_id"].tolist() == [-1, 0]


def test_exact_balance_limit_and_tech_decline():
    bal, s = run([100, 0, 0, 0, 0, 0], [pay(0, 1, 100, 1)])
    assert bal[0] == 0 and s.payments["status"][0] == Status.SUCCESS
    _, s = run([100, 0, 0, 0, 0, 0], [pay(0, 1, 60, 1)], limit=50)
    assert s.payments["status"][0] == Status.DECLINED_LIMIT
    _, s = run([100, 0, 0, 0, 0, 0], [pay(0, 1, 60, 1)], tech=[0.001], rate=0.01)
    assert s.payments["status"][0] == Status.DECLINED_TECH
    bal, s = run([100, 0, 0, 0, 0, 0], [pay(0, 1, 60, 1, rail=Rail.NACH_CR)], limit=50, tech=[0.001], rate=0.01)
    assert s.payments["status"][0] == Status.SUCCESS


def test_cash_purchase_triggers_withdrawal():
    cash = (Kind.CASH_PAYMENT, FlowType.CONSUMPTION, 3, 5, 500, Rail.CASH, 10, 0)
    bal, s = run([5000, 0, 0, 100, 9000, 0], [cash])
    assert s.payments["kind"].tolist() == [Kind.CASH_WITHDRAWAL, Kind.CASH_PAYMENT]
    assert s.payments["rail"].tolist() == [Rail.ATM, Rail.CASH]
    assert bal.tolist() == [3000, 0, 0, 1600, 7000, 500]
    bal, s = run([1000, 0, 0, 100, 9000, 0], [cash])          # less than usual: take what the account holds
    assert s.payments["kind"].tolist() == [Kind.CASH_WITHDRAWAL, Kind.CASH_PAYMENT]
    assert s.payments["amount"].tolist() == [1000, 500] and bal.tolist() == [0, 0, 0, 600, 8000, 500]
    bal, s = run([300, 0, 0, 100, 9000, 0], [cash])           # account cannot cover the shortfall
    assert s.payments["status"].tolist() == [Status.DECLINED_FUNDS] and bal.tolist() == [300, 0, 0, 100, 9000, 0]
    bal, s = run([5000, 0, 0, 100, 1000, 0], [cash])          # vault too low: no withdrawal
    assert s.payments["status"].tolist() == [Status.DECLINED_FUNDS] and bal.tolist() == [5000, 0, 0, 100, 1000, 0]


def test_withdrawal_covers_a_large_purchase():
    big = (Kind.CASH_PAYMENT, FlowType.CONSUMPTION, 3, 5, 3500, Rail.CASH, 10, 0)
    bal, s = run([9000, 0, 0, 100, 9000, 0], [big])
    assert s.payments["amount"].tolist() == [3400, 3500] and bal.tolist() == [5600, 0, 0, 0, 5600, 3500]


def test_withdrawal_rounds_to_notes():
    small = (Kind.CASH_PAYMENT, FlowType.CONSUMPTION, 3, 5, 300, Rail.CASH, 10, 0)
    bal, s = run([1550, 0, 0, 0, 9000, 0], [small], note=100)
    assert s.payments["amount"].tolist() == [1500, 300] and bal.tolist() == [50, 0, 0, 1200, 7500, 300]
    big = (Kind.CASH_PAYMENT, FlowType.CONSUMPTION, 3, 5, 3450, Rail.CASH, 10, 0)
    bal, s = run([9000, 0, 0, 0, 9000, 0], [big], note=100)
    assert s.payments["amount"].tolist() == [3500, 3450] and bal.tolist() == [5500, 0, 0, 50, 5500, 3450]


def test_rejects_bad_intents():
    for row in (pay(0, 1, 0, 1), pay(0, 1, -5, 1), pay(0, 1, 5, 96), pay(0, 1, 5, 1, off=900)):
        with pytest.raises(ValueError):
            run([100, 0, 0, 0, 0, 0], [row])


@settings(max_examples=100, deadline=None)
@given(st.lists(st.tuples(st.integers(0, 2), st.integers(0, 2), st.integers(1, 300), st.integers(0, 95))
                .filter(lambda t: t[0] != t[1]), min_size=1, max_size=60))
def test_money_is_conserved_and_never_negative(rows):
    bal, s = run([500, 500, 500, 0, 0, 0], [pay(p, q, a, sl) for p, q, a, sl in rows])
    assert bal.sum() == 1500 and bal.min() >= 0
    assert s.postings["delta"].sum() == 0
    assert (np.diff(s.payments["slot"]) >= 0).all()
