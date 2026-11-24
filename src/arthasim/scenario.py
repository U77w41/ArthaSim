"""A scenario: an ordered, immutable list of interventions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from arthasim.interventions import Intervention


@dataclass(frozen=True)
class Scenario:
    interventions: tuple[Intervention, ...] = ()

    @classmethod
    def baseline(cls) -> "Scenario":
        return cls()

    def add(self, *interventions: Intervention) -> "Scenario":
        """A new scenario with the interventions appended."""
        for iv in interventions:
            if not isinstance(iv, Intervention):
                raise TypeError(f"not an intervention: {iv!r}")
        return Scenario(self.interventions + tuple(interventions))

    def details(self) -> list[dict[str, Any]]:
        return [{"kind": type(iv).__name__, **iv.details()} for iv in self.interventions]
