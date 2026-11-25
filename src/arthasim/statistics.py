"""Simulated statistics for the core suite's target and holdout checks (plan 1e). `calibrate` and `validate` call
the same functions on the same window, so a statistic is computed one way for fitting and for checking.

A statistic is `fn(ctx) -> dict[str, float]`, keyed by component: `rural` and `urban` (the rural and metro
archetypes), `all` for a national figure, or a named part. A component with no data is left out, never NaN."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable

import numpy as np
import polars as pl

from arthasim.build import categories as c
from arthasim.config import Config
from arthasim.params import ParamRegistry

if TYPE_CHECKING:
    from arthasim.world import Run

AREAS = ("urban", "rural")
EARNING = "('salaried', 'self_employed', 'gig', 'farm', 'casual')"
SPENDING = ("GROCERY", "FOOD", "FUEL", "PHARMACY", "APPAREL", "ELECTRONICS", "TRANSPORT", "SERVICES", "OTHER",
            "UTILITIES", "TELECOM", "MEDICAL")
_SPEND = "(" + ", ".join(f"'{p}'" for p in SPENDING) + ")"
# Each person's area: the metro archetype stands for urban India, the rural one for rural India.
_AREA = """(select p.entity_id, p.household_id, p.sex, p.education, g.district as district_index,
                   case g.kind when 'metro' then 'urban' else 'rural' end as area
            from persons p join (select distinct district, district_id, kind from geo) g on g.district_id = p.district)"""
_IST_DATE = "cast(make_timestamp(y.settle_ts) + interval 330 minute as date)"
# A payment's area: its payer's if a person paid, else its payee's (earnings and transfers from outside the sample).
_PAYMENT_AREA = f"""
    left join accounts ca on ca.account_id = y.payer_account_id left join {_AREA} pa on pa.entity_id = ca.holder_entity_id
    left join accounts cb on cb.account_id = y.payee_account_id left join {_AREA} pb on pb.entity_id = cb.holder_entity_id"""


def run_config(run: "Run") -> Config:
    """The run's config, as its manifest records it (without any release secret)."""
    return Config(**run.manifest["config"])


def run_params(run: "Run") -> ParamRegistry:
    """The registry the run was made with: the config's registry file and its overrides."""
    from arthasim.world import _registry_path
    config = run_config(run)
    return ParamRegistry.load(_registry_path(config), overrides=config.param_overrides)


def complete_months(run: "Run") -> list[str]:
    """Months the run has closed ("YYYY-MM"): those with month-end balances."""
    folder = Path(run.path) / "balances_monthly"
    if not folder.exists():
        return []
    return sorted(p.name.split("=", 1)[1] for p in folder.iterdir() if p.name.startswith("month="))


def window(run: "Run") -> tuple[str, str] | None:
    """The run's complete months from its second month on; None when there are none. The first month is the build
    settling (budgets and buffers start away from where they will be)."""
    first = f"{run_config(run).start:%Y-%m}"
    months = [m for m in complete_months(run) if m > first]
    return (months[0], months[-1]) if months else None


