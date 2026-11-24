"""Experiments, sweeps and reports (plan 1d-2, Task 10)."""
import functools
import hashlib
import json
import tempfile
from datetime import date

import polars as pl
import pytest

from arthasim import Config, Experiment, ExperimentResult, Scenario, World
from arthasim.engine.intents import Intents
from arthasim.experiment import _log_lines
from arthasim.interventions import (ChangeRailRule, DBTTransfer, IncomeShock, MacroPath, ParamOverride, SetHook,
                                    SetPolicyRate)
from arthasim.modules.spending import Consumption
from arthasim.modules.spike import SpikeConsumption
from helpers import P, run_files

FARMERS = "life_stage == 'farm' and not helper"
BASE = Scenario.baseline()
DBT = BASE.add(DBTTransfer("TEST_TRANCHE", 2000, FARMERS, ["2025-05-05"]))
SAME = BASE.add(ParamOverride("rail.upi.limit_paise", P.get("rail.upi.limit_paise"), "2025-05-01"))


def config(out):
    return Config.tier("S", persons=2_000, out_dir=str(out))


@functools.lru_cache(maxsize=None)
def dbt_experiment():
    """Two arms over two seeds, intervening on 1 May and ending on 6 May. Read-only."""
    out = tempfile.mkdtemp(prefix="arthasim-exp-")
    return Experiment(config(out), BASE, {"dbt": DBT, "same": SAME}, [1, 2], "2025-05-01", "2025-05-06").run()


def other(run):
    """A metric with a group only the DBT arm has."""
    return run.sql("select purpose as g, count(*) as value from payments where purpose = 'DBT_OTHER' group by 1")


def test_baseline_arm_equals_a_plain_run(tmp_path):
    res = dbt_experiment()
    plain = World.build(res.config, 1, path=tmp_path / "p", checkpoints=False).run("2025-05-06")
    assert res.runs("baseline")[0].manifest["content_hash"] == plain.manifest["content_hash"]
    assert res.arms == ["baseline", "dbt", "same"] and res.seeds == [1, 2]


def test_arms_match_before_intervene_at():
    res = dbt_experiment()
    april = lambda r: {k: v for k, v in run_files(r.path).items() if "month=2025-04" in k}
    for b, t in zip(res.runs("baseline"), res.runs("dbt")):
        assert april(b) and april(b) == april(t)


def test_effect_on_apbs_credits_is_the_payees():
    res = dbt_experiment()
    eff = res.effect("txn_volume", by="rail", fill=0)
    assert eff.columns == ["arm", "rail", "baseline", "treatment", "effect", "lo", "hi", "n", "relative"]
    row = eff.filter((pl.col("arm") == "dbt") & (pl.col("rail") == "APBS"))
    payees = [r.sql("select count(*) as n from truth_dbt_monthly where scheme = 'TEST_TRANCHE' and enrolled")["n"][0]
              for r in res.runs("dbt")]
    assert row["effect"][0] == sum(payees) / 2 and row["n"][0] == 2
    assert row["lo"][0] <= row["effect"][0] <= row["hi"][0]


def test_an_intervention_that_changes_nothing_has_zero_effect():
    row = dbt_experiment().effect("txn_volume").filter(pl.col("arm") == "same")
    assert (row["effect"][0], row["lo"][0], row["hi"][0], row["relative"][0]) == (0, 0, 0, 0)


def test_fill_decides_groups_missing_from_one_side():
    res = dbt_experiment()
    assert res.effect(other).filter(pl.col("arm") == "dbt").height == 0
    filled = res.effect(other, fill=0).filter(pl.col("arm") == "dbt")
    assert filled["n"].to_list() == [2] and filled["baseline"].to_list() == [0]


def test_window_run_measures_whole_runs():
    res = dbt_experiment()
    arms = res.effect("txn_volume", fill=0).filter(pl.col("arm") == "dbt")
    whole = res.effect("txn_volume", fill=0, window="run").filter(pl.col("arm") == "dbt")
    assert arms["effect"][0] == whole["effect"][0] and arms["baseline"][0] < whole["baseline"][0]


def test_open_reads_back():
    res = dbt_experiment()
    again = ExperimentResult.open(res.path)
    assert again.effect("cash_withdrawal", fill=0).equals(res.effect("cash_withdrawal", fill=0))
    assert json.loads((res.path / "experiment.json").read_text())["runs"]["dbt"]["2"] == "dbt-seed2"


def test_report(tmp_path):
    res = dbt_experiment()
    res.report(tmp_path / "r.md")
    text = (tmp_path / "r.md").read_text()
    assert "TEST_TRANCHE" in text and "cash_withdrawal" in text and "2025-05-01" in text
    read = set().union(*(set(r.manifest["params_read"]) for a in res.arms for r in res.runs(a)))
    status = {r["id"]: r["status"] for r in P.table().iter_rows(named=True)}
    assumptions = [pid for pid in read if status[pid] == "assumption"]
    assert assumptions and all(f"`{pid}`" in text for pid in assumptions)


