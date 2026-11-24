"""Life-stage targets by (district kind, sex, single year of age) and month, from PLFS 2025.

Annual shares come from Table 15 (usual status), mapped to the model's stages and interpolated by age.
The monthly path scales work and seeking by the CWS bulletins and shifts the composition of work by the
quarterly bulletins. Months outside April 2025 to March 2026 repeat the same calendar month."""
from __future__ import annotations

import datetime as dt
from typing import Sequence

import numpy as np

from arthasim.build import categories as c
from arthasim.build.ipf import integerise
from arthasim.life.sources import QUARTERS, Plfs2025, group_name
from arthasim.params import ParamRegistry

AGE_MIN, AGE_MAX = 18, 85
N_AGES = AGE_MAX - AGE_MIN + 1
AGES = np.arange(AGE_MIN, AGE_MAX + 1)
# Interpolation knots, one per PLFS five-year column. The first knot (age 19) holds the mean of the 15-19 and
# 20-24 columns and covers ages 18-19; the last (age 65) holds the 65+ column and covers 65 and over.
MIDPOINTS = [19, 22, 27, 32, 37, 42, 47, 52, 57, 62, 65]
WORKING = [c.SALARIED, c.SELF_EMPLOYED, c.GIG, c.FARM, c.CASUAL]
WINDOW_START, WINDOW_END = (2025, 4), (2026, 3)


def age_index(age) -> np.ndarray:
    return np.clip(np.minimum(np.asarray(age), AGE_MAX) - AGE_MIN, 0, N_AGES - 1)


def fiscal_year(month: dt.date) -> int:
    return month.year if month.month >= 4 else month.year - 1


def gig_share(params: ParamRegistry, month: dt.date) -> float:
    """Gig workers as a share of non-farm workers, linear in the fiscal-year start, clamped outside the points."""
    pts = sorted((int(k), float(v)) for k, v in params.get("life.gig.nonfarm_share").items())
    return float(np.interp(fiscal_year(month), [k for k, _ in pts], [v for _, v in pts]))


def stage_column(src: Plfs2025, group: str, column: int, gig: float) -> np.ndarray:
    """One PLFS Table 15 column mapped to the nine stages, normalised to sum 1."""
    a = {r: v[column] for r, v in src.annual[group].items()}
    farm = a["own_agri"] + a["helper_agri"]
    casual = a["casual_public"] + a["casual_other"]
    nf_self = a["own_secondary"] + a["own_tertiary"] + a["helper_secondary"] + a["helper_tertiary"]
    workers = farm + a["regular"] + casual + nf_self
    nonfarm = workers - (a["own_agri"] + a["helper_agri"] + a["regular_agri"] + a["casual_other_agri"])
    g = min(gig * nonfarm, a["own_secondary"] + a["own_tertiary"])
    out = np.zeros(9)
    out[c.STUDYING] = a["student"]
    out[c.SEEKING] = a["unemployed"]
    out[c.SALARIED] = a["regular"]
    out[c.SELF_EMPLOYED] = nf_self - g
    out[c.GIG] = g
    out[c.FARM] = farm
    out[c.CASUAL] = casual
    out[c.HOMEMAKER] = a["domestic"] + a["domestic_collect"] + a["disabled"] + a["others"]
    out[c.RETIRED] = a["pensioner"]
    return out / out.sum()


def _knots(columns: np.ndarray) -> np.ndarray:
    """The 11 knot rows (at MIDPOINTS) from the 11 five-year columns."""
    k = np.asarray(columns, dtype=np.float64).copy()
    k[0] = (columns[0] + columns[1]) / 2
    return k


def _interpolate(knots: np.ndarray, ages: np.ndarray) -> np.ndarray:
    """Piecewise-linear in age between the knots, flat before the first and after the last."""
    ages = np.asarray(ages, dtype=np.float64)
    mid = np.asarray(MIDPOINTS, dtype=np.float64)
    g = np.clip(np.searchsorted(mid, ages, side="right") - 1, 0, len(mid) - 2)
    w = np.clip((ages - mid[g]) / (mid[g + 1] - mid[g]), 0.0, 1.0)
    return (1 - w)[:, None] * knots[g] + w[:, None] * knots[g + 1]


def window_month(month: dt.date) -> str:
    """"YYYY-MM" of the same calendar month inside April 2025 to March 2026."""
    if WINDOW_START <= (month.year, month.month) <= WINDOW_END:
        return f"{month.year:04d}-{month.month:02d}"
    return f"{2025 if month.month >= 4 else 2026:04d}-{month.month:02d}"


