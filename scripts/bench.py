"""Phase 0 gate run: simulate, then report throughput and memory.

    python scripts/bench.py --tier XS --days 90 --seed 7 --out runs
    python scripts/bench.py --tier S --days 90 --seed 7 --out runs --set transfer.allowance_margin=0.1
"""
from __future__ import annotations

import argparse
import math
import datetime as dt
import json
import resource
import sys
import time

import numpy as np
import yaml

from arthasim import Config, World


def parse_set(text: str) -> tuple[str, object]:
    """`KEY=VALUE` for `--set`; the value is read as YAML, and a number in a form YAML keeps as text
    (such as 1e-1) becomes a float."""
    if "=" not in text:
        raise argparse.ArgumentTypeError(f"--set needs KEY=VALUE, got {text!r}")
    key, raw = text.split("=", 1)
    value = yaml.safe_load(raw)
    if isinstance(value, str):
        try:
            value = float(value)
        except ValueError:
            pass
    if isinstance(value, float) and not math.isfinite(value):
        raise argparse.ArgumentTypeError(f"--set {key} needs a finite number, got {raw!r}")
    return key, value


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", default="XS")
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="runs")
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VALUE", type=parse_set,
                    help="override a registry parameter; repeatable")
    args = ap.parse_args(argv)

    overrides = dict(args.set)
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
            "unbanked_share": round(count(
                "select count(*) as n from entity_state_monthly "
                "where month = (select max(month) from entity_state_monthly) and not has_account") / config.persons, 4),
        })
    if m.get("builder") == "population" and "entity_state_monthly" in run.tables():
        result["life"] = _life_summary(run)
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
    "government": ("DBT_PM_KISAN", "DBT_OLD_AGE_PENSION", "DBT_WOMEN"),
}
_SCHEME_OF_PURPOSE = {"DBT_PM_KISAN": "PM_KISAN", "DBT_OLD_AGE_PENSION": "OLD_AGE_PENSION", "DBT_WOMEN": "WOMEN"}

_PAYER_PERSON = """
    from payments y
    join accounts a on a.account_id = y.payer_account_id
    join persons p on p.entity_id = a.holder_entity_id"""

# The payer's state in the payment's month (IST).
_PAYER_STATE = """
    from payments y
    join accounts a on a.account_id = y.payer_account_id
    join entity_state_monthly e on e.entity_id = a.holder_entity_id
     and e.month = strftime(make_timestamp(y.intent_ts) + interval 330 minute, '%Y-%m')"""

_PANEL_STATE = """
    case when e.life_stage = 'salaried' then 'regular' when e.life_stage = 'casual' then 'casual'
         when e.life_stage in ('farm', 'self_employed', 'gig') then case when e.helper then 'helper' else 'own' end
         when e.life_stage = 'seeking' then 'unemployed' else 'nlf' end"""
_PANEL_ORDER = ("own", "helper", "regular", "casual", "unemployed", "nlf")
_WORKING = "('salaried', 'self_employed', 'gig', 'farm', 'casual')"


