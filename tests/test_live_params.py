"""Parameters a run reads, and modules that follow a changed registry (plan 1d-2, Task 2)."""
import pickle
from datetime import date

import numpy as np

from arthasim import Config, World
from arthasim.build import categories as c
from arthasim.dbt.schemes import default_schemes
from arthasim.life.jobs import firm_shock
from arthasim.modules.spending import Consumption
from helpers import P


def build(tmp_path):
    return World.build(Config.tier("S", persons=2_000, out_dir=str(tmp_path)), seed=7)


def test_reads_are_recorded_only_on_simulated_days(tmp_path):
    world = build(tmp_path)
    assert world._params_read == set()
    read = world.run(until="2025-04-02").manifest["params_read"]
    assert read == sorted(read) and {"rail.upi.limit_paise", "consumption.buffer_target_months"} <= set(read)
    assert "attr.noise_sd" not in read                       # read only at build


def test_targets_follow_set_params(tmp_path):
    world = build(tmp_path)
    T = world.state.life.targets
    month = date(2025, 5, 1)
    before = T.shares(month, 0, c.F).copy()
    world.set_params(world.params.override("life.gig.nonfarm_share", {2020: 0.9, 2029: 0.9}))
    assert T.params is world.params and not np.allclose(T.shares(month, 0, c.F), before)
    world.set_params(world.params.override("life.layoff.employer_shock_sigma", 0.0))
    assert np.allclose(firm_shock(world.state, 7, month.toordinal()), 1.0)


def test_consumption_cache_follows_the_registry(tmp_path):
    world = build(tmp_path)
    m = Consumption()
    a = m._setup(world)
    assert m._setup(world) is a
    shares = list(world.params.get("consumption.category_shares.metro"))
    shares[0], shares[1] = shares[1], shares[0]
    world.set_params(world.params.override("consumption.category_shares.metro", shares))
    b = m._setup(world)
    assert b is not a and not np.array_equal(a.shares, b.shares)
    assert pickle.loads(pickle.dumps(m))._cache is None


def test_default_schemes_pickle():
    again = pickle.loads(pickle.dumps(default_schemes()))
    assert again[1].pays_on(date(2025, 5, 5), P) and not again[1].pays_on(date(2025, 5, 6), P)
