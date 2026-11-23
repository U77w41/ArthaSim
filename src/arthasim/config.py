"""Run configuration and tier presets."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import secrets
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator

_TIERS: dict[str, dict[str, Any]] = {
    "XS": dict(persons=10_000, employers=100, merchants=300, banks=3),
    "S": dict(persons=100_000, banks=12, nbfcs=2, builder="population",
              districts=["metro_archetype", "rural_archetype"]),
}


class Config(BaseModel):
    tier_name: str
    start: dt.date = dt.date(2025, 4, 1)
    persons: int = Field(ge=1)
    employers: int | None = Field(default=None, ge=0)      # spike builder only
    merchants: int | None = Field(default=None, ge=1)      # spike builder only
    banks: int = Field(ge=1)
    nbfcs: int = Field(default=0, ge=0)
    builder: Literal["spike", "population"] = "spike"
    districts: list[str] = Field(default_factory=list)     # population builder only
    localities_per_district: int = Field(default=20, ge=1)
    slots_per_day: int = 96
    out_dir: str = "runs"
    params_path: str = "params/registry.yaml"
    param_overrides: dict[str, Any] = Field(default_factory=dict)
    # Keys the run's random draws and identifiers when set; never written to disk (see `hash` and `to_yaml`).
    release_secret: SecretStr | None = None

    @field_validator("release_secret")
    @classmethod
    def _secret_format(cls, v: SecretStr | None) -> SecretStr | None:
        if v is not None:
            text = v.get_secret_value()
            if not re.fullmatch(r"[0-9a-fA-F]+", text) or len(text) < 32 or len(text) % 2:
                raise ValueError("release_secret must be an even number of hex digits, at least 32 "
                                 "(arthasim.new_release_secret() makes one)")
        return v

    @field_validator("slots_per_day")
    @classmethod
    def _slots_fixed(cls, v: int) -> int:
        if v != 96:
            raise ValueError("slots_per_day must be 96")
        return v

    @model_validator(mode="after")
    def _builder_rules(self) -> "Config":
        if self.builder == "spike":
            if self.employers is None or self.merchants is None:
                raise ValueError("the spike builder needs employers and merchants")
        else:
            if not self.districts:
                raise ValueError("the population builder needs at least one district")
            if self.employers is not None or self.merchants is not None:
                raise ValueError("the population builder derives employers and merchants; leave them unset")
        return self

    @classmethod
    def tier(cls, name: str, **overrides: Any) -> "Config":
        if name not in _TIERS:
            raise ValueError(f"unknown tier {name!r}; available: {sorted(_TIERS)}")
        return cls(tier_name=name, **{**_TIERS[name], **overrides})

    @classmethod
    def from_yaml(cls, path: str | Path) -> "Config":
        return cls(**yaml.safe_load(Path(path).read_text()))

    def to_yaml(self, path: str | Path) -> None:
        """Write the config. The release secret is never written."""
        Path(path).write_text(yaml.safe_dump(self.model_dump(mode="json", exclude={"release_secret"}), sort_keys=True))

    def with_params(self, **overrides: Any) -> "Config":
        return self.model_copy(update={"param_overrides": {**self.param_overrides, **overrides}})

    def secret_bytes(self) -> bytes | None:
        return bytes.fromhex(self.release_secret.get_secret_value()) if self.release_secret is not None else None

    def hash(self) -> str:
        """Unchanged from earlier versions when no secret is set; with one, it covers a keyed digest of it."""
        fields = self.model_dump(mode="json", exclude={"release_secret"})
        secret = self.secret_bytes()
        if secret is not None:
            fields["release_secret"] = hashlib.blake2b(b"arthasim.config-hash", key=secret, digest_size=32).hexdigest()
        blob = json.dumps(fields, sort_keys=True)
        return hashlib.sha256(blob.encode()).hexdigest()


def new_release_secret() -> str:
    """A fresh 256-bit release secret, as 64 hex digits."""
    return secrets.token_hex(32)
