"""Paired experiments over seeds.

For each seed one world runs a shared prefix to the day before `intervene_at`; each treatment arm is a fork of it
that applies its own interventions and runs to `end`; the prefix world then runs on as the baseline. Arms of a seed
share keyed randomness, so their differences come only from the interventions. `effect` gives the mean paired
difference across seeds with a Student-t interval."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import multiprocessing
import pickle
import re
import shutil
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

import polars as pl

from arthasim import where
from arthasim.active import POPULATION_ONLY, check_module, check_policy_rate
from arthasim.config import Config
from arthasim.dbt.schemes import OLD_AGE_PENSION, PM_KISAN, WOMEN
from arthasim.interventions import (RAIL_RULES, ChangeRailRule, DBTTransfer, Intervention, MacroPath, ParamOverride,
                                    SetHook, SetPolicyRate)
from arthasim.params import ParamRegistry
from arthasim.scenario import Scenario
from arthasim.stats import interval
from arthasim.world import Date, Run, World, _as_date, _registry_path

_ARM = re.compile(r"[A-Za-z0-9_-]+")
DEFAULT_METRICS = ("txn_volume", "decline_rate", "consumption", "cash_withdrawal", "deposit_balance")
SUMS = {"txn_volume", "consumption", "cash_withdrawal", "deposit_balance"}       # fill=0 is right for these
_STATS = ["baseline", "treatment", "effect", "lo", "hi", "n", "relative"]


class Experiment:
    def __init__(self, config: Config, baseline: Scenario, treatments: Mapping[str, Scenario], seeds: Iterable[int],
                 intervene_at: Date, end: Date, path: str | Path | None = None) -> None:
        self.config, self.baseline = config, baseline
        self.treatments = dict(treatments)
        self.seeds = [int(s) for s in seeds]
        self.intervene_at, self.end = _as_date(intervene_at), _as_date(end)
        self._check()
        self.path = Path(path) if path is not None else Path(config.out_dir) / f"experiment-{self.digest()}"

    # -- rules ----------------------------------------------------------------------------------------------------
    def _check(self) -> None:
        start, at = self.config.start, self.intervene_at
        if not (at == start or (at.day == 1 and at > start)):
            raise ValueError(f"intervene_at must be the run's start ({start.isoformat()}) or the 1st of a later month; "
                             f"got {at.isoformat()}")
        if not at < self.end:
            raise ValueError(f"intervene_at ({at.isoformat()}) must be before end ({self.end.isoformat()})")
        if not self.seeds:
            raise ValueError("an experiment needs at least one seed")
        if len(set(self.seeds)) != len(self.seeds):
            raise ValueError(f"seeds must be unique; got {self.seeds}")
        for name in self.treatments:
            if name == "baseline" or not _ARM.fullmatch(name):
                raise ValueError(f"arm name {name!r} must use letters, digits, _ and - only, and not be 'baseline'")
        prefix = self._prefix(self.baseline)
        for name, scenario in self.treatments.items():
            if self._prefix(scenario) != prefix:
                raise ValueError(f"arm {name!r}: its interventions effective before {at.isoformat()} must equal the "
                                 "baseline's, in order, since the arms share that prefix")
        # What `World.apply` would check, checked now, so a mistake fails before any seed runs.
        registry = ParamRegistry.load(_registry_path(self.config), overrides=self.config.param_overrides)
        population = self.config.builder == "population"
        modules = [m.name for m in World.default_modules(population)]
        for name, scenario in (("baseline", self.baseline), *self.treatments.items()):
            arm = scenario.interventions if name == "baseline" else (*prefix, *self._later(scenario))
            schemes = {PM_KISAN, OLD_AGE_PENSION, WOMEN}
            for i, iv in enumerate(arm):
                if iv.effective(start) < start:
                    raise ValueError(f"{type(iv).__name__} takes effect on {iv.effective(start).isoformat()}, "
                                     f"before the run's start {start.isoformat()}")
                if isinstance(iv, ParamOverride) and iv.param_id not in registry:
                    raise KeyError(iv.param_id)
                if isinstance(iv, POPULATION_ONLY) and not population:
                    raise ValueError(f"{type(iv).__name__} needs a population world (tier S and above)")
                if isinstance(getattr(iv, "where", None), str):
                    where.check(iv.where)
                if isinstance(iv, DBTTransfer):
                    if iv.scheme in schemes:
                        raise ValueError(f"arm {name!r}: scheme name {iv.scheme!r} is taken")
                    schemes.add(iv.scheme)
                if isinstance(iv, SetHook):
                    check_module(iv.impl, modules)
                if isinstance(iv, SetPolicyRate):
                    check_policy_rate(registry, [(o.effective(start), j, o) for j, o in enumerate(arm[:i])], iv, i)

    def _prefix(self, scenario: Scenario) -> list[Intervention]:
        return [iv for iv in scenario.interventions if iv.effective(self.config.start) < self.intervene_at]

    def _later(self, scenario: Scenario) -> list[Intervention]:
        return [iv for iv in scenario.interventions if iv.effective(self.config.start) >= self.intervene_at]

    def digest(self) -> str:
        """12 hex characters naming the default folder: the config, the arms, seeds and dates, and a swapped module's
        pickled state (its `details` name only the class)."""
        def arm(scenario: Scenario) -> list[dict[str, Any]]:
            out = scenario.details()
            for d, iv in zip(out, scenario.interventions):
                if isinstance(iv, SetHook):
                    d["state"] = hashlib.sha256(pickle.dumps(iv.impl, protocol=5)).hexdigest()
            return out
        blob = json.dumps({"config": self.config.hash(), "baseline": arm(self.baseline),
                           "arms": {n: arm(s) for n, s in self.treatments.items()}, "seeds": self.seeds,
                           "intervene_at": self.intervene_at.isoformat(), "end": self.end.isoformat()},
                          sort_keys=True, default=str)
        return hashlib.sha256(blob.encode()).hexdigest()[:12]

    # -- running --------------------------------------------------------------------------------------------------
    def run(self, workers: int = 1) -> "ExperimentResult":
        """Run every seed (one task per seed; `workers` processes, spawned). Results do not depend on `workers`."""
        if self.path.exists():
            raise FileExistsError(f"experiment folder already exists: {self.path}")
        self.path.mkdir(parents=True)
        try:
            if workers <= 1:
                folders = [_run_seed(self, s) for s in self.seeds]
            else:
                with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context("spawn")) as pool:
                    folders = list(pool.map(_run_seed, [self] * len(self.seeds), self.seeds))
        except BaseException:
            shutil.rmtree(self.path, ignore_errors=True)         # an unfinished experiment leaves nothing behind
            raise
        arms = ["baseline", *self.treatments]
        meta = {"baseline": self.baseline.details(), "arms": {n: s.details() for n, s in self.treatments.items()},
                "seeds": self.seeds, "intervene_at": self.intervene_at.isoformat(), "end": self.end.isoformat(),
                "config": self.config.model_dump(mode="json", exclude={"release_secret"}),
                "config_hash": self.config.hash(), "release_secret": self.config.release_secret is not None,
                "runs": {arm: {str(s): f[arm] for s, f in zip(self.seeds, folders)} for arm in arms}}
        (self.path / "experiment.json").write_text(json.dumps(meta, indent=2, default=str))
        return ExperimentResult.open(self.path)

    def sweep(self, param_id: str, values: Sequence[Any], workers: int = 1) -> "SweepResult":
        """The experiment again at each value of one parameter (set from the build), into
        `<path>/sweep-<param_id>/<value index>/`."""
        ParamRegistry.load(_registry_path(self.config)).get(param_id)          # KeyError for an unknown id
        results = []
        for i, value in enumerate(values):
            exp = Experiment(self.config.with_params(**{param_id: value}), self.baseline, self.treatments, self.seeds,
                             self.intervene_at, self.end, path=self.path / f"sweep-{param_id}" / str(i))
            results.append(exp.run(workers))
        return SweepResult(param_id, list(values), results)


def _run_seed(exp: Experiment, seed: int) -> dict[str, str]:
    """One seed: the shared prefix, a fork per treatment, then the baseline. At most two worlds in memory."""
    base = f"baseline-seed{seed}"
    world = World.build(exp.config, seed, path=exp.path / base, checkpoints=False)
    for iv in exp._prefix(exp.baseline):
        world.apply(iv)
    if exp.intervene_at > exp.config.start:
        world.run(exp.intervene_at - dt.timedelta(days=1))
    out = {}
    for name, scenario in exp.treatments.items():
        folder = f"{name}-seed{seed}"
        fork = world.fork(path_out=exp.path / folder, checkpoints=False)
        for iv in exp._later(scenario):
            fork.apply(iv)
        fork.run(exp.end)
        del fork
        out[name] = folder
    for iv in exp._later(exp.baseline):
        world.apply(iv)
    world.run(exp.end)
    out["baseline"] = base
    return out


# -- results ----------------------------------------------------------------------------------------------------------
def _pair(base: pl.DataFrame, treat: pl.DataFrame, groups: list[str], fill: Any) -> pl.DataFrame:
    b = base.with_columns(pl.col("value").cast(pl.Float64)).rename({"value": "baseline"})
    t = treat.with_columns(pl.col("value").cast(pl.Float64)).rename({"value": "treatment"})
    if groups:
        joined = b.join(t, on=groups, how="full", coalesce=True, nulls_equal=True)
    else:
        joined = b.join(t, how="cross")
    if fill is not None:
        joined = joined.with_columns(pl.col("baseline").fill_null(float(fill)),
                                     pl.col("treatment").fill_null(float(fill)))
    return joined.drop_nulls(["baseline", "treatment"])


def _metric_name(metric: str | Callable[..., Any]) -> str:
    return metric if isinstance(metric, str) else getattr(metric, "__name__", "metric")


def _table(frame: pl.DataFrame) -> list[str]:
    def cell(v: Any) -> str:
        if v is None:
            return ""
        if isinstance(v, float):
            return f"{v:,.6g}" if abs(v) < 1e6 else f"{v:,.0f}"
        return str(v)
    lines = ["| " + " | ".join(frame.columns) + " |", "|" + "|".join(" :--- " for _ in frame.columns) + "|"]
    lines += ["| " + " | ".join(cell(v) for v in row) + " |" for row in frame.iter_rows()]
    return lines


def _nobody(details: dict[str, Any]) -> str:
    """Why an intervention affected nobody: nobody selected, or nobody selected it could act on."""
    selected = details.get("selected", 0)
    if not selected:
        return "selected nobody"
    for key, what in (("not_salaried", "salaried"), ("not_earning", "earning")):
        if details.get(key) == selected:
            return f"affected nobody: none of the {selected:,} selected were {what}"
    return f"affected none of the {selected:,} selected"


def _log_lines(r: dict[str, Any], end: dt.date) -> list[str]:
    """What an `interventions_log` row did, in words, where its table row needs it. `end` is the runs' last day."""
    name = f"{r['kind']} (seq {r['seq']})"
    details = json.loads(r["details"])
    if r["effective"] > end:
        return [f"- {name} takes effect on {r['effective']}, after the end ({end}): it did nothing in these runs."]
    out = []
    if r["kind"] == DBTTransfer.__name__ and dt.date.fromisoformat(details["dates"][0]) > end:
        out.append(f"- {name} first pays on {details['dates'][0]}, after the end ({end}): it enrolled its payees but "
                   "paid no credit in these runs.")
    if r["read_after"] is False:
        if r["kind"] in (MacroPath.__name__, SetPolicyRate.__name__):
            out.append(f"- {name} had no effect: nothing reads macro paths in phase 1.")
        else:
            pid = (RAIL_RULES[(details["rail"], details["rule"])] if r["kind"] == ChangeRailRule.__name__
                   else details["param_id"])
            out.append(f"- {name} had no effect: nothing read `{pid}` on or after {r['effective']}.")
    if r["affected"] == 0:
        out.append(f"- {name} {_nobody(details)}.")
    return out


