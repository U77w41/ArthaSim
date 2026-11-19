import numpy as np
from arthasim.build import categories as c
from arthasim.build.attributes import attach_attributes
from arthasim.build.earnings import starting_pay
from arthasim.build.population import synthesise_persons
from helpers import D, PR, P

p = synthesise_persons(D, PR, 20_000, seed=7)
a = attach_attributes(p, D, P, seed=7)
FIELDS = ("domain_skill", "digital_literacy", "financial_literacy", "risk_appetite",
          "habit_strength", "price_sensitivity", "trust_in_offers")


def test_ranges_and_gradients():
    for f in FIELDS:
        x = getattr(a, f)
        assert x.dtype == np.float32 and x.min() >= 0 and x.max() <= 1 and x.std() > 0.05
    for f in ("digital_literacy", "financial_literacy"):
        by_edu = [getattr(a, f)[p.education == e].mean() for e in range(5)]
        assert by_edu == sorted(by_edu)
    assert a.digital_literacy[p.age >= 60].mean() < a.digital_literacy[p.age < 35].mean()
    assert a.digital_literacy[p.district == 0].mean() > a.digital_literacy[p.district == 1].mean()


def test_income_and_sector_rules():
    inc = a.monthly_income_paise
    earning = np.isin(p.life_stage, c.EARNING)
    assert inc.dtype == np.int64 and (inc[earning] > 0).all() and (inc[p.life_stage == c.RETIRED] > 0).all()
    assert (inc[np.isin(p.life_stage, [c.STUDYING, c.SEEKING, c.HOMEMAKER])] == 0).all()
    sal = p.life_stage == c.SALARIED
    med = [np.median(inc[sal & (p.education == e)]) for e in (0, 2, 3)]
    assert med[0] < med[1] < med[2]
    same = sal & (p.education == 2)
    assert np.median(inc[same & (p.district == 0)]) > np.median(inc[same & (p.district == 1)])
    assert (a.sector[earning] >= 0).all() and (a.sector[~earning] == -1).all()
    assert (a.sector[p.life_stage == c.FARM] == 0).all()
    assert (a.sector[earning & (p.life_stage != c.FARM)] != 0).all()


def test_starting_pay_formula():
    w = starting_pay(np.array([3]), np.array([10.0]), np.array([True]), np.array([5]), np.array([0.0]), P)
    assert abs(w[0] / (1_200_000 * np.exp(0.95 + 0.35 - 0.06 + 0.25 + 0.45)) - 1) < 1e-9


def test_deterministic():
    b = attach_attributes(p, D, P, seed=7)
    assert np.array_equal(a.monthly_income_paise, b.monthly_income_paise)
    assert not np.array_equal(a.risk_appetite, attach_attributes(p, D, P, seed=8).risk_appetite)
