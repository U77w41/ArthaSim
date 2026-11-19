import numpy as np
from arthasim.build.households import form_households
from arthasim.build.population import synthesise_persons
from helpers import D, PR, P, l1

p = synthesise_persons(D, PR, 20_000, seed=7)
h = form_households(p, D, 20, P, seed=7)
N = len(h.adults)


def test_partition_head_and_location():
    assert np.array_equal(np.bincount(h.household_of_person, minlength=N), h.adults)
    assert h.adults.min() >= 1 and h.adults.max() <= 5
    assert np.array_equal(h.district[h.household_of_person], p.district) and (np.diff(h.district) >= 0).all()
    assert ((h.locality >= 0) & (h.locality < 20)).all() and len(np.unique(h.locality)) == 20
    oldest = np.zeros(N, dtype=np.int64)
    np.maximum.at(oldest, h.household_of_person, p.age)
    assert np.array_equal(p.age[h.head], oldest)
    assert np.array_equal(h.household_of_person[h.head], np.arange(N))


def test_size_distribution_and_sex_mixing():
    for d, m in enumerate(D):
        assert l1(np.bincount(h.adults[h.district == d], minlength=6)[1:], m.household_adults) < 0.03
    men = np.zeros(N, dtype=np.int64)
    np.add.at(men, h.household_of_person, p.sex)
    assert (men[h.adults == 2] == 1).mean() > 0.8


def test_dependants_rule():
    in_range = (p.age >= 20) & (p.age <= 49)
    eligible = np.zeros(N, dtype=bool)
    eligible[h.household_of_person[in_range]] = True
    assert (h.dependants[~eligible] == 0).all() and h.dependants.min() >= 0
    for d, m in enumerate(D):
        s = eligible & (h.district == d)
        assert abs(h.dependants[s].mean() - m.dependants_mean) < 0.1


def test_tiny_population_and_determinism():
    small = synthesise_persons(D, PR, 200, seed=7)
    hs = form_households(small, D, 20, P, seed=7)
    assert np.bincount(hs.household_of_person, minlength=len(hs.adults)).min() >= 1
    again = form_households(p, D, 20, P, seed=7)
    assert np.array_equal(again.household_of_person, h.household_of_person)
    assert not np.array_equal(form_households(p, D, 20, P, seed=8).household_of_person, h.household_of_person)
