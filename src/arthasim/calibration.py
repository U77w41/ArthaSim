"""Calibration by simulation (plan 1e, architecture section 15.2). Optuna's TPE sampler proposes values for the free
parameters; each proposal runs one world per seed, the core suite's statistics are taken over the run's window, and
the trial is scored against the target rows in units of each check's tolerance. Trials run one after another and a
trial's seeds run in parallel, so the result does not depend on the number of workers."""
from __future__ import annotations

import calendar
import copy
import datetime as dt
import multiprocessing
import shutil
import tempfile
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import polars as pl
import yaml

from arthasim import statistics
from arthasim.config import Config
from arthasim.params import ParamRegistry
from arthasim.validation import Check, load_suite, target_values

_ROOT = Path(__file__).resolve().parents[2]
SPACE = _ROOT / "params" / "calibration" / "space.yaml"
MISSING_SCORE = 10.0            # a target component the trial produced no value for (as if 10 tolerances off)


@dataclass(frozen=True)
class Free:
    """A free parameter: a registry row's value (`key` sets one entry of a mapping row; `scale` multiplies every
    number of a list or mapping row), searched between `low` and `high`, on a log scale when `log`."""
    id: str
    low: float
    high: float
    log: bool = False
    key: str | None = None
    scale: bool = False

    @property
    def name(self) -> str:
        return self.id + (f":{self.key}" if self.key else "") + (":scale" if self.scale else "")


def load_space(path: str | Path = SPACE) -> tuple[list[Free], list[str]]:
    raw = yaml.safe_load(Path(path).read_text())
    return [Free(**f) for f in raw["free"]], list(raw["targets"])


def resolve_params(params: Sequence[str | Free] | None, registry: ParamRegistry | None = None) -> list[Free]:
    """Free parameters from ids or names (bounds from the default space) or `Free` objects."""
    space, _ = load_space()
    by_name = {f.name: f for f in space}
    by_id: dict[str, list[Free]] = {}
    for f in space:
        by_id.setdefault(f.id, []).append(f)
    if params is None:
        out = space
    else:
        out = []
        for p in params:
            if isinstance(p, Free):
                out.append(p)
            elif p in by_name:
                out.append(by_name[p])
            elif p in by_id:
                out.extend(by_id[p])
            else:
                raise ValueError(f"no default bounds for free parameter {p!r}; pass a Free(...) instead")
    names = [f.name for f in out]
    if len(set(names)) != len(names):
        raise ValueError("a free parameter is listed twice")
    for f in out:
        if not f.low < f.high or (f.log and f.low <= 0):
            raise ValueError(f"{f.name}: bounds must satisfy 0 < low < high on a log scale, low < high otherwise")
        if registry is not None and f.id not in registry:
            raise ValueError(f"no registry row {f.id!r}")
    return out


def narrow(frees: Sequence[Free], values: Mapping[str, float], width: float) -> list[Free]:
    """Bounds narrowed around fitted values, for a refining second calibration: a log parameter keeps
    [v / (1 + 2 width), v * (1 + 2 width)], a linear one v plus or minus `width` of its range; both clipped to the
    original bounds."""
    out = []
    for f in frees:
        v = float(values[f.name])
        if f.log:
            lo, hi = v / (1 + 2 * width), v * (1 + 2 * width)
        else:
            span = (f.high - f.low) * width
            lo, hi = v - span, v + span
        out.append(Free(f.id, max(f.low, lo), min(f.high, hi), f.log, f.key, f.scale))
    return out


def refine(frees: Sequence[Free], earlier: Mapping[str, float], params: ParamRegistry,
           width: float) -> tuple[list[Free], dict[str, float]]:
    """The search space and first proposal of a refining calibration: parameters fitted before are narrowed around
    their fitted values and start there; parameters new to this search keep their bounds and start at the
    registry's value (a scale at 1)."""
    space, start = [], {}
    for f in frees:
        if f.name in earlier:
            space.extend(narrow([f], earlier, width))
            start[f.name] = float(earlier[f.name])
        else:
            space.append(f)
            value = params.get(f.id)
            start[f.name] = 1.0 if f.scale else float(value[f.key] if f.key is not None else value)
    return space, start


