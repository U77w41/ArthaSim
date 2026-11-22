"""Public entry points: World (build and run) and Run (read results)."""
from __future__ import annotations

import datetime as dt
import json
import time
from pathlib import Path
from typing import Any, Callable

import duckdb
import numpy as np
import polars as pl

from arthasim.build.world import EntityKind, WorldState, build_state
from arthasim.config import Config
from arthasim.engine.scheduler import Counters, run_day
from arthasim.modules.allowance import Allowance
from arthasim.modules.base import BehaviourModule
from arthasim.modules.budget import Budget
from arthasim.modules.cash import CashManagement
from arthasim.modules.dbt import GovernmentTransfers
from arthasim.modules.income_flows import Income
from arthasim.modules.lifecourse import LifeCourse
from arthasim.modules.remittances import Remittances
from arthasim.modules.spending import Consumption
from arthasim.modules.spike import SpikeConsumption, SpikeIncome
from arthasim.ledger.instruments import InstrumentType as T
from arthasim.params import ParamRegistry
from arthasim.store.parquet import (DIM_TABLES, FACT_TABLES, Store, content_hash, read_table,
                                    table_files)

Date = str | dt.date
_CODE_VERSION = "0.0.1"


def _as_date(value: Date) -> dt.date:
    return value if isinstance(value, dt.date) else dt.date.fromisoformat(value)


def _registry_path(config: Config) -> Path:
    path = Path(config.params_path)
    if path.is_absolute() or path.exists():
        return path
    return Path(__file__).resolve().parents[2] / path


def _dimension_frames(state: WorldState, config: Config, seed: int) -> dict[str, pl.DataFrame]:
    if state.population is not None:
        from arthasim.build.pipeline import population_frames
        return population_frames(state, config, seed)
    return _spike_frames(state, config)


def _spike_frames(state: WorldState, config: Config) -> dict[str, pl.DataFrame]:
    codes = state.bank_codes
    book = state.book
    persons = pl.DataFrame({
        "entity_id": state.person_ids, "pan_like": pl.Series(state.pan_like.tolist(), dtype=pl.String),
        "bank_code": pl.Series(codes[state.person_bank].tolist(), dtype=pl.String),
        "employer_entity_id": pl.Series(
            np.where(state.person_employer >= 0,
                     state.employer_ids[np.maximum(state.person_employer, 0)] if len(state.employer_ids) else -1,
                     -1)).replace(-1, None),
        "salary_paise": state.person_salary, "digital": state.person_digital})
    orgs = pl.concat([
        pl.DataFrame({"entity_id": state.employer_ids,
                      "kind": pl.Series(["EMPLOYER"] * len(state.employer_ids), dtype=pl.String),
                      "bank_code": pl.Series(codes[state.employer_bank].tolist(), dtype=pl.String),
                      "payday": pl.Series(state.employer_payday, dtype=pl.Int64)}),
        pl.DataFrame({"entity_id": state.merchant_ids,
                      "kind": pl.Series(["MERCHANT"] * len(state.merchant_ids), dtype=pl.String),
                      "bank_code": pl.Series(codes[state.merchant_bank].tolist(), dtype=pl.String),
                      "payday": pl.Series([None] * len(state.merchant_ids), dtype=pl.Int64)})])
    banks = pl.DataFrame({"entity_id": state.bank_ids, "bank_code": pl.Series(codes.tolist(), dtype=pl.String),
                          "is_boundary": [c == "SYNX00" for c in codes.tolist()]})

    type_names = np.array(["", "DEPOSIT", "CASH", "RESERVE", "GOVERNMENT"], dtype=object)[book.type]
    holder_kind = state.kind[book.holder]
    subtype = np.full(len(book), "current", dtype=object)
    subtype[(book.type == T.DEPOSIT) & (holder_kind == EntityKind.PERSON)] = "savings"
    subtype[(book.type == T.DEPOSIT) & (holder_kind == EntityKind.BOUNDARY)] = "boundary"
    subtype[book.type == T.CASH] = "cash_in_hand"
    subtype[(book.type == T.CASH) & (holder_kind == EntityKind.BANK)] = "vault"
    subtype[book.type == T.RESERVE] = "reserve"
    accounts = pl.DataFrame({
        "account_id": np.arange(len(book), dtype=np.int64),
        "type": pl.Series(type_names.tolist(), dtype=pl.String),
        "subtype": pl.Series(subtype.tolist(), dtype=pl.String),
        "holder_entity_id": book.holder, "issuer_entity_id": book.issuer,
        "opened_on": pl.Series([config.start] * len(book), dtype=pl.Date),
        "status": pl.Series(["ACTIVE"] * len(book), dtype=pl.String)})
    return {"persons": persons, "orgs": orgs, "banks": banks, "accounts": accounts}


