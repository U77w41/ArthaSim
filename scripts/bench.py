"""Phase 0 gate run: simulate, then report throughput and memory.

    python scripts/bench.py --tier XS --days 90 --seed 7 --out runs
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import resource
import sys
import time

from arthasim import Config, World


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", default="XS")
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="runs")
    args = ap.parse_args(argv)

    config = Config.tier(args.tier, out_dir=f"{args.out}/bench-{int(time.time())}")
    started = time.perf_counter()
    world = World.build(config, seed=args.seed)
    build_seconds = time.perf_counter() - started
    run = world.run(until=config.start + dt.timedelta(days=args.days - 1))
    total_seconds = time.perf_counter() - started

    m = run.manifest
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    status = run.sql("select status, count(*) as n from payments group by 1 order by 2 desc")
    result = {
        "days": m["days"],
        "payments": m["payments"],
        "wall_seconds": m["wall_seconds"],
        "payments_per_second": round(m["payments"] / m["wall_seconds"]),
        "peak_rss_mb": round(rss / (1e6 if sys.platform == "darwin" else 1e3)),
        "payments_per_person_day": round(m["payments"] / (config.persons * m["days"]), 3),
        "build_seconds": round(build_seconds, 2),
        "total_seconds": round(total_seconds, 2),
        "status_share": {s: round(n / m["payments"], 4) for s, n in status.iter_rows()},
        "run_path": run.path,
    }
    if m.get("builder") == "population":
        count = lambda sql: int(run.sql(sql)["n"][0])
        edges = run.sql("select type, count(*) as n from edges group by 1 order by 1")
        result.update({
            "scale_factor": m["scale_factor"],
            "max_l1": round(m["build_report"]["max_l1"], 5),
            "l1": {d: {k: round(v, 5) for k, v in margins.items()} for d, margins in m["build_report"]["l1"].items()},
            "households": count("select count(*) as n from households"),
            "employers": count("select count(*) as n from orgs where kind = 'EMPLOYER'"),
            "merchants": count("select count(*) as n from orgs where kind = 'MERCHANT'"),
            "accounts": count("select count(*) as n from accounts"),
            "edges_by_type": {int(t): int(n) for t, n in edges.iter_rows()},
            "unbanked_share": round(count("select count(*) as n from persons where not has_account") / config.persons, 4),
        })
    if m.get("builder") == "population" and "truth_household_monthly" in run.tables():
        result.update(_money_flow_summary(world, run))
    print(json.dumps(result, indent=2))
    return result


_GROUPS = {
    "income": ("SALARY", "EARNINGS", "PENSION", "EMPLOYER_REVENUE", "REMITTANCE"),
    "spending": ("GROCERY", "FOOD", "FUEL", "PHARMACY", "APPAREL", "ELECTRONICS", "TRANSPORT", "SERVICES",
                 "OTHER", "UTILITIES", "TELECOM", "MEDICAL"),
    "cash": ("CASH_WITHDRAWAL", "CASH_DEPOSIT"),
}


def _money_flow_summary(world, run) -> dict:
    from arthasim.ledger.instruments import InstrumentType as T

    def shares(column: str) -> dict:
        frame = run.sql(f"select {column} as k, count(*) as n from payments group by 1 order by 2 desc")
        total = int(frame["n"].sum())
        return {k: round(n / total, 4) for k, n in frame.iter_rows()}

    by_purpose = shares("purpose")
    groups = {g: round(sum(by_purpose.get(p, 0.0) for p in names), 4) for g, names in _GROUPS.items()}
    spend_list = ", ".join(f"'{p}'" for p in _GROUPS["spending"])
    ratio = run.sql(f"""
        with spend as (
            select p.household_id,
                   strftime(make_timestamp(y.settle_ts) + interval 330 minute, '%Y-%m') as month,
                   sum(y.amount_paise) as spent
            from payments y
            join accounts a on a.account_id = y.payer_account_id
            join persons p on p.entity_id = a.holder_entity_id
            where y.status = 'SUCCESS' and y.purpose in ({spend_list})
            group by 1, 2)
        select h.month, median(coalesce(s.spent, 0) / h.income_paise) as median_ratio, count(*) as households
        from truth_household_monthly h
        left join spend s on s.household_id = h.household_id and s.month = h.month
        where h.income_paise > 0
        group by 1 order by 1""")
    s, book = world.state, world.state.book
    cash = book.type == T.CASH
    held = lambda accounts: int(book.balance[accounts].sum()) / 100
    return {
        "rail_share": shares("rail"),
        "purpose_group_share": groups,
        "spend_to_income_median_by_month": {mo: round(r, 3) for mo, r, _ in ratio.iter_rows()},
        "cash_held_rupees_at_end": {
            "persons": held(s.person_cash), "merchants": held(s.merchant_cash), "billers": held(s.biller_cash),
            "bank_vaults": held(s.bank_vault), "boundary": held([s.boundary_cash]),
            "total": int(book.balance[cash].sum()) / 100},
    }


if __name__ == "__main__":
    main()
