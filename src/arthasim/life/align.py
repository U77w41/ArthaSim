"""Exact alignment of life-stage counts to cell targets.

In each cell the expected flow matrix (current stage by next stage) is raked so its column totals equal the
targets, rounded to whole people with both totals exact, and the movers for each flow are chosen by weighted
sampling without replacement (keys log(u) / p)."""
from __future__ import annotations

import numpy as np

N_STAGES = 9
RAKE_TOL = 1e-9          # stop once every margin is this close
RAKE_MAX_ITER = 5000
RAKE_ACCEPT = 0.5        # after the last iteration, a margin within half a person is close enough to round


def rake(expected: np.ndarray, rows: np.ndarray, cols: np.ndarray, allowed: np.ndarray, floor: float) -> np.ndarray:
    """Expected flows raked to row totals `rows` (current counts) and column totals `cols` (targets).
    Allowed cells of rows with people get at least `floor * rows[i]`, so every allowed target is reachable.

    Iterative proportional fitting, rows then columns, as `build.ipf.ipf` does. Near the floor it can
    converge very slowly, so after `RAKE_MAX_ITER` iterations the iterate is accepted when every margin is
    within half a person: `round_flows` then makes both margins exact. Raises `ValueError` only when a
    target cannot be reached or the margins stay further apart."""
    rows = np.asarray(rows, dtype=np.float64)
    cols = np.asarray(cols, dtype=np.float64)
    if rows.sum() != cols.sum():
        raise ValueError(f"row total {rows.sum()} differs from target total {cols.sum()}")
    if rows.sum() == 0:
        return np.zeros((rows.size, cols.size))
    seed = np.where(allowed, np.maximum(np.asarray(expected, dtype=np.float64), floor * rows[:, None]), 0.0)
    seed[rows == 0] = 0.0
    if ((seed.sum(axis=1) == 0) & (rows > 0)).any() or ((seed.sum(axis=0) == 0) & (cols > 0)).any():
        raise ValueError("a target or a current stage has no allowed flow")
    w = seed * (rows.sum() / seed.sum())
    gap = np.inf
    for _ in range(RAKE_MAX_ITER):
        r = w.sum(axis=1)
        w *= np.divide(rows, r, out=np.zeros_like(r), where=r > 0)[:, None]
        k = w.sum(axis=0)
        w *= np.divide(cols, k, out=np.zeros_like(k), where=k > 0)[None, :]
        gap = max(np.abs(w.sum(axis=1) - rows).max(), np.abs(w.sum(axis=0) - cols).max())
        if gap < RAKE_TOL:
            return w
    if gap < RAKE_ACCEPT:
        return w
    raise ValueError(f"raking left a margin {gap:.3f} people from its target")


def round_flows(flows: np.ndarray, rows: np.ndarray, cols: np.ndarray, allowed: np.ndarray) -> np.ndarray:
    """Whole-person flows whose row sums equal `rows` and column sums equal `cols` exactly.

    From floor(flows), add 1 to allowed cells in falling order of fractional part (ties by flat index) while
    both the row and the column are short; then sweep allowed cells by falling flow, then any cell."""
    flows = np.asarray(flows, dtype=np.float64)
    out = np.floor(flows + 1e-9).astype(np.int64)
    r = np.asarray(rows, dtype=np.int64) - out.sum(axis=1)
    k = np.asarray(cols, dtype=np.int64) - out.sum(axis=0)
    if (r < 0).any() or (k < 0).any():
        raise ValueError("flows exceed their margins")
    flat = np.arange(flows.size)
    frac = (flows - np.floor(flows + 1e-9)).ravel()
    ok = np.asarray(allowed, dtype=bool).ravel()

    def sweep(order: np.ndarray) -> bool:
        moved = False
        for f in order:
            i, j = divmod(int(f), flows.shape[1])
            if r[i] > 0 and k[j] > 0:
                out[i, j] += 1
                r[i] -= 1
                k[j] -= 1
                moved = True
        return moved

    first = np.lexsort((flat, -frac))
    sweep(first[ok[first]])
    by_flow = np.lexsort((flat, -flows.ravel()))
    while r.any() and sweep(by_flow[ok[by_flow]]):
        pass
    while r.any() and sweep(by_flow):
        pass
    if r.any() or k.any():
        raise ValueError("could not round the flows to their margins")
    return out


def choose_movers(prob: np.ndarray, quota: np.ndarray, u: np.ndarray, own: int) -> np.ndarray:
    """Destination for each of the n people now in stage `own`: quota[d] go to each d != own, the rest stay.

    Destinations are filled in index order; for each, the unassigned people with the largest keys
    log(u[:, d]) / prob[:, d] are chosen (keys are -inf where prob is 0; ties by u, then position)."""
    prob = np.asarray(prob, dtype=np.float64)
    u = np.clip(np.asarray(u, dtype=np.float64), 1e-300, 1.0)
    n = prob.shape[0]
    dest = np.full(n, own, dtype=np.int64)
    free = np.ones(n, dtype=bool)
    pos = np.arange(n)
    for d in range(prob.shape[1]):
        q = int(quota[d])
        if d == own or q == 0:
            continue
        cand = pos[free]
        if q > cand.size:
            raise ValueError(f"quota {q} for stage {d} exceeds the {cand.size} people left")
        p = prob[cand, d]
        key = np.full(cand.size, -np.inf)
        np.divide(np.log(u[cand, d]), p, out=key, where=p > 0)
        order = np.lexsort((cand, -u[cand, d], -key))
        chosen = cand[order[:q]]
        dest[chosen] = d
        free[chosen] = False
    return dest


def align(stage: np.ndarray, prob: np.ndarray, cell: np.ndarray, targets: np.ndarray, allowed: np.ndarray,
          u: np.ndarray, floor: float) -> np.ndarray:
    """New stages: in every cell, counts by stage equal that cell's row of `targets` exactly."""
    stage = np.asarray(stage, dtype=np.int64)
    cell = np.asarray(cell, dtype=np.int64)
    new = stage.copy()
    order = np.argsort(cell, kind="stable")
    bounds = np.flatnonzero(np.diff(cell[order])) + 1
    for idx in np.split(order, bounds):
        if idx.size == 0:
            continue
        k = int(cell[idx[0]])
        rows = np.bincount(stage[idx], minlength=N_STAGES)
        expected = np.zeros((N_STAGES, N_STAGES))
        np.add.at(expected, stage[idx], prob[idx])
        flows = round_flows(rake(expected, rows, targets[k], allowed[k], floor), rows, targets[k], allowed[k])
        for s in np.flatnonzero(rows):
            members = idx[stage[idx] == s]
            new[members] = choose_movers(prob[members], flows[s], u[members], own=int(s))
    return new
