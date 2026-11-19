"""The phase 0 spike behaviour, as modules."""
from __future__ import annotations

from arthasim.modules import consumption, income
from arthasim.modules.base import BehaviourModule


class SpikeIncome(BehaviourModule):
    name = "spike_income"

    def intents(self, world, day):
        return income.intents(world.state, world.params, world.seed, day)


class SpikeConsumption(BehaviourModule):
    name = "spike_consumption"

    def intents(self, world, day):
        return consumption.intents(world.state, world.params, world.seed, day)