def _quarter_deviation(src: Plfs2025, group: str, wm: str) -> dict[str, float]:
    """Deviation of agriculture, casual and regular shares (as shares of workers) from their four-quarter mean,
    at each quarter's middle month, linear in between, flat before the first and after the last."""
    order = [f"{y:04d}-{m:02d}" for y, m in [(2025, k) for k in range(4, 13)] + [(2026, k) for k in range(1, 4)]]
    i = order.index(wm)
    mids = [order.index(q) for q in QUARTERS]
    out = {}
    for key in ("agriculture", "casual", "regular"):
        v = np.array([src.quarterly[q][group][key] for q in QUARTERS]) / 100
        out[key] = float(np.interp(i, mids, v - v.mean()))
    return out


def seasonal_rows(src: Plfs2025, group: str, month: dt.date, rows: np.ndarray, base15: np.ndarray) -> np.ndarray:
    """Apply the month's bulletin path to annual share rows (k, 9); base15 is the group's mapped 15+ column."""
    wm = window_month(month)
    mon, cws = src.monthly[wm][group], src.cws_2025[group]
    w15 = base15[WORKING].sum()
    u15 = base15[c.SEEKING]
    f_w = (w15 + (mon["wpr"] - cws["wpr"]) / 100) / w15
    f_u = (u15 + ((mon["lfpr"] - mon["wpr"]) - (cws["lfpr"] - cws["wpr"])) / 100) / u15 if u15 > 0 else 1.0
    comp = base15 / w15
    dev = _quarter_deviation(src, group, wm)
    new = comp.copy()
    new[c.FARM] = comp[c.FARM] + dev["agriculture"]
    new[c.CASUAL] = comp[c.CASUAL] + dev["casual"]
    new[c.SALARIED] = comp[c.SALARIED] + dev["regular"]
    rest = 1 - (new[c.FARM] + new[c.CASUAL] + new[c.SALARIED])
    sg = comp[c.SELF_EMPLOYED] + comp[c.GIG]
    new[c.SELF_EMPLOYED] = rest * comp[c.SELF_EMPLOYED] / sg
    new[c.GIG] = rest * comp[c.GIG] / sg
    mult = np.ones(9)
    for s in WORKING:
        mult[s] = f_w * new[s] / comp[s] if comp[s] > 0 else 1.0
    rows = np.asarray(rows, dtype=np.float64)
    out = rows.copy()
    out[:, WORKING] *= mult[WORKING]
    out[:, c.SEEKING] *= f_u
    left = 1 - out[:, WORKING].sum(axis=1) - out[:, c.SEEKING] - out[:, c.RETIRED]
    st, hm = rows[:, c.STUDYING], rows[:, c.HOMEMAKER]
    tot = st + hm
    safe = np.where(tot > 0, tot, 1.0)
    out[:, c.STUDYING] = np.where(tot > 0, left * st / safe, 0.0)
    out[:, c.HOMEMAKER] = np.where(tot > 0, left * hm / safe, left)
    neg = (out < 0).any(axis=1)
    if neg.any():
        fixed = np.clip(out[neg], 0.0, None)
        out[neg] = fixed / fixed.sum(axis=1, keepdims=True)
    return out


def cell_counts(rows: np.ndarray, cell: np.ndarray, n_cells: int) -> np.ndarray:
    """Per cell, the column sums of the people's share rows integerised to the cell's size."""
    rows = np.asarray(rows, dtype=np.float64)
    cell = np.asarray(cell, dtype=np.int64)
    sums = np.zeros((n_cells, rows.shape[1]))
    np.add.at(sums, cell, rows)
    size = np.bincount(cell, minlength=n_cells)
    out = np.zeros((n_cells, rows.shape[1]), dtype=np.int64)
    for k in np.flatnonzero(size):
        out[k] = integerise(sums[k], int(size[k]))
    return out


