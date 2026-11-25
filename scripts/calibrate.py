"""Run the default calibration (plan 1e) and write the fitted set, its trials and a report.

    python scripts/calibrate.py --trials 400 --workers 3 --out params/calibration/fitted.yaml

The fitted set is `<out>`, the trials `<stem>_trials.parquet`, the report `<stem>_report.md`.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from arthasim import CalibrationResult, Config, ParamRegistry, calibrate
from arthasim.calibration import load_space, refine

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=200)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--persons", type=int, default=10_000)
    ap.add_argument("--months", type=int, default=8)
    ap.add_argument("--seeds", default="1,2,3")
    ap.add_argument("--sampler-seed", type=int, default=0)
    ap.add_argument("--work", default="runs/calibration", help="folder for the trial runs (each removed when scored)")
    ap.add_argument("--out", default="params/calibration/fitted.yaml")
    ap.add_argument("--around", help="refine: the default space, narrowed around this earlier fit for the parameters "
                                     "it fitted, starting from it")
    ap.add_argument("--width", type=float, default=0.25, help="with --around: the narrowing (see calibration.narrow)")
    args = ap.parse_args(argv)

    config = Config.tier("S", persons=args.persons, out_dir=args.work)
    params, start = None, None
    if args.around:
        earlier = CalibrationResult.load(args.around)
        frees, _ = load_space()
        registry = ParamRegistry.load(ROOT / config.params_path)
        params, start = refine(frees, earlier.free, registry, args.width)
    started = time.perf_counter()

    def progress(trial: int, loss: float, best: float) -> None:
        print(f"trial {trial + 1}/{args.trials}  loss {loss:.4g}  best {best:.4g}  "
              f"{time.perf_counter() - started:.0f}s", flush=True)

    result = calibrate(config, params=params, trials=args.trials, seeds=tuple(int(s) for s in args.seeds.split(",")),
                       months=args.months, workers=args.workers, sampler_seed=args.sampler_seed, progress=progress,
                       start=start, log=Path(args.out).with_name(f"{Path(args.out).stem}_trials.partial.parquet"))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    result.save(out)
    out.with_name(f"{out.stem}_trials.partial.parquet").unlink(missing_ok=True)
    result.report(out.with_name(f"{out.stem}_report.md"))
    print(f"best loss {result.loss:.4g} after {args.trials} trials in {time.perf_counter() - started:.0f}s; "
          f"wrote {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
