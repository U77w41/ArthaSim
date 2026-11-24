"""Hard checks of a stored run (plan 1e): the ledger invariants re-derived from its tables, same seed and same
output, and no synthetic identifier in a real format. Each returns report rows: dicts with `component`, `status`
(pass, fail or skipped) and `detail`."""
from __future__ import annotations

import calendar
import datetime as dt
import hashlib
import shutil
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import numpy as np
import polars as pl

from arthasim.build.identifiers import REAL_FORMATS, SYNTHETIC_VPA_HANDLE, luhn
from arthasim.ledger.instruments import InstrumentType as T
from arthasim.ledger.invariants import InvariantError, _check_shapes
from arthasim.store.hashing import _feed_month, content_hash, fact_files
from arthasim.store.parquet import DIM_TABLES, FACT_TABLES

if TYPE_CHECKING:
    from arthasim.world import Run

ACCOUNT_TABLES = ("accounts", "instruments", "bank_customers")     # rewritten as accounts open during a run
_TYPES = {"DEPOSIT": T.DEPOSIT, "CASH": T.CASH, "RESERVE": T.RESERVE, "GOVERNMENT": T.GOVERNMENT}


def _row(component: str, ok: bool | None, detail: str) -> dict[str, Any]:
    return {"component": component, "status": "skipped" if ok is None else ("pass" if ok else "fail"),
            "detail": detail}


def _month_frame(path: Path, table: str, month: str) -> pl.DataFrame:
    files = [f for f in fact_files(path, table) if f.parent.name == f"month={month}"]
    return pl.read_parquet(files, hive_partitioning=False) if files else pl.DataFrame()


# Ledger -----------------------------------------------------------------------------------------------------------

def ledger(run: "Run") -> list[dict[str, Any]]:
    """Section 7.3's invariants from the stored journal, postings, accounts and month-end balances, month by month:
    each entry's shape; opening balance plus postings equal to every posting's running balance and every month-end
    balance; no deposit or cash balance below zero; each bank's reserves and vault cash less its deposits, and all
    cash held, the same at every month end as at opening."""
    path = Path(run.path)
    acc = pl.read_parquet(path / "accounts.parquet")
    names = ("shapes", "stock_flow", "non_negative", "bank_balance_sheets", "cash_conservation", "flow_matrix")
    if "opening_balance_paise" not in acc.columns:
        return [_row(n, None, "the run's accounts table has no opening balances (a spike-builder run), so the "
                              "invariants cannot be re-derived; the run checked them every simulated day") for n in names]
    book = SimpleNamespace(type=np.array([int(_TYPES[t]) for t in acc["type"].to_list()], dtype=np.int64),
                           holder=acc["holder_entity_id"].to_numpy(), issuer=acc["issuer_entity_id"].to_numpy())
    opening = acc["opening_balance_paise"].to_numpy()
    last = opening.copy()
    money = (book.type == T.DEPOSIT) | (book.type == T.CASH)
    banks = pl.read_parquet(path / "banks.parquet")["entity_id"].to_numpy()

    def bank_position(balance: np.ndarray, present: np.ndarray) -> np.ndarray:
        held = (book.type == T.RESERVE) | (book.type == T.CASH)
        out = np.zeros(banks.size, dtype=np.int64)
        for i, b in enumerate(banks):
            out[i] = (balance[present & held & (book.holder == b)].sum()
                      - balance[present & (book.type == T.DEPOSIT) & (book.issuer == b)].sum())
        return out

    everyone = np.ones(len(opening), dtype=bool)
    equity = bank_position(opening, everyone)
    cash_issued = int(opening[book.type == T.CASH].sum())
    bad = {"shapes": [], "stock_flow": [], "non_negative": [], "bank_balance_sheets": [], "cash_conservation": []}
    months = sorted({f.parent.name.split("=", 1)[1] for f in fact_files(path, "postings")})
    closed = {f.parent.name.split("=", 1)[1] for f in fact_files(path, "balances_monthly")}
    for month in months:
        journal, postings = _month_frame(path, "journal", month), _month_frame(path, "postings", month)
        try:
            _check_shapes(journal, postings, book)
        except InvariantError as e:
            bad["shapes"].append(f"{month}: {e.detail}")
        a = postings["account_id"].to_numpy()
        after = postings["balance_after_paise"].to_numpy()
        delta = postings["delta_paise"].to_numpy()
        order = np.argsort(a, kind="stable")
        a, after, delta = a[order], after[order], delta[order]
        before = np.empty_like(after)
        before[1:] = after[:-1]
        first = np.ones(a.size, dtype=bool)
        first[1:] = a[1:] != a[:-1]
        before[first] = last[a[first]]
        broken = after - delta != before
        if broken.any():
            bad["stock_flow"].append(f"{month}: account {int(a[np.argmax(broken)])}'s running balance does not follow "
                                     f"from its postings ({int(broken.sum())} postings)")
        negative = money[a] & (after < 0)
        if negative.any():
            bad["non_negative"].append(f"{month}: account {int(a[np.argmax(negative)])} went below zero")
        end = np.ones(a.size, dtype=bool)
        end[:-1] = a[1:] != a[:-1]
        last[a[end]] = after[end]
        if month not in closed:
            continue
        b = _month_frame(path, "balances_monthly", month)
        ids, balance = b["account_id"].to_numpy(), b["balance_paise"].to_numpy()
        differs = last[ids] != balance
        if differs.any():
            bad["stock_flow"].append(f"{month}: month-end balance of account {int(ids[np.argmax(differs)])} is not "
                                     f"opening plus postings ({int(differs.sum())} accounts)")
        stated = np.zeros(len(opening), dtype=np.int64)
        stated[ids] = balance
        present = np.zeros(len(opening), dtype=bool)
        present[ids] = True
        moved = bank_position(stated, present) != equity
        if moved.any():
            bad["bank_balance_sheets"].append(f"{month}: bank {int(banks[np.argmax(moved)])}'s reserves and vault cash "
                                              f"less deposits differ from its opening equity")
        cash = int(stated[present & (book.type == T.CASH)].sum())
        if cash != cash_issued:
            bad["cash_conservation"].append(f"{month}: cash held {cash} paise, currency issued {cash_issued}")
    ends = sorted(set(months) & closed)
    span = (f"{months[0]} to {months[-1]}; month ends {ends[0]} to {ends[-1]}" if ends else
            f"{months[0]} to {months[-1]}; no month end yet") if months else "no months"
    rows = [_row(name, not problems, "; ".join(problems[:3]) if problems else f"held in every month, {span}")
            for name, problems in bad.items()]
    rows.append(_row("flow_matrix", None, "needs each holder's sector, which no table records; the run checked the "
                                          "flow matrix every simulated day"))
    return rows


