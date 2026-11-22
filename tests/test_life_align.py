import numpy as np
from hypothesis import given, settings, strategies as st
from arthasim.life.align import align, choose_movers, rake, round_flows

ALL = np.ones((9, 9), dtype=bool)


@st.composite
def cells(draw):
    n = draw(st.integers(5, 60))
    rng = np.random.default_rng(draw(st.integers(0, 10_000)))       # test data only, not under src/
    stage = rng.integers(0, 9, n)
    prob = rng.random((n, 9)) ** 3
    prob /= prob.sum(axis=1, keepdims=True)
    target = np.bincount(rng.integers(0, 9, n), minlength=9)
    return stage, prob, target, rng.random((n, 9))


@settings(max_examples=60, deadline=None)
@given(cells())
def test_align_lands_exactly_on_target(case):
    stage, prob, target, u = case
    new = align(stage, prob, np.zeros(stage.size, dtype=np.int64), target[None], ALL[None], u, 1e-6)
    assert np.bincount(new, minlength=9).tolist() == target.tolist()
    assert np.array_equal(new, align(stage, prob, np.zeros(stage.size, dtype=np.int64), target[None], ALL[None], u, 1e-6))


@settings(max_examples=60, deadline=None)
@given(cells())
def test_round_flows_keeps_both_margins(case):
    stage, prob, target, _ = case
    rows = np.bincount(stage, minlength=9)
    expected = np.zeros((9, 9))
    np.add.at(expected, stage, prob)
    f = rake(expected, rows, target, ALL, 1e-6)
    n = round_flows(f, rows, target, ALL)
    assert n.sum(axis=1).tolist() == rows.tolist() and n.sum(axis=0).tolist() == target.tolist()
    assert (np.abs(n - f) < 2).all()


def test_floor_reaches_a_stage_no_one_would_choose():
    stage = np.zeros(10, dtype=np.int64)
    prob = np.zeros((10, 9)); prob[:, 0] = 1.0
    target = np.zeros(9, dtype=np.int64); target[0], target[1] = 7, 3
    new = align(stage, prob, np.zeros(10, dtype=np.int64), target[None], ALL[None], np.linspace(0.05, 0.95, 90).reshape(10, 9), 1e-6)
    assert np.bincount(new, minlength=9)[:2].tolist() == [7, 3]


def test_choose_movers_prefers_likely_movers():
    prob = np.zeros((1000, 9)); prob[:, 0] = 0.9; prob[:500, 1] = 0.1; prob[500:, 1] = 0.001
    u = (np.arange(1000) * 0.618034) % 1.0
    u = np.repeat(u[:, None], 9, axis=1)
    dest = choose_movers(prob, np.array([0, 100] + [0] * 7), u, own=0)
    assert (dest == 1).sum() == 100 and (dest[:500] == 1).sum() > 90
