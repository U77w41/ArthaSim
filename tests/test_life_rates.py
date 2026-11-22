import numpy as np
from arthasim.build import categories as c
from arthasim.life.rates import (RateInputs, effect_features, monthly_flows, person_probs, quarterly_flows,
                                 study_exit)
from arthasim.life.sources import load_plfs
from arthasim.life.targets import Targets, age_index
from helpers import P
import datetime as dt

S = load_plfs()
T = Targets(S, P, ["metro", "rural"])


def test_flows():
    q = quarterly_flows(S, c.M, 0.025)
    assert np.allclose(q.sum(axis=1), 1) and abs(q[2, 4] - (0.4 + 0.3 + 0.3 + 0.3) / (33.1 + 32.9 + 33.8 + 34.0)) < 1e-12
    m = monthly_flows(q)
    assert np.allclose(m.sum(axis=1), 1) and abs((1 - m[2, 2]) - (1 - (q[2, 2]) ** (1 / 3))) < 1e-12


def test_study_exit_urban_women_mostly_to_homemaker():
    hazard, dest = study_exit(T.columns(0, c.F, dt.date(2025, 4, 1)), np.array([23]))
    assert hazard[0] > 0
    assert dest[0, c.HOMEMAKER] / dest[0].sum() > 0.55


def inputs(n, stage, **kw):
    base = dict(stage=np.full(n, stage), helper=np.zeros(n, bool), sex=np.full(n, c.F), age=np.full(n, 40),
                education=np.full(n, 2), has_child=np.zeros(n, bool), months_in_stage=np.full(n, 24),
                last_stage=np.full(n, -1), months_since_left=np.full(n, 9999),
                shares=np.repeat(T.shares(dt.date(2025, 4, 1), 0, c.F)[age_index(40)][None], n, axis=0),
                study_hazard=np.zeros(n), study_dest=np.zeros((n, 9)), firm_shock=np.ones(n),
                superannuation=np.zeros(n, bool))
    base.update(kw)
    return RateInputs(**base)


def test_rows_sum_to_one_and_centring_keeps_the_published_mean():
    n = 400
    months = np.where(np.arange(n) < 40, 2, 30)
    p = person_probs(inputs(n, c.SALARIED, months_in_stage=months), S, P)
    assert np.allclose(p.sum(axis=1), 1) and (p >= 0).all()
    q = monthly_flows(quarterly_flows(S, c.F, 0.025))
    lost = p[:, c.SEEKING] + p[:, c.HOMEMAKER] + p[:, c.STUDYING] + p[:, c.RETIRED]
    assert abs(lost.mean() - (q[2, 4] + q[2, 5])) < 2e-3
    assert lost[:40].mean() > lost[40:].mean()


def test_return_weight_superannuation_and_study_cut():
    base = person_probs(inputs(2, c.HOMEMAKER), S, P)
    back = person_probs(inputs(2, c.HOMEMAKER, last_stage=np.full(2, c.FARM), months_since_left=np.full(2, 3)), S, P)
    assert abs(back[0, c.FARM] - 5 * base[0, c.FARM]) < 1e-12
    old = person_probs(inputs(1, c.SALARIED, age=np.array([58]), superannuation=np.array([True])), S, P)
    assert old[0, c.RETIRED] >= 0.5
    assert person_probs(inputs(1, c.SEEKING, age=np.array([36])), S, P)[0, c.STUDYING] == 0


def test_effect_features():
    f = effect_features(np.array([19, 25, 40]), np.array([3, 1, 4]), np.array([True, False, False]), np.array([1, 5, 9]))
    assert f.tolist() == [[1, 0, 1, 1, 0, 0], [0, 1, 0, 0, 1, 0], [0, 0, 1, 0, 0, 1]]