class Targets:
    """Life-stage shares by (district, sex, age) and month for the districts of a build."""

    def __init__(self, src: Plfs2025, params: ParamRegistry, kinds: Sequence[str]):
        self.src, self.params, self.kinds = src, params, list(kinds)
        self.n_districts = len(self.kinds)
        self.n_cells = self.n_districts * 2 * c.N_AGE_GROUPS
        self.study_max_age = int(params.get("life.study.max_age"))
        self._annual: dict[tuple, np.ndarray] = {}
        self._shares: dict[tuple, np.ndarray] = {}
        self._helper = self._helper_table()

    def set_params(self, params: ParamRegistry) -> None:
        """Follow a changed registry: the shares are recomputed from it on next use."""
        self.params = params
        self.study_max_age = int(params.get("life.study.max_age"))
        self._annual.clear()
        self._shares.clear()

    def group(self, district: int, sex: int) -> str:
        return group_name(self.kinds[district], sex)

    def columns(self, district: int, sex: int, month: dt.date) -> np.ndarray:
        """The 11 five-year columns (15-19 to 65+) of the group, mapped to stages; the month sets the gig share."""
        gig = gig_share(self.params, month)
        return np.stack([stage_column(self.src, self.group(district, sex), j, gig) for j in range(c.N_AGE_GROUPS)])

    def annual(self, district: int, sex: int, month: dt.date) -> np.ndarray:
        key = (fiscal_year(month), district, sex)
        if key not in self._annual:
            rows = _interpolate(_knots(self.columns(district, sex, month)), AGES)
            rows[AGES >= self.study_max_age, c.STUDYING] = 0.0
            self._annual[key] = rows / rows.sum(axis=1, keepdims=True)
        return self._annual[key]

    def shares(self, month: dt.date, district: int, sex: int) -> np.ndarray:
        key = (window_month(month), fiscal_year(month), district, sex)
        if key not in self._shares:
            g = self.group(district, sex)
            base15 = stage_column(self.src, g, c.N_AGE_GROUPS, gig_share(self.params, month))
            self._shares[key] = seasonal_rows(self.src, g, month, self.annual(district, sex, month), base15)
        return self._shares[key]

    def for_persons(self, month: dt.date, district, sex, age) -> np.ndarray:
        """This month's share rows at each person's age; district and sex may be scalars or arrays."""
        age = np.asarray(age)
        district = np.broadcast_to(np.asarray(district), age.shape)
        sex = np.broadcast_to(np.asarray(sex), age.shape)
        out = np.zeros((age.size, 9))
        ai = age_index(age)
        for d in range(self.n_districts):
            for x in (c.F, c.M):
                m = (district == d) & (sex == x)
                if m.any():
                    out[m] = self.shares(month, d, x)[ai[m]]
        return out

    def start_array(self, month: dt.date) -> np.ndarray:
        return np.stack([np.stack([self.shares(month, d, x) for x in (c.F, c.M)]) for d in range(self.n_districts)])

    def _helper_table(self) -> np.ndarray:
        """(n_districts, 2, 2, N_AGES): helper share among farm (0) and self_employed (1) workers."""
        out = np.zeros((self.n_districts, 2, 2, N_AGES))
        for d in range(self.n_districts):
            for x in (c.F, c.M):
                a = {r: np.asarray(v[: c.N_AGE_GROUPS]) for r, v in self.src.annual[self.group(d, x)].items()}
                for i, (helpers, owners) in enumerate((
                        (a["helper_agri"], a["own_agri"]),
                        (a["helper_secondary"] + a["helper_tertiary"], a["own_secondary"] + a["own_tertiary"]))):
                    h, tot = _knots(helpers[:, None])[:, 0], _knots((helpers + owners)[:, None])[:, 0]
                    ratio = np.divide(h, tot, out=np.zeros_like(h), where=tot > 0)
                    out[d, x, i] = _interpolate(ratio[:, None], AGES)[:, 0]
        return out

    def helper_share(self, district, sex, age, stage) -> np.ndarray:
        """PLFS share of unpaid helpers among farm or self_employed workers at each age; 0 for other stages."""
        age = np.asarray(age)
        district, sex, stage = (np.broadcast_to(np.asarray(v), age.shape) for v in (district, sex, stage))
        kind = np.where(stage == c.FARM, 0, 1)
        out = self._helper[district, sex, kind, age_index(age)]
        return np.where(np.isin(stage, (c.FARM, c.SELF_EMPLOYED)), out, 0.0)

    def counts(self, month: dt.date, district, sex, age) -> tuple[np.ndarray, np.ndarray]:
        """Cell of each person and the integer targets (n_cells, 9) of the cells they fill."""
        age = np.asarray(age)
        cell = (np.asarray(district) * 2 + np.asarray(sex)) * c.N_AGE_GROUPS + c.age_group(age)
        cell = np.broadcast_to(cell, age.shape).astype(np.int64)
        return cell, cell_counts(self.for_persons(month, district, sex, age), cell, self.n_cells)
