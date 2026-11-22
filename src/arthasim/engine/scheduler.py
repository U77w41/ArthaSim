"""One simulated day: intents, settlement, end-of-day jobs, invariants."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from zoneinfo import ZoneInfo

import numpy as np
import polars as pl

from arthasim.build.world import WorldState
from arthasim.engine import rng
from arthasim.engine.intents import Intents, Purpose, Rail, Status
from arthasim.engine.settlement import settle_day
from arthasim.ledger.invariants import check_day
from arthasim.ledger.journal import FlowType, Kind
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from arthasim.world import World

_KOLKATA = ZoneInfo("Asia/Kolkata")
def _names(enum) -> np.ndarray:
    out = np.full(max(int(m) for m in enum) + 1, "", dtype=object)
    for m in enum:
        out[int(m)] = m.name
    return out


_RAIL, _STATUS, _PURPOSE = _names(Rail), _names(Status), _names(Purpose)
_END_OF_DAY_S = 86_399


@dataclass
class Counters:
    next_payment_id: int = 0
    next_journal_id: int = 0


def day_start_us(day: dt.date) -> int:
    """Epoch microseconds of midnight Asia/Kolkata on `day`."""
    return int(dt.datetime(day.year, day.month, day.day, tzinfo=_KOLKATA).timestamp()) * 1_000_000


def _bank_codes(state: WorldState, accounts: np.ndarray) -> pl.Series:
    bank = state.bank_of_account[accounts]
    codes = np.where(bank >= 0, state.bank_codes[np.maximum(bank, 0)], None)
    return pl.Series(codes.tolist(), dtype=pl.String)


def _as_intents(value) -> Intents:
    return Intents.from_frame(value) if isinstance(value, pl.DataFrame) else value


def run_day(world: "World", day: dt.date) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """Simulate one day. Returns the day's payments, journal and postings."""
    state, params, seed, counters = world.state, world.params, world.seed, world.counters
    book = state.book
    if day.day == 1 or world.days_simulated == 0:
        for module in world.modules:
            module.monthly(world, day)
    intents = Intents.concat([_as_intents(m.intents(world, day)) for m in world.modules]).sorted()
    intents.validate()

    # Technical declines are keyed on payer and time of day, not on position in the batch.
    key = intents.payer_acct * 100_000 + intents.slot * 900 + intents.offset_s
    tech_u = rng.uniform(seed, rng.stream_id("settle.tech"), key, day.toordinal())
    s = settle_day(book.balance, book.type, state.deposit_for_cash, state.vault_for_deposit, intents,
                   params.get("rail.upi.limit_paise"), tech_u, params.get("rail.upi.tech_decline_rate"),
                   params.get("spike.cash_withdrawal_paise"), counters.next_payment_id,
                   counters.next_journal_id, withdraw_rail=getattr(state, "withdraw_rail", None),
                   withdrawal_note=params.get("cash.withdrawal_note_paise"),
                   reserve_for_deposit=getattr(state, "reserve_for_deposit", None))
    counters.next_payment_id, counters.next_journal_id = s.next_payment_id, s.next_journal_id

    base = day_start_us(day)
    p = s.payments
    ts = base + (p["slot"] * 900 + p["offset_s"]) * 1_000_000
    payments = pl.DataFrame({
        "payment_id": p["payment_id"], "intent_ts": ts, "settle_ts": ts,
        "rail": pl.Series(_RAIL[p["rail"]].tolist(), dtype=pl.String),
        "status": pl.Series(_STATUS[p["status"]].tolist(), dtype=pl.String),
        "amount_paise": p["amount"],
        "payer_account_id": p["payer_acct"], "payee_account_id": p["payee_acct"],
        "payer_bank": _bank_codes(state, p["payer_acct"]),
        "payee_bank": _bank_codes(state, p["payee_acct"]),
        "journal_id": p["journal_id"],
        "purpose": pl.Series(_PURPOSE[p["purpose"]].tolist(), dtype=pl.String),
    }).with_columns(pl.when(pl.col("journal_id") < 0).then(None).otherwise(pl.col("journal_id")).alias("journal_id"))

    j, q = s.journal, s.postings
    journal = pl.DataFrame({
        "journal_id": j["journal_id"], "ts": base + (j["slot"] * 900 + j["offset_s"]) * 1_000_000,
        "kind": j["kind"], "flow_type": j["flow_type"], "payment_id": j["payment_id"]})
    postings = pl.DataFrame({
        "journal_id": q["journal_id"], "line_no": q["line_no"], "account_id": q["account_id"],
        "delta_paise": q["delta"], "balance_after_paise": q["balance_after"]})

    # End of day: net each bank's deposit change from payments and settle it in reserves.
    if len(j["journal_id"]):
        kind_of_posting = j["kind"][q["journal_id"] - j["journal_id"][0]]
        moved = kind_of_posting == Kind.PAYMENT
        net = np.zeros(len(state.bank_ids), dtype=np.int64)
        np.add.at(net, state.bank_of_account[q["account_id"][moved]], q["delta"][moved])
        banks = np.flatnonzero(net)
        if banks.size:
            jid = counters.next_journal_id
            counters.next_journal_id += 1
            accounts = state.bank_reserve[banks]
            book.balance[accounts] += net[banks]
            journal = pl.concat([journal, pl.DataFrame(
                {"journal_id": [jid], "ts": [base + _END_OF_DAY_S * 1_000_000],
                 "kind": [int(Kind.INTERBANK_SETTLEMENT)], "flow_type": [int(FlowType.SETTLEMENT)],
                 "payment_id": [None]}, schema=journal.schema)])
            postings = pl.concat([postings, pl.DataFrame(
                {"journal_id": np.full(banks.size, jid), "line_no": np.arange(banks.size),
                 "account_id": accounts, "delta_paise": net[banks],
                 "balance_after_paise": book.balance[accounts]}, schema=postings.schema)])

    np.add.at(state.posted_total, postings["account_id"].to_numpy(), postings["delta_paise"].to_numpy())
    check_day(book, journal, postings, state.posted_total, state.bank_ids.tolist(), state.equity,
              state.currency_issued, state.sector)
    return payments, journal, postings
