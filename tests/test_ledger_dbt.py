import numpy as np
import polars as pl
import pytest
from arthasim.build.world import EntityKind, Sector
from arthasim.engine.intents import Purpose, Rail
from arthasim.ledger.instruments import InstrumentBook, InstrumentType as T
from arthasim.ledger.invariants import InvariantError, check_day, flow_matrix, sector_balance
from arthasim.ledger.journal import FlowType, Journal, Kind, LedgerError

HOUSEHOLD, BANK, CENTRAL, GOVERNMENT = 1, 3, 4, 6
A, BANK1, BANK2, CB, GOV = 0, 7, 8, 9, 10
SECTOR = np.zeros(11, dtype=np.int8)
SECTOR[[A, BANK1, BANK2, CB, GOV]] = [HOUSEHOLD, BANK, BANK, CENTRAL, GOVERNMENT]


def world():
    b = InstrumentBook()
    acct = {"gov": b.add(T.GOVERNMENT, GOV, CB, 0), "dep": b.add(T.DEPOSIT, A, BANK1, 0),
            "cash": b.add(T.CASH, A, CB, 100),
            "vault1": b.add(T.CASH, BANK1, CB, 1000), "vault2": b.add(T.CASH, BANK2, CB, 1000),
            "res1": b.add(T.RESERVE, BANK1, CB, 500), "res2": b.add(T.RESERVE, BANK2, CB, 500)}
    b.freeze()
    return b, Journal(b), acct


def transfer(a, amount=1500, reserve="res1"):
    return [(a["gov"], -amount), (a["dep"], amount), (a[reserve], amount)]


def test_enums():
    assert (Kind.GOVERNMENT_TRANSFER, FlowType.SOCIAL_BENEFIT, T.GOVERNMENT, Rail.APBS) == (6, 10, 4, 11)
    assert (Purpose.DBT_PM_KISAN, Purpose.DBT_OLD_AGE_PENSION, Purpose.DBT_WOMEN) == (7, 8, 9)
    assert (EntityKind.GOVERNMENT, Sector.GOVERNMENT) == (9, 6)


def test_reference_journal_posts_and_lets_the_government_go_negative():
    b, j, a = world()
    j.post(0, Kind.GOVERNMENT_TRANSFER, FlowType.SOCIAL_BENEFIT, 1, transfer(a))
    assert (b.balance[a["gov"]], b.balance[a["dep"]], b.balance[a["res1"]]) == (-1500, 1500, 2000)


@pytest.mark.parametrize("bad", ["two_lines", "wrong_reserve_bank", "unequal", "positive_first", "cash_line"])
def test_reference_journal_rejects_malformed(bad):
    b, j, a = world()
    lines = {
        "two_lines": [(a["gov"], -1500), (a["dep"], 1500)],
        "wrong_reserve_bank": transfer(a, reserve="res2"),
        "unequal": [(a["gov"], -1500), (a["dep"], 1500), (a["res1"], 1400)],
        "positive_first": [(a["gov"], 1500), (a["dep"], -1500), (a["res1"], -1500)],
        "cash_line": [(a["gov"], -100), (a["cash"], 100), (a["res1"], 100)],
    }[bad]
    with pytest.raises(LedgerError):
        j.post(0, Kind.GOVERNMENT_TRANSFER, FlowType.SOCIAL_BENEFIT, 1, lines)
    assert b.balance[a["gov"]] == 0


def _check(b, jr, po):
    total = np.zeros(len(b.balance), dtype=np.int64)
    np.add.at(total, po["account_id"].to_numpy(), po["delta_paise"].to_numpy())
    check_day(b, jr, po, total, bank_entities=[BANK1, BANK2], equity={BANK1: 1500, BANK2: 1500},
              currency_issued=2100, sector_of=SECTOR)


def test_day_with_a_transfer_passes_every_invariant_and_balances_by_sector():
    b, j, a = world()
    j.post(0, Kind.GOVERNMENT_TRANSFER, FlowType.SOCIAL_BENEFIT, 1, transfer(a))
    jr, po = j.drain()
    _check(b, jr, po)
    net = sector_balance(po, b, SECTOR)
    assert (net[GOVERNMENT], net[HOUSEHOLD], net[BANK], net[CENTRAL]) == (-1500, 1500, 0, 0)
    fm = flow_matrix(jr, po, b, SECTOR)
    assert fm.rows() == [(FlowType.SOCIAL_BENEFIT, HOUSEHOLD, 1500), (FlowType.SOCIAL_BENEFIT, GOVERNMENT, -1500)]


def test_vectorised_shapes_catch_a_reserve_at_the_wrong_bank():
    b, _, a = world()
    journal = pl.DataFrame({"journal_id": [0], "ts": [0], "kind": [int(Kind.GOVERNMENT_TRANSFER)],
                            "flow_type": [int(FlowType.SOCIAL_BENEFIT)], "payment_id": [0]})
    lines = transfer(a, reserve="res2")
    postings = pl.DataFrame({"journal_id": [0, 0, 0], "line_no": [0, 1, 2], "account_id": [x for x, _ in lines],
                             "delta_paise": [d for _, d in lines], "balance_after_paise": [0, 0, 0]})
    for acct, delta in lines:
        b.balance[acct] += delta
    with pytest.raises(InvariantError) as e:
        _check(b, journal, postings)
    assert e.value.name == "shapes"
