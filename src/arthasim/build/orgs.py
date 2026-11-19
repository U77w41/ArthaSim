"""Employers, merchants and national billers."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import numpy as np

from arthasim.build import categories as c
from arthasim.build.attributes import Attributes
from arthasim.build.ipf import integerise
from arthasim.build.marginals import DistrictMarginals
from arthasim.build.population import Persons
from arthasim.engine import rng
from arthasim.params import ParamRegistry

BILLERS = ["telecom", "electricity", "ecommerce", "amc"]


@dataclass
class Orgs:
    employer_district: np.ndarray
    employer_sector: np.ndarray
    employer_capacity: np.ndarray
    person_employer: np.ndarray          # employer index, -1 if none
    merchant_district: np.ndarray
    merchant_locality: np.ndarray
    merchant_category: np.ndarray
    merchant_accepts_upi: np.ndarray
    merchant_accepts_card: np.ndarray
    billers: list[str] = field(default_factory=lambda: list(BILLERS))


def _capacities(n_staff: int, classes: list[list[float]], seed: int, group_key: int) -> np.ndarray:
    """Employer capacities for one (district, sector) group, enough to hold `n_staff`."""
    ids = group_key * 10_000_000 + np.arange(n_staff, dtype=np.int64)     # at most one employer per person
    cum = np.cumsum([row[2] for row in classes])
    which = np.minimum(np.searchsorted(cum / cum[-1], rng.uniform(seed, rng.stream_id("org.size"), ids, 0),
                                       side="right"), len(classes) - 1)
    lo = np.array([row[0] for row in classes], dtype=np.int64)[which]
    hi = np.array([row[1] for row in classes], dtype=np.int64)[which]
    capacity = lo + (rng.uniform(seed, rng.stream_id("org.capacity"), ids, 0) * (hi - lo + 1)).astype(np.int64)
    capacity = np.minimum(capacity, hi)
    cut = int(np.searchsorted(np.cumsum(capacity), n_staff, side="left"))
    return capacity[:cut + 1]


def build_orgs(persons: Persons, attributes: Attributes, districts: Sequence[DistrictMarginals],
               n_localities: int, params: ParamRegistry, seed: int) -> Orgs:
    n = len(persons)
    S = rng.stream_id
    classes = params.get("org.employer_size_classes")
    salaried = persons.life_stage == c.SALARIED

    # Employers: one group per (district, sector) that has salaried persons.
    person_employer = np.full(n, -1, dtype=np.int64)
    e_district, e_sector, e_capacity = [], [], []
    n_employers = 0
    for di in range(len(districts)):
        for sector in range(len(c.SECTORS)):
            staff = np.flatnonzero(salaried & (persons.district == di) & (attributes.sector == sector))
            if staff.size == 0:
                continue
            capacity = _capacities(staff.size, classes, seed, di * len(c.SECTORS) + sector)
            staff = staff[np.argsort(rng.uniform(seed, S("org.assign"), staff, 0), kind="stable")]
            slot = np.searchsorted(np.cumsum(capacity), np.arange(staff.size), side="right")
            person_employer[staff] = n_employers + slot
            e_district.append(np.full(capacity.size, di, dtype=np.int64))
            e_sector.append(np.full(capacity.size, sector, dtype=np.int64))
            e_capacity.append(capacity)
            n_employers += capacity.size

    # Merchants: a count per district, split by category, with a grocery in every locality.
    shares = np.asarray(params.get("org.merchant_category_shares"))
    m_district, m_locality, m_category = [], [], []
    n_merchants = 0
    for di in range(len(districts)):
        count = max(int((persons.district == di).sum()) // int(params.get("org.persons_per_merchant")), 1)
        category = np.repeat(np.arange(len(shares)), integerise(shares, count))
        ids = n_merchants + np.arange(count, dtype=np.int64)
        locality = np.minimum((rng.uniform(seed, S("org.locality"), ids, 0) * n_localities).astype(np.int64),
                              n_localities - 1)
        missing = np.setdiff1d(np.arange(n_localities), locality[category == c.GROCERY])
        category = np.concatenate([category, np.full(missing.size, c.GROCERY)])
        locality = np.concatenate([locality, missing])
        m_district.append(np.full(category.size, di, dtype=np.int64))
        m_locality.append(locality)
        m_category.append(category)
        n_merchants += category.size

    def cat(parts: list[np.ndarray]) -> np.ndarray:
        return np.concatenate(parts).astype(np.int64) if parts else np.empty(0, dtype=np.int64)

    merchant_district = cat(m_district)
    ids = np.arange(merchant_district.size, dtype=np.int64)
    kinds = np.array([d.kind for d in districts])[merchant_district] if ids.size else np.empty(0, dtype=object)
    upi_rate = np.array([params.get("org.merchant_upi_acceptance")[k] for k in kinds], dtype=np.float64)
    card_rate = np.array([params.get("org.merchant_card_acceptance")[k] for k in kinds], dtype=np.float64)
    return Orgs(
        employer_district=cat(e_district), employer_sector=cat(e_sector), employer_capacity=cat(e_capacity),
        person_employer=person_employer,
        merchant_district=merchant_district, merchant_locality=cat(m_locality), merchant_category=cat(m_category),
        merchant_accepts_upi=rng.uniform(seed, S("org.upi"), ids, 0) < upi_rate,
        merchant_accepts_card=rng.uniform(seed, S("org.card"), ids, 0) < card_rate)
