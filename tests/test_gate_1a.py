import pytest
from arthasim import Config, World


@pytest.mark.slow
def test_plan_1a_gate(tmp_path):
    runs = [World.build(Config.tier("S", out_dir=str(tmp_path / d)), seed=7).run(until="2025-04-30")
            for d in ("a", "b")]
    a, b = (r.manifest for r in runs)
    assert a["days"] == 30 and a["build_report"]["max_l1"] < 0.01
    assert a["content_hash"] == b["content_hash"]
    assert abs(a["scale_factor"] - 50.0) < 1e-9
    assert runs[0].table("persons").collect().height == 100_000
