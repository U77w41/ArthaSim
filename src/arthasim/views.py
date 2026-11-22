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


# -- handles, narration and statement lines (shared by the bank view, the switch view and the inspector) -----------

# Merchant category codes (ISO 18245; checked against Citi's published list of Visa and Mastercard codes).
MCC = {"grocery": 5411, "food": 5812, "fuel": 5541, "pharmacy": 5912, "apparel": 5651, "electronics": 5732,
       "transport": 4121, "services": 7299, "other": 5999, "telecom": 4814, "electricity": 4900, "ecommerce": 5399,
       "amc": 6211}
# Purposes a payer's remark names in the narration, by rail. The only use of `purpose` outside the truth layer.
REMARKS: dict[str, set[str]] = {"NACH_CR": {"SALARY", "PENSION"}}
_NARRATION_RAIL = {"UPI_P2M": "UPI", "UPI_P2P": "UPI", "NACH_CR": "NACH", "DEBIT_CARD": "POS"}


def acct_sql(src: Source) -> str:
    """Every account with its bank code (null for cash) and its holder's merchant or biller category."""
    return f"""select a.account_id, a.type, a.subtype, a.holder_entity_id, a.opened_on, a.status,
                      a.opening_balance_paise, b.bank_code, o.category
               from {src('accounts')} a
               left join {src('banks')} b on a.issuer_entity_id = b.entity_id
               left join {src('orgs')} o on a.holder_entity_id = o.entity_id"""


def handles_sql(src: Source) -> str:
    """One row per account that has instruments: its VPA, account number, terminal, branch, card and device."""
    return f"""select account_id,
                      max(case when kind = 'VPA' then value end) as vpa,
                      max(case when kind = 'ACCOUNT_NO' then value end) as account_no,
                      max(case when kind = 'TERMINAL' then value end) as terminal,
                      min(case when kind = 'BRANCH' then value end) as branch,
                      max(case when kind = 'DEBIT_CARD' then value end) as card_token,
                      max(case when kind = 'DEVICE' then value end) as device_token
               from {src('instruments')} group by account_id"""


def mcc_sql(category: str) -> str:
    whens = " ".join(f"when '{c}' then {code}" for c, code in MCC.items())
    return f"(case {category} {whens} end)"


def counterparty_handle_sql(rail: str, own_is_payer: str, own: str, own_h: str, other_h: str) -> str:
    """What an observer of one side sees of the other side (spec section 4). Withdrawals and branch deposits name
    a terminal or branch made from the own account's home branch."""
    return f"""(case
        when {rail} in ('UPI_P2M', 'UPI_P2P') then coalesce({other_h}.vpa, {other_h}.account_no)
        when {rail} in ('NEFT', 'IMPS', 'NACH_CR') then {other_h}.account_no
        when {rail} = 'DEBIT_CARD' then case when {own_is_payer} then coalesce({other_h}.terminal, {other_h}.account_no)
                                             else coalesce({other_h}.card_token, {other_h}.account_no) end
        when {rail} = 'ATM' then 'ATM' || coalesce({own_h}.branch, {own}.bank_code)
        when {rail} = 'AEPS' then 'MATM' || coalesce({own_h}.branch, {own}.bank_code)
        when {rail} = 'BRANCH' then coalesce({own_h}.branch, {own}.bank_code)
        else coalesce({other_h}.account_no, {other_h}.vpa) end)"""


def counterparty_bank_sql(rail: str, own: str, other: str) -> str:
    return f"(case when {rail} in ('ATM', 'AEPS', 'BRANCH') then {own}.bank_code else {other}.bank_code end)"


def ref_sql(payment_id: str) -> str:
    return f"lpad(cast({payment_id} as varchar), 12, '0')"


def date_sql(ts: str) -> str:
    return f"cast(make_timestamp({ts}) + interval 330 minute as date)"