def month_list(months: tuple[str, str]) -> list[str]:
    lo, hi = (dt.date.fromisoformat(m + "-01") for m in months)
    out, d = [], lo
    while d <= hi:
        out.append(f"{d:%Y-%m}")
        d = (d.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    return out


@dataclass
class Context:
    """A run, the months its statistics read, and the registry it was made with."""
    run: "Run"
    months: tuple[str, str]
    params: ParamRegistry

    @property
    def month_names(self) -> list[str]:
        return month_list(self.months)

    def has_data(self, months: tuple[str, str] | None = None) -> bool:
        """Whether the run has payments in the window (or `months`): a window outside the run has none."""
        from arthasim.store.parquet import table_files
        return bool(table_files(Path(self.run.path), "payments", months or self.months))

    def sql(self, query: str) -> pl.DataFrame:
        """A query whose fact tables see only the window's months; an empty frame for a window outside the run."""
        if not self.has_data():
            return pl.DataFrame()
        return self.run.window(self.months[0] + "-01", self.months[1] + "-01").sql(query)

    def whole(self, query: str) -> pl.DataFrame:
        return self.run.sql(query)


def context(run: "Run", months: tuple[str, str] | None = None) -> Context | None:
    """The context for a run's statistics: its default window, or `months`. None when the window is empty."""
    months = months if months is not None else window(run)
    return None if months is None else Context(run, months, run_params(run))


def gini(values, weights) -> float:
    """Gini coefficient of `values` with each value standing for `weights` units (persons)."""
    v, w = np.asarray(values, dtype=np.float64), np.asarray(weights, dtype=np.float64)
    order = np.argsort(v, kind="stable")
    v, w = v[order], w[order]
    total_w, total = w.sum(), (v * w).sum()
    if total_w <= 0 or total <= 0:
        return 0.0
    cum_w = np.cumsum(w) / total_w
    cum_v = np.cumsum(v * w) / total
    prev_w = np.concatenate([[0.0], cum_w[:-1]])
    prev_v = np.concatenate([[0.0], cum_v[:-1]])
    return float(1.0 - np.sum((cum_w - prev_w) * (cum_v + prev_v)))


def national(ctx: Context, per_area: dict[str, float]) -> float:
    """A national figure from per-adult figures by area, weighted by India's urban share."""
    u = float(ctx.params.get("population.urban_share"))
    return u * per_area.get("urban", 0.0) + (1.0 - u) * per_area.get("rural", 0.0)


def _by_area(frame: pl.DataFrame) -> dict[str, float]:
    return {a: float(v) for a, v in frame.iter_rows() if a is not None and v is not None}


def _persons(ctx: Context) -> dict[str, float]:
    return _by_area(ctx.whole(f"select area, count(*) from {_AREA} group by 1"))


def _national_ratio(ctx: Context, num: dict[str, float], den: dict[str, float]) -> dict[str, float]:
    """Sum over areas of weighted per-adult numerators over the same of denominators: a national ratio."""
    persons = _persons(ctx)
    n = national(ctx, {a: num.get(a, 0.0) / persons[a] for a in persons})
    d = national(ctx, {a: den.get(a, 0.0) / persons[a] for a in persons})
    return {"all": n / d} if d > 0 else {}


# Labour stocks ---------------------------------------------------------------------------------------------------

def _state(ctx: Context, where: str, value: str) -> dict[str, float]:
    return _by_area(ctx.sql(f"""select a.area, avg({value}) from entity_state_monthly e join {_AREA} a using (entity_id)
                                where {where} group by 1"""))


def _unemployment(ctx: Context, extra: str = "true") -> dict[str, float]:
    return _state(ctx, f"e.life_stage in {EARNING[:-1]}, 'seeking') and {extra}",
                  "(e.life_stage = 'seeking')::int")


def labour_stages(ctx: Context) -> dict[str, float]:
    """For each month, district kind and sex: the largest gap between the simulated share of persons in a life
    stage and the mean of the life course's PLFS target shares for the same persons; the largest over months."""
    from arthasim.life.sources import load_plfs
    from arthasim.life.targets import Targets
    kinds = ctx.whole("select distinct district, kind from geo order by district")
    targets = Targets(load_plfs(), ctx.params, kinds["kind"].to_list())
    states = ctx.sql(f"""select e.month, e.age, e.life_stage, a.sex, a.district_index, a.area
                         from entity_state_monthly e join {_AREA} a using (entity_id)""")
    out: dict[str, float] = {}
    if states.height == 0:
        return out
    for (month, district, sex), g in states.group_by(["month", "district_index", "sex"]):
        x = c.SEX.index(sex)
        want = targets.for_persons(dt.date.fromisoformat(month + "-01"), int(district), x,
                                   g["age"].to_numpy()).mean(axis=0)
        stage = np.array([c.LIFE_STAGE.index(s) for s in g["life_stage"].to_list()])
        have = np.bincount(stage, minlength=9) / stage.size
        key = f"{g['area'][0]}_{sex}"
        out[key] = max(out.get(key, 0.0), float(np.abs(have - want).max()))
    return out


# Pay and consumption ---------------------------------------------------------------------------------------------

def _mean_income(ctx: Context, stages: str, divide: float = 1.0) -> dict[str, float]:
    got = _state(ctx, f"e.life_stage in {stages} and e.monthly_income_paise > 0", "e.monthly_income_paise")
    return {a: v / 100 / divide for a, v in got.items()}


def _household_spend(ctx: Context) -> pl.DataFrame:
    """Each household's successful spending in the window (paise), with its size and area; zero for none."""
    return ctx.sql(f"""
        with s as (select a.household_id, sum(y.amount_paise) as spend from payments y
                   join accounts c on c.account_id = y.payer_account_id join {_AREA} a on a.entity_id = c.holder_entity_id
                   where y.status = 'SUCCESS' and y.purpose in {_SPEND} group by 1)
        select h.household_id, case g.kind when 'metro' then 'urban' else 'rural' end as area,
               h.adults + h.dependants as size, coalesce(s.spend, 0) as spend
        from households h join (select distinct district_id, kind from geo) g on g.district_id = h.district
        left join s using (household_id)""")


def mpce(ctx: Context) -> dict[str, float]:
    """Spending by a household's members over the window, per member per month, averaged over persons (rupees)."""
    h, n = _household_spend(ctx), len(ctx.month_names)
    out = {}
    if h.height == 0:
        return out
    for (area,), g in h.group_by(["area"]):
        out[area] = float(g["spend"].sum()) / n / float(g["size"].sum()) / 100
    return out


def consumption_gini(ctx: Context) -> dict[str, float]:
    h, n = _household_spend(ctx), len(ctx.month_names)
    if h.height == 0:
        return {}
    return {area: gini((g["spend"] / g["size"] / n).to_numpy(), g["size"].to_numpy())
            for (area,), g in h.group_by(["area"])}


def food_share(ctx: Context) -> dict[str, float]:
    return _by_area(ctx.sql(f"""
        select a.area, sum(case when y.purpose in ('GROCERY', 'FOOD') then y.amount_paise else 0 end)
                       / sum(y.amount_paise)::double
        from payments y join accounts c on c.account_id = y.payer_account_id join {_AREA} a on a.entity_id = c.holder_entity_id
        where y.status = 'SUCCESS' and y.purpose in {_SPEND} group by 1"""))


# Payments --------------------------------------------------------------------------------------------------------

def _payments(ctx: Context, where: str, value: str = "count(*)") -> dict[str, float]:
    return _by_area(ctx.sql(f"""select coalesce(pa.area, pb.area), {value} from payments y {_PAYMENT_AREA}
                                where y.status = 'SUCCESS' and {where} group by 1"""))


def _per_adult_month(ctx: Context, where: str) -> dict[str, float]:
    if not ctx.has_data():
        return {}
    persons, n = _persons(ctx), len(ctx.month_names)
    count = _payments(ctx, where)
    return {"all": national(ctx, {a: count.get(a, 0.0) / n / persons[a] for a in persons})}


def _ticket(ctx: Context, where: str) -> dict[str, float]:
    return _national_ratio(ctx, _payments(ctx, where, "sum(y.amount_paise) / 100.0"), _payments(ctx, where))


def _under_500(ctx: Context, rail: str) -> dict[str, float]:
    where = f"y.rail = '{rail}'"
    return _national_ratio(ctx, _payments(ctx, f"{where} and y.amount_paise < 50000"), _payments(ctx, where))


def _upi_value_by_day(ctx: Context, months: list[str]) -> dict[dt.date, float]:
    """National UPI value per adult on each day of `months` (weighted by area)."""
    persons = _persons(ctx)
    u = float(ctx.params.get("population.urban_share"))
    if not ctx.has_data((months[0], months[-1])):
        return {}
    frame = ctx.run.window(months[0] + "-01", months[-1] + "-01").sql(f"""
        select {_IST_DATE} as day, coalesce(pa.area, pb.area) as area, sum(y.amount_paise)::double as value
        from payments y {_PAYMENT_AREA}
        where y.status = 'SUCCESS' and y.rail in ('UPI_P2M', 'UPI_P2P') and coalesce(pa.area, pb.area) is not null
        group by 1, 2""")
    out: dict[dt.date, float] = {}
    for day, area, value in frame.iter_rows():
        w = u if area == "urban" else 1.0 - u
        out[day] = out.get(day, 0.0) + w * value / persons[area]
    return out


def month_start_spike(ctx: Context) -> dict[str, float]:
    """UPI value per day on the 1st to 3rd of each month over that on the 10th to 25th, averaged over months."""
    by_day = _upi_value_by_day(ctx, ctx.month_names)
    ratios = []
    for m in ctx.month_names:
        y, mo = int(m[:4]), int(m[5:])
        early = [by_day.get(dt.date(y, mo, d), 0.0) for d in (1, 2, 3)]
        mid = [by_day.get(dt.date(y, mo, d), 0.0) for d in range(10, 26)]
        if sum(mid) > 0:
            ratios.append((sum(early) / 3) / (sum(mid) / 16))
    return {"all": float(np.mean(ratios))} if ratios else {}


# Balances and accounts -------------------------------------------------------------------------------------------

def _basic(ctx: Context, value: str) -> dict[str, float]:
    return _by_area(ctx.sql(f"""select a.area, {value} from balances_monthly b join accounts c using (account_id)
                                join {_AREA} a on a.entity_id = c.holder_entity_id where c.subtype = 'basic' group by 1"""))


def basic_mean(ctx: Context) -> dict[str, float]:
    return _national_ratio(ctx, _basic(ctx, "sum(b.balance_paise) / 100.0"), _basic(ctx, "count(*)"))


def zero_balance(ctx: Context) -> dict[str, float]:
    return _national_ratio(ctx, _basic(ctx, "sum((b.balance_paise = 0)::int)"), _basic(ctx, "count(*)"))


def inoperative(ctx: Context) -> dict[str, float]:
    """Basic accounts open before the window with no transaction the holder made in it: no successful debit, and
    no cash deposit into it."""
    start = ctx.months[0] + "-01"
    frame = ctx.sql(f"""
        with used as (select payer_account_id as account_id from payments where status = 'SUCCESS'
                      union select payee_account_id from payments where status = 'SUCCESS' and purpose = 'CASH_DEPOSIT')
        select a.area, count(*) as n, sum((u.account_id is null)::int) as idle
        from accounts c join {_AREA} a on a.entity_id = c.holder_entity_id left join used u using (account_id)
        where c.subtype = 'basic' and c.opened_on < date '{start}' group by 1""")
    return _national_ratio(ctx, {a: float(i) for a, _, i in frame.iter_rows()},
                           {a: float(n) for a, n, _ in frame.iter_rows()})


# Holdouts --------------------------------------------------------------------------------------------------------

def festival_uplift(ctx: Context) -> dict[str, float]:
    """UPI value per day in October 2025 over the mean of September and November (all three must be complete)."""
    months = ["2025-09", "2025-10", "2025-11"]
    if not set(months) <= set(complete_months(ctx.run)):
        return {}
    by_day = _upi_value_by_day(ctx, months)
    per_day = {}
    for m, days in zip(months, (30, 31, 30)):
        per_day[m] = sum(v for d, v in by_day.items() if f"{d:%Y-%m}" == m) / days
    mean = (per_day["2025-09"] + per_day["2025-11"]) / 2
    return {"all": per_day["2025-10"] / mean} if mean > 0 else {}


_DAY_US = 86_400 * 1_000_000
_IST_US = 330 * 60 * 1_000_000


def cashout_bins(credits, draws, last_day: int) -> dict[str, float]:
    """`credits` and `draws` are (account, settle_ts) pairs in microseconds; `last_day` is a timestamp on the run's
    last day. For each day an account got a credit (its first credit that day), with 30 days of the run after it:
    the share whose next withdrawal from the account at or after the credit came 0-5, 6-15 or 16-30 IST days later."""
    c = pl.DataFrame(list(credits), schema={"account": pl.Int64, "ts": pl.Int64}, orient="row")
    d = pl.DataFrame(list(draws), schema={"account": pl.Int64, "ts": pl.Int64}, orient="row")
    if c.height == 0:
        return {}
    day = lambda col: (pl.col(col) + _IST_US) // _DAY_US
    c = (c.with_columns(day("ts").alias("day")).group_by(["account", "day"]).agg(pl.col("ts").min())
         .filter(pl.col("day") + 30 <= (last_day + _IST_US) // _DAY_US).sort("ts"))
    if c.height == 0:
        return {}
    d = d.with_columns(day("ts").alias("draw_day"), pl.col("ts").alias("draw_ts")).sort("ts")
    joined = c.join_asof(d.select("account", "ts", "draw_day"), on="ts", by="account", strategy="forward",
                         check_sortedness=False)                 # both frames are sorted by ts above
    lag = joined["draw_day"] - joined["day"]
    n = joined.height
    bins = {"d0_5": (0, 5), "d6_15": (6, 15), "d16_30": (16, 30)}
    return {k: float(((lag >= lo) & (lag <= hi)).sum()) / n for k, (lo, hi) in bins.items()}


def dbt_cashout(ctx: Context) -> dict[str, float]:
    """For each day an account got an APBS credit, with 30 days of the run after it: the share whose next cash
    withdrawal from that account, at or after the credit, came 0-5, 6-15 or 16-30 days later (whole run)."""
    credits = ctx.whole("select payee_account_id, settle_ts from payments where status = 'SUCCESS' and rail = 'APBS'")
    if credits.height == 0:
        return {}
    draws = ctx.whole("""select payer_account_id, settle_ts from payments
                         where status = 'SUCCESS' and purpose = 'CASH_WITHDRAWAL'""")
    last = int(ctx.whole("select max(settle_ts) as t from payments")["t"][0])
    return cashout_bins(credits.iter_rows(), draws.iter_rows(), last)


STATISTICS: dict[str, Callable[[Context], dict[str, float]]] = {
    "labour.stages": labour_stages,
    "labour.ur": lambda ctx: _unemployment(ctx),
    "labour.ur.educated": lambda ctx: _unemployment(ctx, "a.education in ('secondary', 'graduate', 'postgraduate')"),
    "labour.ur.graduate_15_29": lambda ctx: _unemployment(ctx, "a.education = 'graduate' and e.age <= 29"),
    "labour.share.regular_salaried": lambda ctx: _state(ctx, f"e.life_stage in {EARNING}",
                                                        "(e.life_stage = 'salaried')::int"),
    "labour.share.self_employed": lambda ctx: _state(ctx, f"e.life_stage in {EARNING}",
                                                     "(e.life_stage in ('self_employed', 'gig', 'farm'))::int"),
    "pay.regular_monthly": lambda ctx: _mean_income(ctx, "('salaried')"),
    "pay.casual_daily": lambda ctx: _mean_income(
        ctx, "('casual')", float(ctx.params.get("income.pay_events_per_month")["casual"])),
    "pay.self_employed_monthly": lambda ctx: _mean_income(ctx, "('self_employed', 'gig', 'farm')"),
    "consumption.mpce": mpce,
    "consumption.gini": consumption_gini,
    "consumption.food_share": food_share,
    "payments.upi_p2m_per_adult": lambda ctx: _per_adult_month(ctx, "y.rail = 'UPI_P2M'"),
    "payments.upi_p2p_per_adult": lambda ctx: _per_adult_month(ctx, "y.rail = 'UPI_P2P'"),
    "payments.debit_card_per_adult": lambda ctx: _per_adult_month(ctx, "y.rail = 'DEBIT_CARD'"),
    "payments.atm_per_adult": lambda ctx: _per_adult_month(ctx, "y.rail = 'ATM' and y.purpose = 'CASH_WITHDRAWAL'"),
    "payments.atm_ticket": lambda ctx: _ticket(ctx, "y.rail = 'ATM' and y.purpose = 'CASH_WITHDRAWAL'"),
    "payments.debit_card_ticket": lambda ctx: _ticket(ctx, "y.rail = 'DEBIT_CARD'"),
    "payments.p2m_under_500": lambda ctx: _under_500(ctx, "UPI_P2M"),
    "payments.p2p_under_500": lambda ctx: _under_500(ctx, "UPI_P2P"),
    "payments.month_start_spike": month_start_spike,
    "balances.basic_mean": basic_mean,
    "accounts.zero_balance": zero_balance,
    "accounts.inoperative": inoperative,
    "holdout.festival_uplift": festival_uplift,
    "holdout.dbt_cashout": dbt_cashout,
}
