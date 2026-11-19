"""Ledger invariants. They run every simulated day; a failure stops the run."""
from __future__ import annotations

from typing import Mapping, Sequence

import numpy as np
import polars as pl

from arthasim.ledger.instruments import InstrumentBook, InstrumentType as T
from arthasim.ledger.journal import Kind

_FLOW_SCHEMA = {"flow_type": pl.Int64, "sector": pl.Int64, "net_paise": pl.Int64}


class InvariantError(Exception):
    def __init__(self, name: str, detail: str = "") -> None:
        self.name = name
        self.detail = detail
        super().__init__(f"{name}: {detail}")


def _arrays(journal: pl.DataFrame, postings: pl.DataFrame):
    jid = journal["journal_id"].to_numpy()
    pj = postings["journal_id"].to_numpy()
    idx = np.searchsorted(jid, pj)
    if len(pj) and (idx.max() >= len(jid) or not np.array_equal(jid[idx], pj)):
        raise InvariantError("shapes", "posting refers to an unknown journal entry")
    return jid, idx, postings["account_id"].to_numpy(), postings["delta_paise"].to_numpy()


def _check_shapes(journal: pl.DataFrame, postings: pl.DataFrame, book: InstrumentBook) -> None:
    if journal.height == 0:
        if postings.height:
            raise InvariantError("shapes", "postings without journal entries")
        return
    jid, idx, acct, delta = _arrays(journal, postings)
    kind = journal["kind"].to_numpy()
    n = np.bincount(idx, minlength=len(jid))
    start = np.cumsum(n) - n
    if not np.array_equal(postings["line_no"].to_numpy(), np.arange(len(idx)) - start[idx]):
        raise InvariantError("shapes", "postings are not ordered by journal entry and line")
    total = np.zeros(len(jid), dtype=np.int64)
    np.add.at(total, idx, delta)
    typ = book.type[acct]
    last = max(len(acct) - 1, 0)

    def line(k: int, arr: np.ndarray) -> np.ndarray:
        return arr[np.minimum(start + k, last)]

    t0, t1, t2 = line(0, typ), line(1, typ), line(2, typ)
    d0, d1, d2 = line(0, delta), line(1, delta), line(2, delta)
    a0, a1, a2 = line(0, acct), line(1, acct), line(2, acct)
    ok = np.zeros(len(jid), dtype=bool)
    for k, want in ((Kind.PAYMENT, T.DEPOSIT), (Kind.CASH_PAYMENT, T.CASH)):
        ok |= (kind == k) & (n == 2) & (t0 == want) & (t1 == want) & (d0 < 0) & (total == 0)
    ok |= ((kind == Kind.CASH_WITHDRAWAL) & (n == 3) & (t0 == T.DEPOSIT) & (t1 == T.CASH) & (t2 == T.CASH)
           & (d0 < 0) & (d1 == -d0) & (d2 == d0)
           & (book.holder[a1] == book.holder[a0]) & (book.holder[a2] == book.issuer[a0]))
    ok |= ((kind == Kind.CASH_DEPOSIT) & (n == 3) & (t0 == T.CASH) & (t1 == T.DEPOSIT) & (t2 == T.CASH)
           & (d0 < 0) & (d1 == -d0) & (d2 == -d0)
           & (book.holder[a1] == book.holder[a0]) & (book.holder[a2] == book.issuer[a1]))
    non_reserve = np.bincount(idx, weights=(typ != T.RESERVE), minlength=len(jid))
    ok |= (kind == Kind.INTERBANK_SETTLEMENT) & (n >= 2) & (non_reserve == 0) & (total == 0)
    if not ok.all():
        bad = int(jid[np.argmin(ok)])
        raise InvariantError("shapes", f"journal entry {bad} does not match the shape for its kind")


