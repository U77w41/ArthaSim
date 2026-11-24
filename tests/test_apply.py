"""Applying interventions: parameters, rails, macro paths and module swaps (plan 1d-2, Task 6)."""
import json
from datetime import date

import pytest

from arthasim import Config, World
from arthasim.interventions import (ChangeRailRule, IncomeShock, MacroPath, ParamOverride, SetHook,
                                    SetPolicyRate)
from arthasim.modules.base import BehaviourModule
from arthasim.modules.spending import Consumption
from arthasim.scenario import Scenario
from helpers import data_files, run_files

IST_DAY = "strftime(make_timestamp(y.intent_ts) + interval 330 minute, '%Y-%m-%d')"
UPI_MAX = "select max(y.amount_paise) as m from payments y where y.rail like 'UPI%' and y.status = 'SUCCESS' and {day}"


class Recorder(Consumption):
    """Consumption that notes the days it runs."""

    def __init__(self) -> None:
        super().__init__()
        self.days = []

    def intents(self, world, day, persons=None):
        self.days.append(day)
        return super().intents(world, day, persons)


class Unnamed(BehaviourModule):
    name = "nothing"


def build(path, **kw):
    return World.build(Config.tier("S", persons=3_000, out_dir=str(path), **kw), 7, path=path / "run",
                       checkpoints=False)


def build_xs(path):
    return World.build(Config.tier("XS", persons=500, employers=10, merchants=30, out_dir=str(path)), 7,
                       path=path / "run", checkpoints=False)


def log(run):
    return run.table("interventions_log").collect()


def test_param_override_from_its_date(tmp_path):
    world = build(tmp_path)
    world.apply(ParamOverride("rail.upi.limit_paise", 100_000, "2025-04-15"))
    run = world.run("2025-04-20")
    assert run.sql(UPI_MAX.format(day=f"{IST_DAY} >= '2025-04-15'"))["m"][0] <= 100_000
    assert run.sql(UPI_MAX.format(day=f"{IST_DAY} < '2025-04-15'"))["m"][0] > 100_000
    assert world.params.get("rail.upi.limit_paise") == 100_000
    row = log(run)
    assert row["kind"].to_list() == ["ParamOverride"] and row["read_after"].to_list() == [True]
    assert row["effective"].to_list() == [date(2025, 4, 15)] and row["affected"].to_list() == [None]
    assert row["seq"].to_list() == [0] and row["ends"].to_list() == [None]
    assert json.loads(row["details"][0]) == {"param_id": "rail.upi.limit_paise", "value": 100_000,
                                             "date": "2025-04-15"}


def test_override_of_a_build_only_parameter_has_no_effect(tmp_path):
    plain = build(tmp_path / "p").run("2025-04-05")
    world = build(tmp_path / "o")
    world.apply(ParamOverride("attr.noise_sd", 0.5, "2025-04-02"))
    run = world.run("2025-04-05")
    assert log(run)["read_after"].to_list() == [False]
    assert data_files(run.path) == data_files(plain.path)
    assert run_files(run.path) != run_files(plain.path)                    # the log differs


def test_change_rail_rule(tmp_path):
    world = build(tmp_path)
    world.apply(ChangeRailRule("2025-04-15", "UPI", "per_txn_limit", 100_000))
    run = world.run("2025-04-20")
    assert run.sql(UPI_MAX.format(day=f"{IST_DAY} >= '2025-04-15'"))["m"][0] <= 100_000
    assert log(run)["kind"].to_list() == ["ChangeRailRule"] and log(run)["read_after"].to_list() == [True]


def test_macro_interventions(tmp_path):
    world = build_xs(tmp_path)
    world.apply(MacroPath("cpi_inflation", {"2025-06-01": 5.0, "2025-07-01": 6.0}))
    world.apply(SetPolicyRate("2025-05-15", -25))
    world.run("2025-05-10")
    assert world.macro("policy_rate", "2025-05-20") == 6.0                     # not yet in force
    run = world.run("2025-06-02")
    assert world.macro("policy_rate", "2025-05-20") == 5.75 and world.macro("policy_rate", "2026-01-01") == 5.0
    assert world.macro("cpi_inflation", "2026-03-01") == 6.0
    cpi = run.sql("select date, value from macro_paths where series = 'cpi_inflation' order by date")
    assert cpi["value"].to_list() == [3.16, 2.82, 5.0, 6.0]
    rate = run.sql("select value from macro_paths where series = 'policy_rate' order by date")
    assert rate["value"].to_list() == [6.25, 6.0, 5.75, 5.25, 5.0]
    assert log(run)["read_after"].to_list() == [False, False]