def _household_monthly(state: WorldState, month: str) -> pl.DataFrame:
    """Each household's budgeting state as set at the start of the month (truth layer). `income_paise` is
    earned income; `transfer_income_paise` is DBT at its monthly value; the budget counts both."""
    beh = state.behaviour
    n = beh.income.size
    return pl.DataFrame({
        "household_id": np.arange(n, dtype=np.int64), "month": pl.Series([month] * n, dtype=pl.String),
        "income_paise": beh.income, "balance_paise": beh.balance, "buffer_months": beh.buffer_months,
        "stress": beh.stress, "budget_paise": beh.budget, "medical_due_paise": beh.medical_due,
        "transfer_income_paise": beh.transfer_income})


class World:
    def __init__(self, config: Config, seed: int, params: ParamRegistry, state: WorldState,
                 path: Path) -> None:
        self.config, self.seed, self.params, self.state = config, seed, params, state
        self.path = path
        self._date = config.start
        self.counters = Counters()
        self.modules: list[BehaviourModule] = (
            [LifeCourse(), Income(), Remittances(), GovernmentTransfers(), Budget(), Allowance(), Consumption(),
             CashManagement()]
            if state.population is not None
            else [SpikeIncome(), SpikeConsumption()])
        self._store = Store(path)
        self._days = 0
        self._payments = 0
        self._wall = 0.0
        self._watchers: dict[int, list[Callable[[dict], None]]] = {}

    @classmethod
    def build(cls, config: Config, seed: int) -> "World":
        path = Path(config.out_dir) / f"{config.tier_name}-seed{seed}-{config.hash()[:8]}"
        if path.exists():
            raise FileExistsError(f"run directory already exists: {path}")
        params = ParamRegistry.load(_registry_path(config), overrides=config.param_overrides)
        state = build_state(config, params, seed)
        path.mkdir(parents=True)
        world = cls(config, seed, params, state, path)
        for name, frame in _dimension_frames(state, config, seed).items():
            world._store.write_dimension(name, frame)
        return world

    @property
    def days_simulated(self) -> int:
        return self._days

    @property
    def date(self) -> dt.date:
        """The next day to be simulated."""
        return self._date

    def watch(self, entity_id: int, callback: Callable[[dict], None]) -> None:
        """Call `callback` after each simulated day on which the entity made or received a payment attempt or had a
        life event, with that day's payments, events, end-of-day balances and (on a month's first day) its state."""
        self._watchers.setdefault(int(entity_id), []).append(callback)

    def unwatch(self, entity_id: int) -> None:
        """Remove every callback watching the entity."""
        self._watchers.pop(int(entity_id), None)

    def _notify(self, day: dt.date, payments: pl.DataFrame, frames: dict[str, pl.DataFrame]) -> None:
        book = self.state.book
        events = frames.get("life_events")
        states = frames.get("entity_state_monthly")
        for eid, callbacks in list(self._watchers.items()):
            accounts = np.flatnonzero(book.holder == eid)
            mine = accounts.tolist()
            pay = payments.filter(pl.col("payer_account_id").is_in(mine) | pl.col("payee_account_id").is_in(mine))
            ev = events.filter(pl.col("entity_id") == eid) if events is not None else None
            if pay.height == 0 and (ev is None or ev.height == 0):
                continue
            payer, payee = pl.col("payer_account_id").is_in(mine), pl.col("payee_account_id").is_in(mine)
            pay = pay.with_columns(pl.when(payer & payee).then(pl.lit("SELF")).when(payer).then(pl.lit("DR"))
                                   .otherwise(pl.lit("CR")).alias("direction"))
            row = states.filter(pl.col("entity_id") == eid) if states is not None else None
            payload = {"date": day, "entity_id": eid, "payments": pay.to_dicts(),
                       "events": ev.to_dicts() if ev is not None else [],
                       "balances": {int(a): int(book.balance[a]) for a in accounts},
                       "state": row.to_dicts()[0] if row is not None and row.height else None}
            for callback in list(callbacks):
                callback(payload)

    def step(self, days: int = 1) -> None:
        for _ in range(days):
            self._day()
        self._flush()

    def run(self, until: Date) -> "Run":
        """Simulate up to and including `until`."""
        until = _as_date(until)
        while self._date <= until:
            self._day()
        self._flush()
        return Run.open(self.path)

    def _day(self) -> None:
        started = time.perf_counter()
        day = self._date
        monthly_ran = day.day == 1 or self._days == 0
        payments, journal, postings = run_day(self, day)
        month = f"{day:%Y-%m}"
        if monthly_ran and self.state.behaviour is not None:
            self._store.add("truth_household_monthly", month, _household_monthly(self.state, month))
        frames: dict[str, pl.DataFrame] = {}
        for module in self.modules:
            for name, frame in module.tables().items():
                self._store.add(name, month, frame)
                frames[name] = frame
        self._store.add("payments", month, payments)
        self._store.add("journal", month, journal)
        self._store.add("postings", month, postings)
        if self._watchers:
            self._notify(day, payments, frames)
        self._days += 1
        self._payments += payments.height
        self._date = day + dt.timedelta(days=1)
        if self._date.month != day.month:
            # The month just ended: every account's closing balance.
            book = self.state.book
            self._store.add("balances_monthly", month, pl.DataFrame({
                "account_id": np.arange(len(book), dtype=np.int64),
                "month": pl.Series([month] * len(book), dtype=pl.String),
                "balance_paise": book.balance.copy()}))
            self._store.end_month(month)
        self._wall += time.perf_counter() - started

    def _content_hashes(self) -> dict[str, str]:
        """Fact tables from the store's live hashes; dimension tables from disk."""
        live = self._store.content_hashes()
        return {t: live[t] if t in live else content_hash(self.path, t)
                for t in FACT_TABLES + DIM_TABLES if table_files(self.path, t)}

    def _flush(self) -> None:
        self._store.flush()
        if self.state.population is not None:
            # Accounts opened during the run join the accounts and instruments tables.
            from arthasim.build.pipeline import account_frames
            for name, frame in account_frames(self.state, self.config, self.seed).items():
                self._store.write_dimension(name, frame)
        manifest: dict[str, Any] = {
            "run_id": self.path.name, "seed": self.seed, "config_hash": self.config.hash(),
            "registry_version": self.params.version(), "code_version": _CODE_VERSION,
            "tier": self.config.tier_name, "start": self.config.start.isoformat(),
            "end": (self._date - dt.timedelta(days=1)).isoformat() if self._days else None,
            "days": self._days, "payments": self._payments, "wall_seconds": round(self._wall, 3),
            "content_hash": self._content_hashes(),
            "polars_version": pl.__version__,
        }
        manifest["builder"] = self.config.builder
        if self.state.population is not None:
            districts = self.state.population.districts
            manifest["districts"] = list(self.config.districts)
            manifest["scale_factor"] = sum(d.adult_population for d in districts) / self.config.persons
            manifest["build_report"] = self.state.population.report
        (self.path / "run_manifest.json").write_text(json.dumps(manifest, indent=2))