def _life_summary(run) -> dict:
    """Life-course figures: events, account ownership, rural women's working share, urban quarterly gross
    flows in the PLFS panel's six states, and funds declines by month and around layoffs."""
    events = run.sql("""
        select strftime(date, '%Y-%m') as month, event, count(*) as n from life_events group by 1, 2 order by 1, 2""")
    by_month: dict = {}
    for month, event, n in events.iter_rows():
        by_month.setdefault(month, {})[event] = int(n)
    ownership = run.sql("select month, avg(case when has_account then 1.0 else 0.0 end) as s "
                        "from entity_state_monthly group by 1 order by 1")
    person_kind = """
        join persons p on p.entity_id = e.entity_id
        join (select distinct district_id, kind from geo) g on g.district_id = p.district"""
    working = run.sql(f"""
        select e.month, p.sex, g.kind,
               avg(case when e.life_stage in {_WORKING} then 1.0 else 0.0 end) as s
        from entity_state_monthly e {person_kind}
        group by 1, 2, 3 order by 1, 2, 3""")
    working_share = {}
    for month, sex, kind, s in working.iter_rows():
        working_share.setdefault(f"{'urban' if kind == 'metro' else 'rural'}_{'female' if sex == 'F' else 'male'}",
                                 {})[month] = round(s, 4)
    flows = run.sql(f"""
        with s as (
            select e.entity_id, p.sex, g.kind, {_PANEL_STATE} as st,
                   date_diff('month', date '2025-01-01', strptime(e.month || '-01', '%Y-%m-%d')) as mi
            from entity_state_monthly e {person_kind})
        select a.sex, a.st as from_st, b.st as to_st, count(*) as n
        from s a join s b on a.entity_id = b.entity_id and b.mi = a.mi + 3
        where a.kind = 'metro'
        group by 1, 2, 3""")
    counts: dict = {}
    for sex, src, dst, n in flows.iter_rows():
        counts.setdefault(sex, {}).setdefault(src, {})[dst] = int(n)
    urban_flows = {sex: {src: {dst: round(100 * row.get(dst, 0) / sum(row.values()), 2) for dst in _PANEL_ORDER}
                         for src in _PANEL_ORDER if (row := rows.get(src))}
                   for sex, rows in counts.items()}
    declines = run.sql("""
        select strftime(make_timestamp(y.intent_ts) + interval 330 minute, '%Y-%m') as month,
               avg(case when y.status = 'DECLINED_FUNDS' then 1.0 else 0.0 end) as s
        from payments y group by 1 order by 1""")
    laid_off = run.sql(f"""
        with l as (select entity_id, strftime(date, '%Y-%m') as month,
                          strftime(date - interval 1 month, '%Y-%m') as before from life_events
                   where event = 'LAID_OFF'),
        y as (select a.holder_entity_id as person, y.status,
                     strftime(make_timestamp(y.intent_ts) + interval 330 minute, '%Y-%m') as month
              from payments y join accounts a on a.account_id = y.payer_account_id)
        select avg(case when y.month = l.month and y.status = 'DECLINED_FUNDS' then 1.0
                        when y.month = l.month then 0.0 end) as after,
               avg(case when y.month = l.before and y.status = 'DECLINED_FUNDS' then 1.0
                        when y.month = l.before then 0.0 end) as before
        from l join y on y.person = l.entity_id""")
    after, before = laid_off.row(0)
    return {
        "events_by_month": by_month,
        "account_ownership_by_month": {mo: round(s, 4) for mo, s in ownership.iter_rows()},
        "working_share_by_month": working_share,
        "urban_quarterly_flows_pct": urban_flows,
        "declined_funds_by_month": {mo: round(s, 4) for mo, s in declines.iter_rows()},
        "declined_funds_laid_off": {"month_of_layoff": round(float(after or 0.0), 4),
                                    "month_before": round(float(before or 0.0), 4)},
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
    by_stage = run.sql(f"""
        select e.life_stage as k, avg(case when y.status = 'DECLINED_FUNDS' then 1.0 else 0.0 end) as share
        {_PAYER_STATE}
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
            select e.entity_id as person, y.intent_ts as ts, y.status
            from payments y join accounts a on a.account_id = y.payer_account_id
            join entity_state_monthly e on e.entity_id = a.holder_entity_id
             and e.month = strftime(make_timestamp(y.intent_ts) + interval 330 minute, '%Y-%m')
            where e.life_stage in ('homemaker', 'studying', 'seeking')
              and y.purpose not in ('ALLOWANCE', 'CASH_WITHDRAWAL', 'CASH_DEPOSIT')),
        j as (
            select att.status, (att.ts - recv.ts) // 86400000000 as days
            from att asof join recv on att.person = recv.person and att.ts >= recv.ts)
        select case when days < 10 then '0-9' when days < 20 then '10-19' when days < 25 then '20-24'
                    when days < 30 then '25-29' else '30+' end as k,
               avg(case when status = 'DECLINED_FUNDS' then 1.0 else 0.0 end) as share
        from j group by 1 order by 1""")
    no_income_rate = run.sql(f"""
        with a as (
            select p.household_id, y.status,
                   strftime(make_timestamp(y.intent_ts) + interval 330 minute, '%Y-%m') as month
            {_PAYER_PERSON})
        select avg(case when a.status = 'DECLINED_FUNDS' then 1.0 else 0.0 end) as rate
        from a join truth_household_monthly h on h.household_id = a.household_id and h.month = a.month
        where h.income_paise = 0""")
    no_income_households = run.sql("""
        select month, sum(case when income_paise = 0 then 1 else 0 end) as n
        from truth_household_monthly group by 1 order by 1""")
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
        "declined_funds_rate_no_income_households": round(float(no_income_rate["rate"][0] or 0.0), 4),
        "no_income_households_by_month": {mo: int(n) for mo, n in no_income_households.iter_rows()},
        "recipient_declined_by_days_since_allowance": {k: round(v, 4) for k, v in by_days.iter_rows()},
        "allowance_scaled_households": _scaled_households(world),
        "allowance_margin_short_households": _margin_short_households(world),
        "cash_held_rupees_at_end": {
            "persons": held(s.person_cash), "merchants": held(s.merchant_cash), "billers": held(s.biller_cash),
            "bank_vaults": held(s.bank_vault), "boundary": held([s.boundary_cash]),
            "total": int(book.balance[cash].sum()) / 100},
        **_dbt_summary(world, run),
    }


