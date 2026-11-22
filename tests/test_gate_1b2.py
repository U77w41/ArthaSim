import datetime as dt
import numpy as np
import polars as pl
import pytest
from arthasim import Config, World
from arthasim.build import categories as c

MONTHS = [f"2025-{m:02d}" for m in range(4, 13)] + [f"2026-{m:02d}" for m in range(1, 4)]


@pytest.mark.slow
def test_plan_1b2_gate(tmp_path):
    world = World.build(Config.tier("S", out_dir=str(tmp_path)), seed=7)
    run = world.run(until="2026-03-31")
    assert run.manifest["days"] == 365
    s, t = world.state, world.state.life.targets
    p = s.population.persons
    esm = run.table("entity_state_monthly").collect()
    assert esm["month"].unique().sort().to_list() == MONTHS
    for month in MONTHS:
        m = esm.filter(pl.col("month") == month).sort("entity_id")
        assert m.height == len(p)
        stage = np.array([c.LIFE_STAGE.index(x) for x in m["life_stage"].to_list()])
        age = m["age"].to_numpy()
        for d in range(t.n_districts):
            for sex in (c.F, c.M):
                sel = (p.district == d) & (p.sex == sex)
                cell, want = t.counts(dt.date.fromisoformat(month + "-01"), d, sex, age[sel])
                got = np.zeros_like(want)
                np.add.at(got, (cell, stage[sel]), 1)
                assert np.array_equal(got, want), (month, d, sex)
