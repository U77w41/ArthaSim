import numpy as np
from arthasim.build import categories as c
from arthasim.build.attributes import attach_attributes
from arthasim.build.orgs import build_orgs
from arthasim.build.population import synthesise_persons
from helpers import D, PR, P, l1

p = synthesise_persons(D, PR, 20_000, seed=7)
a = attach_attributes(p, D, P, seed=7)
o = build_orgs(p, a, D, 20, P, seed=7)


def test_every_salaried_person_has_a_matching_employer():
    sal = p.life_stage == c.SALARIED
    assert (o.person_employer[sal] >= 0).all() and (o.person_employer[~sal] == -1).all()
    e = o.person_employer[sal]
    assert np.array_equal(o.employer_district[e], p.district[sal])
    assert np.array_equal(o.employer_sector[e], a.sector[sal])
    staff = np.bincount(e, minlength=len(o.employer_capacity))
    assert (staff >= 1).all() and (staff <= o.employer_capacity).all()
    assert (o.employer_capacity <= 9).mean() > 0.5 and o.employer_capacity.max() <= 2000


def test_merchants_and_billers():
    persons_in = np.bincount(p.district)
    for d in range(2):
        m = o.merchant_district == d
        assert m.sum() >= persons_in[d] // 40
        assert set(o.merchant_locality[m & (o.merchant_category == c.GROCERY)].tolist()) == set(range(20))
        assert l1(np.bincount(o.merchant_category[m], minlength=9), P.get("org.merchant_category_shares")) < 0.08
    upi = [o.merchant_accepts_upi[o.merchant_district == d].mean() for d in range(2)]
    assert upi[0] > upi[1] and abs(upi[0] - 0.80) < 0.08
    assert o.billers == ["telecom", "electricity", "ecommerce", "amc"]


def test_tiny_population_and_determinism():
    ps = synthesise_persons(D, PR, 200, seed=7)
    at = attach_attributes(ps, D, P, seed=7)
    small = build_orgs(ps, at, D, 20, P, seed=7)
    for d in range(2):
        m = (small.merchant_district == d) & (small.merchant_category == c.GROCERY)
        assert set(small.merchant_locality[m].tolist()) == set(range(20))
    assert (small.person_employer[ps.life_stage == c.SALARIED] >= 0).all()
    again = build_orgs(p, a, D, 20, P, seed=7)
    assert np.array_equal(again.person_employer, o.person_employer)
    assert np.array_equal(again.merchant_locality, o.merchant_locality)
