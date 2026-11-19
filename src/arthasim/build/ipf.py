"""Iterative proportional fitting and integerisation."""
from __future__ import annotations

from typing import Sequence

import numpy as np

Target = tuple[tuple[int, ...], np.ndarray]


def _other_axes(ndim: int, axes: tuple[int, ...]) -> tuple[int, ...]:
    return tuple(a for a in range(ndim) if a not in axes)


def ipf(seed: np.ndarray, targets: Sequence[Target], tol: float = 1e-9, max_iter: int = 500) -> np.ndarray:
    """Scale `seed` until every listed margin matches its target.

    Each target is (axes kept, array of that shape). Cells that are zero in
    the seed stay zero."""
    w = np.asarray(seed, dtype=np.float64).copy()
    targets = [(tuple(axes), np.asarray(t, dtype=np.float64)) for axes, t in targets]
    totals = [float(t.sum()) for _, t in targets]
    if max(totals) - min(totals) > 1e-6:
        raise ValueError(f"targets have different totals: {totals}")
    for i, (axes, t) in enumerate(targets):
        if ((w.sum(axis=_other_axes(w.ndim, axes)) == 0) & (t > 0)).any():
            raise ValueError(f"margin {i} has mass where the seed is zero")
    w *= totals[0] / w.sum()

    for _ in range(max_iter):
        for axes, t in targets:
            current = w.sum(axis=_other_axes(w.ndim, axes))
            factor = np.divide(t, current, out=np.zeros_like(current), where=current > 0)
            w *= factor.reshape([w.shape[a] if a in axes else 1 for a in range(w.ndim)])
        gaps = [np.abs(w.sum(axis=_other_axes(w.ndim, axes)) - t).max() for axes, t in targets]
        if max(gaps) < tol:
            return w
    worst = int(np.argmax(gaps))
    raise ValueError(f"margin {worst} did not converge within {max_iter} iterations")


def integerise(weights: np.ndarray, n: int) -> np.ndarray:
    """Integer counts with the shape of `weights` that sum to `n` (largest remainder,
    ties broken by flat index)."""
    w = np.asarray(weights, dtype=np.float64)
    scaled = w.ravel() * (n / w.sum())
    counts = np.floor(scaled).astype(np.int64)
    short = int(n - counts.sum())
    order = np.lexsort((np.arange(scaled.size), -(scaled - counts)))
    counts[order[:short]] += 1
    return counts.reshape(w.shape)
