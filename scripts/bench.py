"""Phase 0 gate run: simulate, then report throughput and memory.

    python scripts/bench.py --tier XS --days 90 --seed 7 --out runs
    python scripts/bench.py --tier S --days 90 --seed 7 --out runs --set transfer.allowance_margin=0.1
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import resource
import sys
import time

import numpy as np
import yaml

from arthasim import Config, World


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", default="XS")
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="runs")
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                    help="override a registry parameter; repeatable")
    args = ap.parse_args(argv)

    overrides = {k: yaml.safe_load(v) for k, v in (s.split("=", 1) for s in args.set)}
    config = Config.tier(args.tier, out_dir=f"{args.out}/bench-{int(time.time())}").with_params(**overrides)
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
        "param_overrides": overrides,
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
    "transfers": ("ALLOWANCE",),
}

_PAYER_PERSON = """
    from payments y
    join accounts a on a.account_id = y.payer_account_id
    join persons p on p.entity_id = a.holder_entity_id"""


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
    by_stage = run.sql(f"""
        select p.life_stage as k, avg(case when y.status = 'DECLINED_FUNDS' then 1.0 else 0.0 end) as share
        {_PAYER_PERSON}
        group by 1 order by 2 desc""")
    no_income = run.sql(f"""
        with d as (
            select p.household_id, strftime(make_timestamp(y.intent_ts) + interval 330 minute, '%Y-%m') as month
            {_PAYER_PERSON}
            where y.status = 'DECLINED_FUNDS')
        select avg(case when h.income_paise = 0 then 1.0 else 0.0 end) as share
        from d join truth_household_monthly h on h.household_id = d.household_id and h.month = d.month""")
    by_days = run.sql("""
        with recv as (
            select b.holder_entity_id as person, y.intent_ts as ts
            from payments y join accounts b on b.account_id = y.payee_account_id
            where y.purpose = 'ALLOWANCE' and y.status = 'SUCCESS'),
        att as (
            select p.entity_id as person, y.intent_ts as ts, y.status
            from payments y join accounts a on a.account_id = y.payer_account_id
            join persons p on p.entity_id = a.holder_entity_id
            where p.life_stage in ('homemaker', 'studying', 'seeking')
              and y.purpose not in ('ALLOWANCE', 'CASH_WITHDRAWAL', 'CASH_DEPOSIT')),
        j as (
            select att.status, (att.ts - recv.ts) // 86400000000 as days
            from att asof join recv on att.person = recv.person and att.ts >= recv.ts)
        select case when days < 10 then '0-9' when days < 20 then '10-19' when days < 25 then '20-24'
                    when days < 30 then '25-29' else '30+' end as k,
               avg(case when status = 'DECLINED_FUNDS' then 1.0 else 0.0 end) as share
        from j group by 1 order by 1""")
    s, book = world.state, world.state.book
    cash = book.type == T.CASH
    held = lambda accounts: int(book.balance[accounts].sum()) / 100
    return {
        "rail_share": shares("rail"),
        "purpose_group_share": groups,
        "spend_to_income_median_by_month": {mo: round(r, 3) for mo, r, _ in ratio.iter_rows()},
        "declined_funds_by_life_stage": {k: round(v, 4) for k, v in by_stage.iter_rows()},
        "declined_funds_by_rail": {k: round(float(v), 4) for k, v in run.sql(
            "select rail, avg(case when status = 'DECLINED_FUNDS' then 1.0 else 0.0 end) from payments "
            "group by 1 order by 1").iter_rows()},
        "declined_funds_no_income_households": round(float(no_income["share"][0] or 0.0), 4),
        "recipient_declined_by_days_since_allowance": {k: round(v, 4) for k, v in by_days.iter_rows()},
        "allowance_scaled_households": _scaled_households(world),
        "allowance_margin_short_households": _margin_short_households(world),
        "cash_held_rupees_at_end": {
            "persons": held(s.person_cash), "merchants": held(s.merchant_cash), "billers": held(s.biller_cash),
            "bank_vaults": held(s.bank_vault), "boundary": held([s.boundary_cash]),
            "total": int(book.balance[cash].sum()) / 100},
    }


def _scaled_households(world) -> float:
    """Of households with both surplus and shortfall in the last simulated month, the share whose
    allowances are scaled down because surplus cannot cover every shortfall."""
    from arthasim.modules.allowance import allowance_need, household_scale

    pop = world.state.population
    hh, income = pop.households.household_of_person, pop.attributes.monthly_income_paise
    need = allowance_need(world)
    scale = household_scale(hh, income, need)
    n = scale.size
    short = np.bincount(hh, weights=np.maximum(0.0, need - income), minlength=n) > 0
    surplus = np.bincount(hh, weights=np.maximum(0.0, income - need), minlength=n) > 0
    both = short & surplus
    return round(float((scale[both] < 1).mean()), 4) if both.any() else 0.0


def _margin_short_households(world) -> float:
    """Of households with both surplus and a recipient in the last simulated month, the share whose
    leftover surplus cannot pay every recipient's full margin."""
    from arthasim.modules.allowance import allowance_need, margin_scale

    pop = world.state.population
    hh, income = pop.households.household_of_person, pop.attributes.monthly_income_paise
    need = allowance_need(world)
    scale = margin_scale(hh, income, need, world.params.get("transfer.allowance_margin"))
    n = scale.size
    short = np.bincount(hh, weights=np.maximum(0.0, need - income), minlength=n) > 0
    surplus = np.bincount(hh, weights=np.maximum(0.0, income - need), minlength=n) > 0
    both = short & surplus
    return round(float((scale[both] < 1).mean()), 4) if both.any() else 0.0


if __name__ == "__main__":
    main()
