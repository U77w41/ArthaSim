import numpy as np
from arthasim.build import categories as c
from arthasim.life.helpers import assign_helpers, orphaned
from world_fixture import small_world


def test_helper_rule():
    stage = np.array([c.FARM, c.FARM, c.FARM, c.SELF_EMPLOYED, c.FARM, c.FARM])
    hh = np.array([0, 0, 1, 1, 2, 2])
    cand = np.array([True, False, True, False, True, True])
    assert assign_helpers(stage, hh, cand).tolist() == [True, False, False, False, False, False]
    assert orphaned(stage, hh, np.array([True, False, True, False, True, False])).tolist() == [False, False, True, False, False, False]


def test_build_state():
    s = small_world().state
    b, life = s.population, s.life
    stage, inc = b.persons.life_stage, b.attributes.monthly_income_paise
    assert life.helper.shape == stage.shape and (inc[life.helper] == 0).all()
    assert np.isin(stage[life.helper], [c.FARM, c.SELF_EMPLOYED]).all()
    assert not orphaned(stage, b.households.household_of_person, life.helper).any()
    own = np.isin(stage, [c.FARM, c.SELF_EMPLOYED]) & ~life.helper
    assert (inc[own] > 0).all() and life.helper.any()
    assert life.birth_month.min() >= 1 and life.birth_month.max() <= 12
    assert 0.45 < (life.raise_month == 4).mean() < 0.67 and life.raise_month.size == len(s.employer_ids)
    assert (life.months_in_stage >= 1).all() and (life.last_stage == -1).all()
    assert s.account_opened_on.shape == (len(s.book),)
    assert abs(b.banking.person_has_account[stage != c.SALARIED].mean() - 0.89) < 0.03
    assert all(v["life_stage_F"] < 0.01 and v["life_stage_M"] < 0.01 for v in b.report["l1"].values())
