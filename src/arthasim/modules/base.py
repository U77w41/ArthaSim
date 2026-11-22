"""Base class for behaviour modules."""
from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

import polars as pl

from arthasim.engine.intents import Intents

if TYPE_CHECKING:
    from arthasim.world import World


class BehaviourModule:
    """A unit of behaviour. The engine calls `monthly` at the start of each month (and on a
    world's first simulated day), then `intents` every day. Modules read state and emit
    intents; only settlement changes balances."""

    name = "module"

    def monthly(self, world: "World", month: dt.date) -> None:
        return None

    def intents(self, world: "World", day: dt.date) -> Intents | pl.DataFrame:
        return Intents.empty()

    def tables(self) -> dict[str, pl.DataFrame]:
        """Fact-table frames produced since the last call; the world stores them under the day's month."""
        return {}
