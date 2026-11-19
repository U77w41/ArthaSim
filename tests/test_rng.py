import numpy as np
from arthasim.engine import rng

S = rng.stream_id("test")
E = np.arange(1_000_000, dtype=np.int64)


def test_deterministic_and_order_free():
    a = rng.uniform(7, S, E, 100)
    assert np.array_equal(a, rng.uniform(7, S, E, 100))
    perm = np.random.default_rng(0).permutation(E)
    assert np.array_equal(rng.uniform(7, S, perm, 100), a[perm])
    assert np.array_equal(rng.uniform(7, S, E[:10], 100), a[:10])


def test_range_and_moments():
    u = rng.uniform(7, S, E, 100)
    assert u.min() >= 0.0 and u.max() < 1.0
    assert abs(u.mean() - 0.5) < 0.002 and abs(u.var() - 1 / 12) < 0.001
    counts = np.bincount((u * 100).astype(int), minlength=100)
    assert ((counts - 10_000) ** 2 / 10_000).sum() < 160


def test_keys_are_independent():
    base = rng.uniform(7, S, E, 100)
    others = (rng.uniform(8, S, E, 100), rng.uniform(7, rng.stream_id("other"), E, 100),
              rng.uniform(7, S, E, 101), rng.uniform(7, S, E, 100, index=1),
              rng.uniform(7, S, E + 1, 100))
    for other in others:
        assert abs(np.corrcoef(base, other)[0, 1]) < 0.005


def test_distributions():
    z = rng.normal(7, S, E, 100)
    assert abs(z.mean()) < 0.005 and abs(z.std() - 1.0) < 0.005
    k = rng.poisson(7, S, E, 100, lam=1.2)
    assert k.dtype == np.int64 and abs(k.mean() - 1.2) < 0.01 and abs(k.var() - 1.2) < 0.02
    x = rng.lognormal(7, S, E, 100, median=20_000, sigma=0.9)
    assert abs(np.median(x) / 20_000 - 1.0) < 0.01 and x.min() > 0