def _scaled(value: Any, factor: float) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value * factor
    if isinstance(value, list):
        return [_scaled(v, factor) for v in value]
    if isinstance(value, dict):
        return {k: _scaled(v, factor) for k, v in value.items()}
    return value


def overrides(params: ParamRegistry, frees: Sequence[Free], values: Sequence[float]) -> dict[str, Any]:
    """The registry overrides for proposed values: each row's whole new value. Integer rows stay integers."""
    out: dict[str, Any] = {}
    for f, v in zip(frees, values):
        v = float(v)
        base = out.get(f.id, copy.deepcopy(params.get(f.id)))
        if f.key is not None:
            base = dict(base)
            base[f.key] = v
        elif f.scale:
            base = _scaled(base, v)
        else:
            base = int(round(v)) if isinstance(params.get(f.id), int) else v
        out[f.id] = base
    return out


def score(simulated: float, target: float, compare: str, tolerance: float) -> float:
    """The error in units of the check's tolerance: 1 is at the edge of its band."""
    if compare == "relative":
        return (simulated / target - 1.0) / tolerance
    if compare == "absolute":
        return (simulated - target) / tolerance
    return max(0.0, simulated - tolerance) / tolerance


def loss(scores: Mapping[str, Mapping[str, float]]) -> float:
    """The mean squared score over every component of every target."""
    values = [s for comps in scores.values() for s in comps.values()]
    return sum(s * s for s in values) / len(values)


def _last_day(start: dt.date, months: int) -> dt.date:
    y, m = start.year, start.month + months - 1
    y, m = y + (m - 1) // 12, (m - 1) % 12 + 1
    return dt.date(y, m, calendar.monthrange(y, m)[1])


def _trial_seed(config: Config, seed: int, until: dt.date, checks: list[str], path: str) -> dict[str, dict[str, float]]:
    """One world: build, run to `until`, take the statistics over its window, remove the run. (Runs in a worker.)"""
    from arthasim.world import World
    run = World.build(config, seed=seed, path=Path(path), checkpoints=False).run(until)
    try:
        ctx = statistics.context(run)
        return {c: statistics.STATISTICS[c](ctx) for c in checks} if ctx is not None else {}
    finally:
        shutil.rmtree(path, ignore_errors=True)


