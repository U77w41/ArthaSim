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


# The suite and run.validate ---------------------------------------------------------------------------------------

import functools
import tempfile

import pytest
import yaml

from arthasim import validation
from helpers import P

COLUMNS = ["suite", "check", "kind", "component", "target_id", "target_status", "simulated", "target", "lower",
           "upper", "status", "window", "detail", "gap"]


@functools.lru_cache(maxsize=None)
def three_months():
    """600 persons, April to June 2025 (window May and June)."""
    out = tempfile.mkdtemp(prefix="arthasim-validate-")
    return World.build(Config.tier("S", persons=600, out_dir=out), seed=21, checkpoints=False).run("2025-06-30")


def test_core_suite_names_registry_rows_with_matching_roles():
    suite = validation.load_suite("core")
    kinds = {c.kind for c in suite}
    assert kinds == {"hard", "target", "holdout"}
    for c in suite:
        assert c.why and (c.kind == "hard" or c.tolerance > 0)
        if c.target is not None:
            row = P.table().filter(pl.col("id") == c.target).row(0, named=True)
            assert row["role"] == ("holdout" if c.kind == "holdout" else "target"), c.id


def test_a_suite_naming_a_missing_row_or_statistic_raises(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(yaml.safe_dump({"checks": [{"id": "x", "kind": "target", "statistic": "pay.regular_monthly",
                                               "target": "nope", "compare": "relative", "tolerance": 0.1, "why": "w"}]}))
    with pytest.raises(ValueError, match="nope"):
        validation.load_suite(bad)
    bad.write_text(yaml.safe_dump({"checks": [{"id": "x", "kind": "target", "statistic": "nope",
                                               "target": "pay.regular_monthly", "compare": "relative",
                                               "tolerance": 0.1, "why": "w"}]}))
    with pytest.raises(ValueError, match="nope"):
        validation.load_suite(bad)


def test_validate_writes_the_report_into_the_run():
    run = three_months()
    report = run.validate()
    table = report.table()
    assert table.columns == COLUMNS
    assert set(table["check"]) == {c.id for c in validation.load_suite("core")}
    assert run.table("validation_report").collect().equals(table)
    hard = table.filter(pl.col("kind") == "hard")
    assert set(hard["status"]) <= {"pass", "skipped"} and (hard["status"] == "pass").sum() >= 10
    festival = table.filter(pl.col("check") == "holdout.festival_uplift")
    assert festival["status"].to_list() == ["skipped"]          # the run has no September to November
    pay = table.filter(pl.col("check") == "pay.regular_monthly").sort("component")
    assert pay["component"].to_list() == ["rural", "urban"] and pay["target"].to_list() == [17841.0, 26247.0]
    assert pay["window"].to_list() == ["2025-05 to 2025-06"] * 2
    assert report.passed == (table["status"] != "fail").all()
    assert report.failures().height == (table["status"] == "fail").sum()


def test_uprated_and_derived_targets():
    table = three_months().validate().table()
    mpce = table.filter(pl.col("check") == "consumption.mpce").sort("component")
    assert mpce["target"].to_list() == pytest.approx([4122 * 1.0467, 6996 * 1.0501])
    p2m = table.filter(pl.col("check") == "payments.upi_p2m_per_adult")["target"][0]
    assert p2m == pytest.approx((18677.46 + 18395.006) / 2 * 0.63 / 1016.1)
    ticket = table.filter(pl.col("check") == "payments.atm_ticket")["target"][0]
    assert ticket == pytest.approx((244945 + 228735) * 1e7 / ((457.988 + 435.858) * 1e6))
    inop = table.filter(pl.col("check") == "accounts.inoperative")["target"][0]
    assert inop == pytest.approx(1 - 0.7355)


def test_bands_statuses_and_gaps(tmp_path):
    suite = tmp_path / "s.yaml"
    checks = [
        {"id": "tight", "kind": "target", "statistic": "pay.regular_monthly", "target": "pay.regular_monthly",
         "compare": "relative", "tolerance": 1e-9, "why": "w"},
        {"id": "loose", "kind": "target", "statistic": "pay.regular_monthly", "target": "pay.regular_monthly",
         "compare": "relative", "tolerance": 100.0, "why": "w"},
        {"id": "gap", "kind": "target", "statistic": "pay.regular_monthly", "target": "pay.regular_monthly",
         "compare": "absolute", "tolerance": 1e-9, "why": "w", "gap": "Ruling: no such mechanism"},
    ]
    suite.write_text(yaml.safe_dump({"checks": checks}))
    table = validation.validate(three_months(), suite, write=False).table()
    status = {(r["check"], r["component"]): r["status"] for r in table.iter_rows(named=True)}
    assert {s for (c, _), s in status.items() if c == "tight"} == {"fail"}
    assert {s for (c, _), s in status.items() if c == "loose"} == {"pass"}
    gap = table.filter(pl.col("check") == "gap")
    assert set(gap["status"]) == {"fail"} and set(gap["gap"]) == {"Ruling: no such mechanism"}
    row = table.filter((pl.col("check") == "loose") & (pl.col("component") == "urban")).row(0, named=True)
    assert row["lower"] == pytest.approx(26247 * (1 - 100)) and row["upper"] == pytest.approx(26247 * 101)
    assert not validation.ValidationReport(table).passed


def test_a_run_with_one_month_skips_targets(tmp_path):
    run = World.build(Config.tier("S", persons=300, out_dir=str(tmp_path)), seed=4, checkpoints=False).run("2025-04-30")
    table = run.validate().table()
    targets = table.filter(pl.col("kind") != "hard")
    assert set(targets["status"]) == {"skipped"}
    assert "no complete month after the first" in targets["detail"][0]


def test_a_window_cannot_be_validated():
    with pytest.raises(ValueError, match="window"):
        three_months().window("2025-05-01", "2025-05-31").validate()


def test_a_spike_run_skips_what_it_cannot_check(tmp_path):
    config = Config.tier("XS", persons=400, employers=4, merchants=12, out_dir=str(tmp_path))
    table = World.build(config, seed=6, checkpoints=False).run("2025-05-31").validate().table()
    ledger = table.filter(pl.col("check") == "ledger")
    assert set(ledger["status"]) == {"skipped"} and "opening balances" in ledger["detail"][0]
    assert set(table.filter(pl.col("check") == "determinism")["status"]) == {"pass"}
    targets = table.filter(pl.col("kind") != "hard")
    assert set(targets["status"]) == {"skipped"} and "population" in targets["detail"][0]


def test_a_report_never_outlives_the_run_it_describes(tmp_path):
    world = World.build(Config.tier("S", persons=400, out_dir=str(tmp_path)), seed=8)
    run = world.run("2025-06-30")
    run.validate()
    assert "validation_report" in Run.open(run.path).tables()
    fork = world.fork(tmp_path / "fork")
    assert "validation_report" not in Run.open(fork.path).tables()       # a fork starts without its parent's report
    assert "validation_report" in Run.open(run.path).tables()            # and leaves the parent's in place
    world.run("2025-07-05")
    assert "validation_report" not in Run.open(run.path).tables()        # running on makes the old report stale
    loaded = Run.open(run.path).fork_at("2025-06-01")
    assert "validation_report" not in Run.open(loaded.path).tables()
