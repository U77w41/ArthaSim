import numpy as np
import pytest
from arthasim.engine.intents import Intents, Purpose, Rail, Status
from arthasim.engine.settlement import settle_day
from arthasim.ledger.instruments import InstrumentBook, InstrumentType as T
from arthasim.ledger.journal import FlowType, Journal, Kind, LedgerError

# accounts: 0 deposit A, 1 deposit B, 2 cash A, 3 vault, 4 cash merchant, 5 deposit merchant
TYPE = np.array([1, 1, 2, 2, 2, 1], dtype=np.int64)
DEP_FOR_CASH = np.array([-1, -1, 0, -1, 5, -1], dtype=np.int64)
VAULT_FOR_DEP = np.array([3, 3, -1, -1, -1, 3], dtype=np.int64)


def row(kind, flow, payer, payee, amount, rail, purpose, slot=10):
    return (kind, flow, payer, payee, amount, rail, slot, 0, purpose)


def run(balance, rows, withdraw_rail=None, limit=10_000_000, tech=None, rate=0.0):
    it = Intents(*[np.array(col, dtype=np.int64) for col in zip(*rows)]).sorted()
    it.validate()
    bal = np.array(balance, dtype=np.int64)
    tech_u = np.ones(len(rows)) if tech is None else np.array(tech, dtype=np.float64)
    return bal, settle_day(bal, TYPE, DEP_FOR_CASH, VAULT_FOR_DEP, it, limit, tech_u, rate, 2000, 0, 0,
                           withdraw_rail=withdraw_rail)


def test_enums():
    assert (Kind.CASH_DEPOSIT, FlowType.EARNINGS, FlowType.PENSION, FlowType.REMITTANCE) == (5, 6, 7, 8)
    assert (Rail.UPI_P2P, Rail.DEBIT_CARD, Rail.IMPS, Rail.AEPS, Rail.BRANCH) == (6, 7, 8, 9, 10)
    assert (Purpose.UNSPECIFIED, Purpose.GROCERY, Purpose.OTHER, Purpose.CASH_DEPOSIT) == (0, 10, 18, 31)
    assert Intents(*[np.array([1])] * 8).purpose.tolist() == [0]


def test_reference_journal_cash_deposit():
    b = InstrumentBook()
    dep = b.add(T.DEPOSIT, holder=1, issuer=9, opening_paise=0)
    cash = b.add(T.CASH, holder=1, issuer=99, opening_paise=800)
    vault = b.add(T.CASH, holder=9, issuer=99, opening_paise=100)
    other = b.add(T.CASH, holder=2, issuer=99, opening_paise=500)
    b.freeze()
    j = Journal(b)
    j.post(0, Kind.CASH_DEPOSIT, FlowType.CASH_CONVERSION, 1, [(cash, -300), (dep, 300), (vault, 300)])
    assert (b.balance[cash], b.balance[dep], b.balance[vault]) == (500, 300, 400)
    for lines in ([(cash, -300), (dep, 300), (vault, 200)], [(other, -300), (dep, 300), (vault, 300)],
                  [(cash, -900), (dep, 900), (vault, 900)], [(dep, -100), (cash, 100), (vault, 100)]):
        with pytest.raises(LedgerError):
            j.post(0, Kind.CASH_DEPOSIT, FlowType.CASH_CONVERSION, 2, lines)


def test_kernel_cash_deposit_and_purpose():
    deposit = row(Kind.CASH_DEPOSIT, FlowType.CASH_CONVERSION, 4, 5, 600, Rail.BRANCH, Purpose.CASH_DEPOSIT)
    bal, s = run([0, 0, 0, 1000, 700, 0], [deposit])
    assert bal.tolist() == [0, 0, 0, 1600, 100, 600] and s.payments["status"].tolist() == [Status.SUCCESS]
    assert s.payments["purpose"].tolist() == [Purpose.CASH_DEPOSIT]
    assert s.postings["delta"].tolist() == [-600, 600, 600]
    bal, s = run([0, 0, 0, 1000, 500, 0], [deposit])
    assert s.payments["status"].tolist() == [Status.DECLINED_FUNDS] and bal.tolist() == [0, 0, 0, 1000, 500, 0]


def test_upi_p2p_rules_card_and_withdrawal_rail():
    p2p = row(Kind.PAYMENT, FlowType.REMITTANCE, 0, 1, 60, Rail.UPI_P2P, Purpose.REMITTANCE)
    assert run([100, 0, 0, 0, 0, 0], [p2p], limit=50)[1].payments["status"][0] == Status.DECLINED_LIMIT
    assert run([100, 0, 0, 0, 0, 0], [p2p], tech=[0.001], rate=0.01)[1].payments["status"][0] == Status.DECLINED_TECH
    card = row(Kind.PAYMENT, FlowType.CONSUMPTION, 0, 5, 60, Rail.DEBIT_CARD, Purpose.GROCERY)
    assert run([100, 0, 0, 0, 0, 0], [card], limit=50, tech=[0.001], rate=0.01)[1].payments["status"][0] == Status.SUCCESS
    cash = row(Kind.CASH_PAYMENT, FlowType.CONSUMPTION, 2, 4, 500, Rail.CASH, Purpose.FOOD)
    rails = np.full(6, int(Rail.ATM), dtype=np.int64)
    rails[2] = Rail.AEPS
    s = run([5000, 0, 100, 9000, 0, 0], [cash], withdraw_rail=rails)[1]
    assert s.payments["rail"].tolist() == [Rail.AEPS, Rail.CASH]
    assert s.payments["purpose"].tolist() == [Purpose.CASH_WITHDRAWAL, Purpose.FOOD]
    assert run([5000, 0, 100, 9000, 0, 0], [cash])[1].payments["rail"].tolist() == [Rail.ATM, Rail.CASH]
