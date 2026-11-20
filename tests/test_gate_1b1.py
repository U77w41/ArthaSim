import polars as pl
import pytest
from arthasim import Config, World


@pytest.mark.slow
def test_plan_1b1_gate(tmp_path):
    runs = [World.build(Config.tier("S", out_dir=str(tmp_path / d)), seed=7).run(until="2025-06-29")
            for d in ("a", "b")]
    a, b = (r.manifest for r in runs)
    assert a["days"] == 90 and a["content_hash"] == b["content_hash"]
    purposes = set(runs[0].table("payments").select(pl.col("purpose").unique()).collect()["purpose"])
    assert "UNSPECIFIED" not in purposes
    assert {"SALARY", "EARNINGS", "PENSION", "REMITTANCE", "ALLOWANCE", "GROCERY", "FOOD", "FUEL", "PHARMACY", "APPAREL",
            "ELECTRONICS", "TRANSPORT", "SERVICES", "OTHER", "UTILITIES", "TELECOM", "MEDICAL"} <= purposes