def _dbt_summary(world, run) -> dict:
    """Government transfers: credits, rupees and beneficiaries by scheme; the government's balance; accounts
    opened for DBT; and, in the last month, the share of women aged 21-60, of people aged 60+ and of
    households with an own-account farmer who are enrolled."""
    gov = world.state.government
    if gov is None or "truth_dbt_monthly" not in run.tables():
        return {}
    dbt = {scheme: {"credits": 0, "rupees": 0.0, "beneficiaries": 0} for scheme in _SCHEME_OF_PURPOSE.values()}
    paid = run.sql("""
        select purpose, count(*) as credits, sum(amount_paise) as paise, count(distinct payee_account_id) as people
        from payments where purpose like 'DBT_%' and status = 'SUCCESS' group by 1""")
    for purpose, credits, paise, people in paid.iter_rows():
        dbt[_SCHEME_OF_PURPOSE[purpose]] = {"credits": int(credits), "rupees": int(paise) / 100,
                                            "beneficiaries": int(people)}
    last = run.sql("select max(month) as m from entity_state_monthly")["m"][0]
    share = run.sql(f"""
        with e as (select e.entity_id, e.age, e.life_stage, e.helper, p.sex, p.household_id
                   from entity_state_monthly e join persons p using (entity_id) where e.month = '{last}'),
        t as (select entity_id, scheme from truth_dbt_monthly where month = '{last}' and enrolled)
        select
          (select count(*) from t where scheme = 'WOMEN') * 1.0
            / (select count(*) from e where sex = 'F' and age between 21 and 60) as women_21_60,
          (select count(*) from t where scheme = 'OLD_AGE_PENSION') * 1.0
            / (select count(*) from e where age >= 60) as aged_60_plus,
          (select count(*) from t where scheme = 'PM_KISAN') * 1.0
            / (select count(distinct household_id) from e where life_stage = 'farm' and not helper)
            as farm_households""")
    opened = run.sql("select count(distinct entity_id) as n from truth_dbt_monthly where opened_account")["n"][0]
    return {
        "dbt": dbt,
        "government_balance_rupees": int(world.state.book.balance[gov.balance_account]) / 100,
        "dbt_accounts_opened": int(opened),
        "dbt_enrolled_share": {k: round(float(v or 0.0), 4) for k, v in zip(share.columns, share.row(0))},
    }


def _mixed_households(world):
    """Last simulated month's need, and the households with both surplus and a shortfall."""
    from arthasim.modules.allowance import allowance_need

    pop = world.state.population
    hh = pop.households.household_of_person
    income = pop.attributes.monthly_income_paise + world.state.behaviour.person_transfer   # as Allowance sees it
    need = allowance_need(world)
    n = len(pop.households.adults)
    short = np.bincount(hh, weights=np.maximum(0.0, need - income), minlength=n) > 0
    surplus = np.bincount(hh, weights=np.maximum(0.0, income - need), minlength=n) > 0
    return hh, income, need, short & surplus


def _scaled_households(world) -> float:
    """Of households with both surplus and shortfall in the last simulated month, the share whose
    allowances are scaled down because surplus cannot cover every shortfall."""
    from arthasim.modules.allowance import household_scale

    hh, income, need, both = _mixed_households(world)
    scale = household_scale(hh, income, need)
    return round(float((scale[both] < 1).mean()), 4) if both.any() else 0.0


def _margin_short_households(world) -> float:
    """Of households with both surplus and a recipient in the last simulated month, the share whose
    leftover surplus cannot pay every recipient's full margin."""
    from arthasim.modules.allowance import margin_scale

    hh, income, need, both = _mixed_households(world)
    scale = margin_scale(hh, income, need, world.params.get("transfer.allowance_margin"))
    return round(float((scale[both] < 1).mean()), 4) if both.any() else 0.0


if __name__ == "__main__":
    main()
