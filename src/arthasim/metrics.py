"""Outcome metrics of a run. A metric is `fn(run, **kwargs)` returning a Polars frame with one column per grouping
and a `value` column (one row when ungrouped). Plan 1d's `effect(metric, by=...)` uses the same contract."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

import polars as pl

if TYPE_CHECKING:
    from arthasim.world import Run

METRICS: dict[str, Callable[..., Any]] = {}

SPENDING = ("GROCERY", "FOOD", "FUEL", "PHARMACY", "APPAREL", "ELECTRONICS", "TRANSPORT", "SERVICES", "OTHER",
            "UTILITIES", "TELECOM", "MEDICAL")
_PAYMENT_BY = ("month", "rail", "bank", "district", "life_stage")
_BALANCE_BY = ("bank", "district", "life_stage")
_MONTH = "strftime(make_timestamp(y.settle_ts) + interval 330 minute, '%Y-%m')"


class register:
    """`@register.metric` adds a function under its name; a name already taken raises ValueError."""

    @staticmethod
    def metric(fn: Callable[..., Any]) -> Callable[..., Any]:
        name = fn.__name__
        if name in METRICS:
            raise ValueError(f"metric {name!r} is already registered")
        METRICS[name] = fn
        return fn


def run_metric(run: "Run", name_or_fn: str | Callable[..., Any], **kwargs: Any) -> pl.DataFrame:
    if callable(name_or_fn):
        fn = name_or_fn
    else:
        if name_or_fn not in METRICS:
            raise KeyError(f"no metric {name_or_fn!r}; metrics are {', '.join(sorted(METRICS))}")
        fn = METRICS[name_or_fn]
    out = fn(run, **kwargs)
    return out if isinstance(out, pl.DataFrame) else pl.DataFrame({"value": [out]})


def _groups(by: str | list[str] | None, allowed: tuple[str, ...], metric: str) -> list[str]:
    groups = [] if by is None else [by] if isinstance(by, str) else list(by)
    bad = [g for g in groups if g not in allowed]
    if bad:
        raise ValueError(f"{metric} groups by {', '.join(allowed)}; got {', '.join(map(str, bad))}")
    return groups


def _needs_population(run: "Run", groups: list[str], metric: str) -> None:
    if {"district", "life_stage"} & set(groups) and run.manifest.get("builder") != "population":
        raise ValueError(f"{metric}: district and life_stage groupings need a population-built run")


def _payments(run: "Run", metric: str, by, value: str, where: str) -> pl.DataFrame:
    groups = _groups(by, _PAYMENT_BY, metric)
    _needs_population(run, groups, metric)
    expr = {"month": _MONTH, "rail": "y.rail", "bank": "y.payer_bank",
            "district": "coalesce(pp.district, po.district)", "life_stage": "e.life_stage"}
    joins = ""
    if {"district", "life_stage"} & set(groups):
        joins += " left join accounts pa on pa.account_id = y.payer_account_id"
    if "district" in groups:
        joins += (" left join persons pp on pp.entity_id = pa.holder_entity_id"
                  " left join orgs po on po.entity_id = pa.holder_entity_id")
    if "life_stage" in groups:
        joins += f" left join entity_state_monthly e on e.entity_id = pa.holder_entity_id and e.month = {_MONTH}"
    select = ", ".join([f"{expr[g]} as {g}" for g in groups] + [f"{value} as value"])
    pos = ", ".join(str(i + 1) for i in range(len(groups)))
    group = f" group by {pos} order by {pos}" if groups else ""
    return run.sql(f"select {select} from payments y{joins} where {where}{group}")


@register.metric
def txn_volume(run: "Run", by=None, status: str | None = "SUCCESS") -> pl.DataFrame:
    """Number of payment attempts with `status` (None counts all)."""
    where = "true" if status is None else f"y.status = '{status}'"
    return _payments(run, "txn_volume", by, "count(*)::bigint", where)


@register.metric
def decline_rate(run: "Run", by=None) -> pl.DataFrame:
    """Share of payment attempts that did not succeed."""
    return _payments(run, "decline_rate", by, "avg((y.status <> 'SUCCESS')::int)::double", "true")


@register.metric
def consumption(run: "Run", by=None) -> pl.DataFrame:
    """Paise of successful payments for goods, services, bills and medical costs."""
    spend = ", ".join(f"'{p}'" for p in SPENDING)
    return _payments(run, "consumption", by, "coalesce(sum(y.amount_paise), 0)::bigint",
                     f"y.status = 'SUCCESS' and y.purpose in ({spend})")


@register.metric
def cash_withdrawal(run: "Run", by=None) -> pl.DataFrame:
    """Paise of successful cash withdrawals (ATM, AePS and automatic withdrawals)."""
    return _payments(run, "cash_withdrawal", by, "coalesce(sum(y.amount_paise), 0)::bigint",
                     "y.status = 'SUCCESS' and y.purpose = 'CASH_WITHDRAWAL'")


@register.metric
def deposit_balance(run: "Run", by=None) -> pl.DataFrame:
    """Paise in persons' deposit accounts at each month end; always grouped by month."""
    groups = _groups(by, _BALANCE_BY, "deposit_balance")
    _needs_population(run, groups or ["district"], "deposit_balance")
    expr = {"bank": "k.bank_code", "district": "p.district", "life_stage": "e.life_stage"}
    joins = " left join banks k on k.entity_id = a.issuer_entity_id" if "bank" in groups else ""
    if "life_stage" in groups:
        joins += " left join entity_state_monthly e on e.entity_id = a.holder_entity_id and e.month = b.month"
    pos = ", ".join(str(i + 1) for i in range(len(groups) + 1))
    select = ", ".join(["b.month as month"] + [f"{expr[g]} as {g}" for g in groups]
                       + ["sum(b.balance_paise)::bigint as value"])
    return run.sql(f"""select {select} from balances_monthly b
                       join accounts a using (account_id) join persons p on p.entity_id = a.holder_entity_id{joins}
                       where a.type = 'DEPOSIT' group by {pos} order by {pos}""")
