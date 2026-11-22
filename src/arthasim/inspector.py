"""Follow one person or organisation through a finished run. A truth-level tool: it shows the purpose of each
payment and the simulator IDs of the other side."""
from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, Any

import duckdb
import polars as pl

from arthasim.engine.scheduler import day_start_us
from arthasim.views import Date, Source, as_date, asof_us, lines_sql

if TYPE_CHECKING:
    from arthasim.world import Run

_LOAN_SCHEMA = {"loan_id": pl.Int64, "product": pl.String, "lender_code": pl.String, "sanctioned_paise": pl.Int64,
                "outstanding_paise": pl.Int64, "dpd": pl.Int64}


class EntityTrace:
    def __init__(self, run: "Run", entity_id: int) -> None:
        self.run, self.entity_id = run, int(entity_id)
        self.src = Source(run.path)
        if run.manifest.get("builder") != "population":
            raise ValueError("inspect needs a population-built run (tier S and above); this run used the spike builder")
        kind = self._q(f"""select 'PERSON' as kind from {self.src('persons')} where entity_id = {self.entity_id}
                           union all select kind from {self.src('orgs')} where entity_id = {self.entity_id}""")
        if kind.height == 0:
            raise KeyError(f"no person or organisation with entity_id {self.entity_id}")
        self.kind = kind["kind"][0]
        self._accounts = f"select account_id from {self.src('accounts')} where holder_entity_id = {self.entity_id}"

    def _q(self, sql: str) -> pl.DataFrame:
        return duckdb.connect().sql(sql).pl()

    def profile(self, asof: Date | None = None) -> dict[str, Any]:
        """Who they are, their month state at `asof` (the last month if None) and each account's balance then."""
        src, eid = self.src, self.entity_id
        table = "persons" if self.kind == "PERSON" else "orgs"
        static = self._q(f"select * from {src(table)} where entity_id = {eid}").row(0, named=True)
        state = household = None
        if self.kind == "PERSON":
            month = f"'{as_date(asof):%Y-%m}'" if asof is not None else \
                f"(select max(month) from {src('entity_state_monthly')})"
            rows = self._q(f"select * from {src('entity_state_monthly')} where entity_id = {eid} and month = {month}")
            state = rows.row(0, named=True) if rows.height else None
            household = self._q(f"""select entity_id from {src('persons')} where household_id = {static['household_id']}
                                    order by entity_id""")["entity_id"].to_list()
        cut = asof_us(asof) if asof is not None else None
        opened = f"and a.opened_on <= date '{as_date(asof).isoformat()}'" if asof is not None else ""
        when = f"and j.ts < {cut}" if cut is not None else ""
        accounts = self._q(f"""
            with last as (
                select p.account_id, arg_max(p.balance_after_paise, p.journal_id * 64 + p.line_no) as b
                from {src('postings')} p join {src('journal')} j using (journal_id)
                where p.account_id in ({self._accounts}) {when} group by 1)
            select a.account_id, a.type, a.subtype, b.bank_code, a.opened_on,
                   coalesce(last.b, a.opening_balance_paise) as balance_paise
            from {src('accounts')} a left join {src('banks')} b on a.issuer_entity_id = b.entity_id
            left join last using (account_id)
            where a.holder_entity_id = {eid} {opened}
            order by a.account_id""")
        handles = self._q(f"""select account_id, kind, value from {src('instruments')}
                              where account_id in ({self._accounts}) order by instrument_id""")
        out = []
        for a in accounts.iter_rows(named=True):
            mine = handles.filter(pl.col("account_id") == a["account_id"])
            out.append({**{k: a[k] for k in ("account_id", "type", "subtype", "bank_code", "opened_on")},
                        "handles": dict(zip(mine["kind"].to_list(), mine["value"].to_list())),
                        "balance_paise": a["balance_paise"]})
        return {"entity_id": eid, "kind": self.kind, "static": static, "state": state, "household": household,
                "accounts": out}

    def timeline(self) -> pl.DataFrame:
        """Payments on any of their accounts (declines included) and life events, in time order."""
        src, eid, mine = self.src, self.entity_id, self._accounts
        return self._q(f"""
            with mine as ({mine}),
            pay as (
                select y.settle_ts as ts, 'payment' as kind, y.rail, y.status,
                       case when y.payer_account_id in (select * from mine) and y.payee_account_id in (select * from mine)
                            then 'SELF'
                            when y.payer_account_id in (select * from mine) then 'DR' else 'CR' end as direction,
                       y.amount_paise,
                       case when y.payer_account_id in (select * from mine) then y.payer_account_id
                            else y.payee_account_id end as account_id,
                       case when y.payer_account_id in (select * from mine) then y.payee_account_id
                            else y.payer_account_id end as counterparty_account_id,
                       y.purpose, null::varchar as event, null::varchar as detail, y.payment_id as seq
                from {src('payments')} y
                where y.payer_account_id in (select * from mine) or y.payee_account_id in (select * from mine)),
            ev as (
                select ({day_start_us(dt.date(1970, 1, 1))} + datediff('day', date '1970-01-01', e.date)
                        * 86400000000)::bigint as ts,
                       'event' as kind, null::varchar as rail, null::varchar as status, null::varchar as direction,
                       null::bigint as amount_paise, e.account_id, null::bigint as counterparty_account_id,
                       null::varchar as purpose, e.event,
                       concat_ws('; ',
                           case when e.from_stage is not null or e.to_stage is not null
                                then 'stage ' || coalesce(e.from_stage, '-') || ' -> ' || coalesce(e.to_stage, '-') end,
                           case when e.employer_from is not null or e.employer_to is not null
                                then 'employer ' || coalesce(cast(e.employer_from as varchar), '-') || ' -> '
                                     || coalesce(cast(e.employer_to as varchar), '-') end,
                           case when e.income_before_paise <> e.income_after_paise
                                then 'income ' || e.income_before_paise || ' -> ' || e.income_after_paise end,
                           case when e.account_id is not null then 'account ' || e.account_id end) as detail,
                       e.event_id as seq
                from {src('life_events')} e where e.entity_id = {eid})
            select t.ts, t.kind, t.rail, t.status, t.direction, t.amount_paise, t.account_id,
                   a.holder_entity_id as counterparty_entity_id, t.counterparty_account_id, t.purpose, t.event, t.detail
            from (select * from pay union all select * from ev) t
            left join {src('accounts')} a on a.account_id = t.counterparty_account_id
            order by t.ts, t.kind, t.seq""")

    def passbook(self, account_id: int | None = None) -> pl.DataFrame:
        """One row per posting on their accounts (cash in hand included), with running balances."""
        accounts = self._accounts
        if account_id is not None:
            if account_id not in self._q(accounts)["account_id"].to_list():
                raise KeyError(f"account {account_id} is not held by entity {self.entity_id}")
            accounts = f"select {int(account_id)} as account_id"
        lines = self._q(lines_sql(self.src, accounts, None, truth=True))
        return lines.select("ts", "date", "account_id", "account_type", "line_seq", "rail", "direction",
                            "amount_paise", "balance_after_paise", "counterparty_handle", "narration", "purpose",
                            "payment_id", "counterparty_entity_id", "counterparty_account_id")

    def net_worth(self) -> pl.DataFrame:
        """Month-end deposits and cash, from the monthly closing balances."""
        return self._q(f"""
            select b.month,
                   coalesce(sum(case when a.type = 'DEPOSIT' then b.balance_paise end), 0)::bigint as deposits_paise,
                   coalesce(sum(case when a.type = 'CASH' then b.balance_paise end), 0)::bigint as cash_paise,
                   sum(b.balance_paise)::bigint as total_paise
            from {self.src('balances_monthly')} b join {self.src('accounts')} a using (account_id)
            where a.holder_entity_id = {self.entity_id}
            group by b.month order by b.month""")

    def loans(self) -> pl.DataFrame:
        """Empty until loans exist (phase 3)."""
        return pl.DataFrame(schema=_LOAN_SCHEMA)

    def ego_network(self, hops: int = 1) -> pl.DataFrame:
        """Social links within `hops` of the entity, each with the hop at which it was first reached."""
        edges = pl.read_parquet(self.src.path / "edges.parquet")
        seen, frontier, parts = {self.entity_id}, {self.entity_id}, []
        taken = pl.DataFrame(schema=edges.schema)
        for hop in range(1, hops + 1):
            ids = list(frontier)
            found = edges.filter(pl.col("src_entity_id").is_in(ids) | pl.col("dst_entity_id").is_in(ids))
            found = found.join(taken, on=edges.columns, how="anti")
            if found.height == 0:
                break
            taken = pl.concat([taken, found])
            parts.append(found.with_columns(pl.lit(hop, dtype=pl.Int64).alias("hop")))
            reached = set(found["src_entity_id"].to_list()) | set(found["dst_entity_id"].to_list())
            frontier = reached - seen
            seen |= reached
        if not parts:
            return pl.DataFrame(schema={**edges.schema, "hop": pl.Int64})
        return pl.concat(parts)
