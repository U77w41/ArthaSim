import numpy as np
from arthasim.engine.intents import Purpose
from arthasim.ledger.journal import FlowType
from arthasim.modules.allowance import allowance_pairs, person_need


def test_enum_values():
    assert Purpose.ALLOWANCE == 6 and FlowType.HOUSEHOLD_TRANSFER == 9


def test_person_need():
    need = person_need(person_budget=np.array([30_000, 30_000, 30_000]), budget=np.array([90_000]),
                       medical_due=np.array([5_000]), head=np.array([0]),
                       utilities_share=np.array([0.1, 0.1, 0.1]))
    assert np.allclose(need, [41_000, 27_000, 27_000])    # head: 27,000 + 9,000 utilities + 5,000 medical


def test_pairs_cover_shortfall():
    # Earner, homemaker, pensioner with a small pension: the pension is topped up, not replaced.
    p, r, a = allowance_pairs(np.array([0, 0, 0]), np.array([100_000, 0, 7_000]),
                              np.array([41_000.0, 27_000.0, 27_000.0]))
    assert list(zip(p.tolist(), r.tolist(), a.tolist())) == [(0, 1, 27_000), (0, 2, 20_000)]


def test_pairs_scaled_when_short():
    # Surplus 10,000 + 5,000; shortfall 20,000 + 10,000; scale 0.5, split 2:1 between payers.
    p, r, a = allowance_pairs(np.array([0, 0, 0, 0]), np.array([30_000, 10_000, 0, 0]),
                              np.array([20_000.0, 5_000.0, 20_000.0, 10_000.0]))
    assert list(zip(p.tolist(), r.tolist(), a.tolist())) == [(0, 2, 6_667), (0, 3, 3_333), (1, 2, 3_333), (1, 3, 1_667)]
    assert a[p == 0].sum() == 10_000 and a[p == 1].sum() == 5_000


def test_no_surplus_no_pairs():
    # Household 0: two non-earners. Household 1: one adult short of need.
    p, r, a = allowance_pairs(np.array([0, 0, 1]), np.array([0, 0, 0]), np.array([10_000.0, 10_000.0, 10_000.0]))
    assert p.size == r.size == a.size == 0 and p.dtype == np.int64
