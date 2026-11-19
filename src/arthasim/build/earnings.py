"""Starting pay: a Mincer-type equation. Reused by the income module."""
from __future__ import annotations

import numpy as np

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