@dataclass
class CalibrationResult:
    best: dict[str, Any]
    free: dict[str, float]
    loss: float
    scores: dict[str, dict[str, float]]
    simulated: dict[str, dict[str, float]]
    targets: dict[str, dict[str, float]]
    trials: pl.DataFrame
    registry_version: str
    config: dict[str, Any]
    seeds: tuple[int, ...]
    months: int
    sampler_seed: int
    space: list[dict[str, Any]] = field(default_factory=list)
    versions: dict[str, str] = field(default_factory=dict)

    def apply(self, config: Config) -> Config:
        """`config` with the fitted values as parameter overrides."""
        return config.with_params(**self.best)

    def _meta(self) -> dict[str, Any]:
        return {"best": self.best, "free": self.free, "loss": self.loss, "scores": self.scores,
                "simulated": self.simulated, "targets": self.targets, "registry_version": self.registry_version,
                "config": self.config, "seeds": list(self.seeds), "months": self.months,
                "sampler_seed": self.sampler_seed, "space": self.space, "versions": self.versions,
                "trials": self.trials.height}

    def save(self, path: str | Path) -> None:
        """YAML at `path`, with the trials table beside it as `<stem>_trials.parquet`."""
        path = Path(path)
        path.write_text(yaml.safe_dump(self._meta(), sort_keys=False))
        self.trials.write_parquet(path.with_name(f"{path.stem}_trials.parquet"))

    @classmethod
    def load(cls, path: str | Path) -> "CalibrationResult":
        path = Path(path)
        meta = yaml.safe_load(path.read_text())
        trials = pl.read_parquet(path.with_name(f"{path.stem}_trials.parquet"))
        return cls(best=meta["best"], free=meta["free"], loss=meta["loss"], scores=meta["scores"],
                   simulated=meta["simulated"], targets=meta["targets"], trials=trials,
                   registry_version=meta["registry_version"], config=meta["config"], seeds=tuple(meta["seeds"]),
                   months=meta["months"], sampler_seed=meta["sampler_seed"], space=meta.get("space", []),
                   versions=meta.get("versions", {}))

    def report(self, path: str | Path) -> None:
        """Markdown: the free parameters, each target's published and simulated value and score, the loss path."""
        def fmt(v: float) -> str:
            return f"{v:,.0f}" if abs(v) >= 1000 else f"{v:.4g}"
        lines = ["# Calibration report", "",
                 f"{self.trials.height} trials, seeds {', '.join(map(str, self.seeds))}, {self.months}-month runs "
                 f"of {self.config.get('persons')} persons from {self.config.get('start')}; sampler seed "
                 f"{self.sampler_seed}; registry version `{self.registry_version[:16]}`; "
                 + ", ".join(f"{k} {v}" for k, v in self.versions.items()) + ".", "",
                 f"Best loss {self.loss:.4g} (the mean squared error in tolerances; 1 is every target at its "
                 "band's edge).", "", "## Free parameters", "",
                 "| Parameter | Low | High | Scale | Fitted |", "| :--- | ---: | ---: | :--- | ---: |"]
        for f in self.space:
            name = f["id"] + (f":{f['key']}" if f.get("key") else "") + (":scale" if f.get("scale") else "")
            v = self.free[name]
            edge = " (at a bound)" if min(abs(v - f["low"]), abs(v - f["high"])) <= 0.01 * (f["high"] - f["low"]) else ""
            lines.append(f"| `{name}` | {fmt(f['low'])} | {fmt(f['high'])} | {'log' if f.get('log') else 'linear'} | "
                         f"{fmt(v)}{edge} |")
        lines += ["", "## Targets (best trial, mean over seeds)", "",
                  "| Check | Component | Published | Simulated | Score |", "| :--- | :--- | ---: | ---: | ---: |"]
        for check, comps in self.scores.items():
            for comp, s in comps.items():
                sim = self.simulated.get(check, {}).get(comp)
                lines.append(f"| `{check}` | {comp} | {fmt(self.targets[check][comp])} | "
                             f"{fmt(sim) if sim is not None else ''} | {s:+.2f} |")
        best_so_far, running = [], float("inf")
        for v in self.trials["loss"].to_list():
            running = min(running, v)
            best_so_far.append(running)
        marks = sorted({min(len(best_so_far), k) for k in (1, 10, 25, 50, 100, 200, 300, 400, len(best_so_far))})
        lines += ["", "## Best loss so far", "", "| After trial | Best loss |", "| ---: | ---: |"]
        lines += [f"| {k} | {best_so_far[k - 1]:.4g} |" for k in marks]
        Path(path).write_text("\n".join(lines) + "\n")


