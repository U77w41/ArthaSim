"""Plan 1d-2 results: a paired DBT experiment at tier S, and a checkpoint demonstration.

    python scripts/phase1d2_results.py --part experiment --workers 4 --seeds 1-10 --out runs/1d2
    python scripts/phase1d2_results.py --part checkpoint --out runs/1d2

Each prints one JSON object; docs/phase1d2_results.md quotes them.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import resource
import sys
import time
from pathlib import Path

import polars as pl

from arthasim import Config, Experiment, Scenario, World
from arthasim.interventions import DBTTransfer

FARMERS = "life_stage == 'farm' and not helper"


def _mb(rss: int) -> int:
    return round(rss / (1e6 if sys.platform == "darwin" else 1e3))


def _seeds(text: str) -> list[int]:
    if "-" in text:
        lo, hi = text.split("-")
        return list(range(int(lo), int(hi) + 1))
    return [int(s) for s in text.split(",")]


def _rows(frame: pl.DataFrame) -> list[dict]:
    return frame.to_dicts()


def _config(out: Path, persons: int | None) -> Config:
    return Config.tier("S", out_dir=str(out), **({"persons": persons} if persons else {}))


def experiment(out: Path, workers: int, seeds: list[int], persons: int | None = None) -> dict:
    config = _config(out, persons)
    base = Scenario.baseline()
    treat = base.add(DBTTransfer("DBT_2000", 2000, FARMERS, ["2025-11-15"]))
    exp = Experiment(config, base, {"dbt_2000": treat}, seeds, "2025-11-01", "2025-12-31",
                     path=out / f"experiment-w{workers}")
    started = time.perf_counter()
    res = exp.run(workers=workers)
    wall = time.perf_counter() - started
    payees = [int(r.sql("select count(*) as n from truth_dbt_monthly where scheme = 'DBT_2000' and enrolled")["n"][0])
              for r in res.runs("dbt_2000")]
    res.report(out / f"report-w{workers}.md")
    return {
        "path": str(res.path), "workers": workers, "seeds": seeds, "wall_seconds": round(wall, 1),
        "peak_rss_mb_parent": _mb(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
        "peak_rss_mb_children": _mb(resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss),
        "payees_per_seed": payees,
        "cash_withdrawal": _rows(res.effect("cash_withdrawal", fill=0)),
        "cash_withdrawal_by_month": _rows(res.effect("cash_withdrawal", by="month", fill=0)),
        "cash_withdrawal_by_district": _rows(res.effect("cash_withdrawal", by="district", fill=0)),
        "consumption": _rows(res.effect("consumption", fill=0)),
        "funds_declines": _rows(res.effect("txn_volume", status="DECLINED_FUNDS", fill=0)),
        "apbs_credits": _rows(res.effect("txn_volume", by="rail", fill=0).filter(pl.col("rail") == "APBS")),
    }


def _files(path: str) -> dict[str, str]:
    root = Path(path)
    return {str(f.relative_to(root)): hashlib.sha256(f.read_bytes()).hexdigest()
            for f in sorted(root.rglob("*.parquet")) if f.relative_to(root).parts[0] != "checkpoints"}


def checkpoint(out: Path, persons: int | None = None) -> dict:
    root = out / "checkpoint-demo"
    config = _config(root, persons)
    plain = World.build(config, 7, path=root / "plain", checkpoints=False).run("2025-07-31")
    world = World.build(config, 7, path=root / "saved", checkpoints=False)
    world.run("2025-05-31")
    started = time.perf_counter()
    world.save(root / "ck")
    save_s = time.perf_counter() - started
    started = time.perf_counter()
    child = world.fork(path_out=root / "fork")
    fork_s = time.perf_counter() - started
    del child
    started = time.perf_counter()
    loaded = World.load(root / "ck", path_out=root / "resumed", checkpoints=False)
    load_s = time.perf_counter() - started
    resumed = loaded.run("2025-07-31")
    a, b = _files(plain.path), _files(resumed.path)
    ma, mb = plain.manifest, resumed.manifest
    differ = sorted(k for k in set(ma) | set(mb) if ma.get(k) != mb.get(k))
    return {
        "files": len(a), "all_match": a == b, "file_hashes": {k: [a.get(k), b.get(k)] for k in sorted(set(a) | set(b))},
        "content_hash_match": ma["content_hash"] == mb["content_hash"],
        "manifest_fields_that_differ": {k: [ma.get(k), mb.get(k)] for k in differ},
        "save_seconds": round(save_s, 2), "world_pkl_mb": round((root / "ck" / "world.pkl").stat().st_size / 1e6, 1),
        "checkpoint_json_kb": round((root / "ck" / "checkpoint.json").stat().st_size / 1e3, 1),
        "fork_seconds": round(fork_s, 2), "load_seconds": round(load_s, 2),
        "prefix_days": 61, "resumed_days": mb["days"],
    }


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", choices=["experiment", "checkpoint"], required=True)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--seeds", default="1-10")
    ap.add_argument("--out", default="runs/1d2")
    ap.add_argument("--persons", type=int, default=None, help="smaller than tier S, for a smoke test only")
    args = ap.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    result = (experiment(out, args.workers, _seeds(args.seeds), args.persons) if args.part == "experiment"
              else checkpoint(out, args.persons))
    print(json.dumps(result, indent=2, default=str))
    return result


if __name__ == "__main__":
    main()
