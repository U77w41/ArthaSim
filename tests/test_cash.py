import datetime as dt
import numpy as np
from arthasim import Config, World
from arthasim.engine.intents import Purpose, Rail
from arthasim.ledger.journal import FlowType, Kind
from arthasim.modules.cash import CashManagement

DAY = dt.date(2025, 4, 3)


def world(tmp_path):
    return World.build(Config.tier("S", persons=2_000, out_dir=str(tmp_path)), seed=7)


def test_merchants_and_billers_deposit_the_excess(tmp_path):
    w = world(tmp_path)
    s = w.state
    s.book.balance[s.merchant_cash[:3]] = [1_200_000, 500_000, 400_000]
    s.book.balance[s.biller_cash[0]] = 900_000
    it = CashManagement().intents(w, DAY)
    it.validate()
    assert it.payer_acct.tolist() == [s.merchant_cash[0], s.biller_cash[0]]
    assert it.payee_acct.tolist() == [s.merchant_deposit[0], s.biller_deposit[0]]
    assert it.amount.tolist() == [700_000, 400_000]
    assert (it.kind == Kind.CASH_DEPOSIT).all() and (it.flow_type == FlowType.CASH_CONVERSION).all()
    assert (it.rail == Rail.BRANCH).all() and (it.purpose == Purpose.CASH_DEPOSIT).all() and (it.slot == 40).all()


def test_persons_deposit_large_cash_holdings(tmp_path):
    w = world(tmp_path)
    s = w.state
    banked = np.flatnonzero(s.person_deposit >= 0)[:400]
    unbanked = np.flatnonzero(s.person_deposit == -1)[:50]
    s.book.balance[s.person_cash[banked]] = 3_000_000
    s.book.balance[s.person_cash[unbanked]] = 3_000_000
    it = CashManagement().intents(w, DAY)
    assert np.isin(it.payer_acct, s.person_cash[banked]).all() and (it.amount == 2_500_000).all()
    assert abs(len(it) / 400 - 0.2) < 0.08
    person = np.full(len(s.book), -1, dtype=np.int64)
    person[s.person_cash] = s.person_ids
    assert np.array_equal(it.payee_acct, s.person_deposit[person[it.payer_acct]])
    assert len(CashManagement().intents(w, DAY)) == len(it)
    s.book.balance[s.person_cash[banked]] = 2_000_000
    assert len(CashManagement().intents(w, DAY)) == 0