def test_module_swap_from_its_month_start(tmp_path):
    plain = build(tmp_path / "p").run("2025-05-03")
    world = build(tmp_path / "s")
    rec = Recorder()
    world.apply(SetHook("module", rec, date="2025-05-01"))
    world.run("2025-04-30")
    assert not isinstance(world.module("consumption"), Recorder)
    run = world.run("2025-05-03")
    swapped = world.module("consumption")
    assert isinstance(swapped, Recorder) and world.modules.index(swapped) == 6
    assert swapped.days == [date(2025, 5, 1), date(2025, 5, 2), date(2025, 5, 3)]
    assert swapped is not rec and rec.days == []               # the world runs its own copy
    assert data_files(run.path) == data_files(plain.path)            # Recorder behaves as Consumption does
    assert json.loads(log(run)["details"][0])["impl"] == "test_apply.Recorder"


def test_apply_errors(tmp_path):
    world = build(tmp_path)
    world.run("2025-04-10")
    with pytest.raises(ValueError, match="2025-04-11"):
        world.apply(ParamOverride("rail.upi.limit_paise", 1, "2025-04-05"))
    with pytest.raises(KeyError):
        world.apply(ParamOverride("no.such", 1, "2025-04-20"))
    with pytest.raises(ValueError):
        world.set_hook("module", Recorder())                             # 2025-04-11 is not the 1st
    with pytest.raises(ValueError, match="consumption"):
        world.apply(SetHook("module", Unnamed(), date="2025-05-01"))     # its name matches no module
    with pytest.raises(TypeError):
        world.apply(SetHook("module", object(), date="2025-05-01"))
    with pytest.raises(ValueError):
        world.apply(IncomeShock("2025-05-01", "occupation == 'farmer'", "layoff", 0.1))
    with pytest.raises(ValueError, match="population"):
        build_xs(tmp_path / "x").apply(IncomeShock("2025-05-01", "true", "layoff", 0.1))
    assert log(world.run("2025-04-11")).height == 0


def test_run_applies_a_scenario_once_across_segments(tmp_path):
    a = ParamOverride("rail.upi.limit_paise", 100_000, "2025-04-03")
    b = ParamOverride("consumption.spend_share", 0.7, "2025-04-09")
    world = build(tmp_path)
    s = Scenario.baseline().add(a)
    world.run("2025-04-05", s)
    world.run("2025-04-08", s)
    run = world.run("2025-04-10", s.add(b))
    row = log(run)
    assert row["seq"].to_list() == [0, 1]
    assert [json.loads(d)["param_id"] for d in row["details"]] == ["rail.upi.limit_paise", "consumption.spend_share"]
    assert [x["kind"] for x in run.manifest["scenario"]] == ["ParamOverride", "ParamOverride"]


def test_interventions_survive_a_checkpoint(tmp_path):
    iv = ParamOverride("rail.upi.limit_paise", 100_000, "2025-05-10")
    plain = build(tmp_path / "p")
    plain.apply(iv)
    plain = plain.run("2025-05-12")
    world = build(tmp_path / "s")
    world.apply(iv)
    world.run("2025-04-30")
    world.save(tmp_path / "ck")
    meta = json.loads((tmp_path / "ck" / "checkpoint.json").read_text())
    assert [x["kind"] for x in meta["interventions"]] == ["ParamOverride"]
    resumed = World.load(tmp_path / "ck", path_out=tmp_path / "r", checkpoints=False).run("2025-05-12")
    assert run_files(resumed.path) == run_files(plain.path)
    assert log(resumed)["read_after"].to_list() == [True]


def test_a_scenario_with_a_module_swap_matches_after_fork_and_load(tmp_path):
    s = Scenario.baseline().add(ParamOverride("rail.upi.limit_paise", 100_000, "2025-04-03"),
                                SetHook("module", Recorder(), date="2025-05-01"))
    world = build(tmp_path)
    world.run("2025-04-30", s)
    child = world.fork(path_out=tmp_path / "child", checkpoints=False)
    assert log(child.run("2025-05-02", s))["kind"].to_list() == ["ParamOverride", "SetHook"]
    world.run("2025-05-31", s)
    world.save(tmp_path / "ck")
    loaded = World.load(tmp_path / "ck", path_out=tmp_path / "loaded", checkpoints=False)
    assert log(loaded.run("2025-06-02", s))["kind"].to_list() == ["ParamOverride", "SetHook"]