def narration_sql(rail: str, direction: str, ref: str, handle: str, purpose: str) -> str:
    """Rail, direction, reference, the other side's handle, then the payer's remark where real files carry one."""
    name = " ".join(f"when '{r}' then '{n}'" for r, n in _NARRATION_RAIL.items())
    remark = " or ".join(f"({rail} = '{r}' and {purpose} in ({', '.join(repr(x) for x in sorted(ps))}))"
                         for r, ps in REMARKS.items()) or "false"
    return f"""(case
        when {rail} in ('ATM', 'AEPS') then {rail} || '/WDL/' || {ref} || '/' || {handle}
        when {rail} = 'BRANCH' then 'CASH DEP/' || {ref} || '/' || {handle}
        else (case {rail} {name} else {rail} end) || '/' || {direction} || '/' || {ref} || '/' || coalesce({handle}, '')
        end || case when {remark} then '/' || {purpose} else '' end)"""


def lines_sql(src: Source, accounts: str, cut: int | None, truth: bool = False) -> str:
    """Statement lines: one row per posting on the accounts that `accounts` (a subquery of account_id) selects.
    `truth` adds the purpose, journal and the other side's simulator IDs, and leaves narration null on cash."""
    when = f"and j.ts < {cut}" if cut is not None else ""
    direction = "case when l.delta_paise < 0 then 'DR' else 'CR' end"
    payer = "y.payer_account_id = l.account_id"
    handle = counterparty_handle_sql("y.rail", payer, "own", "oh", "xh")
    narration = narration_sql("y.rail", direction, ref_sql("l.payment_id"), handle, "y.purpose")
    if truth:
        narration = f"case when own.type = 'DEPOSIT' then {narration} end"
        extra = """, y.purpose, l.journal_id, l.line_no, own.type as account_type,
                   oth.holder_entity_id as counterparty_entity_id, oth.account_id as counterparty_account_id"""
        customer, customer_join = "", ""
    else:
        extra = ""
        customer = "c.customer_no,"
        customer_join = (f"left join {src('bank_customers')} c on c.bank_code = own.bank_code "
                         "and c.entity_id = own.holder_entity_id")
    return f"""
        with acct as ({acct_sql(src)}), h as ({handles_sql(src)}),
        l as (select p.account_id, p.journal_id, p.line_no, p.delta_paise, p.balance_after_paise, j.ts, j.payment_id
              from {src('postings')} p join {src('journal')} j using (journal_id)
              where p.account_id in ({accounts}) {when})
        select l.account_id, oh.account_no, own.holder_entity_id as entity_id, {customer}
               l.ts, {date_sql('l.ts')} as date,
               row_number() over (partition by l.account_id order by l.ts, l.journal_id, l.line_no) as line_seq,
               l.payment_id, {ref_sql('l.payment_id')} as ref, y.rail, {direction} as direction,
               abs(l.delta_paise) as amount_paise, l.balance_after_paise,
               {handle} as counterparty_handle, {counterparty_bank_sql('y.rail', 'own', 'oth')} as counterparty_bank,
               {narration} as narration {extra}
        from l
        join acct own on own.account_id = l.account_id
        left join h oh on oh.account_id = l.account_id
        left join {src('payments')} y on y.payment_id = l.payment_id
        left join acct oth on oth.account_id = case when {payer} then y.payee_account_id else y.payer_account_id end
        left join h xh on xh.account_id = oth.account_id
        {customer_join}
        order by l.ts, l.journal_id, l.line_no"""


# -- bank ---------------------------------------------------------------------------------------------------------

def _bank_codes(view: View) -> list[str]:
    banks = duckdb.sql(f"select bank_code from {view.src('banks')} where kind = 'BANK' order by bank_code").pl()
    return banks["bank_code"].to_list()


