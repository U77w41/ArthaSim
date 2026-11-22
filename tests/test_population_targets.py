import datetime as dt
import numpy as np
from arthasim.build import categories as c
from arthasim.build.population import synthesise_persons
from arthasim.life.sources import load_plfs
from arthasim.life.targets import Targets
from helpers import D, PR, P, l1

T = Targets(load_plfs(), P, [d.kind for d in D])
APR = dt.date(2025, 4, 1)
p = synthesise_persons(D, PR, 20_000, seed=7, stage_shares=T.start_array(APR))


def test_every_cell_lands_on_the_start_targets():
    for d in (0, 1):
        for sex in (c.F, c.M):
            m = (p.district == d) & (p.sex == sex)
            cell, want = T.counts(APR, d, sex, p.age[m])
            got = np.zeros_like(want)
            np.add.at(got, (cell, p.life_stage[m]), 1)
            assert np.array_equal(got, want)


def test_other_margins_and_age_profile():
    for d, m in enumerate(D):
        s = p.district == d
        assert l1(np.bincount(p.age_band[s], minlength=5), m.age_band) < 0.02
        assert l1(np.bincount(p.education[s], minlength=5), m.education) < 0.02
    young, older = p.age <= 20, (p.age >= 24) & (p.age <= 26)
    assert (p.life_stage[young] == c.STUDYING).mean() > 3 * (p.life_stage[older] == c.STUDYING).mean()
    assert not ((p.life_stage == c.STUDYING) & (p.age >= 35)).any()
    assert np.array_equal(p.age_band, np.searchsorted([25, 35, 45, 60], p.age, side="right"))


def test_deterministic():
    again = synthesise_persons(D, PR, 20_000, seed=7, stage_shares=T.start_array(APR))
    assert np.array_equal(again.life_stage, p.life_stage) and np.array_equal(again.age, p.age)


def test_fit_report_compares_life_stage_with_the_target_rows():
    from arthasim.build.pipeline import fit_report
    target = np.zeros((2, 2, 9))
    for d in (0, 1):
        for sex in (c.F, c.M):
            m = (p.district == d) & (p.sex == sex)
            target[d, sex] = T.for_persons(APR, d, sex, p.age[m]).mean(axis=0)
    rep = fit_report(D, p, stage_target=target)
    assert all(v["life_stage_F"] < 0.01 and v["life_stage_M"] < 0.01 for v in rep["l1"].values())
    assert max(v["life_stage_F"] for v in fit_report(D, p)["l1"].values()) > 0.05
