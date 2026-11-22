"""Monthly transition probabilities between life stages.

Base rates are the PLFS urban panel's quarterly gross flows by sex, converted to monthly. Study exits come
from the age profile of studying; moves inside the self-employment and outside-the-labour-force blocks have
their own rates; Bhattacharya's effects rank people within each (sex, flow row); people who left a stage
recently are likelier to return; salaried people at superannuation age often retire."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from arthasim.build import categories as c
from arthasim.life.sources import Plfs2025
from arthasim.life.targets import MIDPOINTS, _interpolate, _knots
from arthasim.params import ParamRegistry

FLOW_STATES = ("own", "helper", "regular", "casual", "unemployed", "nlf")
OWN, HELPER, REGULAR, CASUAL, UNEMPLOYED, NLF = range(6)
EFFECTS_USED = ("very_young", "young", "graduate", "has_child", "streak2", "streak3")
SELF_BLOCK = (c.FARM, c.SELF_EMPLOYED, c.GIG)
NLF_BLOCK = (c.STUDYING, c.HOMEMAKER, c.RETIRED)


def _sex_key(sex: int) -> str:
    return "F" if sex == c.F else "M"


def quarterly_flows(src: Plfs2025, sex: int, negligible_pct: float) -> np.ndarray:
    """Row-conditional quarterly probabilities (6, 6), pooled over the four quarter pairs."""
    f = src.flows[_sex_key(sex)]
    cells = np.array([[[negligible_pct if v is None else v for v in row] for row in pair] for pair in f.pairs])
    totals = np.array(f.row_totals, dtype=np.float64)          # (4, 6)
    summed = cells.sum(axis=0)
    row_total = totals.sum(axis=0)
    q = summed / row_total[:, None]
    residual = (row_total - summed.sum(axis=1)) / row_total
    q[np.arange(6), np.arange(6)] += residual
    return q


def monthly_flows(q: np.ndarray) -> np.ndarray:
    """Exit e becomes 1 - (1 - e) ** (1/3), split across destinations in the quarterly proportions."""
    q = np.asarray(q, dtype=np.float64)
    stay = np.diag(q)
    exit_q = 1 - stay
    exit_m = 1 - np.clip(stay, 0.0, 1.0) ** (1 / 3)
    scale = np.divide(exit_m, exit_q, out=np.zeros_like(exit_q), where=exit_q > 0)
    m = q * scale[:, None]
    m[np.arange(len(q)), np.arange(len(q))] = 1 - exit_m
    return m


def study_exit(columns: np.ndarray, age: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Monthly hazard of leaving study (n,) and destination weights (n, 9), from the fall in the studying
    share between neighbouring age knots and the rise in the other stages over the same years."""
    knots = _knots(np.asarray(columns, dtype=np.float64))
    age = np.asarray(age, dtype=np.float64)
    mid = np.asarray(MIDPOINTS, dtype=np.float64)
    g = np.clip(np.searchsorted(mid, age, side="right") - 1, 0, len(mid) - 2)
    delta = knots[g + 1] - knots[g]                                # (n, 9)
    share = _interpolate(knots, age)[:, c.STUDYING]
    fall = np.maximum(0.0, -delta[:, c.STUDYING]) / ((mid[g + 1] - mid[g]) * 12)
    hazard = np.minimum(np.divide(fall, share, out=np.zeros_like(fall), where=share > 0), 0.95)
    hazard[age >= mid[-1]] = 0.0
    dest = np.maximum(0.0, delta)
    dest[:, c.STUDYING] = 0.0
    none = dest.sum(axis=1) == 0
    dest[none, c.SEEKING] = 1.0
    return hazard, dest


