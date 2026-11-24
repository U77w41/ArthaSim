"""Public entry points: World (build and run) and Run (read results)."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import shutil
import time
from pathlib import Path
from typing import Any, Callable

import duckdb
import numpy as np
import polars as pl

from arthasim.build.world import EntityKind, WorldState, build_state
from arthasim.config import Config
from arthasim.engine.rng import KeyedSeed, Seed
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
from arthasim import checkpoint as _checkpoint
from arthasim import macro as _macro
from arthasim.store.hashing import RunningHash
from arthasim.store.parquet import (DIM_TABLES, FACT_TABLES, LOG_SCHEMA, META_TABLES, Store, content_hash, read_table,
                                    table_files, write_atomic)

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


def _source_label(run_id: str, secret: bytes | None) -> str:
    """The label an export gives its source run. With a release secret it is keyed, so it reveals nothing about the
    run's seed or settings; without one it is the original unkeyed digest."""
    if secret is None:
        return hashlib.sha256(run_id.encode()).hexdigest()[:16]
    return hashlib.blake2b(run_id.encode(), key=secret, digest_size=8).hexdigest()


class World:
    def __init__(self, config: Config, seed: Seed, params: ParamRegistry, state: WorldState,
                 path: Path, run_seed: int | None = None) -> None:
        # `seed` is what every draw and identifier is keyed with: the run seed, or a KeyedSeed when the config has a
        # release secret. `run_seed` is the seed as typed, which names the run.
        self.config, self.seed, self.params, self.state = config, seed, params, state
        self.run_seed = run_seed if run_seed is not None else (seed.run_seed if isinstance(seed, KeyedSeed) else seed)
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
        self._params_read: set[str] = set()     # registry ids read on a simulated day
        self._checkpoints = True                 # keep a checkpoint at every month end
        self._forked_from: dict[str, str] | None = None

    def __getstate__(self) -> dict[str, Any]:
        """What a checkpoint holds: everything but the store, the watchers, the release secret and the keys derived
        from it (the seed is kept as the run seed only)."""
        state = dict(self.__dict__)
        state.pop("_store", None)
        state.pop("_watchers", None)
        state["seed"] = self.run_seed
        state["config"] = self.config.model_copy(update={"release_secret": None})
        return state

    def __setstate__(self, state: dict[str, Any]) -> None:
        self.__dict__.update(state)
        self._store = None
        self._watchers = {}

    @classmethod
    def build(cls, config: Config, seed: int, path: str | Path | None = None, checkpoints: bool = True) -> "World":
        """Build a world. `path` is the run folder (by default `<out_dir>/<tier>-seed<seed>-<config hash[:8]>`);
        with `checkpoints` the world keeps a checkpoint at every month end in `<run>/checkpoints/<YYYY-MM>/`."""
        path = Path(path) if path is not None else Path(config.out_dir) / f"{config.tier_name}-seed{seed}-{config.hash()[:8]}"
        if path.exists():
            raise FileExistsError(f"run directory already exists: {path}")
        params = ParamRegistry.load(_registry_path(config), overrides=config.param_overrides)
        secret = config.secret_bytes()
        draw: Seed = seed if secret is None else KeyedSeed.derive(seed, secret)
        state = build_state(config, params, draw)
        path.mkdir(parents=True)
        world = cls(config, draw, params, state, path, run_seed=seed)
        world._checkpoints = bool(checkpoints)
        for name, frame in _dimension_frames(state, config, draw).items():
            world._store.write_dimension(name, frame)
        return world

    @property
    def label(self) -> str:
        """The month that has just ended ("YYYY-MM"), or "start" before the first simulated day."""
        return _checkpoint.label(self)

    def save(self, path: str | Path) -> None:
        """Write a checkpoint into the new folder `path`. Only at a month end (or before the first day)."""
        _checkpoint.write(self, Path(path))

    @classmethod
    def load(cls, path: str | Path, path_out: str | Path | None = None, release_secret: str | None = None,
             checkpoints: bool = True) -> "World":
        """Continue a checkpoint in a new run folder: `path_out`, or `<out_dir>/<run_id>-from-<label>` numbered
        `-2`, `-3`, ... when taken. A checkpoint of a run with a release secret needs the secret again. Loading
        a pickle runs code: load only checkpoints from your own runs."""
        world, meta = _checkpoint.read(Path(path), release_secret)
        if path_out is not None:
            folder = Path(path_out)
            if folder.exists():
                raise FileExistsError(f"run directory already exists: {folder}")
        else:
            folder = _checkpoint.next_free(Path(world.config.out_dir) / f"{meta['run_id']}-from-{meta['label']}")
        _checkpoint.link_tree(Path(path) / "run", folder)
        try:
            store = Store(folder)
            hashes = {t: RunningHash.from_disk(store.spool_dir, t, folder)
                      for t in FACT_TABLES if table_files(folder, t)}
            recorded = meta["content_hash"]
            for t in FACT_TABLES:
                if (t in recorded) != (t in hashes) or (t in hashes and hashes[t].digest() != recorded[t]):
                    raise ValueError(f"checkpoint file changed: table {t} no longer matches its recorded hash")
            store.restore(hashes)
            world._open(folder, store, checkpoints, {"run_id": meta["run_id"], "month": meta["label"], "how": "load"})
        except BaseException:
            shutil.rmtree(folder, ignore_errors=True)
            raise
        return world

    def _open(self, path: Path, store: Store, checkpoints: bool, forked_from: dict[str, str]) -> None:
        """Attach a loaded or forked world to its own folder, and rewrite the files its parent may since have
        replaced (accounts, instruments, bank customers, metadata and the manifest) from its own state."""
        self.path, self._store, self._watchers = Path(path), store, {}
        self._checkpoints, self._forked_from = bool(checkpoints), forked_from
        self._flush()

    def _intervention_details(self) -> list[dict[str, Any]]:
        return []

    def set_params(self, params: ParamRegistry) -> None:
        """Replace the registry from now on; the life course's targets follow it."""
        self.params = params
        if self.state.life is not None:
            self.state.life.targets.set_params(params)

    @property
    def days_simulated(self) -> int:
        return self._days

    @property
    def date(self) -> dt.date:
        """The next day to be simulated."""
        return self._date

    def macro(self, series: str, day: Date) -> float | None:
        """The value of a macro series (`policy_rate`, `cpi_inflation`) in force on a day, under the paths now set."""
        return _macro.value_on(_macro.steps(self.params, series), _as_date(day))

    def watch(self, entity_id: int, callback: Callable[[dict], None]) -> None:
        """Call `callback` after each simulated day on which the entity made or received a payment attempt or had a
        life event, with that day's payments, events, end-of-day balances and, on a day the life course ran (the
        first of a month and the first simulated day), its monthly state. The day is complete before the call, so
        a callback that raises leaves the world ready to continue."""
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
        try:
            for _ in range(days):
                self._day()
        finally:
            self._store.flush()                 # close open files even when a day or a callback raised
        self._flush()

    def run(self, until: Date) -> "Run":
        """Simulate up to and including `until`."""
        until = _as_date(until)
        try:
            while self._date <= until:
                self._day()
        finally:
            self._store.flush()                 # close open files even when a day or a callback raised
        self._flush()
        return Run.open(self.path)

    def _day(self) -> None:
        started = time.perf_counter()
        day = self._date
        monthly_ran = day.day == 1 or self._days == 0
        reads: set[str] = set()
        params = self.params
        params._reads = reads
        try:
            payments, journal, postings = run_day(self, day)
        finally:
            params._reads = None
        self._params_read |= reads
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
        if self._watchers:                      # last, once the day is complete (callback time is not counted)
            self._notify(day, payments, frames)

    def _content_hashes(self) -> dict[str, str]:
        """Fact tables from the store's live hashes; dimension tables from disk."""
        live = self._store.content_hashes()
        return {t: live[t] if t in live else content_hash(self.path, t)
                for t in FACT_TABLES + DIM_TABLES + META_TABLES if table_files(self.path, t)}

    def _flush(self) -> None:
        self._store.flush()
        if self.state.population is not None:
            # Accounts opened during the run join the accounts and instruments tables.
            from arthasim.build.pipeline import account_frames
            for name, frame in account_frames(self.state, self.config, self.seed).items():
                self._store.write_dimension(name, frame)
        self._store.write_dimension("macro_paths", _macro.frame(self.params))
        self._store.write_dimension("interventions_log", pl.DataFrame(schema=LOG_SCHEMA))
        manifest: dict[str, Any] = {
            "run_id": self.path.name, "seed": self.run_seed, "config_hash": self.config.hash(),
            "release_secret": self.config.release_secret is not None,
            "source_label": _source_label(self.path.name, self.config.secret_bytes()),
            "registry_version": self.params.version(), "code_version": _CODE_VERSION,
            "tier": self.config.tier_name, "start": self.config.start.isoformat(),
            "end": (self._date - dt.timedelta(days=1)).isoformat() if self._days else None,
            "days": self._days, "payments": self._payments, "wall_seconds": round(self._wall, 3),
            "content_hash": self._content_hashes(),
            "polars_version": pl.__version__,
            "params_read": sorted(self._params_read),
            "forked_from": self._forked_from, "checkpoints": self._checkpoints,
        }
        manifest["builder"] = self.config.builder
        if self.state.population is not None:
            districts = self.state.population.districts
            manifest["districts"] = list(self.config.districts)
            manifest["scale_factor"] = sum(d.adult_population for d in districts) / self.config.persons
            manifest["build_report"] = self.state.population.report
        write_atomic(self.path / "run_manifest.json", json.dumps(manifest, indent=2))


class Run:
    def __init__(self, path: str | Path, manifest: dict[str, Any]) -> None:
        self.path = str(path)
        self.manifest = manifest

    @classmethod
    def open(cls, path: str | Path) -> "Run":
        return cls(path, json.loads((Path(path) / "run_manifest.json").read_text()))

    def tables(self) -> list[str]:
        return [t for t in FACT_TABLES + DIM_TABLES + META_TABLES if table_files(Path(self.path), t)]

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

    def export(self, dest: str | Path, view: str = "bank", asof: Date | None = None, **scope: Any) -> Path:
        """Write a view to Parquet under `dest`, with a manifest and a data dictionary. Observer views drop every
        simulator ID; a bank export carries the bank's own customer and account numbers."""
        from arthasim.export import export_view
        return export_view(self, dest, view=view, asof=asof, **scope)

    def sql(self, query: str) -> pl.DataFrame:
        con = duckdb.connect()
        for t in self.tables():
            files = [str(f) for f in table_files(Path(self.path), t)]
            con.execute(f"create view {t} as select * from read_parquet({files!r}, hive_partitioning=false)")
        return con.sql(query).pl()
