"""Journal entries and postings. This Python Journal is the reference
implementation; the compiled settlement kernel must agree with it."""
from __future__ import annotations

from enum import IntEnum
from typing import Sequence

import polars as pl

from arthasim.ledger.instruments import InstrumentBook, InstrumentType as T


class Kind(IntEnum):
    PAYMENT = 1
    CASH_PAYMENT = 2
    CASH_WITHDRAWAL = 3
    INTERBANK_SETTLEMENT = 4
    CASH_DEPOSIT = 5
    GOVERNMENT_TRANSFER = 6


class FlowType(IntEnum):
    WAGE = 1
    CONSUMPTION = 2
    TRANSFER = 3
    CASH_CONVERSION = 4
    SETTLEMENT = 5
    EARNINGS = 6
    PENSION = 7
    REMITTANCE = 8
    HOUSEHOLD_TRANSFER = 9
    SOCIAL_BENEFIT = 10


class LedgerError(Exception):
    pass


JOURNAL_COLUMNS = ["journal_id", "ts", "kind", "flow_type", "payment_id"]
POSTING_COLUMNS = ["journal_id", "line_no", "account_id", "delta_paise", "balance_after_paise"]


def check_shape(kind: int, lines: Sequence[tuple[int, int]], book: InstrumentBook) -> None:
    """Raise LedgerError unless `lines` has the shape required for `kind`."""
    accts = [a for a, _ in lines]
    deltas = [d for _, d in lines]
    types = [int(book.type[a]) for a in accts]
    if kind in (Kind.PAYMENT, Kind.CASH_PAYMENT):
        want = T.DEPOSIT if kind == Kind.PAYMENT else T.CASH
        ok = (len(lines) == 2 and types == [want, want] and deltas[0] < 0
              and deltas[0] + deltas[1] == 0)
    elif kind == Kind.CASH_WITHDRAWAL:
        ok = (len(lines) == 3 and types == [T.DEPOSIT, T.CASH, T.CASH]
              and deltas[0] < 0 and deltas[1] == -deltas[0] and deltas[2] == deltas[0]
              and book.holder[accts[1]] == book.holder[accts[0]]
              and book.holder[accts[2]] == book.issuer[accts[0]])
    elif kind == Kind.CASH_DEPOSIT:
        ok = (len(lines) == 3 and types == [T.CASH, T.DEPOSIT, T.CASH]
              and deltas[0] < 0 and deltas[1] == -deltas[0] and deltas[2] == -deltas[0]
              and book.holder[accts[1]] == book.holder[accts[0]]
              and book.holder[accts[2]] == book.issuer[accts[1]])
    elif kind == Kind.GOVERNMENT_TRANSFER:
        # Government balance down; the beneficiary's deposit and its bank's reserves up.
        ok = (len(lines) == 3 and types == [T.GOVERNMENT, T.DEPOSIT, T.RESERVE]
              and deltas[0] < 0 and deltas[1] == -deltas[0] and deltas[2] == -deltas[0]
              and book.holder[accts[2]] == book.issuer[accts[1]])
    elif kind == Kind.INTERBANK_SETTLEMENT:
        ok = len(lines) >= 2 and all(t == T.RESERVE for t in types) and sum(deltas) == 0
    else:
        ok = False
    if not ok:
        raise LedgerError(f"lines do not match the shape for kind {kind}")


class Journal:
    def __init__(self, book: InstrumentBook) -> None:
        self._book = book
        self._next_id = 0
        self._journal: list[tuple[int, int, int, int, int]] = []
        self._postings: list[tuple[int, int, int, int, int]] = []

    def post(self, ts: int, kind: int, flow_type: int, payment_id: int,
             lines: Sequence[tuple[int, int]]) -> int:
        """Validate, then apply. Nothing changes if any check fails."""
        book = self._book
        check_shape(kind, lines, book)
        for acct, delta in lines:
            if delta < 0 and book.type[acct] in (T.DEPOSIT, T.CASH) and book.balance[acct] + delta < 0:
                raise LedgerError(f"insufficient funds in account {acct}")
        jid = self._next_id
        self._next_id += 1
        self._journal.append((jid, int(ts), int(kind), int(flow_type), int(payment_id)))
        for line_no, (acct, delta) in enumerate(lines):
            book.balance[acct] += delta
            self._postings.append((jid, line_no, int(acct), int(delta), int(book.balance[acct])))
        return jid

    def drain(self) -> tuple[pl.DataFrame, pl.DataFrame]:
        journal = pl.DataFrame(self._journal, schema={c: pl.Int64 for c in JOURNAL_COLUMNS}, orient="row")
        postings = pl.DataFrame(self._postings, schema={c: pl.Int64 for c in POSTING_COLUMNS}, orient="row")
        self._journal, self._postings = [], []
        return journal, postings