# Same seed, same output ---------------------------------------------------------------------------------------------

def _month_hash(path: Path, table: str, month: str) -> str | None:
    parts = [f for f in fact_files(path, table) if f.parent.name == f"month={month}"]
    if not parts:
        return None
    h = hashlib.sha256()
    _feed_month(h, parts)
    return h.hexdigest()


def determinism(run: "Run", release_secret: str | None = None) -> list[dict[str, Any]]:
    """Rebuild the run from its config and seed and run its first month: every fact table's first month and every
    dimension table that does not change during a run must hash the same."""
    from arthasim.config import Config
    from arthasim.world import World
    m = run.manifest

    def skip(reason: str) -> list[dict[str, Any]]:
        return [_row("first_month_facts", None, reason), _row("build_dimensions", None, reason)]

    if "config" not in m:
        return skip("the run was made before plan 1e and its manifest has no config to rebuild from")
    if m.get("forked_from"):
        how = m["forked_from"].get("how", "fork")
        return skip(f"the run continues a {how} of {m['forked_from'].get('run_id')}, so a rebuild is not the same run")
    if m.get("release_secret") and release_secret is None:
        return skip("the run was made with a release secret; pass release_secret to rebuild it")
    if m.get("days", 0) == 0:
        return skip("the run has no simulated day")
    config = Config(**m["config"], **({"release_secret": release_secret} if release_secret else {}))
    start = config.start
    first_end = start.replace(day=calendar.monthrange(start.year, start.month)[1])
    until = min(first_end, dt.date.fromisoformat(m["end"]))
    log = run.table("interventions_log").collect() if "interventions_log" in run.tables() else pl.DataFrame()
    if log.height and log.filter(pl.col("effective").is_null() | (pl.col("effective") <= until)).height:
        return skip("the run applied an intervention that takes effect in its first month")
    folder = Path(tempfile.mkdtemp(prefix="arthasim-rerun-"))
    try:
        rerun = World.build(config, seed=int(m["seed"]), path=folder / "rerun", checkpoints=False).run(until)
        month = f"{start:%Y-%m}"
        facts = [t for t in FACT_TABLES if _month_hash(Path(run.path), t, month) != _month_hash(Path(rerun.path), t, month)]
        def dim_hash(p: Path, t: str) -> str | None:
            return content_hash(p, t, fact=False) if (p / f"{t}.parquet").exists() else None
        compared = [t for t in DIM_TABLES if t not in ACCOUNT_TABLES
                    and ((Path(run.path) / f"{t}.parquet").exists() or (Path(rerun.path) / f"{t}.parquet").exists())]
        dims = [t for t in compared if dim_hash(Path(run.path), t) != dim_hash(Path(rerun.path), t)]
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    days = (until - start).days + 1
    return [
        _row("first_month_facts", not facts, f"differ: {', '.join(facts)}" if facts else
             f"all {len(FACT_TABLES)} fact tables equal over {start} to {until} ({days} days) after a rebuild"),
        _row("build_dimensions", not dims, f"differ: {', '.join(dims)}" if dims else
             f"{len(compared)} dimension tables equal (the account tables change as accounts open, so they are "
             "left out)"),
    ]


