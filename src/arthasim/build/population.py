"""Synthetic adults fitted to district marginals."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from arthasim.build.categories import AGE_EDGES
from arthasim.build.ipf import integerise, ipf
from arthasim.build.marginals import DistrictMarginals, Priors
from arthasim.engine import rng


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


def synthesise_persons(districts: Sequence[DistrictMarginals], priors: Priors, n: int, seed: int) -> Persons:
    per_district = integerise(np.array([d.adult_population for d in districts], dtype=np.float64), n)
    # Seed table over (age band, sex, education, life stage).
    prior = (np.asarray(priors.age_life_stage)[:, None, None, :]
             * np.asarray(priors.age_education)[:, None, :, None] * np.ones((5, 2, 5, 9)))
    edges = np.asarray(AGE_EDGES)
    cols: dict[str, list[np.ndarray]] = {k: [] for k in ("district", "age", "age_band", "sex", "education", "life_stage")}
    offset = 0
    for di, (d, count) in enumerate(zip(districts, per_district.tolist())):
        if count == 0:
            continue
        sex_by_stage = np.asarray(d.life_stage) * np.asarray(d.sex)[:, None]
        weights = ipf(prior, [((0,), d.age_band), ((1,), d.sex), ((2,), d.education), ((1, 3), sex_by_stage)])
        cells = integerise(weights, count)
        band, sex, edu, stage = np.unravel_index(np.repeat(np.arange(cells.size), cells.ravel()), cells.shape)
        ids = np.arange(offset, offset + count, dtype=np.int64)
        # Keyed random order, so a person's id says nothing about their attributes.
        order = np.argsort(rng.uniform(seed, rng.stream_id("pop.order"), ids, 0), kind="stable")
        band, sex, edu, stage = band[order], sex[order], edu[order], stage[order]
        lo, hi = edges[band], edges[band + 1]
        age = np.minimum(lo + (rng.uniform(seed, rng.stream_id("pop.age"), ids, 0) * (hi - lo)).astype(np.int64), hi - 1)
        for key, value in (("district", np.full(count, di)), ("age", age), ("age_band", band), ("sex", sex),
                           ("education", edu), ("life_stage", stage)):
            cols[key].append(np.asarray(value, dtype=np.int64))
        offset += count
    return Persons(**{k: np.concatenate(v) if v else np.empty(0, dtype=np.int64) for k, v in cols.items()})