def test_workers_do_not_change_results(tmp_path):
    cfg = config(tmp_path)
    one = Experiment(cfg, BASE, {"dbt": DBT}, [1, 2], "2025-05-01", "2025-05-03", path=tmp_path / "a").run(workers=1)
    two = Experiment(cfg, BASE, {"dbt": DBT}, [1, 2], "2025-05-01", "2025-05-03", path=tmp_path / "b").run(workers=2)
    assert one.effect("txn_volume", by="rail", fill=0).equals(two.effect("txn_volume", by="rail", fill=0))
    for arm in one.arms:
        assert ([r.manifest["content_hash"] for r in one.runs(arm)]
                == [r.manifest["content_hash"] for r in two.runs(arm)])


def test_sweep(tmp_path):
    exp = Experiment(config(tmp_path), BASE, {"dbt": DBT}, [1], "2025-05-01", "2025-05-03", path=tmp_path / "s")
    sw = exp.sweep("consumption.buffer_target_months", [2, 3])
    eff = sw.effect("consumption", fill=0)
    assert eff.columns[0] == "param_value" and eff["param_value"].dtype == pl.Int64
    assert eff["param_value"].to_list() == [2, 3]
    assert (tmp_path / "s" / "sweep-consumption.buffer_target_months" / "1" / "experiment.json").exists()
    with pytest.raises(KeyError):
        exp.sweep("no.such", [1])


@pytest.mark.parametrize("kw", [
    dict(intervene_at="2025-05-02"),
    dict(intervene_at="2025-05-01", end="2025-05-01"),
    dict(treatments={"baseline": BASE}),
    dict(treatments={"a b": BASE}),
    dict(treatments={"x": BASE.add(ParamOverride("rail.upi.limit_paise", 1, "2025-04-10"))}),
    dict(treatments={"x": BASE.add(DBTTransfer("X", 1, "occupation == 'farmer'", ["2025-05-05"]))}),
    dict(baseline=BASE.add(ParamOverride("rail.upi.limit_paise", 1, "2025-03-01")),
         treatments={"x": BASE.add(ParamOverride("rail.upi.limit_paise", 1, "2025-03-01"))}),
    dict(seeds=[]),
    dict(seeds=[1, 1])])
def test_construction_errors(tmp_path, kw):
    args = dict(config=config(tmp_path), baseline=BASE, treatments={"dbt": DBT}, seeds=[1], intervene_at="2025-05-01",
                end="2025-05-03")
    with pytest.raises(ValueError):
        Experiment(**{**args, **kw})


def test_existing_folder(tmp_path):
    (tmp_path / "e").mkdir()
    with pytest.raises(FileExistsError):
        Experiment(config(tmp_path), BASE, {"dbt": DBT}, [1], "2025-05-01", "2025-05-03", path=tmp_path / "e").run()


# -- Final review fixes -----------------------------------------------------------------------------------------------

class StopsAfter(SpikeConsumption):
    """Spike spending that stops after 20 days of its own: state that must not carry from one seed to the next."""

    def __init__(self) -> None:
        self.days = 0

    def intents(self, world, day):
        self.days += 1
        return super().intents(world, day) if self.days <= 20 else Intents.empty()


class Boom(SpikeConsumption):
    def intents(self, world, day):
        raise RuntimeError("boom")


def xs(out):
    return Config.tier("XS", persons=500, employers=10, merchants=30, out_dir=str(out))


def test_a_stateful_module_does_not_carry_between_seeds(tmp_path):
    impl = StopsAfter()
    arm = BASE.add(SetHook("module", impl, date="2025-05-01"))
    runs = {w: Experiment(xs(tmp_path), BASE, {"swap": arm}, [1, 2], "2025-05-01", "2025-05-31",
                          path=tmp_path / f"w{w}").run(workers=w) for w in (1, 2)}
    assert impl.days == 0                                           # the caller's module is never run
    one, two = runs[1], runs[2]
    assert one.effect("txn_volume", fill=0).equals(two.effect("txn_volume", fill=0))
    assert ([r.manifest["content_hash"] for r in one.runs("swap")]
            == [r.manifest["content_hash"] for r in two.runs("swap")])


def test_apply_checks_run_at_construction(tmp_path):
    with pytest.raises(KeyError):
        Experiment(config(tmp_path), BASE, {"x": BASE.add(ParamOverride("no.such", 1, "2025-05-01"))}, [1],
                   "2025-05-01", "2025-05-03")
    bad = [(xs(tmp_path), BASE.add(DBTTransfer("X", 1, "true", ["2025-05-05"]))),
           (config(tmp_path), BASE.add(DBTTransfer("PM_KISAN", 1, "true", ["2025-05-05"]))),
           (config(tmp_path), BASE.add(DBTTransfer("X", 1, "true", ["2025-05-05"]),
                                       DBTTransfer("X", 2, "true", ["2025-05-06"]))),
           (xs(tmp_path), BASE.add(SetHook("module", Consumption(), date="2025-05-01")))]
    for cfg, arm in bad:
        with pytest.raises(ValueError):
            Experiment(cfg, BASE, {"x": arm}, [1], "2025-05-01", "2025-05-03")


