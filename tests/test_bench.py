import argparse
import importlib.util
import pathlib
import pytest

_spec = importlib.util.spec_from_file_location("bench", pathlib.Path(__file__).parents[1] / "scripts" / "bench.py")
bench = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bench)


def test_set_parses_key_and_value():
    assert bench.parse_set("transfer.allowance_margin=0.1") == ("transfer.allowance_margin", 0.1)
    assert bench.parse_set("transfer.allowance_margin=1e-1") == ("transfer.allowance_margin", 0.1)
    assert bench.parse_set("a.b=x=y") == ("a.b", "x=y")


def test_set_without_equals_names_the_argument():
    with pytest.raises(argparse.ArgumentTypeError, match="transfer.allowance_margin"):
        bench.parse_set("transfer.allowance_margin")


def test_set_rejects_values_that_are_not_finite():
    for raw in ("nan", ".nan", "inf", "-.inf", "Infinity"):
        with pytest.raises(argparse.ArgumentTypeError, match="finite"):
            bench.parse_set(f"transfer.allowance_margin={raw}")


def test_money_flow_summary_reports_dbt_and_no_income_declines(tmp_path):
    from arthasim import Config, World
    world = World.build(Config.tier("S", persons=2_000, out_dir=str(tmp_path)), seed=7)
    run = world.run(until="2025-05-10")
    out = bench._money_flow_summary(world, run)
    dbt = out["dbt"]
    assert set(dbt) == {"PM_KISAN", "OLD_AGE_PENSION", "WOMEN"} and dbt["PM_KISAN"]["credits"] == 0
    assert dbt["WOMEN"]["credits"] > 0 and dbt["WOMEN"]["beneficiaries"] <= dbt["WOMEN"]["credits"]
    paid = sum(v["rupees"] for v in dbt.values())
    assert out["government_balance_rupees"] == -paid and out["purpose_group_share"]["government"] > 0
    assert out["dbt_accounts_opened"] >= 0
    assert set(out["dbt_enrolled_share"]) == {"women_21_60", "aged_60_plus", "farm_households"}
    assert 0 < out["dbt_enrolled_share"]["women_21_60"] < 1
    assert 0 <= out["declined_funds_rate_no_income_households"] <= 1
    assert list(out["no_income_households_by_month"]) == ["2025-04", "2025-05"]


def test_release_flag_reads_the_secret_from_the_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("ARTHASIM_RELEASE_SECRET", "5a" * 32)
    r = bench.main(["--tier", "XS", "--days", "2", "--release", "--out", str(tmp_path / "a")])
    assert r["release_secret"] is True
    assert bench.main(["--tier", "XS", "--days", "2", "--out", str(tmp_path / "b")])["release_secret"] is False
    monkeypatch.delenv("ARTHASIM_RELEASE_SECRET")
    with pytest.raises(SystemExit, match="ARTHASIM_RELEASE_SECRET"):
        bench.main(["--tier", "XS", "--days", "2", "--release", "--out", str(tmp_path / "c")])
