import datetime as dt
import numpy as np
from arthasim.build import categories as c
from arthasim.life.sources import load_plfs
from arthasim.life.targets import (Targets, cell_counts, gig_share, seasonal_rows, stage_column, window_month,
                                   age_index)
from helpers import P

S = load_plfs()
T = Targets(S, P, ["metro", "rural"])
APR, JUN = dt.date(2025, 4, 1), dt.date(2025, 6, 1)
WORKING = [c.SALARIED, c.SELF_EMPLOYED, c.GIG, c.FARM, c.CASUAL]


def test_stage_column_rural_female_40_44():
    gig = 0.026 + 0.041 * 5 / 9
    assert abs(gig_share(P, APR) - gig) < 1e-12
    g = gig * 17.7          # non-farm workers: 67.7 workers less 50.0 in agriculture
    want = np.array([0.0, 0.1, 6.1, 8.2 - g, g, 40.4, 13.0, 31.4, 1.0]) / 100.2
    assert np.allclose(stage_column(S, "rural_female", 5, gig), want, atol=1e-12)


def test_interpolation_and_study_cut():
    a = T.annual(1, c.F, APR)
    assert np.allclose(a[age_index(42)], stage_column(S, "rural_female", 5, gig_share(P, APR)))
    assert np.allclose(a[age_index(44)], 0.6 * a[age_index(42)] + 0.4 * a[age_index(47)])
    assert (a[age_index(np.arange(35, 86)), c.STUDYING] == 0).all()
    assert age_index(np.array([18, 85, 90])).tolist() == [0, 67, 67]


def test_ends_of_the_age_range_follow_the_design():
    # Ages 18-19 take the mean of the 15-19 and 20-24 columns; 65 and over use the 65+ column.
    gig = gig_share(P, APR)
    a = T.annual(0, c.M, APR)
    young = (stage_column(S, "urban_male", 0, gig) + stage_column(S, "urban_male", 1, gig)) / 2
    assert np.allclose(a[age_index(18)], young) and np.allclose(a[age_index(19)], young)
    old = stage_column(S, "urban_male", 10, gig)
    old[c.STUDYING] = 0
    old /= old.sum()
    assert np.allclose(a[age_index(np.arange(65, 86))], old)


def test_seasonal_moves_work_and_seeking_by_the_bulletin():
    base = stage_column(S, "rural_female", 11, gig_share(P, JUN))
    out = seasonal_rows(S, "rural_female", JUN, base[None], base)[0]
    assert abs(out[WORKING].sum() - (base[WORKING].sum() + (33.6 - 36.8) / 100)) < 1e-9
    assert abs(out[c.SEEKING] - (base[c.SEEKING] + ((35.2 - 33.6) - (38.3 - 36.8)) / 100)) < 1e-9
    assert out[c.RETIRED] == base[c.RETIRED] and abs(out.sum() - 1) < 1e-12


def test_every_month_is_valid_and_outside_months_repeat_the_window():
    for m in [dt.date(2025, k, 1) for k in range(4, 13)] + [dt.date(2026, k, 1) for k in range(1, 7)]:
        for d in (0, 1):
            for sex in (c.F, c.M):
                s = T.shares(m, d, sex)
                assert (s >= 0).all() and np.allclose(s.sum(axis=1), 1)
    assert window_month(dt.date(2026, 6, 1)) == "2025-06"
    # The seasonal path repeats; only the gig share of non-farm self-employment grows with the fiscal year.
    late, early = T.shares(dt.date(2026, 6, 1), 1, c.F), T.shares(dt.date(2025, 6, 1), 1, c.F)
    other = [s for s in range(9) if s not in (c.SELF_EMPLOYED, c.GIG)]
    assert np.allclose(late[:, other], early[:, other], atol=1e-15)
    assert np.allclose(late[:, c.SELF_EMPLOYED] + late[:, c.GIG], early[:, c.SELF_EMPLOYED] + early[:, c.GIG], atol=1e-15)
    assert (late[:, c.GIG] >= early[:, c.GIG]).all() and (late[:, c.GIG] > early[:, c.GIG]).any()


def test_counts_and_helper_share():
    rows = np.array([[0.5, 0.5] + [0.0] * 7] * 3 + [[0.0] * 8 + [1.0]])
    assert cell_counts(rows, np.array([0, 0, 0, 1]), 2).tolist() == [[2, 1] + [0] * 7, [0] * 8 + [1]]
    age = np.array([42, 42, 70])
    cell, tgt = T.counts(APR, 1, c.F, age)
    assert cell.tolist() == [(1 * 2 + c.F) * 11 + 5] * 2 + [(1 * 2 + c.F) * 11 + 10]
    assert tgt.shape == (44, 9) and tgt.sum() == 3
    assert abs(T.helper_share(1, c.F, np.array([42]), c.FARM)[0] - 18.5 / 40.4) < 1e-12
