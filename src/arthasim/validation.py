"""Validation suites and `run.validate` (plan 1e). A suite (`params/validation/<name>.yaml`) lists hard checks,
target checks and holdouts; each target and holdout compares a simulated statistic (`arthasim.statistics`) with a
registry row. The report is written into the run as `validation_report.parquet`."""
from __future__ import annotations

import io
import math
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

import polars as pl
import yaml

from arthasim import checks, statistics
from arthasim.params import ParamRegistry
from arthasim.store.parquet import write_atomic

if TYPE_CHECKING:
    from arthasim.world import Run

KINDS = ("hard", "target", "holdout")
COMPARE = ("relative", "absolute", "at_most")
HARD: dict[str, Callable[..., list[dict[str, Any]]]] = {
    "ledger": lambda run, secret: checks.ledger(run),
    "determinism": lambda run, secret: checks.determinism(run, release_secret=secret),
    "identifiers": lambda run, secret: checks.identifiers(run),
}
SCHEMA = {"suite": pl.String, "check": pl.String, "kind": pl.String, "component": pl.String,
          "target_id": pl.String, "target_status": pl.String, "simulated": pl.Float64, "target": pl.Float64,
          "lower": pl.Float64, "upper": pl.Float64, "status": pl.String, "window": pl.String, "detail": pl.String,
          "gap": pl.String}
_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Check:
    id: str
    kind: str
    statistic: str
    why: str
    target: str | None = None
    compare: str | None = None
    tolerance: float | None = None
    gap: str | None = None


def suite_path(name_or_path: str | Path) -> Path:
    p = Path(name_or_path)
    if p.suffix in (".yaml", ".yml") or p.exists():
        return p
    return _ROOT / "params" / "validation" / f"{name_or_path}.yaml"


def load_suite(name_or_path: str | Path = "core", params: ParamRegistry | None = None) -> list[Check]:
    """The suite's checks; every target row, statistic and comparison must exist."""
    path = suite_path(name_or_path)
    if params is None:
        params = ParamRegistry.load(_ROOT / "params" / "registry.yaml")
    out = []
    for raw in (yaml.safe_load(path.read_text()) or {}).get("checks", []):
        c = Check(id=raw["id"], kind=raw["kind"], statistic=raw.get("statistic", raw["id"]), why=raw.get("why", ""),
                  target=raw.get("target"), compare=raw.get("compare"), tolerance=raw.get("tolerance"),
                  gap=raw.get("gap"))
        if c.kind not in KINDS:
            raise ValueError(f"{path.name}: check {c.id}: kind must be one of {KINDS}")
        if c.kind == "hard":
            if c.statistic not in HARD:
                raise ValueError(f"{path.name}: check {c.id}: no hard check {c.statistic!r}")
        else:
            if c.statistic not in statistics.STATISTICS:
                raise ValueError(f"{path.name}: check {c.id}: no statistic {c.statistic!r}")
            if c.compare not in COMPARE or not (c.tolerance and c.tolerance > 0):
                raise ValueError(f"{path.name}: check {c.id}: needs compare in {COMPARE} and a positive tolerance")
            if c.target is not None and c.target not in params:
                raise ValueError(f"{path.name}: check {c.id}: no registry row {c.target!r}")
            if c.target is None and c.compare != "at_most":
                raise ValueError(f"{path.name}: check {c.id}: only an at_most check may have no target row")
        out.append(c)
    return out


# Targets --------------------------------------------------------------------------------------------------------

def _monthly_mean(params: ParamRegistry, row: str, months: list[str]) -> tuple[float, str]:
    """The mean of a monthly row over the window's months (all its months when none overlap)."""
    values = params.get(row)
    used = [m for m in months if m in values] or sorted(values)
    note = "" if used == [m for m in months if m in values] and used else f"; {row} has none of the window's months, so all its months are used"
    return sum(values[m] for m in used) / len(used), note


def _per_adult(params, row, months, factor=1.0):
    mean, note = _monthly_mean(params, row, months)
    return {"all": mean * factor / float(params.get("population.adults_18plus"))}, note


