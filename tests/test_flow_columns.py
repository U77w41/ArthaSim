import numpy as np
import polars as pl
import pytest
from arthasim.ledger.instruments import InstrumentBook, InstrumentType as T
from arthasim.ledger.invariants import InvariantError, check_day, check_flow_columns, sector_balance
from arthasim.ledger.journal import FlowType, Journal, Kind

HOUSEHOLD, FIRM, BANK, CENTRAL = 1, 2, 3, 4
A, SHOP, BANK1, BANK2, CB = 0, 1, 7, 8, 9
SECTOR = np.zeros(10, dtype=np.int8)
SECTOR[[A, SHOP, BANK1, BANK2, CB]] = [HOUSEHOLD, FIRM, BANK, BANK, CENTRAL]


def world():
    b = InstrumentBook()
    acct = {"dep_a": b.add(T.DEPOSIT, A, BANK1, 5000), "cash_a": b.add(T.CASH, A, CB, 400),
            "dep_shop": b.add(T.DEPOSIT, SHOP, BANK2, 0), "cash_shop": b.add(T.CASH, SHOP, CB, 0),
            "vault1": b.add(T.CASH, BANK1, CB, 3000), "vault2": b.add(T.CASH, BANK2, CB, 3000),
            "res1": b.add(T.RESERVE, BANK1, CB, 3000), "res2": b.add(T.RESERVE, BANK2, CB, 1000)}
    b.freeze()
    return b, Journal(b), acct


def test_a_mixed_day_passes_and_balances_by_sector():
    b, j, a = world()
    j.post(0, Kind.PAYMENT, FlowType.CONSUMPTION, 1, [(a["dep_a"], -700), (a["dep_shop"], 700)])
    j.post(0, Kind.CASH_PAYMENT, FlowType.CONSUMPTION, 2, [(a["cash_a"], -300), (a["cash_shop"], 300)])
    j.post(0, Kind.CASH_WITHDRAWAL, FlowType.CASH_CONVERSION, 3, [(a["dep_a"], -1000), (a["cash_a"], 1000), (a["vault1"], -1000)])
    j.post(0, Kind.CASH_DEPOSIT, FlowType.CASH_CONVERSION, 4, [(a["cash_shop"], -200), (a["dep_shop"], 200), (a["vault2"], 200)])
    j.post(0, Kind.INTERBANK_SETTLEMENT, FlowType.SETTLEMENT, -1, [(a["res1"], -700), (a["res2"], 700)])
    jr, po = j.drain()
    total = np.zeros(len(b.balance), dtype=np.int64)
    np.add.at(total, po["account_id"].to_numpy(), po["delta_paise"].to_numpy())
    check_day(b, jr, po, total, bank_entities=[BANK1, BANK2], equity={BANK1: 1000, BANK2: 4000},
              currency_issued=6400, sector_of=SECTOR)
    net = sector_balance(po, b, SECTOR)
    assert (net[HOUSEHOLD], net[FIRM], net[BANK], net[CENTRAL]) == (-1000, 1000, 0, 0)


def test_columns_catch_wealth_with_no_flow_behind_it():
    b, _, a = world()
    journal = pl.DataFrame({"journal_id": [0], "ts": [0], "kind": [int(Kind.CASH_WITHDRAWAL)],
                            "flow_type": [int(FlowType.CASH_CONVERSION)], "payment_id": [0]})
    postings = pl.DataFrame({"journal_id": [0], "line_no": [0], "account_id": [a["cash_a"]],
                             "delta_paise": [500], "balance_after_paise": [900]})
    with pytest.raises(InvariantError) as e:
        check_flow_columns(journal, postings, b, SECTOR)
    assert e.value.name == "flow_columns"
    empty = journal.clear(), postings.clear()
    check_flow_columns(*empty, b, SECTOR)
