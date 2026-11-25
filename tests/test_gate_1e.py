"""Plan 1e gate: the core validation suite on a calibrated tier S run (architecture section 18's phase 1 exit)."""
from pathlib import Path

import polars as pl
import pytest

from arthasim import Config, ParamRegistry, World
from arthasim.calibration import CalibrationResult
from arthasim.validation import load_suite

ROOT = Path(__file__).resolve().parents[1]
FITTED = ROOT / "params" / "calibration" / "fitted.yaml"


@pytest.mark.slow
def test_core_suite_on_a_calibrated_tier_s_run(tmp_path):
    fit = CalibrationResult.load(FITTED)
    # A calibration fitted to other inputs is stale: refit with scripts/calibrate.py.
    assert fit.registry_version == ParamRegistry.load(ROOT / "params" / "registry.yaml").version()
    config = fit.apply(Config.tier("S", out_dir=str(tmp_path)))
    run = World.build(config, seed=7, checkpoints=False).run("2025-11-30")
    table = run.validate("core").table()

    hard = table.filter(pl.col("kind") == "hard")
    assert (hard["status"] != "fail").all(), hard.filter(pl.col("status") == "fail")
    assert (hard["status"] == "pass").sum() == hard.height - 1          # only the flow matrix is left to the run
    others = table.filter(pl.col("kind") != "hard")
    assert (others["status"] != "skipped").all(), others.filter(pl.col("status") == "skipped")

    failed = set(table.filter(pl.col("status") == "fail")["check"].to_list())
    gaps = {c.id for c in load_suite("core") if c.gap}
    assert failed - gaps == set(), f"failing checks not listed as gaps: {sorted(failed - gaps)}"
    assert gaps - failed == set(), f"listed gaps that now pass (update the suite): {sorted(gaps - failed)}"