def flow_matrix(journal: pl.DataFrame, postings: pl.DataFrame, book: InstrumentBook,
                sector_of: np.ndarray) -> pl.DataFrame:
    """Net income and expenditure flows by flow type and holder sector.

    Covers PAYMENT and CASH_PAYMENT entries. Asset swaps (cash withdrawal,
    interbank settlement) change stocks, not income, and are left out."""
    if journal.height == 0 or postings.height == 0:
        return pl.DataFrame(schema=_FLOW_SCHEMA)
    _, idx, acct, delta = _arrays(journal, postings)
    kind = journal["kind"].to_numpy()[idx]
    flow = journal["flow_type"].to_numpy()[idx]
    m = (kind == Kind.PAYMENT) | (kind == Kind.CASH_PAYMENT)
    frame = pl.DataFrame({"flow_type": flow[m].astype(np.int64),
                          "sector": np.asarray(sector_of)[book.holder[acct[m]]].astype(np.int64),
                          "net_paise": delta[m].astype(np.int64)}, schema=_FLOW_SCHEMA)
    return (frame.group_by(["flow_type", "sector"]).agg(pl.col("net_paise").sum())
            .sort(["flow_type", "sector"]))


def sector_balance(postings: pl.DataFrame, book: InstrumentBook, sector_of: np.ndarray) -> np.ndarray:
    """Change in each sector's net financial position: +delta to the holder's sector,
    -delta to the issuer's sector. Indexed by sector code."""
    sector_of = np.asarray(sector_of)
    out = np.zeros(int(sector_of.max()) + 1, dtype=np.int64)
    if postings.height == 0:
        return out
    acct = postings["account_id"].to_numpy()
    delta = postings["delta_paise"].to_numpy()
    np.add.at(out, sector_of[book.holder[acct]].astype(np.int64), delta)
    np.subtract.at(out, sector_of[book.issuer[acct]].astype(np.int64), delta)
    return out


def check_flow_columns(journal: pl.DataFrame, postings: pl.DataFrame, book: InstrumentBook,
                       sector_of: np.ndarray) -> None:
    """Each sector's net income from flows must equal the change in its net financial position."""
    net = sector_balance(postings, book, sector_of)
    fm = flow_matrix(journal, postings, book, sector_of)
    flows = np.zeros_like(net)
    if fm.height:
        np.add.at(flows, fm["sector"].to_numpy(), fm["net_paise"].to_numpy())
    if not np.array_equal(flows, net):
        bad = int(np.argmax(flows != net))
        raise InvariantError("flow_columns", f"sector {bad}: flows {flows[bad]} != change in net position {net[bad]}")


def check_day(book: InstrumentBook, journal: pl.DataFrame, postings: pl.DataFrame,
              posted_total: np.ndarray, bank_entities: Sequence[int], equity: Mapping[int, int],
              currency_issued: int, sector_of: np.ndarray) -> None:
    _check_shapes(journal, postings, book)

    if not np.array_equal(book.opening + posted_total, book.balance):
        bad = int(np.argmax(book.opening + posted_total != book.balance))
        raise InvariantError("stock_flow", f"account {bad}: opening plus postings differs from balance")

    money = (book.type == T.DEPOSIT) | (book.type == T.CASH)
    if (book.balance[money] < 0).any():
        raise InvariantError("non_negative", "a deposit or cash balance is below zero")

    for bank in bank_entities:
        held = book.holder == bank
        assets = int(book.balance[held & ((book.type == T.RESERVE) | (book.type == T.CASH))].sum())
        deposits = int(book.balance[(book.issuer == bank) & (book.type == T.DEPOSIT)].sum())
        if assets != deposits + int(equity[bank]):
            raise InvariantError("bank_balance_sheet",
                                 f"bank {bank}: assets {assets} != deposits {deposits} + equity {equity[bank]}")

    cash = int(book.balance[book.type == T.CASH].sum())
    if cash != int(currency_issued):
        raise InvariantError("cash_conservation", f"cash held {cash} != currency issued {currency_issued}")

    rows = flow_matrix(journal, postings, book, sector_of).group_by("flow_type").agg(pl.col("net_paise").sum())
    if rows.height and (rows["net_paise"] != 0).any():
        raise InvariantError("flow_rows", "a flow type does not sum to zero across sectors")

    check_flow_columns(journal, postings, book, sector_of)
