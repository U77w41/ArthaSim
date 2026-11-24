"""The Student-t interval for paired differences across seeds, computed in-house (no SciPy).

The t CDF is the regularised incomplete beta function (Lentz's continued fraction, as in Numerical Recipes, section
6.4); the quantile inverts it by bisection."""
from __future__ import annotations

import math
from typing import Sequence

import numpy as np

_EPS, _TINY, _MAXIT = 1e-15, 1e-300, 500


def _betacf(a: float, b: float, x: float) -> float:
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > _TINY else _TINY)
    h = d
    for m in range(1, _MAXIT + 1):
        m2 = 2 * m
        for aa in (m * (b - m) * x / ((qam + m2) * (a + m2)), -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))):
            d = 1.0 + aa * d
            d = 1.0 / (d if abs(d) > _TINY else _TINY)
            c = 1.0 + aa / c
            c = c if abs(c) > _TINY else _TINY
            step = d * c
            h *= step
        if abs(step - 1.0) < _EPS:
            break
    return h


def _betai(a: float, b: float, x: float) -> float:
    """The regularised incomplete beta function I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    front = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def t_cdf(t: float, df: int) -> float:
    tail = 0.5 * _betai(df / 2.0, 0.5, df / (df + t * t))
    return 1.0 - tail if t >= 0 else tail


def t_quantile(p: float, df: int) -> float:
    """The `p` quantile of Student's t with `df` degrees of freedom."""
    if not 0.0 < p < 1.0:
        raise ValueError(f"p must be in (0, 1); got {p}")
    if df < 1:
        raise ValueError(f"df must be at least 1; got {df}")
    if p == 0.5:
        return 0.0
    if p < 0.5:
        return -t_quantile(1.0 - p, df)
    lo, hi = 0.0, 1.0
    while t_cdf(hi, df) < p:
        hi *= 2.0
    while hi - lo > 1e-10 * max(1.0, hi):
        mid = (lo + hi) / 2.0
        if t_cdf(mid, df) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def interval(d: Sequence[float], level: float) -> tuple[float, float | None, float | None, int]:
    """Mean paired difference with a two-sided Student-t interval: (mean, lo, hi, n); lo and hi are None for n < 2."""
    d = np.asarray(d, dtype=np.float64)
    n = int(d.size)
    if n == 0:
        raise ValueError("no differences")
    mean = float(d.mean())
    if n < 2:
        return mean, None, None, n
    half = t_quantile(1.0 - (1.0 - level) / 2.0, n - 1) * float(d.std(ddof=1)) / math.sqrt(n)
    return mean, mean - half, mean + half, n
