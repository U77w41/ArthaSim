import numpy as np
from arthasim.build import categories as c
from arthasim.life.sources import ANNUAL_ROWS, GROUPS, load_plfs
from helpers import P

S = load_plfs()
PARTITION = [r for r in ANNUAL_ROWS if r not in ("regular_agri", "casual_other_agri")]


def test_table_15_spot_values_and_column_sums():
    assert S.annual["urban_female"]["domestic"][11] == 47.7
    assert S.annual["rural_female"]["helper_agri"][11] == 13.6
    assert S.annual["rural_male"]["student"][0] == 68.6
    assert S.annual["urban_male"]["regular"][9] == 14.5
    for g in GROUPS:
        for j in range(12):
            assert abs(sum(S.annual[g][r][j] for r in PARTITION) - 100) < 0.7, (g, j)


def test_bulletins():
    assert len(S.monthly) == 12 and min(S.monthly) == "2025-04" and max(S.monthly) == "2026-03"
    assert S.monthly["2025-06"]["rural_female"]["wpr"] == 33.6 and S.monthly["2025-12"]["rural_female"]["wpr"] == 38.6
    assert S.cws_2025["rural_female"] == {"lfpr": 38.3, "wpr": 36.8}
    assert sorted(S.quarterly) == ["2025-05", "2025-08", "2025-11", "2026-02"]
    assert S.quarterly["2025-11"]["rural_female"]["agriculture"] == 75.5


def test_flows_and_effects():
    m = S.flows["M"]
    assert len(m.pairs) == 4 and m.pairs[0][2] == [0.3, None, 32.1, 0.2, 0.4, 0.1] and m.row_totals[0][2] == 33.1
    assert S.effects["F"]["lost"]["streak3"] == -0.099 and S.effects["M"]["gained"]["very_young"] == -0.054


def test_categories_and_registry():
    assert c.age_group(np.array([18, 19, 20, 34, 35, 64, 65, 90])).tolist() == [0, 0, 1, 3, 4, 9, 10, 10]
    assert c.SECTORS[c.PUBLIC_ADMIN] == "public_admin"
    assert P.get("life.raise.mean") == 0.089 and P.get("inclusion.account_ownership") == {"metro": 0.89, "rural": 0.89}
    assert P.table().height == 184
