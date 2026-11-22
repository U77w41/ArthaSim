"""Observer views: what a bank, a payment switch, the bureau or the truth layer sees of a run.

A view is a set of SQL definitions over the run's Parquet files, run in DuckDB when read. Each definition is a
self-contained SELECT that names files directly (`read_parquet([...])`), so a view's connection holds only the
view's own tables and a query cannot reach a truth table by name. Nothing is written per observer."""
from __future__ import annotations

import calendar
import datetime as dt
from pathlib import Path
from typing import TYPE_CHECKING, Callable

import duckdb
import polars as pl

from arthasim.engine.scheduler import day_start_us
from arthasim.store.parquet import table_files

if TYPE_CHECKING:
    from arthasim.world import Run

Date = str | dt.date
KINDS = ("bank", "switch", "bureau", "truth")

# Columns of fact tables a view may need before the run has written any rows of them.
_EMPTY = {
    "payments": "payment_id BIGINT, intent_ts BIGINT, settle_ts BIGINT, rail VARCHAR, status VARCHAR, "
                "amount_paise BIGINT, payer_account_id BIGINT, payee_account_id BIGINT, payer_bank VARCHAR, "
                "payee_bank VARCHAR, journal_id BIGINT, purpose VARCHAR",
    "journal": "journal_id BIGINT, ts BIGINT, kind BIGINT, flow_type BIGINT, payment_id BIGINT",
    "postings": "journal_id BIGINT, line_no BIGINT, account_id BIGINT, delta_paise BIGINT, balance_after_paise BIGINT",
    "balances_monthly": "account_id BIGINT, month VARCHAR, balance_paise BIGINT",
    "life_events": "event_id BIGINT, date DATE, entity_id BIGINT, event VARCHAR, from_stage VARCHAR, "
                   "to_stage VARCHAR, employer_from BIGINT, employer_to BIGINT, income_before_paise BIGINT, "
                   "income_after_paise BIGINT, account_id BIGINT",
}


def as_date(value: Date) -> dt.date:
    return value if isinstance(value, dt.date) else dt.date.fromisoformat(value)


def asof_us(asof: Date) -> int:
    """Epoch microseconds of IST midnight at the start of the day after `asof`: everything before it is visible."""
    return day_start_us(as_date(asof) + dt.timedelta(days=1))


def month_end(asof: Date) -> str:
    """The last month that had ended by the end of `asof`, as YYYY-MM."""
    d = as_date(asof)
    if d.day == calendar.monthrange(d.year, d.month)[1]:
        return f"{d:%Y-%m}"
    prev = d.replace(day=1) - dt.timedelta(days=1)
    return f"{prev:%Y-%m}"


def _empty(columns: str) -> str:
    cols = ", ".join(f"null::{c.split()[1]} as {c.split()[0]}" for c in columns.split(", "))
    return f"(select {cols} where false)"


class Source:
    """The run's files, as SQL table expressions."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def has(self, name: str) -> bool:
        return bool(table_files(self.path, name))

    def __call__(self, name: str) -> str:
        files = [str(f) for f in table_files(self.path, name)]
        if not files:
            if name in _EMPTY:
                return _empty(_EMPTY[name])
            raise FileNotFoundError(f"no table {name!r} in {self.path}")
        return f"read_parquet({files!r}, hive_partitioning=false)"


Builder = Callable[["View", "dt.date | None"], dict[str, str]]


class View:
    """What one observer sees. `table` and `sql` take an `asof` date (everything up to and including that day);
    `table(name, asof=...)` overrides the view's own."""

    def __init__(self, run: "Run", kind: str, scope: dict, asof: Date | None, builder: Builder,
                 fact_tables: set[str]) -> None:
        self.kind, self.scope = kind, dict(scope)
        self.asof = as_date(asof) if asof is not None else None
        self.src = Source(run.path)
        self.run = run
        self.fact_tables = set(fact_tables)
        self._builder = builder

    def _definitions(self, asof: Date | None = None) -> dict[str, str]:
        cut = as_date(asof) if asof is not None else self.asof
        return self._builder(self, cut)

    def tables(self) -> list[str]:
        return sorted(self._definitions())

    def table(self, name: str, asof: Date | None = None) -> pl.LazyFrame:
        defs = self._definitions(asof)
        if name not in defs:
            raise KeyError(f"view {self.kind!r} has no table {name!r}; it has {sorted(defs)}")
        return duckdb.connect().sql(defs[name]).pl(lazy=True)

    def sql(self, query: str) -> pl.DataFrame:
        con = duckdb.connect()
        for name, definition in self._definitions().items():
            con.execute(f"create view {name} as {definition}")
        return con.sql(query).pl()


