"""Figures for docs/phase1e_results.md (plan 1e).

    python scripts/phase1e_results.py --out runs/phase1e > runs/phase1e/results.json
    python scripts/phase1e_results.py --part seed --seed 8 --out runs/phase1e-seed8 > runs/phase1e-seed8/seed.json

Runs tier S (seed 7) from 1 April to 30 November 2025 twice, with the committed calibration and with the registry
defaults, validates both with the core suite, and prints a JSON summary: every report row of both runs, month-by-month
drift, timings, and the calibration's fitted values and loss path.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import polars as pl

from arthasim import Config, Run, World, statistics
from arthasim.calibration import CalibrationResult
from arthasim.validation import load_suite

ROOT = Path(__file__).resolve().parents[1]


def _rows(table: pl.DataFrame) -> list[dict]:
    return [{k: r[k] for k in ("check", "kind", "component", "simulated", "target", "lower", "upper", "status",
                               "detail")} for r in table.iter_rows(named=True)]


def _monthly(run) -> dict:
    """Month by month (May to November): basic accounts' mean month-end balance, MPCE and UPI P2M per adult."""
    out = {}
    for month in statistics.month_list(statistics.window(run)):
        ctx = statistics.context(run, (month, month))
        out[month] = {k: {c: round(v, 4) for c, v in statistics.STATISTICS[k](ctx).items()}
                      for k in ("balances.basic_mean", "consumption.mpce", "payments.upi_p2m_per_adult",
                                "pay.regular_monthly")}
    return out


def one(config: Config, label: str, out: Path) -> dict:
    started = time.perf_counter()
    world = World.build(config.model_copy(update={"out_dir": str(out / label)}), seed=7, checkpoints=False)
    run = world.run("2025-11-30")
    simulated = time.perf_counter() - started
    started = time.perf_counter()
    report = run.validate("core")
    validated = time.perf_counter() - started
    report.report(out / f"{label}_report.md")
    table = report.table()
    return {"path": run.path, "payments": run.manifest["payments"], "simulate_seconds": round(simulated, 1),
            "validate_seconds": round(validated, 1), "passed": report.passed,
            "failed_checks": sorted(set(table.filter(pl.col("status") == "fail")["check"].to_list())),
            "rows": _rows(table), "monthly": _monthly(run)}


_DAY = "extract(day from make_timestamp(y.settle_ts) + interval 330 minute)"


def month_start(run) -> dict:
    """What makes up the month-start statistic: for each kind of payment, its value per day on the 1st to 3rd over
    that on the 10th to 25th, May to November (successful payments, all persons and organisations)."""
    out = {"spike": statistics.STATISTICS["payments.month_start_spike"](statistics.context(run))["all"]}
    kinds = {"salary": "y.purpose = 'SALARY'", "allowance": "y.purpose = 'ALLOWANCE'",
             "allowance_upi": "y.purpose = 'ALLOWANCE' and y.rail like 'UPI%'", "upi_p2m": "y.rail = 'UPI_P2M'",
             "upi_p2p": "y.rail = 'UPI_P2P'"}
    window = run.window("2025-05-01", "2025-11-30")
    for name, where in kinds.items():
        q = window.sql(f"""select sum(case when {_DAY} between 1 and 3 then y.amount_paise end) / 3.0
                                  / (sum(case when {_DAY} between 10 and 25 then y.amount_paise end) / 16.0) as r
                           from payments y where y.status = 'SUCCESS' and {where}""")
        out[name] = q["r"][0]
    payday = run.sql("""select o.payday, count(*) as staff from entity_state_monthly e join orgs o
                        on o.entity_id = e.employer_entity_id where e.month = '2025-05' and e.life_stage = 'salaried'
                        group by 1 order by 2 desc limit 3""")
    out["largest_paydays"] = [{"day": d, "salaried": n} for d, n in payday.iter_rows()]
    return out


def seed_part(fit: CalibrationResult, seed: int, out: Path) -> dict:
    """The calibrated run at another seed: its failing checks and the month-start decomposition."""
    config = fit.apply(Config.tier("S", out_dir=str(out / f"seed{seed}")))
    run = World.build(config, seed=seed, checkpoints=False).run("2025-11-30")
    table = run.validate("core").table()
    return {"seed": seed, "failed_checks": sorted(set(table.filter(pl.col("status") == "fail")["check"].to_list())),
            "rows": _rows(table), "month_start": month_start(run)}


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", choices=["runs", "seed"], default="runs")
    ap.add_argument("--seed", type=int, default=7, help="with --part seed")
    ap.add_argument("--out", default="runs/phase1e")
    ap.add_argument("--fitted", default=str(ROOT / "params" / "calibration" / "fitted.yaml"))
    args = ap.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    fit = CalibrationResult.load(args.fitted)
    if args.part == "seed":
        result = seed_part(fit, args.seed, out)
        json.dump(result, sys.stdout, indent=1, default=str)
        return result
    best_so_far, running = [], float("inf")
    for v in fit.trials["loss"].to_list():
        running = min(running, v)
        best_so_far.append(running)
    result = {
        "calibration": {"loss": fit.loss, "trials": fit.trials.height, "best_trial":
                        int(fit.trials.filter(pl.col("loss") == fit.loss)["trial"][0]),
                        "best_so_far": {k: best_so_far[k - 1] for k in (1, 20, 50, 100, 200, 300, 400)
                                        if k <= len(best_so_far)},
                        "free": fit.free, "space": fit.space, "scores": fit.scores, "simulated": fit.simulated,
                        "targets": fit.targets, "registry_version": fit.registry_version, "versions": fit.versions},
        "gaps": sorted(c.id for c in load_suite("core") if c.gap),
        "calibrated": one(fit.apply(Config.tier("S")), "calibrated", out),
        "default": one(Config.tier("S"), "default", out),
    }
    for label in ("calibrated", "default"):
        result[label]["month_start"] = month_start(Run.open(result[label]["path"]))
    json.dump(result, sys.stdout, indent=1, default=str)
    return result


if __name__ == "__main__":
    main()
