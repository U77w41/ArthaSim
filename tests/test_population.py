# tests/test_population.py
import numpy as np
from arthasim.build import categories as c
from arthasim.build.population import synthesise_persons
from helpers import D, PR, l1

p = synthesise_persons(D, PR, 20_000, seed=7)


def test_margins_fit_in_each_district():
    assert np.bincount(p.district).tolist() == [12_000, 8_000]
    for d, m in enumerate(D):
        s = p.district == d
        assert l1(np.bincount(p.age_band[s], minlength=5), m.age_band) < 0.02
        assert l1(np.bincount(p.sex[s], minlength=2), m.sex) < 0.02
        assert l1(np.bincount(p.education[s], minlength=5), m.education) < 0.02
        for sex in (c.F, c.M):
            t = s & (p.sex == sex)
            assert l1(np.bincount(p.life_stage[t], minlength=9), m.life_stage[sex]) < 0.03


def test_structure_and_ranges():
    assert p.age.min() >= 18 and p.age.max() <= 84
    assert np.array_equal(p.age_band, np.searchsorted([25, 35, 45, 60], p.age, side="right"))
    assert not ((p.life_stage == c.STUDYING) & (p.age >= 35)).any()
    assert not ((p.life_stage == c.RETIRED) & (p.age < 45)).any()
    assert not ((p.district == 0) & (p.sex == c.F) & (p.life_stage == c.FARM)).any()
    assert not ((p.sex == c.M) & (p.life_stage == c.HOMEMAKER)).any()
    assert (np.diff(p.district) >= 0).all()


def test_deterministic_and_not_sorted_by_cell():
    a, b = (synthesise_persons(D, PR, 5_000, seed=7) for _ in range(2))
    other = synthesise_persons(D, PR, 5_000, seed=8)
    assert np.array_equal(a.age, b.age) and np.array_equal(a.life_stage, b.life_stage)
    assert not np.array_equal(a.age, other.age)
    assert 0.3 < a.sex[:200].mean() < 0.7
