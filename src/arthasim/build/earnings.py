"""Starting pay: a Mincer-type equation. Reused by the income module."""
from __future__ import annotations

import numpy as np

from arthasim.build import categories as c
from arthasim.params import ParamRegistry


def starting_pay(education: np.ndarray, experience: np.ndarray, is_metro: np.ndarray, sector: np.ndarray,
                 z: np.ndarray, params: ParamRegistry) -> np.ndarray:
    """Monthly pay in paise (float). `z` is a standard normal draw."""
    returns = np.asarray(params.get("earn.return_by_education"))[education]
    sector_premium = np.asarray(params.get("earn.premium.by_sector"))[sector]
    log_pay = (returns
               + params.get("earn.experience.linear") * experience
               - params.get("earn.experience.quadratic") * experience ** 2
               + params.get("earn.premium.metro") * np.asarray(is_metro, dtype=np.float64)
               + sector_premium
               + params.get("earn.sigma") * z)
    return params.get("earn.base_paise") * np.exp(log_pay)


def income_for(stage: np.ndarray, education: np.ndarray, age: np.ndarray, is_metro: np.ndarray, sector: np.ndarray,
               z: np.ndarray, params: ParamRegistry) -> np.ndarray:
    """Monthly income in paise (int64): earning stages from the Mincer equation times the stage multiplier,
    retired the pension rule, everyone else 0."""
    stage = np.asarray(stage)
    n = stage.shape[0]
    experience = np.maximum(0, np.asarray(age) - np.asarray(params.get("earn.start_age_by_education"))[education]
                            ).astype(np.float64)
    earning = np.isin(stage, c.EARNING)
    multiplier = np.zeros(n)
    for name, value in params.get("earn.stage_multiplier").items():
        multiplier[stage == c.LIFE_STAGE.index(name)] = value
    pay = starting_pay(education, experience, is_metro, np.maximum(sector, 0), z, params) * multiplier
    pension = params.get("earn.pension_ratio") * starting_pay(
        education, experience, is_metro, np.full(n, c.OTHER_SERVICES), np.zeros(n), params)
    return np.where(earning, np.maximum(100, np.rint(pay)),
                    np.where(stage == c.RETIRED, np.maximum(100, np.rint(pension)), 0)).astype(np.int64)