class Run:
    def __init__(self, path: str | Path, manifest: dict[str, Any]) -> None:
        self.path = str(path)
        self.manifest = manifest

    @classmethod
    def open(cls, path: str | Path) -> "Run":
        return cls(path, json.loads((Path(path) / "run_manifest.json").read_text()))

    def tables(self) -> list[str]:
        return [t for t in FACT_TABLES + DIM_TABLES if table_files(Path(self.path), t)]

    def table(self, name: str) -> pl.LazyFrame:
        return read_table(Path(self.path), name)

    def view(self, kind: str, asof: Date | None = None, **scope: Any):
        """What one observer (bank, switch, bureau or truth) sees of this run."""
        from arthasim.views import make_view
        return make_view(self, kind, asof=asof, **scope)

    def inspect(self, entity_id: int):
        """Follow one person or organisation: profile, timeline, passbook, net worth, social links."""
        from arthasim.inspector import EntityTrace
        return EntityTrace(self, entity_id)

    def metric(self, name_or_fn, **kwargs: Any) -> pl.DataFrame:
        """An outcome measure: a frame with one column per grouping and a `value` column."""
        from arthasim.metrics import run_metric
        return run_metric(self, name_or_fn, **kwargs)

    def sql(self, query: str) -> pl.DataFrame:
        con = duckdb.connect()
        for t in self.tables():
            files = [str(f) for f in table_files(Path(self.path), t)]
            con.execute(f"create view {t} as select * from read_parquet({files!r}, hive_partitioning=false)")
        return con.sql(query).pl()
