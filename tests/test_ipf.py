import numpy as np
import pytest
from arthasim.build.ipf import ipf, integerise


def test_ipf_matches_all_margins_and_keeps_zeros():
    seed = np.ones((3, 2, 4))
    seed[0, :, 3] = 0
    t0 = np.array([0.2, 0.5, 0.3])
    t12 = np.array([[0.1, 0.2, 0.1, 0.1], [0.2, 0.1, 0.1, 0.1]])
    w = ipf(seed, [((0,), t0), ((1, 2), t12)])
    assert np.allclose(w.sum(axis=(1, 2)), t0, atol=1e-8) and np.allclose(w.sum(axis=0), t12, atol=1e-8)
    assert (w[0, :, 3] == 0).all() and (w >= 0).all()


def test_ipf_handles_a_zero_target():
    w = ipf(np.ones((2, 3)), [((0,), np.array([0.4, 0.6])), ((1,), np.array([0.5, 0.0, 0.5]))])
    assert (w[:, 1] == 0).all() and np.isfinite(w).all() and abs(w.sum() - 1.0) < 1e-9


def test_ipf_rejects_infeasible_and_mismatched_targets():
    seed = np.ones((2, 2))
    seed[0, :] = 0
    with pytest.raises(ValueError, match="margin 0"):
        ipf(seed, [((0,), np.array([0.5, 0.5])), ((1,), np.array([0.5, 0.5]))])
    with pytest.raises(ValueError):
        ipf(np.ones((2, 2)), [((0,), np.array([0.5, 0.5])), ((1,), np.array([0.6, 0.6]))])


def test_integerise():
    w = np.array([[0.26, 0.24], [0.25, 0.25]])
    counts = integerise(w, 10)
    assert counts.dtype == np.int64 and counts.sum() == 10 and (np.abs(counts - w * 10) < 1).all()
    assert np.array_equal(counts, integerise(w, 10))
    assert integerise(np.array([0.0, 1.0]), 7).tolist() == [0, 7]
    assert integerise(np.array([1.0, 1.0, 1.0]), 2).tolist() == [1, 1, 0]