def test_a_failed_run_leaves_no_folder(tmp_path):
    exp = Experiment(xs(tmp_path), BASE, {"x": BASE.add(SetHook("module", Boom(), date="2025-05-01"))}, [1],
                     "2025-05-01", "2025-05-03", path=tmp_path / "e")
    with pytest.raises(RuntimeError, match="boom"):
        exp.run()
    assert not (tmp_path / "e").exists()
    with pytest.raises(RuntimeError, match="boom"):                   # the same error again, not FileExistsError
        exp.run()


# -- Deferred minors tidy-up -------------------------------------------------------------------------------------------

def _lines(log, end):
    return [line for r in log.iter_rows(named=True) for line in _log_lines(r, end)]


def test_report_lines_for_people_selected_but_not_affected_and_for_dates_after_the_end(tmp_path):
    world = World.build(config(tmp_path), 1, path=tmp_path / "run", checkpoints=False)
    for iv in (IncomeShock("2025-04-01", "life_stage == 'retired'", "layoff", 0.5),
               IncomeShock("2025-04-01", "life_stage == 'retired'", "pay_cut", 0.5, months=1),
               IncomeShock("2025-04-01", "age > 500", "layoff", 0.5),
               ParamOverride("rail.upi.limit_paise", 100_000, "2025-04-03"),
               ChangeRailRule("2025-05-01", "UPI", "per_txn_limit", 100_000),
               DBTTransfer("LATE", 2000, "life_stage == 'retired'", ["2025-04-20"])):
        world.apply(iv)
    log = world.run("2025-04-02").table("interventions_log").collect()
    retired = json.loads(log["details"][0])["selected"]
    assert retired > 0 and json.loads(log["details"][1])["selected"] == retired
    assert _lines(log, date(2025, 4, 2)) == [
        f"- IncomeShock (seq 0) affected nobody: none of the {retired:,} selected were salaried.",
        f"- IncomeShock (seq 1) affected nobody: none of the {retired:,} selected were earning.",
        "- IncomeShock (seq 2) selected nobody.",
        "- ParamOverride (seq 3) takes effect on 2025-04-03, after the end (2025-04-02): it did nothing in these runs.",
        "- ChangeRailRule (seq 4) takes effect on 2025-05-01, after the end (2025-04-02): it did nothing in these "
        "runs.",
        "- DBTTransfer (seq 5) first pays on 2025-04-20, after the end (2025-04-02): it enrolled its payees but paid "
        "no credit in these runs."]


def test_report_names_a_rail_rule_s_parameter():
    row = {"seq": 0, "kind": "ChangeRailRule", "effective": date(2025, 5, 1), "affected": None, "read_after": False,
           "details": json.dumps({"date": "2025-05-01", "rail": "UPI", "rule": "per_txn_limit", "value": 1})}
    assert _log_lines(row, date(2025, 5, 3)) == [
        "- ChangeRailRule (seq 0) had no effect: nothing read `rail.upi.limit_paise` on or after 2025-05-01."]


class Limited(SpikeConsumption):
    """Spike spending with a setting."""

    def __init__(self, limit: int) -> None:
        self.limit = limit


def test_the_default_folder_follows_a_swapped_module_s_settings():
    cfg = Config.tier("XS", persons=500, employers=10, merchants=30, out_dir="/nonexistent/out")

    def folder(limit):
        arm = BASE.add(SetHook("module", Limited(limit), date="2025-05-01"))
        return Experiment(cfg, BASE, {"swap": arm}, [1], "2025-05-01", "2025-05-03").path

    assert folder(20) == folder(20) and folder(20) != folder(30)
    # Experiments without a module swap keep the folder names they had (the digest as it was before swaps counted).
    arm = BASE.add(ParamOverride("rail.upi.limit_paise", 100000, "2025-05-02"))
    same = Experiment(cfg, BASE, {"a": arm}, [1, 2], "2025-05-01", "2025-05-03")
    before = json.dumps({"config": cfg.hash(), "baseline": BASE.details(), "arms": {"a": arm.details()},
                         "seeds": [1, 2], "intervene_at": "2025-05-01", "end": "2025-05-03"},
                        sort_keys=True, default=str)
    assert same.digest() == hashlib.sha256(before.encode()).hexdigest()[:12]


def test_a_policy_rate_change_before_the_series_is_refused_at_construction(tmp_path):
    cfg = Config.tier("XS", persons=500, employers=10, merchants=30, out_dir=str(tmp_path), start="2025-01-01")
    early = SetPolicyRate("2025-01-15", -25)
    with pytest.raises(ValueError, match="2025-02-07"):
        Experiment(cfg, BASE, {"x": BASE.add(early)}, [1], "2025-01-01", "2025-01-20")
    Experiment(cfg, BASE, {"x": BASE.add(MacroPath("policy_rate", {"2025-01-01": 6.5}), early)}, [1], "2025-01-01",
               "2025-01-20")
