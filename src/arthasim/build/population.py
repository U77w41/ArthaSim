"""Synthetic adults fitted to district marginals."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from arthasim.build.categories import AGE_EDGES, N_AGE_GROUPS, age_group
from arthasim.build.ipf import integerise, ipf
from arthasim.build.marginals import DistrictMarginals, Priors
from arthasim.engine import rng
from arthasim.life.align import align
from arthasim.life.targets import age_index, cell_counts

ALIGN_FLOOR = 1e-6          # life.rake.floor


@dataclass
class Persons:
    """One entry per adult, ordered by district. Values are category indices."""
    district: np.ndarray
    age: np.ndarray
    age_band: np.ndarray
    sex: np.ndarray
    education: np.ndarray
    life_stage: np.ndarray

    def __len__(self) -> int:
        return int(self.district.shape[0])


def _band_shares(stage_shares: np.ndarray, di: int) -> np.ndarray:
    """(5 age bands, 2 sexes, 9 stages): mean of the single-age shares over each band's ages, renormalised."""
    out = np.zeros((5, 2, 9))
    for b in range(5):
        ages = age_index(np.arange(AGE_EDGES[b], AGE_EDGES[b + 1]))
        for x in range(2):
            m = stage_shares[di, x, ages].mean(axis=0)
            out[b, x] = m / m.sum()
    return out


def _ages_given_stage(stage_shares, di, band, sex, stage, u) -> np.ndarray:
    """Age within the band, P(age) proportional to the share of the person's stage at that age."""
    age = np.empty(band.size, dtype=np.int64)
    for b in range(5):
        lo, hi = AGE_EDGES[b], AGE_EDGES[b + 1]
        idx = age_index(np.arange(lo, hi))
        for x in range(2):
            for s in range(9):
                m = (band == b) & (sex == x) & (stage == s)
                if not m.any():
                    continue
                w = stage_shares[di, x, idx, s]
                w = w if w.sum() > 0 else np.ones(hi - lo)
                cdf = np.cumsum(w) / w.sum()
                age[m] = lo + np.minimum(np.searchsorted(cdf, u[m], side="right"), hi - lo - 1)
    return age


def synthesise_persons(districts: Sequence[DistrictMarginals], priors: Priors, n: int, seed: int,
                       stage_shares: np.ndarray | None = None) -> Persons:
    """Adults fitted to the district marginals. With `stage_shares` ((n_districts, 2, N_AGES, 9), from
    `Targets.start_array`), life stages follow those shares by age and every (district, sex, age group) cell
    is aligned exactly to its integer targets; otherwise the YAML life_stage rows and the age prior are used."""
    per_district = integerise(np.array([d.adult_population for d in districts], dtype=np.float64), n)
    # Seed table over (age band, sex, education, life stage).
    if stage_shares is None:
        prior = (np.asarray(priors.age_life_stage)[:, None, None, :]
                 * np.asarray(priors.age_education)[:, None, :, None] * np.ones((5, 2, 5, 9)))
    else:
        prior = np.asarray(priors.age_education)[:, None, :, None] * np.ones((5, 2, 5, 9))
    n_cells = len(districts) * 2 * N_AGE_GROUPS
    edges = np.asarray(AGE_EDGES)
    cols: dict[str, list[np.ndarray]] = {k: [] for k in ("district", "age", "age_band", "sex", "education", "life_stage")}
    offset = 0
    for di, (d, count) in enumerate(zip(districts, per_district.tolist())):
        if count == 0:
            continue
        if stage_shares is None:
            stage_margin = ((1, 3), np.asarray(d.life_stage) * np.asarray(d.sex)[:, None])
        else:
            joint = np.asarray(d.age_band)[:, None, None] * np.asarray(d.sex)[None, :, None]
            stage_margin = ((0, 1, 3), joint * _band_shares(stage_shares, di))
        weights = ipf(prior, [((0,), d.age_band), ((1,), d.sex), ((2,), d.education), stage_margin])
        cells = integerise(weights, count)
        band, sex, edu, stage = np.unravel_index(np.repeat(np.arange(cells.size), cells.ravel()), cells.shape)
        ids = np.arange(offset, offset + count, dtype=np.int64)
        # Keyed random order, so a person's id says nothing about their attributes.
        order = np.argsort(rng.uniform(seed, rng.stream_id("pop.order"), ids, 0), kind="stable")
        band, sex, edu, stage = band[order], sex[order], edu[order], stage[order]
        if stage_shares is None:
            lo, hi = edges[band], edges[band + 1]
            age = np.minimum(lo + (rng.uniform(seed, rng.stream_id("pop.age"), ids, 0) * (hi - lo)).astype(np.int64), hi - 1)
        else:
            u = rng.uniform(seed, rng.stream_id("pop.age_given_stage"), ids, 0)
            age = _ages_given_stage(stage_shares, di, band, sex, stage, u)
            stage = _align_start(stage_shares, di, age, sex, stage, ids, seed, n_cells)
            band = np.searchsorted(edges[1:-1], age, side="right")
        for key, value in (("district", np.full(count, di)), ("age", age), ("age_band", band), ("sex", sex),
                           ("education", edu), ("life_stage", stage)):
            cols[key].append(np.asarray(value, dtype=np.int64))
        offset += count
    return Persons(**{k: np.concatenate(v) if v else np.empty(0, dtype=np.int64) for k, v in cols.items()})


def _align_start(stage_shares, di, age, sex, stage, ids, seed, n_cells) -> np.ndarray:
    """One alignment pass: every (district, sex, age group) cell of this district lands on its start targets."""
    rows = stage_shares[di, sex, age_index(age)]
    cell = ((di * 2 + sex) * N_AGE_GROUPS + age_group(age)).astype(np.int64)
    targets = np.zeros((n_cells, 9), dtype=np.int64)
    for x in range(2):
        m = sex == x
        targets += cell_counts(rows[m], cell[m], n_cells)
    u = np.stack([rng.uniform(seed, rng.stream_id("pop.align"), ids, 0, d) for d in range(9)], axis=1)
    allowed = np.ones((n_cells, 9, 9), dtype=bool)
    return align(stage, rows, cell, targets, allowed, u, ALIGN_FLOOR)
