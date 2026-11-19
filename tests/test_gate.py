import pytest
from arthasim import Config, World


@pytest.mark.slow
def test_phase0_gate(tmp_path):
    runs = [World.build(Config.tier("XS", out_dir=str(tmp_path / d)), seed=7).run(until="2025-06-29")
            for d in ("a", "b")]
    a, b = (r.manifest for r in runs)
    assert a["days"] == 90
    assert a["content_hash"] == b["content_hash"]
    assert 1.0 <= a["payments"] / (10_000 * 90) <= 1.6