def _ticket(params, value_row, volume_row, months):
    values, volumes = params.get(value_row), params.get(volume_row)
    used = [m for m in months if m in values] or sorted(values)
    # crore (1e7 rupees) over million (1e6 transactions): rupees per transaction.
    return {"all": sum(values[m] for m in used) * 1e7 / (sum(volumes[m] for m in used) * 1e6)}, ""


TARGETS: dict[str, Callable[[ParamRegistry, list[str]], tuple[dict[str, float], str]]] = {
    "labour.stages": lambda p, m: ({}, ""),
    "consumption.mpce": lambda p, m: ({a: p.get("consumption.mpce")[a] * p.get("consumption.hces_uprate")[a]
                                       for a in ("rural", "urban")}, "; HCES 2023-24 MPCE times consumption.hces_uprate"),
    "payments.upi_p2m_per_adult": lambda p, m: _per_adult(p, "upi.volume.monthly", m,
                                                          p.get("upi.p2m.share")["volume"]),
    "payments.upi_p2p_per_adult": lambda p, m: _per_adult(p, "upi.volume.monthly", m,
                                                          1.0 - p.get("upi.p2m.share")["volume"]),
    "payments.debit_card_per_adult": lambda p, m: _per_adult(p, "cards.debit.volume_monthly", m),
    "payments.atm_per_adult": lambda p, m: _per_adult(p, "atm.withdrawal.volume_monthly", m),
    "payments.atm_ticket": lambda p, m: _ticket(p, "atm.withdrawal.value_monthly", "atm.withdrawal.volume_monthly", m),
    "payments.debit_card_ticket": lambda p, m: _ticket(p, "cards.debit.value_monthly", "cards.debit.volume_monthly", m),
    "accounts.inoperative": lambda p, m: ({"all": 1.0 - p.get("inclusion.pmjdy.operative_share")}, ""),
}


def target_values(check: Check, params: ParamRegistry, months: list[str]) -> tuple[dict[str, float], str]:
    """The published value(s) a check compares with, by component, and a note on how they were derived."""
    if check.statistic in TARGETS:
        return TARGETS[check.statistic](params, months)
    value = params.get(check.target)
    if isinstance(value, dict):
        return {k: float(v) for k, v in value.items()}, ""
    return {"all": float(value)}, ""


def band(compare: str, target: float, tolerance: float) -> tuple[float | None, float]:
    if compare == "relative":
        return target * (1 - tolerance), target * (1 + tolerance)
    if compare == "absolute":
        return target - tolerance, target + tolerance
    return None, tolerance


# The report -----------------------------------------------------------------------------------------------------

class ValidationReport:
    """One row per check component. `passed` is true when no check failed; skipped checks do not fail."""

    def __init__(self, frame: pl.DataFrame) -> None:
        self._frame = frame

    @property
    def passed(self) -> bool:
        return bool((self._frame["status"] != "fail").all())

    def table(self) -> pl.DataFrame:
        return self._frame

    def failures(self) -> pl.DataFrame:
        return self._frame.filter(pl.col("status") == "fail")

    @classmethod
    def open(cls, run: "Run") -> "ValidationReport":
        return cls(run.table("validation_report").collect())

    def report(self, path: str | Path) -> None:
        """Markdown: every row, grouped by kind."""
        f = self._frame
        lines = [f"# Validation report: suite {f['suite'][0] if f.height else ''}", "",
                 f"Passed: {'yes' if self.passed else 'no'}. Failed: {self.failures().height} of {f.height} rows; "
                 f"skipped: {(f['status'] == 'skipped').sum()}.", ""]
        def fmt(v) -> str:
            if v is None or (isinstance(v, float) and math.isnan(v)):
                return ""
            return f"{v:,.0f}" if abs(v) >= 1000 else f"{v:.4g}"
        for kind in KINDS:
            rows = f.filter(pl.col("kind") == kind)
            if not rows.height:
                continue
            lines += [f"## {kind.capitalize()} checks", "",
                      "| Check | Component | Simulated | Target | Band | Status | Detail |",
                      "| :--- | :--- | ---: | ---: | :--- | :--- | :--- |"]
            for r in rows.iter_rows(named=True):
                lo, hi = fmt(r["lower"]), fmt(r["upper"])
                bandtxt = f"{lo} to {hi}" if lo else (f"at most {hi}" if hi else "")
                detail = r["detail"] + (f" Known gap: {r['gap']}" if r["gap"] else "")
                lines.append(f"| `{r['check']}` | {r['component']} | {fmt(r['simulated'])} | {fmt(r['target'])} | "
                             f"{bandtxt} | {r['status']} | {detail.replace('|', '/')} |")
            lines.append("")
        Path(path).write_text("\n".join(lines))


