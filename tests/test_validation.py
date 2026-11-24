"""Validation (plan 1e): run metadata, the core suite and the report."""
import polars as pl

from arthasim import Config, Run, World
from run_fixture import secret_run, small_run


def test_manifest_records_the_config():
    run = small_run()
    config = Config(**run.manifest["config"])
    assert config.hash() == run.manifest["config_hash"]
    secret = secret_run().manifest
    assert secret["release_secret"] is True and "release_secret" not in secret["config"]


def test_report_table_is_listed_but_not_hashed(tmp_path):
    world = World.build(Config.tier("S", persons=500, out_dir=str(tmp_path)), seed=3, checkpoints=False)
    world.run("2025-04-03")
    pl.DataFrame({"check": ["x"]}).write_parquet(world.path / "validation_report.parquet")
    assert "validation_report" in Run.open(world.path).tables()
    assert Run.open(world.path).table("validation_report").collect().height == 1
    world.step(1)
    assert "validation_report" not in Run.open(world.path).manifest["content_hash"]