# Identifiers --------------------------------------------------------------------------------------------------------

def identifiers(run: "Run") -> list[dict[str, Any]]:
    """Every identifier against the real format it imitates (architecture section 5.3)."""
    path = Path(run.path)
    persons = pl.read_parquet(path / "persons.parquet")
    instruments = pl.read_parquet(path / "instruments.parquet") if (path / "instruments.parquet").exists() \
        else pl.DataFrame({"kind": [], "value": []}, schema={"kind": pl.String, "value": pl.String})
    customers = pl.read_parquet(path / "bank_customers.parquet") if (path / "bank_customers.parquet").exists() \
        else pl.DataFrame({"customer_no": []}, schema={"customer_no": pl.String})

    def values(frame: pl.DataFrame, column: str, kind: str | None = None) -> list[str] | None:
        if column not in frame.columns:
            return None
        if kind is not None:
            frame = frame.filter(pl.col("kind") == kind)
        return frame[column].drop_nulls().to_list()

    def check(name: str, groups: list[tuple[str, list[str] | None]], real) -> dict[str, Any]:
        seen = [(label, v) for label, vs in groups if vs is not None for v in vs]
        if not seen:
            return _row(name, None, "no such identifiers in this run")
        hits = [(label, v) for label, v in seen if real(v)]
        if hits:
            return _row(name, False, f"{len(hits)} of {len(seen)} in a real format, for example {hits[0][1]!r} "
                                     f"({hits[0][0]})")
        return _row(name, True, f"none of {len(seen)} ({', '.join(l for l, vs in groups if vs)}) in a real format")

    fmt = REAL_FORMATS
    return [
        check("pan", [("persons.pan_like", values(persons, "pan_like"))], lambda v: bool(fmt["pan"].match(v))),
        check("aadhaar", [("persons.uid_token", values(persons, "uid_token"))], lambda v: bool(fmt["aadhaar"].match(v))),
        check("mobile", [("persons.mobile_token", values(persons, "mobile_token")),
                         ("instruments MOBILE", values(instruments, "value", "MOBILE"))],
              lambda v: bool(fmt["mobile"].match(v))),
        check("ifsc", [("instruments BRANCH", values(instruments, "value", "BRANCH"))],
              lambda v: bool(fmt["ifsc"].match(v))),
        check("account_no", [("instruments ACCOUNT_NO", values(instruments, "value", "ACCOUNT_NO")),
                             ("bank_customers.customer_no", values(customers, "customer_no"))],
              lambda v: bool(fmt["account_no"].match(v))),
        check("card", [("instruments DEBIT_CARD", values(instruments, "value", "DEBIT_CARD"))],
              lambda v: bool(fmt["card"].match(v)) and luhn(v)),
        check("vpa", [("instruments VPA", values(instruments, "value", "VPA"))],
              lambda v: not SYNTHETIC_VPA_HANDLE.match(v.rsplit("@", 1)[-1])),
    ]
