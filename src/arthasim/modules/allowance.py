"""Household allowances: earners pass money to members whose own income falls short of their need."""
from __future__ import annotations

import numpy as np

_EMPTY = np.empty(0, dtype=np.int64)


def person_need(person_budget: np.ndarray, budget: np.ndarray, medical_due: np.ndarray, head: np.ndarray,
                utilities_share: np.ndarray) -> np.ndarray:
    """Each adult's monthly outgoings: their spending share less utilities, plus, for the head,
    the household's utilities bill and medical costs. Per-household arrays are indexed by household."""
    u = np.asarray(utilities_share, dtype=np.float64)
    need = np.asarray(person_budget, dtype=np.float64) * (1.0 - u)
    head = np.asarray(head, dtype=np.int64)
    need[head] += np.asarray(budget, dtype=np.float64) * u[head] + np.asarray(medical_due, dtype=np.float64)
    return need


def allowance_pairs(household_of_person: np.ndarray, income: np.ndarray,
                    need: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(payer, recipient, amount) inside each household. Members with surplus cover members with
    shortfall, pro rata to surplus; if shortfall exceeds surplus, every shortfall is scaled down alike."""
    hh = np.asarray(household_of_person, dtype=np.int64)
    income, need = np.asarray(income, dtype=np.float64), np.asarray(need, dtype=np.float64)
    shortfall, surplus = np.maximum(0.0, need - income), np.maximum(0.0, income - need)
    n_h = int(hh.max()) + 1 if hh.size else 0
    total_surplus = np.bincount(hh, weights=surplus, minlength=n_h)
    total_short = np.bincount(hh, weights=shortfall, minlength=n_h)
    scale = np.minimum(1.0, np.divide(total_surplus, total_short, out=np.zeros(n_h), where=total_short > 0))

    # Pair members by position within their household (households are small).
    order = np.argsort(hh, kind="stable")
    count = np.bincount(hh, minlength=n_h)
    start = np.cumsum(count) - count
    payers, recipients = [_EMPTY], [_EMPTY]
    for a in range(int(count.max()) if n_h else 0):
        for b in range(int(count.max())):
            if a == b:
                continue
            rows = start[count > max(a, b)]
            p, r = order[rows + a], order[rows + b]
            keep = (surplus[p] > 0) & (shortfall[r] > 0)
            payers.append(p[keep])
            recipients.append(r[keep])
    p, r = np.concatenate(payers), np.concatenate(recipients)
    h = hh[p]
    amount = np.rint(shortfall[r] * scale[h] * surplus[p] / total_surplus[h]).astype(np.int64)
    keep = amount > 0
    p, r, amount = p[keep], r[keep], amount[keep]
    order = np.lexsort((r, p))
    return p[order], r[order], amount[order]
