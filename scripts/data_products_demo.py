"""Open a finished run and time each data-product call; prints JSON (seconds and rows per call).

    python scripts/data_products_demo.py runs/.../S-seed7-xxxxxxxx --bank SYNB03 --out /tmp/export
"""
from __future__ import annotations

import argparse
import json
import resource
import sys
import time
from pathlib import Path

import polars as pl

from arthasim import Run


def _timed(results: dict, name: str, fn):
    started = time.perf_counter()
    out = fn()
    seconds = round(time.perf_counter() - started, 3)
    rows = out.height if isinstance(out, pl.DataFrame) else len(out) if isinstance(out, (list, dict)) else None
    results[name] = {"seconds": seconds, "rows": rows}
    return out


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_path")
    ap.add_argument("--bank", default="SYNB03")
    ap.add_argument("--entity", type=int, default=None, help="person to inspect (default: the first salaried one)")
    ap.add_argument("--out", default=None, help="folder for the bank export (default: <run>-export-<bank>)")
    args = ap.parse_args(argv)
    r: dict = {}

    run = _timed(r, "Run.open", lambda: Run.open(args.run_path))
    _timed(r, "run.table payments UPI_P2M count",
           lambda: run.table("payments").filter(pl.col("rail") == "UPI_P2M").select(pl.len()).collect())
    _timed(r, "run.sql status counts", lambda: run.sql("select status, count(*) n from payments group by 1"))

    bank = run.view("bank", bank=args.bank)
    for t in ("customers", "accounts", "payments", "statement_lines", "balances_monthly"):
        _timed(r, f"bank view {t}", lambda t=t: bank.table(t).collect())
    _timed(r, "switch view upi counts by rail and status",
           lambda: run.view("switch").sql("select rail, status, count(*) n from payments group by 1, 2"))
    _timed(r, "switch view atm payments", lambda: run.view("switch", network="atm").table("payments").collect())
    _timed(r, "bureau view consumers", lambda: run.view("bureau").table("consumers").collect())

    eid = args.entity
    if eid is None:
        eid = int(run.sql("""select entity_id from entity_state_monthly where life_stage = 'salaried' and has_account
                             order by month, entity_id limit 1""")["entity_id"][0])
    trace = _timed(r, "run.inspect", lambda: run.inspect(eid))
    _timed(r, "inspect.profile", lambda: trace.profile()["accounts"])
    _timed(r, "inspect.timeline", trace.timeline)
    _timed(r, "inspect.passbook", trace.passbook)
    _timed(r, "inspect.net_worth", trace.net_worth)
    _timed(r, "inspect.ego_network", trace.ego_network)

    for name in ("txn_volume", "decline_rate", "consumption", "cash_withdrawal", "deposit_balance"):
        by = None if name == "deposit_balance" else "month"
        _timed(r, f"metric {name}", lambda name=name, by=by: run.metric(name, by=by))

    out = Path(args.out or f"{args.run_path.rstrip('/')}-export-{args.bank}")
    _timed(r, "export bank", lambda: run.export(out, view="bank", bank=args.bank) and [])
    size = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    result = {"run": run.manifest["run_id"], "bank": args.bank, "entity": eid, "calls": r,
              "export_mb": round(size / 1e6, 1), "export_path": str(out),
              "peak_rss_mb": round(rss / (1e6 if sys.platform == "darwin" else 1e3))}
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    main()
