"""Settlement kernel: settle a day's intents in order against live balances."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numba import njit

from arthasim.engine.intents import Intents, Purpose, Rail

# Enum values, repeated as plain ints for the compiled loop.
_PAYMENT, _CASH_PAYMENT, _CASH_WITHDRAWAL, _CASH_DEPOSIT = 1, 2, 3, 5
_CASH_CONVERSION = 4
_UPI_P2M, _UPI_P2P = int(Rail.UPI_P2M), int(Rail.UPI_P2P)
_SUCCESS, _DECLINED_TECH, _DECLINED_FUNDS, _DECLINED_LIMIT = 1, 2, 3, 4
_PURPOSE_WITHDRAWAL = int(Purpose.CASH_WITHDRAWAL)

PAYMENT_FIELDS = ["payment_id", "slot", "offset_s", "rail", "status", "amount", "payer_acct",
                  "payee_acct", "journal_id", "kind", "flow_type", "purpose"]
JOURNAL_FIELDS = ["journal_id", "payment_id", "kind", "flow_type", "slot", "offset_s"]
POSTING_FIELDS = ["journal_id", "line_no", "account_id", "delta", "balance_after"]


@dataclass
class Settled:
    payments: dict[str, np.ndarray]
    journal: dict[str, np.ndarray]
    postings: dict[str, np.ndarray]
    next_payment_id: int
    next_journal_id: int


@njit(cache=True)
def _post(Q, n_q, balance, jid, line, acct, delta):
    balance[acct] += delta
    Q[n_q, 0] = jid; Q[n_q, 1] = line; Q[n_q, 2] = acct; Q[n_q, 3] = delta; Q[n_q, 4] = balance[acct]
    return n_q + 1


@njit(cache=True)
def _record(P, n_p, pid, slot, off, rail, status, amount, src, dst, jid, kind, flow, purpose):
    P[n_p, 0] = pid; P[n_p, 1] = slot; P[n_p, 2] = off; P[n_p, 3] = rail; P[n_p, 4] = status
    P[n_p, 5] = amount; P[n_p, 6] = src; P[n_p, 7] = dst; P[n_p, 8] = jid; P[n_p, 9] = kind
    P[n_p, 10] = flow; P[n_p, 11] = purpose
    return n_p + 1


@njit(cache=True)
def _journal(J, n_j, jid, pid, kind, flow, slot, off):
    J[n_j, 0] = jid; J[n_j, 1] = pid; J[n_j, 2] = kind; J[n_j, 3] = flow; J[n_j, 4] = slot; J[n_j, 5] = off
    return n_j + 1


@njit(cache=True)
def _settle(balance, deposit_for_cash, vault_for_deposit, withdraw_rail, kind, flow, payer, payee, amount,
            rail, slot, off, purpose, upi_limit, tech_u, tech_rate, wd, note, next_pid, next_jid, P, J, Q):
    n_p = 0
    n_j = 0
    n_q = 0
    for i in range(kind.shape[0]):
        k = kind[i]
        a = amount[i]
        src = payer[i]
        dst = payee[i]
        status = _SUCCESS
        if rail[i] == _UPI_P2M or rail[i] == _UPI_P2P:
            if a > upi_limit:
                status = _DECLINED_LIMIT
            elif tech_u[i] < tech_rate:
                status = _DECLINED_TECH

        # A cash purchase with too little cash first tries a withdrawal (ATM or AePS): the usual amount,
        # or enough for a large purchase, capped at what the account holds in whole notes.
        if status == _SUCCESS and k == _CASH_PAYMENT and balance[src] < a:
            dep = deposit_for_cash[src]
            if dep >= 0:
                vault = vault_for_deposit[dep]
                need = a - balance[src]
                take = max(wd, (need + note - 1) // note * note)
                take = min(take, balance[dep] // note * note)
                if vault >= 0 and take >= need and balance[vault] >= take:
                    pid = next_pid + n_p
                    jid = next_jid + n_j
                    n_p = _record(P, n_p, pid, slot[i], off[i], withdraw_rail[src], _SUCCESS, take, dep, src, jid,
                                  _CASH_WITHDRAWAL, _CASH_CONVERSION, _PURPOSE_WITHDRAWAL)
                    n_j = _journal(J, n_j, jid, pid, _CASH_WITHDRAWAL, _CASH_CONVERSION, slot[i], off[i])
                    n_q = _post(Q, n_q, balance, jid, 0, dep, -take)
                    n_q = _post(Q, n_q, balance, jid, 1, src, take)
                    n_q = _post(Q, n_q, balance, jid, 2, vault, -take)

        vault = -1
        if status == _SUCCESS:
            if balance[src] < a:
                status = _DECLINED_FUNDS
            elif k == _CASH_WITHDRAWAL:
                vault = vault_for_deposit[src]
                if vault < 0 or balance[vault] < a:
                    status = _DECLINED_FUNDS
            elif k == _CASH_DEPOSIT:
                vault = vault_for_deposit[dst]
                if vault < 0:
                    status = _DECLINED_FUNDS

        pid = next_pid + n_p
        jid = next_jid + n_j if status == _SUCCESS else -1
        n_p = _record(P, n_p, pid, slot[i], off[i], rail[i], status, a, src, dst, jid, k, flow[i], purpose[i])
        if status != _SUCCESS:
            continue
        n_j = _journal(J, n_j, jid, pid, k, flow[i], slot[i], off[i])
        n_q = _post(Q, n_q, balance, jid, 0, src, -a)
        n_q = _post(Q, n_q, balance, jid, 1, dst, a)
        if k == _CASH_WITHDRAWAL:
            n_q = _post(Q, n_q, balance, jid, 2, vault, -a)
        elif k == _CASH_DEPOSIT:
            n_q = _post(Q, n_q, balance, jid, 2, vault, a)
    return n_p, n_j, n_q


def settle_day(balance: np.ndarray, acct_type: np.ndarray, deposit_for_cash: np.ndarray,
               vault_for_deposit: np.ndarray, intents: Intents, upi_limit: int, tech_u: np.ndarray,
               tech_rate: float, withdrawal_paise: int, next_payment_id: int, next_journal_id: int,
               withdraw_rail: np.ndarray | None = None, withdrawal_note: int = 1) -> Settled:
    """Settle sorted intents in order. Mutates `balance` in place.

    `withdraw_rail` gives, per cash account, the rail of an automatic withdrawal (ATM when omitted).
    A cash payment larger than the payer's cash first triggers an automatic withdrawal from their deposit:
    `withdrawal_paise`, or the shortfall rounded up to `withdrawal_note` if that is more, capped at the
    deposit balance rounded down to `withdrawal_note`. It goes ahead only if it covers the shortfall and
    the bank's vault holds all of it; otherwise nothing is withdrawn and the payment fails for funds."""
    if withdrawal_note < 1:
        raise ValueError(f"withdrawal_note must be at least 1 paisa, got {withdrawal_note}")
    n = len(intents)
    if withdraw_rail is None:
        withdraw_rail = np.full(balance.shape[0], int(Rail.ATM), dtype=np.int64)
    P = np.empty((2 * n, len(PAYMENT_FIELDS)), dtype=np.int64)
    J = np.empty((2 * n, len(JOURNAL_FIELDS)), dtype=np.int64)
    Q = np.empty((6 * n, len(POSTING_FIELDS)), dtype=np.int64)
    n_p, n_j, n_q = _settle(balance, deposit_for_cash, vault_for_deposit,
                            np.ascontiguousarray(withdraw_rail, dtype=np.int64), intents.kind, intents.flow_type,
                            intents.payer_acct, intents.payee_acct, intents.amount, intents.rail, intents.slot,
                            intents.offset_s, intents.purpose, int(upi_limit),
                            np.ascontiguousarray(tech_u, dtype=np.float64), float(tech_rate),
                            int(withdrawal_paise), int(withdrawal_note), int(next_payment_id), int(next_journal_id),
                            P, J, Q)

    def cols(arr: np.ndarray, count: int, names: list[str]) -> dict[str, np.ndarray]:
        return {name: arr[:count, i].copy() for i, name in enumerate(names)}

    return Settled(cols(P, n_p, PAYMENT_FIELDS), cols(J, n_j, JOURNAL_FIELDS),
                   cols(Q, n_q, POSTING_FIELDS), next_payment_id + n_p, next_journal_id + n_j)