# -- truth --------------------------------------------------------------------------------------------------------

def _truth(view: View, asof: dt.date | None) -> dict[str, str]:
    src, run = view.src, view.run
    defs = {t: f"select * from {src(t)}" for t in run.tables()}
    if asof is None:
        return defs
    cut, day, month = asof_us(asof), f"date '{asof.isoformat()}'", f"{asof:%Y-%m}"
    where = {
        "payments": f"settle_ts < {cut}",
        "journal": f"ts < {cut}",
        "postings": f"journal_id in (select journal_id from {src('journal')} where ts < {cut})",
        "life_events": f"date <= {day}",
        "entity_state_monthly": f"month <= '{month}'",
        "truth_household_monthly": f"month <= '{month}'",
        "balances_monthly": f"month <= '{month_end(asof)}'",
        "accounts": f"opened_on <= {day}",
        "instruments": f"account_id in (select account_id from {src('accounts')} where opened_on <= {day})",
    }
    return {t: f"{q} where {where[t]}" if t in where else q for t, q in defs.items()}


# -- bank ---------------------------------------------------------------------------------------------------------

def _bank_codes(view: View) -> list[str]:
    banks = duckdb.sql(f"select bank_code from {view.src('banks')} where kind = 'BANK' order by bank_code").pl()
    return banks["bank_code"].to_list()


def _bank(view: View, asof: dt.date | None) -> dict[str, str]:
    src, code = view.src, view.scope["bank"]
    day = f"date '{asof.isoformat()}'" if asof is not None else None
    opened = f"and a.opened_on <= {day}" if day else ""
    customers = f"""
        with first_open as (
            select a.holder_entity_id as entity_id, min(a.opened_on) as first_opened
            from {src('accounts')} a join {src('banks')} b on a.issuer_entity_id = b.entity_id
            where b.bank_code = '{code}' and a.type = 'DEPOSIT' {opened}
            group by 1)
        select c.entity_id, c.customer_no,
               case when p.entity_id is not null then 'PERSON' else o.kind end as kind,
               p.sex, p.birth_year, p.birth_month,
               coalesce(p.district, o.district) as district, coalesce(p.locality, o.locality) as locality,
               p.has_pan, p.pan_like, p.mobile_token, o.sector, o.category
        from {src('bank_customers')} c
        join first_open f using (entity_id)
        left join {src('persons')} p using (entity_id)
        left join {src('orgs')} o using (entity_id)
        where c.bank_code = '{code}'
        order by c.entity_id"""
    return {"customers": customers}


def _bank_view(run: "Run", asof: Date | None, scope: dict) -> View:
    if set(scope) != {"bank"}:
        raise ValueError(f"the bank view takes one scope argument, bank=<code>; got {sorted(scope)}")
    view = View(run, "bank", scope, asof, _bank, set())
    codes = _bank_codes(view)
    if scope["bank"] not in codes:
        raise ValueError(f"unknown bank {scope['bank']!r}; banks are {', '.join(codes)}")
    return view


def _truth_view(run: "Run", asof: Date | None, scope: dict) -> View:
    if scope:
        raise ValueError(f"the truth view takes no scope arguments; got {sorted(scope)}")
    from arthasim.store.parquet import FACT_TABLES
    return View(run, "truth", scope, asof, _truth, set(FACT_TABLES))


_FACTORIES = {"bank": _bank_view, "truth": _truth_view}


def make_view(run: "Run", kind: str, asof: Date | None = None, **scope) -> View:
    if kind not in KINDS:
        raise ValueError(f"unknown view {kind!r}; views are {', '.join(KINDS)}")
    if run.manifest.get("builder") != "population":
        raise ValueError("views need a population-built run (tier S and above); this run used the spike builder")
    return _FACTORIES[kind](run, asof, scope)
