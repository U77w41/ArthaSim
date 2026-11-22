"""Unpaid family helpers exist only inside a family farm or business (decided by the project owner)."""
from __future__ import annotations

import numpy as np

from arthasim.build import categories as c

HELPER_STAGES = (c.FARM, c.SELF_EMPLOYED)


def _owners(stage: np.ndarray, household: np.ndarray, owner: np.ndarray) -> np.ndarray:
    """Per person: how many members of their household are `owner` and in the same stage."""
    key = np.asarray(household, dtype=np.int64) * 9 + np.asarray(stage, dtype=np.int64)
    count = np.bincount(key[owner], minlength=int(key.max()) + 1 if key.size else 0)
    return count[key] if key.size else np.zeros(0, dtype=np.int64)


def assign_helpers(stage: np.ndarray, household: np.ndarray, candidate: np.ndarray) -> np.ndarray:
    """Helper iff a candidate in farm or self_employed whose household has a non-candidate in the same stage."""
    in_stage = np.isin(stage, HELPER_STAGES)
    candidate = np.asarray(candidate, dtype=bool)
    return candidate & in_stage & (_owners(stage, household, in_stage & ~candidate) > 0)


def orphaned(stage: np.ndarray, household: np.ndarray, helper: np.ndarray) -> np.ndarray:
    """Helpers whose household has no own-account member in their stage."""
    helper = np.asarray(helper, dtype=bool) & np.isin(stage, HELPER_STAGES)
    owner = np.isin(stage, HELPER_STAGES) & ~helper
    return helper & (_owners(stage, household, owner) == 0)
