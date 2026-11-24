"""Versioned parameter registry: every number a module uses lives here."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import polars as pl
import yaml

_STATUS = {"verified", "unverified", "assumption"}
_ROLE = {"input", "target", "holdout"}
_COLUMNS = ["id", "value", "unit", "as_of", "source", "status", "role"]


class ParamRegistry:
    # While the world simulates a day it sets this to a set, and `get` records every id it serves.
    _reads: set[str] | None = None

    def __init__(self, entries: dict[str, dict[str, Any]]):
        self._entries = entries

    def __contains__(self, param_id: str) -> bool:
        return param_id in self._entries

    @classmethod
    def load(cls, path: str | Path, overrides: Mapping[str, Any] | None = None) -> "ParamRegistry":
        rows = yaml.safe_load(Path(path).read_text()) or []
        entries: dict[str, dict[str, Any]] = {}
        for row in rows:
            pid = row["id"]
            if pid in entries:
                raise ValueError(f"duplicate parameter id {pid!r}")
            if row.get("status") not in _STATUS:
                raise ValueError(f"{pid}: status must be one of {sorted(_STATUS)}")
            if row.get("role") not in _ROLE:
                raise ValueError(f"{pid}: role must be one of {sorted(_ROLE)}")
            entries[pid] = {
                "id": pid,
                "value": row["value"],
                "unit": str(row.get("unit", "")),
                "as_of": str(row.get("as_of", "")),
                "source": str(row.get("source", "")),
                "status": row["status"],
                "role": row["role"],
            }
        registry = cls(entries)
        for pid, value in (overrides or {}).items():
            registry = registry.override(pid, value)
        return registry

    def get(self, param_id: str) -> Any:
        value = self._entries[param_id]["value"]
        if self._reads is not None:
            self._reads.add(param_id)
        return value

    def override(self, param_id: str, value: Any) -> "ParamRegistry":
        if param_id not in self._entries:
            raise KeyError(param_id)
        entries = {k: dict(v) for k, v in self._entries.items()}
        entries[param_id]["value"] = value
        return ParamRegistry(entries)

    def table(self) -> pl.DataFrame:
        rows = [{**e, "value": json.dumps(e["value"])} for e in self._entries.values()]
        return pl.DataFrame(rows, schema={c: pl.String for c in _COLUMNS})

    def version(self) -> str:
        pairs = sorted((k, json.dumps(v["value"], sort_keys=True)) for k, v in self._entries.items())
        return hashlib.sha256(json.dumps(pairs).encode()).hexdigest()
