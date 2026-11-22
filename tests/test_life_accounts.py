import datetime as dt
import numpy as np
import polars as pl
import pytest
from arthasim import Config, World
from arthasim.engine.intents import Rail
from arthasim.ledger.instruments import InstrumentBook, InstrumentType as T
from arthasim.ledger.invariants import check_day
from arthasim.life.accounts import open_accounts


def test_extend_after_freeze_only():
    b = InstrumentBook()
    b.add(T.CASH, 1, 9, 50)
    with pytest.raises(RuntimeError):
        b.extend(T.DEPOSIT, [1], [2], [0])
    b.freeze()
    ids = b.extend(T.DEPOSIT, [1, 3], [2, 2], [0, 0])
    assert ids.tolist() == [1, 2] and b.type.tolist() == [2, 1, 1] and b.balance.tolist() == [50, 0, 0]


def test_open_accounts_keeps_the_ledger_whole(tmp_path):
    w = World.build(Config.tier("S", persons=3_000, out_dir=str(tmp_path)), seed=7)
    s = w.state
    who = np.flatnonzero(s.person_deposit < 0)[:20]
    n0 = len(s.book)
    ids = open_accounts(s, w.params, who, np.zeros(who.size, dtype=np.int64), dt.date(2025, 5, 1), w.seed)
    assert ids.tolist() == list(range(n0, n0 + who.size)) and (s.book.balance[ids] == 0).all()
    assert (s.person_deposit[who] == ids).all() and (s.deposit_for_cash[s.person_cash[who]] == ids).all()
    assert s.population.banking.person_has_account[who].all() and (s.person_bank[who] == 0).all()
    card = s.population.banking.person_has_card[who]
    assert (s.withdraw_rail[s.person_cash[who]] == np.where(card, Rail.ATM, Rail.AEPS)).all()
    assert all(len(a) == len(s.book) for a in (s.posted_total, s.bank_of_account, s.vault_for_deposit,
                                                s.withdraw_rail, s.account_opened_on))
    empty_j = pl.DataFrame(schema={"journal_id": pl.Int64, "ts": pl.Int64, "kind": pl.Int64, "flow_type": pl.Int64,
                                   "payment_id": pl.Int64})
    empty_p = pl.DataFrame(schema={"journal_id": pl.Int64, "line_no": pl.Int64, "account_id": pl.Int64,
                                   "delta_paise": pl.Int64, "balance_after_paise": pl.Int64})
    check_day(s.book, empty_j, empty_p, s.posted_total, s.bank_ids.tolist(), s.equity, s.currency_issued, s.sector)
    with pytest.raises(ValueError):
        open_accounts(s, w.params, who[:1], np.zeros(1, dtype=np.int64), dt.date(2025, 5, 1), w.seed)
