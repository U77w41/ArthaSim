"""Plan 1d-2 gate (slow): resume at tier S reproduces an uninterrupted run byte for byte, and a two-seed DBT
experiment returns an effect with an interval."""
import polars as pl
import pytest

from arthasim import Config, Experiment, Scenario, World
from arthasim.interventions import DBTTransfer
from helpers import run_files

FARMERS = "life_stage == 'farm' and not helper"


@pytest.mark.slow
def test_plan_1d2_gate_resume(tmp_path):
    cfg = Config.tier("S", out_dir=str(tmp_path))
    plain = World.build(cfg, 7, path=tmp_path / "plain", checkpoints=False).run("2025-07-31")
    w = World.build(cfg, 7, path=tmp_path / "saved", checkpoints=False)
    w.run("2025-05-31")
    w.save(tmp_path / "ck")
    resumed = World.load(tmp_path / "ck", path_out=tmp_path / "resumed", checkpoints=False).run("2025-07-31")
    files = run_files(plain.path)
    assert files and run_files(resumed.path) == files
    assert resumed.manifest["content_hash"] == plain.manifest["content_hash"]


@pytest.mark.slow
def test_plan_1d2_gate_experiment(tmp_path):
    base = Scenario.baseline()
    treat = base.add(DBTTransfer("GATE_TRANCHE", 2000, FARMERS, ["2025-06-15"]))
    res = Experiment(Config.tier("S", out_dir=str(tmp_path)), base, {"dbt": treat}, [1, 2], "2025-06-01",
                     "2025-07-31").run(workers=2)

    def apbs(run):
        v = run.window("2025-06-01", "2025-07-31").metric("txn_volume", by="rail").filter(pl.col("rail") == "APBS")
        return v["value"][0]

    for b, t in zip(res.runs("baseline"), res.runs("dbt")):
        payees = t.sql("select count(*) as n from truth_dbt_monthly where scheme = 'GATE_TRANCHE' and enrolled")["n"][0]
        assert payees > 0 and apbs(t) - apbs(b) == payees
    eff = res.effect("cash_withdrawal", fill=0).filter(pl.col("arm") == "dbt")
    assert eff["n"][0] == 2 and eff["lo"][0] is not None and eff["hi"][0] is not None
    assert eff["lo"][0] <= eff["effect"][0] <= eff["hi"][0]