class ExperimentResult:
    def __init__(self, path: str | Path, meta: dict[str, Any]) -> None:
        self.path = Path(path)
        self._meta = meta
        self.arms: list[str] = ["baseline", *meta["arms"]]
        self.seeds: list[int] = list(meta["seeds"])
        self.intervene_at = dt.date.fromisoformat(meta["intervene_at"])
        self.end = dt.date.fromisoformat(meta["end"])
        self.config = Config(**meta["config"])

    @classmethod
    def open(cls, path: str | Path) -> "ExperimentResult":
        return cls(path, json.loads((Path(path) / "experiment.json").read_text()))

    def runs(self, arm: str) -> list[Run]:
        if arm not in self.arms:
            raise KeyError(f"no arm {arm!r}; arms are {', '.join(self.arms)}")
        return [Run.open(self.path / self._meta["runs"][arm][str(s)]) for s in self.seeds]

    def effect(self, metric: str | Callable[..., Any], by: str | list[str] | None = None, fill: Any = None,
               level: float = 0.95, window: str = "arms", **kwargs: Any) -> pl.DataFrame:
        """Mean paired difference (treatment minus baseline) across seeds, per arm and group, with a Student-t
        interval. `window="arms"` measures from `intervene_at` to `end`; `"run"` measures whole runs. A group missing
        from one side takes `fill`; with `fill=None` that seed gives no difference for it."""
        if window not in ("arms", "run"):
            raise ValueError(f"window must be 'arms' or 'run'; got {window!r}")
        kw = dict(kwargs)
        if by is not None:
            kw["by"] = by

        def measure(run: Run) -> pl.DataFrame:
            seen = run.window(self.intervene_at, self.end) if window == "arms" else run
            return seen.metric(metric, **kw)

        base = [measure(r) for r in self.runs("baseline")]
        groups = [c for c in base[0].columns if c != "value"]
        pairs = []
        for k, arm in enumerate(self.arms[1:]):
            for seed, b, run in zip(self.seeds, base, self.runs(arm)):
                pairs.append(_pair(b, measure(run), groups, fill).with_columns(
                    pl.lit(arm).alias("arm"), pl.lit(k).alias("_order")))
        schema = {"arm": pl.String, **{g: base[0].schema[g] for g in groups}, "baseline": pl.Float64,
                  "treatment": pl.Float64, "effect": pl.Float64, "lo": pl.Float64, "hi": pl.Float64, "n": pl.Int64,
                  "relative": pl.Float64}
        if not pairs or not any(p.height for p in pairs):
            return pl.DataFrame(schema=schema)
        joined = pl.concat([p for p in pairs if p.height], how="vertical_relaxed")
        grouped = (joined.group_by(["_order", "arm", *groups], maintain_order=True)
                   .agg(pl.col("baseline"), pl.col("treatment")).sort(["_order", *groups], nulls_last=True))
        rows = []
        for r in grouped.iter_rows(named=True):
            d = [t - b for b, t in zip(r["baseline"], r["treatment"])]
            mean, lo, hi, n = interval(d, level)
            base_mean = sum(r["baseline"]) / n
            rows.append({"arm": r["arm"], **{g: r[g] for g in groups}, "baseline": base_mean,
                         "treatment": sum(r["treatment"]) / n, "effect": mean, "lo": lo, "hi": hi, "n": n,
                         "relative": mean / base_mean if base_mean != 0 else None})
        return pl.DataFrame(rows, schema=schema)

    def _sections(self, metrics, window: str) -> list[str]:
        cfg, meta = self.config, self._meta
        out = [f"- Config: tier {cfg.tier_name}, {cfg.persons:,} persons, start {cfg.start.isoformat()}, "
               f"config hash {meta['config_hash'][:12]}",
               f"- Seeds: {', '.join(map(str, self.seeds))} (n = {len(self.seeds)})",
               f"- Intervene at {self.intervene_at.isoformat()}, end {self.end.isoformat()}",
               f"- Window measured: {'from intervene_at to end' if window == 'arms' else 'whole runs'}", "",
               "## Arms", ""]
        for arm in self.arms:
            ivs = meta["baseline"] if arm == "baseline" else meta["arms"][arm]
            out.append(f"- **{arm}**: " + ("no interventions" if not ivs else
                                           "; ".join(json.dumps(iv, sort_keys=True) for iv in ivs)))
        out += ["", "## Effects", ""]
        for metric in metrics or DEFAULT_METRICS:
            name = _metric_name(metric)
            fill = 0 if name in SUMS else None
            out += [f"### {name}" + (" (fill 0)" if fill is not None else ""), ""]
            out += _table(self.effect(metric, fill=fill, window=window)) + [""]
        out += ["## Interventions", "", "From seed " + str(self.seeds[0]) + "'s runs.", ""]
        for arm in self.arms:
            log = self.runs(arm)[0].table("interventions_log").collect()
            if not log.height:
                continue
            out += [f"### {arm}", ""] + _table(log.select("seq", "kind", "effective", "ends", "affected",
                                                         "read_after")) + [""]
            for r in log.iter_rows(named=True):
                out += _log_lines(r, self.end)
            out.append("")
        registry = {row["id"]: row for row in
                    ParamRegistry.load(_registry_path(cfg), overrides=cfg.param_overrides).table().iter_rows(named=True)}
        read = set().union(*(set(r.manifest.get("params_read", [])) for a in self.arms for r in self.runs(a)))
        out += ["## Assumptions read", "",
                "Registry parameters with status `assumption` that the runs read on a simulated day.", ""]
        out += [f"- `{pid}`: {registry[pid]['source']}" for pid in sorted(read)
                if pid in registry and registry[pid]["status"] == "assumption"]
        return out

    def report(self, path: str | Path, metrics: Sequence[str | Callable[..., Any]] | None = None,
               window: str = "arms") -> None:
        """Write a Markdown report: the setup, each arm's interventions, the effects, what each intervention did,
        and the assumption-status parameters the runs read."""
        text = [f"# Experiment {self.path.name}", ""] + self._sections(metrics, window)
        Path(path).write_text("\n".join(text) + "\n")


