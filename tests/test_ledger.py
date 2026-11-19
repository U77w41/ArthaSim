import pytest
from arthasim.ledger.instruments import InstrumentBook, InstrumentType as T
from arthasim.ledger.journal import Journal, Kind, FlowType, LedgerError


def make():
    b = InstrumentBook()                      # entities: 1, 2 persons; 9 bank; 99 central bank
    a = b.add(T.DEPOSIT, holder=1, issuer=9, opening_paise=1000)
    c = b.add(T.DEPOSIT, holder=2, issuer=9, opening_paise=0)
    ca = b.add(T.CASH, holder=1, issuer=99, opening_paise=0)
    v = b.add(T.CASH, holder=9, issuer=99, opening_paise=5000)
    b.freeze()
    return b, Journal(b), a, c, ca, v


def test_payment_posts_and_records():
    b, j, a, c, _, _ = make()
    jid = j.post(0, Kind.PAYMENT, FlowType.CONSUMPTION, 11, [(a, -400), (c, 400)])
    assert (b.balance[a], b.balance[c]) == (600, 400)
    jr, po = j.drain()
    assert jr.columns == ["journal_id", "ts", "kind", "flow_type", "payment_id"]
    assert po.columns == ["journal_id", "line_no", "account_id", "delta_paise", "balance_after_paise"]
    assert po["balance_after_paise"].to_list() == [600, 400] and jr["journal_id"].to_list() == [jid]
    assert j.drain()[0].height == 0


def test_exact_balance_ok_overdraw_rejected_atomically():
    b, j, a, c, _, _ = make()
    j.post(0, Kind.PAYMENT, FlowType.CONSUMPTION, 1, [(a, -1000), (c, 1000)])
    assert b.balance[a] == 0
    with pytest.raises(LedgerError):
        j.post(0, Kind.PAYMENT, FlowType.CONSUMPTION, 2, [(a, -1), (c, 1)])
    assert (b.balance[a], b.balance[c]) == (0, 1000)


def test_shapes():
    b, j, a, c, ca, v = make()
    j.post(0, Kind.CASH_WITHDRAWAL, FlowType.CASH_CONVERSION, 3, [(a, -300), (ca, 300), (v, -300)])
    assert (b.balance[a], b.balance[ca], b.balance[v]) == (700, 300, 4700)
    for kind, lines in [(Kind.PAYMENT, [(a, -5), (c, 4)]), (Kind.PAYMENT, [(a, 5), (c, -5)]),
                        (Kind.PAYMENT, [(a, -5), (ca, 5)]), (Kind.CASH_PAYMENT, [(a, -5), (c, 5)]),
                        (Kind.CASH_WITHDRAWAL, [(c, -5), (ca, 5), (v, -5)])]:
        with pytest.raises(LedgerError):
            j.post(0, kind, FlowType.TRANSFER, 4, lines)
