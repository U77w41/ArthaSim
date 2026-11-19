"""Group adults into households that match each district's size distribution."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from arthasim.build.categories import F, M
from arthasim.build.ipf import integerise
from arthasim.build.marginals import DistrictMarginals
from arthasim.build.population import Persons
from arthasim.engine import rng
from arthasim.params import ParamRegistry


@dataclass
class Households:
    household_of_person: np.ndarray     # one entry per person
    district: np.ndarray                # the rest: one entry per household
    locality: np.ndarray
    adults: np.ndarray
    dependants: np.ndarray
    head: np.ndarray                    # person index of the oldest member


def _keyed_order(seed: int, stream: str, ids: np.ndarray) -> np.ndarray:
    return ids[np.argsort(rng.uniform(seed, rng.stream_id(stream), ids, 0), kind="stable")]


def _sizes_for(n_persons: int, shares: np.ndarray, seed: int, first_id: int) -> np.ndarray:
    """Household sizes (in adults) that add up to exactly `n_persons`."""
    mean = float((shares * np.arange(1, 6)).sum())
    n_households = max(1, int(round(n_persons / mean)))
    sizes = np.repeat(np.arange(1, 6), integerise(shares, n_households))
    sizes = sizes[np.argsort(rng.uniform(seed, rng.stream_id("hh.size"), first_id + np.arange(sizes.size), 0),
                             kind="stable")]
    total = np.cumsum(sizes)
    if total[-1] < n_persons:                       # rounding left some adults over
        extra = n_persons - int(total[-1])
        sizes = np.concatenate([sizes, np.full(extra // 2, 2), np.full(extra % 2, 1)])
    else:
        cut = int(np.searchsorted(total, n_persons, side="left"))
        sizes = sizes[:cut + 1].copy()
        sizes[cut] -= int(total[cut]) - n_persons   # the last household takes the remainder
    return sizes.astype(np.int64)


def form_households(persons: Persons, districts: Sequence[DistrictMarginals], n_localities: int,
                    params: ParamRegistry, seed: int) -> Households:
    n = len(persons)
    household_of_person = np.full(n, -1, dtype=np.int64)
    lo_age, hi_age = params.get("hh.dependant_ages")
    parts: dict[str, list[np.ndarray]] = {k: [] for k in ("district", "locality", "adults", "dependants")}
    next_id = 0
    for di, d in enumerate(districts):
        members = np.flatnonzero(persons.district == di)
        if members.size == 0:
            continue
        sizes = _sizes_for(members.size, np.asarray(d.household_adults), seed, next_id)
        ids = next_id + np.arange(sizes.size, dtype=np.int64)
        # Alternate man, woman while both remain, then whoever is left.
        men = _keyed_order(seed, "hh.member", members[persons.sex[members] == M])
        women = _keyed_order(seed, "hh.member", members[persons.sex[members] == F])
        pairs = min(men.size, women.size)
        sequence = np.empty(members.size, dtype=np.int64)
        sequence[0:2 * pairs:2], sequence[1:2 * pairs:2] = men[:pairs], women[:pairs]
        sequence[2 * pairs:] = np.concatenate([men[pairs:], women[pairs:]])
        household_of_person[sequence] = np.repeat(ids, sizes)

        eligible = np.zeros(sizes.size, dtype=bool)
        in_range = members[(persons.age[members] >= lo_age) & (persons.age[members] <= hi_age)]
        eligible[household_of_person[in_range] - next_id] = True
        dependants = rng.poisson(seed, rng.stream_id("hh.dependants"), ids, 0, d.dependants_mean)
        locality = np.minimum((rng.uniform(seed, rng.stream_id("hh.locality"), ids, 0) * n_localities).astype(np.int64),
                              n_localities - 1)
        parts["district"].append(np.full(sizes.size, di, dtype=np.int64))
        parts["locality"].append(locality)
        parts["adults"].append(sizes)
        parts["dependants"].append(np.where(eligible, dependants, 0))
        next_id += sizes.size

    # Head: oldest member, lowest index on ties.
    order = np.lexsort((np.arange(n), -persons.age, household_of_person))
    first = np.flatnonzero(np.diff(household_of_person[order], prepend=-1) != 0)
    out = {k: np.concatenate(v) if v else np.empty(0, dtype=np.int64) for k, v in parts.items()}
    return Households(household_of_person=household_of_person, head=order[first], **out)