@dataclass
class RateInputs:
    stage: np.ndarray
    helper: np.ndarray
    sex: np.ndarray
    age: np.ndarray
    education: np.ndarray
    has_child: np.ndarray
    months_in_stage: np.ndarray
    last_stage: np.ndarray
    months_since_left: np.ndarray
    shares: np.ndarray            # (n, 9) this month's targets at each person's age
    study_hazard: np.ndarray
    study_dest: np.ndarray        # (n, 9)
    firm_shock: np.ndarray        # 1 for non-salaried
    superannuation: np.ndarray    # bool


def effect_features(age, education, has_child, months_in_stage) -> np.ndarray:
    """(n, 6) indicators: age < 21, age 21-30, graduate or above, child in household, 4-6 and 7+ months in stage."""
    age, months = np.asarray(age), np.asarray(months_in_stage)
    return np.stack([age < 21, (age >= 21) & (age <= 30), np.asarray(education) >= 3, np.asarray(has_child, bool),
                     (months >= 4) & (months <= 6), months >= 7], axis=1).astype(np.int64)


def flow_row(stage: np.ndarray, helper: np.ndarray) -> np.ndarray:
    """The panel state each person's stage maps to."""
    row = np.full(stage.shape, NLF, dtype=np.int64)
    row[stage == c.SALARIED] = REGULAR
    row[stage == c.CASUAL] = CASUAL
    row[stage == c.SEEKING] = UNEMPLOYED
    work = np.isin(stage, SELF_BLOCK)
    row[work] = np.where(np.asarray(helper)[work], HELPER, OWN)
    return row


def _monthly_matrices(src: Plfs2025, params: ParamRegistry) -> np.ndarray:
    neg = float(params.get("life.flows.negligible_pct"))
    return np.stack([monthly_flows(quarterly_flows(src, s, neg)) for s in (c.F, c.M)])


def _split(weights: np.ndarray, fallback: int, cols: tuple[int, ...]) -> np.ndarray:
    """Rows of `weights` over `cols` normalised to 1 (all to `fallback` where they sum to 0)."""
    w = weights[:, list(cols)].astype(np.float64)
    tot = w.sum(axis=1, keepdims=True)
    out = np.divide(w, tot, out=np.zeros_like(w), where=tot > 0)
    out[tot[:, 0] == 0, cols.index(fallback)] = 1.0
    return out