def _bank(view: View, asof: dt.date | None) -> dict[str, str]:
    src, code = view.src, view.scope["bank"]
    day = f"date '{asof.isoformat()}'" if asof is not None else None
    cut = asof_us(asof) if asof is not None else None
    opened = f"and opened_on <= {day}" if day else ""
    own = f"select account_id from ({acct_sql(src)}) where bank_code = '{code}' and type = 'DEPOSIT' {opened}"
    customers = f"""
        with first_open as (
            select a.holder_entity_id as entity_id, min(a.opened_on) as first_opened
            from {src('accounts')} a join {src('banks')} b on a.issuer_entity_id = b.entity_id
            where b.bank_code = '{code}' and a.type = 'DEPOSIT' {opened.replace('opened_on', 'a.opened_on')}
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
    accounts = f"""
        with acct as ({acct_sql(src)}), h as ({handles_sql(src)})
        select a.account_id, h.account_no, a.holder_entity_id as entity_id, c.customer_no, a.subtype, a.opened_on,
               a.status, a.opening_balance_paise
        from acct a left join h using (account_id)
        left join {src('bank_customers')} c on c.bank_code = a.bank_code and c.entity_id = a.holder_entity_id
        where a.account_id in ({own})
        order by a.account_id"""
    instruments = f"select * from {src('instruments')} where account_id in ({own}) order by instrument_id"
    when = f"and y.settle_ts < {cut}" if cut is not None else ""
    payer = "s.direction = 'DR'"
    payments = f"""
        with acct as ({acct_sql(src)}), h as ({handles_sql(src)}),
        side as (
            select y.*, 'DR' as direction, y.payer_account_id as own_id, y.payee_account_id as other_id
            from {src('payments')} y
            where y.payer_account_id in ({own}) and y.rail <> 'CASH' {when}
            union all
            select y.*, 'CR' as direction, y.payee_account_id as own_id, y.payer_account_id as other_id
            from {src('payments')} y
            where y.payee_account_id in ({own}) and y.status = 'SUCCESS' {when})
        select s.payment_id, {ref_sql('s.payment_id')} as ref, s.settle_ts as ts, {date_sql('s.settle_ts')} as date,
               s.rail, s.status, s.amount_paise, s.direction, s.own_id as account_id, oh.account_no,
               own.holder_entity_id as entity_id, c.customer_no,
               {counterparty_handle_sql('s.rail', payer, 'own', 'oh', 'xh')} as counterparty_handle,
               {counterparty_bank_sql('s.rail', 'own', 'oth')} as counterparty_bank,
               case when s.rail in ('UPI_P2M', 'DEBIT_CARD') then {mcc_sql('pay.category')} end as mcc,
               case when s.direction = 'DR' and s.rail in ('UPI_P2M', 'UPI_P2P') then oh.device_token end
                   as device_token
        from side s
        join acct own on own.account_id = s.own_id
        left join h oh on oh.account_id = s.own_id
        left join acct oth on oth.account_id = s.other_id
        left join h xh on xh.account_id = s.other_id
        left join acct pay on pay.account_id = s.payee_account_id
        left join {src('bank_customers')} c on c.bank_code = '{code}' and c.entity_id = own.holder_entity_id
        order by s.settle_ts, s.payment_id, s.direction"""
    statement_lines = lines_sql(src, own, cut)
    month = f"and b.month <= '{month_end(asof)}'" if asof is not None else ""
    balances = f"""
        with h as ({handles_sql(src)})
        select b.account_id, h.account_no, b.month, b.balance_paise
        from {src('balances_monthly')} b left join h using (account_id)
        where b.account_id in ({own}) {month}
        order by b.month, b.account_id"""
    return {"customers": customers, "accounts": accounts, "instruments": instruments, "payments": payments,
            "statement_lines": statement_lines, "balances_monthly": balances}


def _bank_view(run: "Run", asof: Date | None, scope: dict) -> View:
    if set(scope) != {"bank"}:
        raise ValueError(f"the bank view takes one scope argument, bank=<code>; got {sorted(scope)}")
    view = View(run, "bank", scope, asof, _bank, {"payments", "statement_lines", "balances_monthly"})
    codes = _bank_codes(view)
    if scope["bank"] not in codes:
        raise ValueError(f"unknown bank {scope['bank']!r}; banks are {', '.join(codes)}")
    return view


# -- switch -------------------------------------------------------------------------------------------------------

NETWORKS = {"upi": ("UPI_P2M", "UPI_P2P"), "imps": ("IMPS",), "nach": ("NACH_CR",), "card": ("DEBIT_CARD",),
            "atm": ("ATM",), "aeps": ("AEPS",)}


def _switch(view: View, asof: dt.date | None) -> dict[str, str]:
    src = view.src
    rails = ", ".join(f"'{r}'" for r in NETWORKS[view.scope["network"]])
    when = f"and y.settle_ts < {asof_us(asof)}" if asof is not None else ""
    payments = f"""
        with acct as ({acct_sql(src)}), h as ({handles_sql(src)})
        select y.payment_id, {ref_sql('y.payment_id')} as ref, y.settle_ts as ts, {date_sql('y.settle_ts')} as date,
               y.rail, y.status, y.amount_paise,
               case when y.rail in ('UPI_P2M', 'UPI_P2P') then coalesce(ph.vpa, ph.account_no)
                    when y.rail in ('IMPS', 'NACH_CR') then ph.account_no
                    when y.rail in ('DEBIT_CARD', 'ATM') then coalesce(ph.card_token, ph.account_no)
                    when y.rail = 'AEPS' then pp.uid_token end as payer_handle,
               y.payer_bank,
               case when y.rail in ('UPI_P2M', 'UPI_P2P') then coalesce(eh.vpa, eh.account_no)
                    when y.rail in ('IMPS', 'NACH_CR') then eh.account_no
                    when y.rail = 'DEBIT_CARD' then coalesce(eh.terminal, eh.account_no)
                    when y.rail = 'ATM' then 'ATM' || coalesce(ph.branch, pa.bank_code)
                    when y.rail = 'AEPS' then 'MATM' || coalesce(ph.branch, pa.bank_code) end as payee_handle,
               case when y.rail in ('ATM', 'AEPS') then y.payer_bank else y.payee_bank end as payee_bank,
               case when y.rail in ('UPI_P2M', 'DEBIT_CARD') then {mcc_sql('pe.category')} end as mcc,
               case when y.rail in ('UPI_P2M', 'UPI_P2P') then ph.device_token end as payer_device_token
        from {src('payments')} y
        left join acct pa on pa.account_id = y.payer_account_id
        left join h ph on ph.account_id = y.payer_account_id
        left join acct pe on pe.account_id = y.payee_account_id
        left join h eh on eh.account_id = y.payee_account_id
        left join {src('persons')} pp on pp.entity_id = pa.holder_entity_id
        where y.rail in ({rails}) {when}
        order by y.settle_ts, y.payment_id"""
    return {"payments": payments}


def _switch_view(run: "Run", asof: Date | None, scope: dict) -> View:
    scope = {"network": "upi", **scope}
    if set(scope) != {"network"} or scope["network"] not in NETWORKS:
        raise ValueError(f"the switch view takes network=<one of {', '.join(NETWORKS)}>; got {scope}")
    return View(run, "switch", scope, asof, _switch, {"payments"})


# -- bureau -------------------------------------------------------------------------------------------------------

# A bureau holds files only on people reported by lenders (credit applied for or taken). Nobody borrows until
# phase 3, so every table is empty; the columns are fixed now so code written against them keeps working.
_BUREAU = {
    "consumers": "pan_like VARCHAR, birth_year BIGINT, birth_month BIGINT, sex VARCHAR, district VARCHAR, "
                 "mobile_token VARCHAR",
    "tradelines": "pan_like VARCHAR, lender_code VARCHAR, product VARCHAR, month VARCHAR, sanctioned_paise BIGINT, "
                  "balance_paise BIGINT, dpd BIGINT",
    "enquiries": "pan_like VARCHAR, lender_code VARCHAR, product VARCHAR, ts BIGINT",
    "scores": "pan_like VARCHAR, month VARCHAR, score BIGINT",
}


def _bureau(view: View, asof: dt.date | None) -> dict[str, str]:
    return {t: f"select * from {_empty(cols)}" for t, cols in _BUREAU.items()}


def _bureau_view(run: "Run", asof: Date | None, scope: dict) -> View:
    if scope:
        raise ValueError(f"the bureau view takes no scope arguments; got {sorted(scope)}")
    return View(run, "bureau", scope, asof, _bureau, {"tradelines", "scores"})


def _truth_view(run: "Run", asof: Date | None, scope: dict) -> View:
    if scope:
        raise ValueError(f"the truth view takes no scope arguments; got {sorted(scope)}")
    from arthasim.store.parquet import FACT_TABLES
    return View(run, "truth", scope, asof, _truth, set(FACT_TABLES))


_FACTORIES = {"bank": _bank_view, "switch": _switch_view, "bureau": _bureau_view, "truth": _truth_view}


def make_view(run: "Run", kind: str, asof: Date | None = None, **scope) -> View:
    if kind not in KINDS:
        raise ValueError(f"unknown view {kind!r}; views are {', '.join(KINDS)}")
    if run.manifest.get("builder") != "population":
        raise ValueError("views need a population-built run (tier S and above); this run used the spike builder")
    return _FACTORIES[kind](run, asof, scope)