def _param_values(values: list[Any]) -> tuple[list[Any], pl.DataType]:
    if all(isinstance(v, int) and not isinstance(v, bool) for v in values):
        return values, pl.Int64
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
        return [float(v) for v in values], pl.Float64
    return [v if isinstance(v, str) else json.dumps(v) for v in values], pl.String


class SweepResult:
    def __init__(self, param_id: str, values: list[Any], results: list[ExperimentResult]) -> None:
        self.param_id, self.values, self.results = param_id, values, results

    def effect(self, metric: str | Callable[..., Any], by: str | list[str] | None = None, fill: Any = None,
               level: float = 0.95, window: str = "arms", **kwargs: Any) -> pl.DataFrame:
        """`ExperimentResult.effect` for each value, with a `param_value` column first."""
        values, dtype = _param_values(self.values)
        frames = []
        for value, res in zip(values, self.results):
            frame = res.effect(metric, by=by, fill=fill, level=level, window=window, **kwargs)
            frames.append(frame.select(pl.lit(value, dtype=dtype).alias("param_value"), pl.all()))
        return pl.concat(frames)

    def report(self, path: str | Path, metrics: Sequence[str | Callable[..., Any]] | None = None,
               window: str = "arms") -> None:
        text = [f"# Sweep of `{self.param_id}`", ""]
        for value, res in zip(self.values, self.results):
            text += [f"## `{self.param_id}` = {value}", ""] + res._sections(metrics, window) + [""]
        Path(path).write_text("\n".join(text) + "\n")