def validate(run: "Run", suite: str | Path = "core", release_secret: str | None = None,
             write: bool = True) -> ValidationReport:
    """Run a suite against a finished run. With `write`, the report replaces `validation_report.parquet` in it."""
    if run.months is not None:
        raise ValueError(f"validation reads whole runs; this Run is a window ({run.months[0]} to {run.months[1]})")
    params = statistics.run_params(run) if "config" in run.manifest else None
    name = suite_path(suite).stem
    population = run.manifest.get("builder") == "population"
    ctx = statistics.context(run) if params is not None and population else None
    window = f"{ctx.months[0]} to {ctx.months[1]}" if ctx is not None else None
    rows: list[dict[str, Any]] = []
    for check in load_suite(suite, params):
        base = {"suite": name, "check": check.id, "kind": check.kind, "target_id": check.target,
                "target_status": None, "gap": check.gap}
        if check.kind == "hard":
            for r in HARD[check.statistic](run, release_secret):
                rows.append({**base, "component": r["component"], "simulated": None, "target": None, "lower": None,
                             "upper": None, "status": r["status"], "window": None, "detail": r["detail"]})
            continue
        if check.target is not None and params is not None:
            row = params.table().filter(pl.col("id") == check.target)
            base["target_status"] = row["status"][0]
        if ctx is None or not population:
            reason = ("the run has no population (spike builder): the statistics need persons, households and "
                      "districts" if not population else "no complete month after the first" if params is not None
                      else "the run was made before plan 1e and has no recorded config")
            rows.append({**base, "component": "all", "simulated": None, "target": None, "lower": None,
                         "upper": None, "status": "skipped", "window": None, "detail": reason})
            continue
        targets, note = target_values(check, params, ctx.month_names)
        simulated = statistics.STATISTICS[check.statistic](ctx)
        components = sorted(set(targets) | set(simulated)) if check.compare != "at_most" else sorted(simulated)
        if not components:
            components = sorted(targets) or ["all"]
        for comp in components:
            sim, tgt = simulated.get(comp), targets.get(comp)
            if check.compare == "at_most":
                tgt = 0.0
            if sim is None or tgt is None:
                missing = "no simulated value (no persons in the group, or the run lacks the months)" if sim is None \
                    else "no published value for this component"
                rows.append({**base, "component": comp, "simulated": sim, "target": tgt, "lower": None,
                             "upper": None, "status": "skipped", "window": window, "detail": missing})
                continue
            lo, hi = band(check.compare, tgt, check.tolerance)
            ok = (lo is None or sim >= lo) and sim <= hi
            rows.append({**base, "component": comp, "simulated": float(sim), "target": float(tgt), "lower": lo,
                         "upper": hi, "status": "pass" if ok else "fail", "window": window,
                         "detail": f"{check.compare} band, tolerance {check.tolerance:g}{note}"})
    frame = pl.DataFrame(rows, schema=SCHEMA) if rows else pl.DataFrame(schema=SCHEMA)
    if write:
        buf = io.BytesIO()
        frame.write_parquet(buf)
        write_atomic(Path(run.path) / "validation_report.parquet", buf.getvalue())
    return ValidationReport(frame)
