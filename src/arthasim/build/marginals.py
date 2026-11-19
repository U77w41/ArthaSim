"""District marginals and association priors, read from params/population."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, model_validator

_DEFAULT_ROOT = "params/population"


def _is_distribution(shares: list[float], length: int) -> bool:
    return len(shares) == length and min(shares) >= 0 and abs(sum(shares) - 1.0) < 1e-6


class DistrictMarginals(BaseModel):
    id: str
    name: str
    kind: Literal["metro", "rural"]
    state_code: str | None = None
    district_code: str | None = None
    status: str
    adult_population: int
    age_band: list[float]
    sex: list[float]
    education: list[float]
    life_stage: list[list[float]]          # two rows: F, then M
    household_adults: list[float]          # households with 1 to 5 adults
    dependants_mean: float

    @model_validator(mode="after")
    def _check(self) -> "DistrictMarginals":
        checks = [("age_band", self.age_band, 5), ("sex", self.sex, 2), ("education", self.education, 5),
                  ("household_adults", self.household_adults, 5)]
        checks += [(f"life_stage[{i}]", row, 9) for i, row in enumerate(self.life_stage)]
        for name, shares, length in checks:
            if not _is_distribution(shares, length):
                raise ValueError(f"{self.id}: {name} must be {length} non-negative shares summing to 1")
        if len(self.life_stage) != 2 or self.adult_population <= 0 or self.dependants_mean < 0:
            raise ValueError(f"{self.id}: invalid life_stage rows, adult_population or dependants_mean")
        return self


class Priors(BaseModel):
    age_life_stage: list[list[float]]      # 5 age bands by 9 life stages
    age_education: list[list[float]]       # 5 age bands by 5 education levels

    @model_validator(mode="after")
    def _check(self) -> "Priors":
        for name, table, width in (("age_life_stage", self.age_life_stage, 9),
                                   ("age_education", self.age_education, 5)):
            if len(table) != 5 or any(len(r) != width or min(r) < 0 for r in table):
                raise ValueError(f"priors: {name} must be 5 rows of {width} non-negative weights")
        return self


def _resolve(root: str | Path) -> Path:
    root = Path(root)
    if root.is_absolute() or root.exists():
        return root
    return Path(__file__).resolve().parents[3] / root


def load_district(name: str, root: str | Path = _DEFAULT_ROOT) -> DistrictMarginals:
    path = _resolve(root) / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"no district file {path}")
    return DistrictMarginals(**yaml.safe_load(path.read_text()))


def load_priors(root: str | Path = _DEFAULT_ROOT) -> Priors:
    return Priors(**yaml.safe_load((_resolve(root) / "priors.yaml").read_text()))