def calibrate(config: Config, params: Sequence[str | Free] | None = None, targets: Sequence[str] | None = None,
              trials: int = 200, seeds: Sequence[int] = (1, 2, 3), months: int = 8, workers: int = 1,
              sampler_seed: int = 0, path: str | Path | None = None,
              progress: Callable[[int, float, float], None] | None = None,
              start: Mapping[str, float] | None = None) -> CalibrationResult:
    """Fit free parameters by simulation. Each trial runs `months` months from `config.start` for every seed and
    scores the window's statistics against the target checks (core-suite ids). `progress(trial, loss, best)` is
    called after each trial. `start` (free-parameter name to value) is the first trial's proposal, as when a
    refining calibration starts from an earlier fit."""
    import optuna
    from optuna.distributions import FloatDistribution
    from arthasim.world import _registry_path

    registry = ParamRegistry.load(_registry_path(config), overrides=config.param_overrides)
    frees = resolve_params(params, registry)
    _, default_targets = load_space()
    suite = {c.id: c for c in load_suite("core", registry)}
    target_ids = list(targets) if targets is not None else default_targets
    unknown = [t for t in target_ids if t not in suite or suite[t].kind != "target"]
    if unknown:
        raise ValueError(f"not target checks of the core suite: {', '.join(unknown)}")
    checks: list[Check] = [suite[t] for t in target_ids]
    seeds = tuple(int(s) for s in seeds)
    if months < 2:
        raise ValueError("months must be at least 2: statistics leave out the first month")
    until = _last_day(config.start, months)
    second = config.start.replace(day=1) + dt.timedelta(days=32)
    month_names = statistics.month_list((f"{second:%Y-%m}", f"{until:%Y-%m}"))
    goal = {c.id: target_values(c, registry, month_names)[0] for c in checks}
    folder = Path(path) if path is not None else Path(tempfile.mkdtemp(prefix="calibration-", dir=_ensure(config.out_dir)))
    folder.mkdir(parents=True, exist_ok=True)

    level = optuna.logging.get_verbosity()
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(direction="minimize", sampler=optuna.samplers.TPESampler(
        seed=sampler_seed, multivariate=True, n_startup_trials=min(20, trials)))
    dists = {f.name: FloatDistribution(f.low, f.high, log=f.log) for f in frees}
    if start is not None:
        study.enqueue_trial({f.name: min(max(float(start[f.name]), f.low), f.high) for f in frees})
    n_workers = max(1, min(int(workers), len(seeds)))
    pool = ProcessPoolExecutor(max_workers=n_workers, mp_context=multiprocessing.get_context("spawn")) \
        if n_workers > 1 else None
    rows: list[dict[str, Any]] = []
    best: tuple[float, int, dict] | None = None
    try:
        for t in range(trials):
            trial = study.ask(dists)
            values = [trial.params[f.name] for f in frees]
            ov = overrides(registry, frees, values)
            cfg = config.with_params(**ov)
            jobs = [(cfg, s, until, [c.id for c in checks], str(folder / f"t{t:04d}-s{s}")) for s in seeds]
            per_seed = list(pool.map(_trial_seed, *zip(*jobs))) if pool else [_trial_seed(*j) for j in jobs]
            mean: dict[str, dict[str, float]] = {}
            scores: dict[str, dict[str, float]] = {}
            for c in checks:
                comps = {}
                for comp in goal[c.id]:
                    got = [r.get(c.id, {}).get(comp) for r in per_seed]
                    if all(g is not None for g in got):
                        comps[comp] = sum(got) / len(got)
                mean[c.id] = comps
                scores[c.id] = {comp: (score(comps[comp], tgt, c.compare, c.tolerance) if comp in comps
                                       else MISSING_SCORE) for comp, tgt in goal[c.id].items()}
            value = loss(scores)
            study.tell(trial, value)
            row: dict[str, Any] = {"trial": t, "loss": value}
            row.update({f"free:{f.name}": float(v) for f, v in zip(frees, values)})
            for c in checks:
                for comp in goal[c.id]:
                    row[f"sim:{c.id}:{comp}"] = mean[c.id].get(comp)
                    row[f"score:{c.id}:{comp}"] = scores[c.id][comp]
            rows.append(row)
            if best is None or value < best[0]:
                best = (value, t, {"ov": ov, "free": dict(zip([f.name for f in frees], map(float, values))),
                                   "scores": scores, "mean": mean})
            if progress is not None:
                progress(t, value, best[0])
    finally:
        if pool is not None:
            pool.shutdown()
        optuna.logging.set_verbosity(level)
        if path is None:
            shutil.rmtree(folder, ignore_errors=True)
    assert best is not None
    import arthasim
    return CalibrationResult(
        best=best[2]["ov"], free=best[2]["free"], loss=best[0], scores=best[2]["scores"],
        simulated=best[2]["mean"], targets=goal, trials=pl.DataFrame(rows),
        registry_version=ParamRegistry.load(_registry_path(config)).version(),
        config=config.model_dump(mode="json", exclude={"release_secret"}), seeds=seeds, months=months,
        sampler_seed=sampler_seed,
        space=[{k: v for k, v in f.__dict__.items() if v is not None and v is not False} for f in frees],
        versions={"optuna": optuna.__version__, "arthasim": arthasim.__version__, "polars": pl.__version__})


def _ensure(folder: str) -> str:
    Path(folder).mkdir(parents=True, exist_ok=True)
    return folder
