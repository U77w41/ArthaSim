"""Human capital, traits, sector and income for each person."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from arthasim.build import categories as c
from arthasim.build.earnings import starting_pay
from arthasim.build.marginals import DistrictMarginals
from arthasim.build.population import Persons
from arthasim.engine import rng
from arthasim.params import ParamRegistry

TRAITS = ("risk_appetite", "habit_strength", "price_sensitivity", "trust_in_offers")


@dataclass
class Attributes:
    domain_skill: np.ndarray
    digital_literacy: np.ndarray
    financial_literacy: np.ndarray
    risk_appetite: np.ndarray
    habit_strength: np.ndarray
    price_sensitivity: np.ndarray
    trust_in_offers: np.ndarray
    sector: np.ndarray                  # -1 when not earning
    monthly_income_paise: np.ndarray


def attach_attributes(persons: Persons, districts: Sequence[DistrictMarginals], params: ParamRegistry,
                      seed: int) -> Attributes:
    n = len(persons)
    ids = np.arange(n, dtype=np.int64)
    edu, age, stage = persons.education, persons.age, persons.life_stage
    is_metro = np.array([d.kind == "metro" for d in districts])[persons.district]
    experience = np.maximum(0, age - np.asarray(params.get("earn.start_age_by_education"))[edu]).astype(np.float64)
    noise_sd = params.get("attr.noise_sd")

    def u(stream: str) -> np.ndarray:
        return rng.uniform(seed, rng.stream_id(stream), ids, 0)

    def noise(stream: str) -> np.ndarray:
        return noise_sd * rng.normal(seed, rng.stream_id(stream), ids, 0)

    def unit(x: np.ndarray) -> np.ndarray:
        return np.clip(x, 0.0, 1.0).astype(np.float32)

    digital = unit(np.asarray(params.get("attr.digital.base_by_education"))[edu]
                   + params.get("attr.digital.metro_bonus") * is_metro
                   - params.get("attr.digital.age_penalty") * np.maximum(0, age - 35) / 50
                   + noise("attr.digital"))
    financial = unit(np.asarray(params.get("attr.financial.base_by_education"))[edu] + noise("attr.financial"))
    skill = unit(params.get("attr.skill.base") + params.get("attr.skill.per_education_level") * edu
                 + params.get("attr.skill.per_year_experience") * experience + noise("attr.skill"))
    # Kumaraswamy(a, b): a Beta-like distribution with a closed-form inverse CDF.
    traits = {name: unit((1 - (1 - u(f"attr.{name}")) ** (1 / b)) ** (1 / a))
              for name, (a, b) in params.get("attr.trait_shapes").items()}

    # Sector: farm is agriculture; other earners draw from the district kind's non-farm shares.
    earning = np.isin(stage, c.EARNING)
    sector = np.full(n, -1, dtype=np.int64)
    draw = u("attr.sector")
    for kind in ("metro", "rural"):
        shares = np.asarray(params.get(f"org.sector_shares.{kind}"))[1:]
        cum = np.cumsum(shares / shares.sum())
        rows = earning & (is_metro == (kind == "metro"))
        sector[rows] = 1 + np.minimum(np.searchsorted(cum, draw[rows], side="right"), len(cum) - 1)
    sector[stage == c.FARM] = 0

    z = rng.normal(seed, rng.stream_id("attr.pay"), ids, 0)
    multiplier = np.zeros(n)
    for name, value in params.get("earn.stage_multiplier").items():
        multiplier[stage == c.LIFE_STAGE.index(name)] = value
    pay = starting_pay(edu, experience, is_metro, np.maximum(sector, 0), z, params) * multiplier
    pension = params.get("earn.pension_ratio") * starting_pay(
        edu, experience, is_metro, np.full(n, c.OTHER_SERVICES), np.zeros(n), params)
    income = np.where(earning, np.maximum(100, np.rint(pay)),
                      np.where(stage == c.RETIRED, np.maximum(100, np.rint(pension)), 0)).astype(np.int64)

    return Attributes(domain_skill=skill, digital_literacy=digital, financial_literacy=financial,
                      sector=sector.astype(np.int8), monthly_income_paise=income, **traits)
