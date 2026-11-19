import numpy as np
import pytest
from hypothesis import given, settings, strategies as st
from arthasim.ledger.instruments import InstrumentBook, InstrumentType as T
from arthasim.ledger.journal import Journal, Kind, FlowType, LedgerError
from arthasim.ledger.invariants import InvariantError, check_day, flow_matrix

BANK, CB = 9, 99
SECTOR = np.zeros(100, dtype=np.int8); SECTOR[:5] = 1; SECTOR[BANK] = 3; SECTOR[CB] = 4


def world(payments):
    b = InstrumentBook()
    dep = [b.add(T.DEPOSIT, holder=i, issuer=BANK, opening_paise=1000) for i in range(5)]
    b.add(T.CASH, holder=BANK, issuer=CB, opening_paise=2000)
    b.add(T.RESERVE, holder=BANK, issuer=CB, opening_paise=4000)
    b.freeze()
    j = Journal(b)
    for p, q, amt in payments:
        try:
            j.post(0, Kind.PAYMENT, FlowType.CONSUMPTION, 0, [(dep[p], -amt), (dep[q], amt)])
        except LedgerError:
            pass
    jr, po = j.drain()
    total = np.zeros(len(b.balance), dtype=np.int64)
    np.add.at(total, po["account_id"].to_numpy(), po["delta_paise"].to_numpy())
    return b, jr, po, total


def check(b, jr, po, total):
    check_day(b, jr, po, total, bank_entities=[BANK], equity={BANK: 1000},
              currency_issued=2000, sector_of=SECTOR)


pay = st.tuples(st.integers(0, 4), st.integers(0, 4), st.integers(1, 1500)).filter(lambda t: t[0] != t[1])


@settings(max_examples=200, deadline=None)
@given(st.lists(pay, max_size=40))
def test_valid_histories_pass(payments):
    b, jr, po, total = world(payments)
    check(b, jr, po, total)
    fm = flow_matrix(jr, po, b, SECTOR)
    assert fm.columns == ["flow_type", "sector", "net_paise"] and fm["net_paise"].sum() == 0


@pytest.mark.parametrize("acct,delta,name", [(0, 7, "stock_flow"), (5, 7, "stock_flow")])
def test_tampering_is_caught(acct, delta, name):
    b, jr, po, total = world([(0, 1, 100)])
    b.balance[acct] += delta
    with pytest.raises(InvariantError) as e:
        check(b, jr, po, total)
    assert e.value.name == name


def test_each_rule_fires():
    b, jr, po, total = world([(0, 1, 100)])
    with pytest.raises(InvariantError) as e:
        check_day(b, jr, po, total, [BANK], {BANK: 999}, 2000, SECTOR)
    assert e.value.name == "bank_balance_sheet"
    with pytest.raises(InvariantError) as e:
        check_day(b, jr, po, total, [BANK], {BANK: 1000}, 2001, SECTOR)
    assert e.value.name == "cash_conservation"
    b.balance[0] -= 5000; total[0] -= 5000
    with pytest.raises(InvariantError) as e:
        check(b, jr, po, total)
    assert e.value.name == "non_negative"