def person_probs(x: RateInputs, src: Plfs2025, params: ParamRegistry) -> np.ndarray:
    """(n, 9) monthly probabilities of each person's next stage; rows sum to 1."""
    n = x.stage.size
    stage = np.asarray(x.stage, dtype=np.int64)
    sex = np.asarray(x.sex, dtype=np.int64)
    lo, hi = (float(v) for v in params.get("life.prob_bounds"))
    mats = _monthly_matrices(src, params)

    # 1. Flow row by sex.
    row = flow_row(stage, x.helper)
    R = mats[sex, row].copy()                                       # (n, 6)

    # 2. Effects on losing (employed rows) and gaining (unemployed and nlf rows), centred per (sex, row).
    feats = effect_features(x.age, x.education, x.has_child, x.months_in_stage)
    lost = np.stack([[src.effects[_sex_key(s)]["lost"][k] for k in EFFECTS_USED] for s in (c.F, c.M)])
    gained = np.stack([[src.effects[_sex_key(s)]["gained"][k] for k in EFFECTS_USED] for s in (c.F, c.M)])
    employed = row <= CASUAL
    eff = np.where(employed, (feats * lost[sex]).sum(axis=1), (feats * gained[sex]).sum(axis=1)) / 3
    centre_group = (row != NLF) | (stage != c.STUDYING)            # students' rows are replaced below
    for s in (c.F, c.M):
        for r in range(6):
            m = (sex == s) & (row == r)
            g = m & centre_group
            if g.any():
                eff[m] -= eff[g].mean()
    out_cols = np.where(employed[:, None], np.isin(np.arange(6), (UNEMPLOYED, NLF))[None, :],
                        np.isin(np.arange(6), (OWN, HELPER, REGULAR, CASUAL))[None, :])
    total = (R * out_cols).sum(axis=1)
    new_total = np.clip(total + eff, lo, hi)
    factor = np.divide(new_total, total, out=np.ones_like(total), where=total > 0)
    R = np.where(out_cols, R * factor[:, None], R)

    # 3. Expand the six panel states to the nine stages.
    p = np.zeros((n, 9))
    self_split = _split(x.shares, c.SELF_EMPLOYED, SELF_BLOCK)
    nlf_split = _split(x.shares, c.HOMEMAKER, NLF_BLOCK)
    in_self = np.isin(stage, SELF_BLOCK)
    in_nlf = np.isin(stage, NLF_BLOCK)
    work = R[:, OWN] + R[:, HELPER]
    for i, s in enumerate(SELF_BLOCK):
        p[:, s] += np.where(in_self, 0.0, work * self_split[:, i])
    p[:, c.SALARIED] += R[:, REGULAR]
    p[:, c.CASUAL] += R[:, CASUAL]
    p[:, c.SEEKING] += R[:, UNEMPLOYED]
    for i, s in enumerate(NLF_BLOCK):
        p[:, s] += np.where(in_nlf, 0.0, R[:, NLF] * nlf_split[:, i])
    p[np.arange(n), stage] = 0.0                                    # staying is set in step 10

    # 4. Students: leave at the age-profile hazard, to the age-profile destinations.
    st = stage == c.STUDYING
    if st.any():
        dest = _split(np.asarray(x.study_dest, dtype=np.float64), c.SEEKING, tuple(range(9)))
        p[st] = np.asarray(x.study_hazard, dtype=np.float64)[st, None] * dest[st]
        p[st, c.STUDYING] = 0.0

    # 5. Moves inside the blocks.
    fn = float(params.get("life.within.farm_nonfarm"))
    sg = float(params.get("life.within.self_gig"))
    hr = float(params.get("life.within.homemaker_retired"))
    nonfarm = _split(x.shares, c.SELF_EMPLOYED, (c.SELF_EMPLOYED, c.GIG))
    farm = stage == c.FARM
    p[farm, c.SELF_EMPLOYED] += fn * nonfarm[farm, 0]
    p[farm, c.GIG] += fn * nonfarm[farm, 1]
    for a, b in ((c.SELF_EMPLOYED, c.GIG), (c.GIG, c.SELF_EMPLOYED)):
        m = stage == a
        p[m, c.FARM] += fn
        p[m, b] += sg
    for a, b in ((c.HOMEMAKER, c.RETIRED), (c.RETIRED, c.HOMEMAKER)):
        p[stage == a, b] += hr

    # 6. Coming back to the stage left within the window.
    last = np.asarray(x.last_stage, dtype=np.int64)
    back = (last >= 0) & (last != stage) & (np.asarray(x.months_since_left) <= int(params.get("life.return.window_months")))
    idx = np.flatnonzero(back)
    p[idx, last[idx]] *= float(params.get("life.return.weight"))

    # 7. Employer shocks scale every move out of salaried.
    sal = stage == c.SALARIED
    p[sal] *= np.asarray(x.firm_shock, dtype=np.float64)[sal, None]

    # 8. Superannuation.
    sup = np.asarray(x.superannuation, dtype=bool)
    p[sup, c.RETIRED] = np.maximum(p[sup, c.RETIRED], float(params.get("life.retire.superannuation_prob")))

    # 9. No move into studying from the maximum study age.
    p[(np.asarray(x.age) >= int(params.get("life.study.max_age"))) & (stage != c.STUDYING), c.STUDYING] = 0.0

    # 10. Cap the moves out at 0.95; staying is the rest.
    p[np.arange(n), stage] = 0.0
    out = p.sum(axis=1)
    over = out > 0.95
    p[over] *= (0.95 / out[over])[:, None]
    p[np.arange(n), stage] = 1.0 - p.sum(axis=1)
    return p
