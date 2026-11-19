# arthasim Phase 0 (Spike) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A tier XS world (10,000 persons) that pays salaries and makes UPI and cash purchases for 90 simulated days, with every ledger invariant passing, identical output for an identical seed, and measured throughput.

**Architecture:** State is NumPy arrays. Behaviour modules turn keyed random draws into a day's payment intents. A Numba kernel settles them in slot order against live balances and writes postings. End-of-day jobs net interbank positions and check invariants. Output goes to month-partitioned Parquet.

**Tech Stack:** Python 3.11+, NumPy, Numba, Polars, PyArrow, DuckDB, Pydantic 2, PyYAML, pytest, Hypothesis.

**Spec:** `simulation_architecture_v2.md`, sections 5.3, 5.4, 6, 7, 13.3, 14.2, 15.1, 16 and 18. In the repo this plan lives at `docs/superpowers/plans/2026-11-15-arthasim-phase-0-spike.md`.

## Global Constraints

- Python 3.11 or later, plain `venv`, no conda. Package name `arthasim`, `src/` layout.
- Money is `int64` paise everywhere. No floats in balances or postings.
- One step per calendar day, 96 settlement slots of 15 minutes.
- Every random draw is a pure function of `(run_seed, stream, entity_id, day, index)`. `np.random.*` and `random.*` are banned under `src/`.
- `day` passed to the generator is `date.toordinal()`.
- Times are Asia/Kolkata. Default start date is 2025-04-01. Tier XS is 10,000 persons.
- Bank codes are `SYNB01`, `SYNB02`, and so on. The boundary bank is `SYNX00`.
- `pan_like` has a digit in position 3 and must never match `^[A-Z]{5}[0-9]{4}[A-Z]$`.
- Every number a module uses comes from `params/registry.yaml`.
- A failed invariant stops the run.
- No Spark, GPU or LLM dependencies.

## Scope

- **In:** spec invariants 1 to 5 and the row sums of invariant 6 (section 7.3); the public calls `Config`, `ParamRegistry`, `World.build`, `World.step`, `World.run`, `Run.open`, `Run.tables`, `Run.table`, `Run.sql`, `Run.manifest`.
- **Out, with reason:** column sums of invariant 6 need the full instrument set (phase 1). Invariant 7 needs fraud cases (phase 2). `payments` omits handle, MCC, narration, channel, device and location columns until phase 1.

## Review Focus

1. A run that crosses a month boundary writes both month partitions with no row lost or duplicated (Task 9).
2. A payment equal to the payer's balance succeeds and leaves zero. Zero and negative amounts are rejected before settlement (Task 6).
3. `world.step(10)` followed by `world.run(until)` gives the same tables as a single `world.run(until)` (Task 9).
4. An output directory that already holds the same run id raises `FileExistsError` and nothing is overwritten (Task 9).
5. Degenerate configs run and pass invariants: `banks=1` (no interbank settlement) and `employers=0` (no salaries) (Tasks 7 and 9).

## File Structure

| File | Responsibility |
| :--- | :--- |
| `pyproject.toml` | Package metadata, dependencies, pytest config |
| `src/arthasim/__init__.py` | Public names: `Config`, `ParamRegistry`, `World`, `Run`, `__version__ = "0.0.1"` |
| `src/arthasim/config.py` | `Config`, tier presets |
| `src/arthasim/params.py` | `ParamRegistry` |
| `src/arthasim/engine/rng.py` | Keyed random numbers |
| `src/arthasim/ledger/instruments.py` | `InstrumentType`, `InstrumentBook` |
| `src/arthasim/ledger/journal.py` | `Kind`, `FlowType`, `Journal`, `LedgerError` |
| `src/arthasim/ledger/invariants.py` | Invariant checks, `InvariantError` |
| `src/arthasim/engine/intents.py` | `Intents`, `Rail`, `Status` |
| `src/arthasim/engine/settlement.py` | `settle_day`, `Settled` |
| `src/arthasim/build/world.py` | `WorldState`, `build_state` |
| `src/arthasim/modules/income.py`, `consumption.py` | Intent generators |
| `src/arthasim/engine/scheduler.py` | Day loop, end-of-day settlement |
| `src/arthasim/store/parquet.py` | Partitioned writers, manifest, content hashes |
| `src/arthasim/world.py` | `World`, `Run` |
| `params/registry.yaml`, `configs/tier_xs.yaml` | Parameters and tier config |
| `scripts/bench.py`, `docs/phase0_results.md` | Gate run and its written result |

---

### Task 1: Project skeleton and Config

**Files:**
- Create: `pyproject.toml`, `src/arthasim/__init__.py`, `src/arthasim/config.py`, `configs/tier_xs.yaml`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `Config` (Pydantic model) with fields `tier: str`, `start: date`, `persons: int`, `employers: int`, `merchants: int`, `banks: int`, `slots_per_day: int`, `out_dir: str = "runs"`, `params_path: str = "params/registry.yaml"`, `param_overrides: dict[str, Any] = {}`; methods `Config.tier(name, **overrides)`, `Config.from_yaml(path)`, `to_yaml(path)`, `with_params(**overrides) -> Config`, `hash() -> str`.

- [ ] **Step 1: Write the failing test**

```python
import datetime as dt
import pytest
from arthasim import Config


def test_tier_xs_defaults():
    c = Config.tier("XS")
    assert (c.persons, c.employers, c.merchants, c.banks) == (10_000, 100, 300, 3)
    assert c.slots_per_day == 96 and c.start == dt.date(2025, 4, 1)


def test_overrides_yaml_and_hash(tmp_path):
    c = Config.tier("XS", persons=500, start="2025-04-28")
    assert c.persons == 500 and c.start == dt.date(2025, 4, 28)
    c.to_yaml(tmp_path / "c.yaml")
    assert Config.from_yaml(tmp_path / "c.yaml") == c
    assert c.hash() != Config.tier("XS").hash()
    d = c.with_params(**{"spike.purchases_per_day": 2.0})
    assert d.param_overrides == {"spike.purchases_per_day": 2.0} and d.hash() != c.hash()


def test_rejects_bad_input():
    for bad in ({"persons": 0}, {"banks": 0}, {"slots_per_day": 24}, {"employers": -1}):
        with pytest.raises(ValueError):
            Config.tier("XS", **bad)
    with pytest.raises(ValueError):
        Config.tier("XXL")
```

- [ ] **Step 2: Run** `pytest tests/test_config.py -v`. Expected: FAIL, `arthasim` not importable.
- [ ] **Step 3: Implement.** `pyproject.toml` declares `requires-python = ">=3.11"`, runtime deps `numpy`, `numba`, `polars`, `pyarrow`, `duckdb`, `pydantic>=2`, `pyyaml`, and a `dev` extra with `pytest`, `hypothesis`. `slots_per_day` must equal 96. `employers` may be 0; `persons`, `merchants`, `banks` must be at least 1. `hash()` is the SHA-256 of the model's JSON with sorted keys. Only tier `XS` exists in this plan.
- [ ] **Step 4: Run** `pytest tests/test_config.py -v`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "feat: project skeleton and Config"`.

### Task 2: Parameter registry

**Files:**
- Create: `src/arthasim/params.py`, `params/registry.yaml`
- Test: `tests/test_params.py`

**Interfaces:**
- Produces: `ParamRegistry.load(path, overrides=None)`, `.get(param_id)`, `.table() -> pl.DataFrame` with columns `id, value, unit, as_of, source, status, role` (`value` is JSON text), `.override(param_id, value) -> ParamRegistry`, `.version() -> str`.

Registry entries for this plan (all `role: input`):

| id | value | status |
| :--- | :--- | :--- |
| `spike.salaried_share` | 0.6 | assumption |
| `spike.salary.median_paise` | 2500000 | assumption |
| `spike.salary.sigma` | 0.6 | assumption |
| `spike.purchases_per_day` | 1.2 | assumption |
| `spike.purchase.median_paise` | 20000 | assumption |
| `spike.purchase.sigma` | 0.9 | assumption |
| `spike.digital_share` | 0.6 | assumption |
| `spike.cash_withdrawal_paise` | 200000 | assumption |
| `spike.opening_balance.median_paise` | 1000000 | assumption |
| `spike.opening_balance.sigma` | 1.0 | assumption |
| `spike.opening_cash_paise` | 100000 | assumption |
| `spike.employer_revenue_multiple` | 1.3 | assumption |
| `spike.bank_shares` | [0.5, 0.3, 0.2] | assumption |
| `spike.bank_equity_paise` | 1000000000 | assumption |
| `spike.vault_cash_per_customer_paise` | 5000000 | assumption |
| `rail.upi.limit_paise` | 10000000 | unverified |
| `rail.upi.tech_decline_rate` | 0.01 | assumption |

- [ ] **Step 1: Write the failing test**

```python
import pathlib
import polars as pl
import pytest
from arthasim import ParamRegistry

PATH = pathlib.Path(__file__).parents[1] / "params" / "registry.yaml"


def test_load_get_table():
    r = ParamRegistry.load(PATH)
    assert r.get("spike.purchases_per_day") == 1.2
    assert r.get("spike.bank_shares") == [0.5, 0.3, 0.2]
    t = r.table()
    assert t.columns == ["id", "value", "unit", "as_of", "source", "status", "role"]
    assert t.schema["value"] == pl.String and t.height == 17
    assert set(t["status"]) <= {"verified", "unverified", "assumption"}
    assert set(t["role"]) <= {"input", "target", "holdout"}


def test_override_and_version():
    r = ParamRegistry.load(PATH)
    s = r.override("spike.purchases_per_day", 2.0)
    assert s.get("spike.purchases_per_day") == 2.0 and r.get("spike.purchases_per_day") == 1.2
    assert s.version() != r.version() == ParamRegistry.load(PATH).version()
    assert ParamRegistry.load(PATH, overrides={"spike.purchases_per_day": 2.0}).version() == s.version()


def test_errors(tmp_path):
    r = ParamRegistry.load(PATH)
    with pytest.raises(KeyError):
        r.get("nope")
    with pytest.raises(KeyError):
        r.override("nope", 1)
    bad = tmp_path / "bad.yaml"
    bad.write_text("- {id: a, value: 1, status: guess, role: input}\n")
    with pytest.raises(ValueError):
        ParamRegistry.load(bad)
    bad.write_text("- {id: a, value: 1, status: assumption, role: input}\n" * 2)
    with pytest.raises(ValueError):
        ParamRegistry.load(bad)
```

- [ ] **Step 2: Run** `pytest tests/test_params.py -v`. Expected: FAIL, `ParamRegistry` not defined.
- [ ] **Step 3: Implement.** `unit`, `as_of` and `source` default to empty strings. `version()` is the SHA-256 of the sorted `(id, JSON value)` pairs.
- [ ] **Step 4: Run** `pytest tests/test_params.py -v`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "feat: parameter registry"`.

### Task 3: Keyed random numbers

**Files:**
- Create: `src/arthasim/engine/rng.py`
- Test: `tests/test_rng.py`

**Interfaces:**
- Produces: `stream_id(name: str) -> int`; `uniform(seed, stream, entity, day, index=0) -> float64[n]` in `[0, 1)`; `normal(seed, stream, entity, day, index=0) -> float64[n]`; `lognormal(seed, stream, entity, day, median, sigma, index=0) -> float64[n]`; `poisson(seed, stream, entity, day, lam, index=0) -> int64[n]`. `entity` is an `int64` array; the result is aligned with it.

- [ ] **Step 1: Write the failing test**

```python
import numpy as np
from arthasim.engine import rng

S = rng.stream_id("test")
E = np.arange(1_000_000, dtype=np.int64)


def test_deterministic_and_order_free():
    a = rng.uniform(7, S, E, 100)
    assert np.array_equal(a, rng.uniform(7, S, E, 100))
    perm = np.random.default_rng(0).permutation(E)
    assert np.array_equal(rng.uniform(7, S, perm, 100), a[perm])
    assert np.array_equal(rng.uniform(7, S, E[:10], 100), a[:10])


def test_range_and_moments():
    u = rng.uniform(7, S, E, 100)
    assert u.min() >= 0.0 and u.max() < 1.0
    assert abs(u.mean() - 0.5) < 0.002 and abs(u.var() - 1 / 12) < 0.001
    counts = np.bincount((u * 100).astype(int), minlength=100)
    assert ((counts - 10_000) ** 2 / 10_000).sum() < 160


def test_keys_are_independent():
    base = rng.uniform(7, S, E, 100)
    others = (rng.uniform(8, S, E, 100), rng.uniform(7, rng.stream_id("other"), E, 100),
              rng.uniform(7, S, E, 101), rng.uniform(7, S, E, 100, index=1),
              rng.uniform(7, S, E + 1, 100))
    for other in others:
        assert abs(np.corrcoef(base, other)[0, 1]) < 0.005


def test_distributions():
    z = rng.normal(7, S, E, 100)
    assert abs(z.mean()) < 0.005 and abs(z.std() - 1.0) < 0.005
    k = rng.poisson(7, S, E, 100, lam=1.2)
    assert k.dtype == np.int64 and abs(k.mean() - 1.2) < 0.01 and abs(k.var() - 1.2) < 0.02
    x = rng.lognormal(7, S, E, 100, median=20_000, sigma=0.9)
    assert abs(np.median(x) / 20_000 - 1.0) < 0.01 and x.min() > 0
```

- [ ] **Step 2: Run** `pytest tests/test_rng.py -v`. Expected: FAIL, module not found.
- [ ] **Step 3: Implement.** The generator is a keyed hash, which the tests do not determine, so the core is given here. All arithmetic stays in `uint64`.

```python
_G = np.uint64(0x9E3779B97F4A7C15)
_M1 = np.uint64(0xBF58476D1CE4E5B9)
_M2 = np.uint64(0x94D049BB133111EB)


@njit(cache=True)
def _mix(x):
    x = (x ^ (x >> np.uint64(30))) * _M1
    x = (x ^ (x >> np.uint64(27))) * _M2
    return x ^ (x >> np.uint64(31))


@njit(cache=True)
def _key(seed, stream, entity, day, index):
    h = _mix(np.uint64(seed) + _G)
    h = _mix(h ^ np.uint64(stream))
    h = _mix(h ^ np.uint64(entity))
    h = _mix(h ^ np.uint64(day))
    return _mix(h ^ np.uint64(index))
```

`uniform` is `(_key(...) >> 11) * 2**-53` in a compiled loop over `entity`. `stream_id` is the first 8 bytes of SHA-256 of the name, little-endian, shifted right by one bit. `normal` is Box-Muller on two uniforms drawn at indices `2 * index + 1_000_003` and `2 * index + 1_000_004`. `lognormal` is `median * exp(sigma * normal)`. `poisson` inverts the CDF from one uniform. This core passed these exact tests in a prototype and produced 10 million draws in under 0.1 s.
- [ ] **Step 4: Run** `pytest tests/test_rng.py -v`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "feat: keyed random numbers"`.

### Task 4: Instruments and journal

**Files:**
- Create: `src/arthasim/ledger/instruments.py`, `src/arthasim/ledger/journal.py`
- Test: `tests/test_ledger.py`

**Interfaces:**
- Produces: `InstrumentType` (`DEPOSIT=1, CASH=2, RESERVE=3`); `InstrumentBook` with `add(type, holder, issuer, opening_paise) -> int`, `freeze()`, and after `freeze()` the `int64` arrays `type`, `holder`, `issuer`, `opening`, `balance`; `Kind` (`PAYMENT=1, CASH_PAYMENT=2, CASH_WITHDRAWAL=3, INTERBANK_SETTLEMENT=4`); `FlowType` (`WAGE=1, CONSUMPTION=2, TRANSFER=3, CASH_CONVERSION=4, SETTLEMENT=5`); `Journal(book)` with `post(ts, kind, flow_type, payment_id, lines) -> int` and `drain() -> tuple[pl.DataFrame, pl.DataFrame]`; `LedgerError`.
- `journal` columns: `journal_id, ts, kind, flow_type, payment_id`. `postings` columns: `journal_id, line_no, account_id, delta_paise, balance_after_paise`. All integer columns are `Int64`.

Shapes that `post` enforces:

| Kind | Lines |
| :--- | :--- |
| `PAYMENT` | 2 lines, both `DEPOSIT`, first negative, sum zero |
| `CASH_PAYMENT` | 2 lines, both `CASH`, first negative, sum zero |
| `CASH_WITHDRAWAL` | 3 lines: `DEPOSIT` −x; `CASH` +x with the same holder; `CASH` −x whose holder is the deposit's issuer |
| `INTERBANK_SETTLEMENT` | 2 or more lines, all `RESERVE`, sum zero |

- [ ] **Step 1: Write the failing test**

```python
import pytest
from arthasim.ledger.instruments import InstrumentBook, InstrumentType as T
from arthasim.ledger.journal import Journal, Kind, FlowType, LedgerError


def make():
    b = InstrumentBook()                      # entities: 1, 2 persons; 9 bank; 99 central bank
    a = b.add(T.DEPOSIT, holder=1, issuer=9, opening_paise=1000)
    c = b.add(T.DEPOSIT, holder=2, issuer=9, opening_paise=0)
    ca = b.add(T.CASH, holder=1, issuer=99, opening_paise=0)
    v = b.add(T.CASH, holder=9, issuer=99, opening_paise=5000)
    b.freeze()
    return b, Journal(b), a, c, ca, v


def test_payment_posts_and_records():
    b, j, a, c, _, _ = make()
    jid = j.post(0, Kind.PAYMENT, FlowType.CONSUMPTION, 11, [(a, -400), (c, 400)])
    assert (b.balance[a], b.balance[c]) == (600, 400)
    jr, po = j.drain()
    assert jr.columns == ["journal_id", "ts", "kind", "flow_type", "payment_id"]
    assert po.columns == ["journal_id", "line_no", "account_id", "delta_paise", "balance_after_paise"]
    assert po["balance_after_paise"].to_list() == [600, 400] and jr["journal_id"].to_list() == [jid]
    assert j.drain()[0].height == 0


def test_exact_balance_ok_overdraw_rejected_atomically():
    b, j, a, c, _, _ = make()
    j.post(0, Kind.PAYMENT, FlowType.CONSUMPTION, 1, [(a, -1000), (c, 1000)])
    assert b.balance[a] == 0
    with pytest.raises(LedgerError):
        j.post(0, Kind.PAYMENT, FlowType.CONSUMPTION, 2, [(a, -1), (c, 1)])
    assert (b.balance[a], b.balance[c]) == (0, 1000)


def test_shapes():
    b, j, a, c, ca, v = make()
    j.post(0, Kind.CASH_WITHDRAWAL, FlowType.CASH_CONVERSION, 3, [(a, -300), (ca, 300), (v, -300)])
    assert (b.balance[a], b.balance[ca], b.balance[v]) == (700, 300, 4700)
    for kind, lines in [(Kind.PAYMENT, [(a, -5), (c, 4)]), (Kind.PAYMENT, [(a, 5), (c, -5)]),
                        (Kind.PAYMENT, [(a, -5), (ca, 5)]), (Kind.CASH_PAYMENT, [(a, -5), (c, 5)]),
                        (Kind.CASH_WITHDRAWAL, [(c, -5), (ca, 5), (v, -5)])]:
        with pytest.raises(LedgerError):
            j.post(0, kind, FlowType.TRANSFER, 4, lines)
```

- [ ] **Step 2: Run** `pytest tests/test_ledger.py -v`. Expected: FAIL, modules not found.
- [ ] **Step 3: Implement.** `post` validates first and mutates only if every check passes. `journal_id` starts at 0 and increments by one. This Python `Journal` is the reference; the compiled kernel in Task 6 must agree with it.
- [ ] **Step 4: Run** `pytest tests/test_ledger.py -v`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "feat: instruments and journal"`.

### Task 5: Invariants

**Files:**
- Create: `src/arthasim/ledger/invariants.py`
- Test: `tests/test_invariants.py`

**Interfaces:**
- Consumes: `InstrumentBook`, journal and postings frames from Task 4.
- Produces: `InvariantError(name, detail)` with attribute `name`; `check_day(book, journal, postings, posted_total, bank_entities, equity, currency_issued, sector_of) -> None`; `flow_matrix(journal, postings, book, sector_of) -> pl.DataFrame` with columns `flow_type, sector, net_paise`.
- `posted_total` is an `int64` array, one entry per account, holding the sum of all postings since the build. `equity` maps bank entity id to paise.

| `name` | Rule |
| :--- | :--- |
| `shapes` | Every journal entry matches its kind's shape (Task 4 table) |
| `stock_flow` | `opening + posted_total == balance` for every account |
| `non_negative` | No `DEPOSIT` or `CASH` balance below zero |
| `bank_balance_sheet` | For each bank: reserves held + cash held == deposits issued + equity |
| `cash_conservation` | Sum of all `CASH` balances == `currency_issued` |
| `flow_rows` | Each `flow_type` row of `flow_matrix` sums to zero |

- [ ] **Step 1: Write the failing test**

```python
import numpy as np
import pytest
from hypothesis import given, settings, strategies as st
from arthasim.ledger.instruments import InstrumentBook, InstrumentType as T
from arthasim.ledger.journal import Journal, Kind, FlowType, LedgerError
from arthasim.ledger.invariants import InvariantError, check_day, flow_matrix

BANK, CB = 9, 99
SECTOR = np.zeros(100, dtype=np.int8); SECTOR[:5] = 1; SECTOR[BANK] = 3; SECTOR[CB] = 4


def world(payments):
    b = InstrumentBook()
    dep = [b.add(T.DEPOSIT, holder=i, issuer=BANK, opening_paise=1000) for i in range(5)]
    b.add(T.CASH, holder=BANK, issuer=CB, opening_paise=2000)
    b.add(T.RESERVE, holder=BANK, issuer=CB, opening_paise=4000)
    b.freeze()
    j = Journal(b)
    for p, q, amt in payments:
        try:
            j.post(0, Kind.PAYMENT, FlowType.CONSUMPTION, 0, [(dep[p], -amt), (dep[q], amt)])
        except LedgerError:
            pass
    jr, po = j.drain()
    total = np.zeros(len(b.balance), dtype=np.int64)
    np.add.at(total, po["account_id"].to_numpy(), po["delta_paise"].to_numpy())
    return b, jr, po, total


def check(b, jr, po, total):
    check_day(b, jr, po, total, bank_entities=[BANK], equity={BANK: 1000},
              currency_issued=2000, sector_of=SECTOR)


pay = st.tuples(st.integers(0, 4), st.integers(0, 4), st.integers(1, 1500)).filter(lambda t: t[0] != t[1])


@settings(max_examples=200, deadline=None)
@given(st.lists(pay, max_size=40))
def test_valid_histories_pass(payments):
    b, jr, po, total = world(payments)
    check(b, jr, po, total)
    fm = flow_matrix(jr, po, b, SECTOR)
    assert fm.columns == ["flow_type", "sector", "net_paise"] and fm["net_paise"].sum() == 0


@pytest.mark.parametrize("acct,delta,name", [(0, 7, "stock_flow"), (5, 7, "stock_flow")])
def test_tampering_is_caught(acct, delta, name):
    b, jr, po, total = world([(0, 1, 100)])
    b.balance[acct] += delta
    with pytest.raises(InvariantError) as e:
        check(b, jr, po, total)
    assert e.value.name == name


def test_each_rule_fires():
    b, jr, po, total = world([(0, 1, 100)])
    with pytest.raises(InvariantError) as e:
        check_day(b, jr, po, total, [BANK], {BANK: 999}, 2000, SECTOR)
    assert e.value.name == "bank_balance_sheet"
    with pytest.raises(InvariantError) as e:
        check_day(b, jr, po, total, [BANK], {BANK: 1000}, 2001, SECTOR)
    assert e.value.name == "cash_conservation"
    b.balance[0] -= 5000; total[0] -= 5000
    with pytest.raises(InvariantError) as e:
        check(b, jr, po, total)
    assert e.value.name == "non_negative"
```

- [ ] **Step 2: Run** `pytest tests/test_invariants.py -v`. Expected: FAIL, module not found.
- [ ] **Step 3: Implement.** `check_day` runs the rules in the table's order and raises on the first failure. A posting's sector is the sector of the account's holder.
- [ ] **Step 4: Run** `pytest tests/test_invariants.py -v`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "feat: ledger invariants"`.

### Task 6: Intents and the settlement kernel

**Files:**
- Create: `src/arthasim/engine/intents.py`, `src/arthasim/engine/settlement.py`
- Test: `tests/test_settlement.py`

**Interfaces:**
- Produces: `Rail` (`CASH=1, UPI_P2M=2, NACH_CR=3, ATM=4, NEFT=5`); `Status` (`SUCCESS=1, DECLINED_TECH=2, DECLINED_FUNDS=3, DECLINED_LIMIT=4`).
- Produces: `Intents`, a dataclass of equal-length arrays `kind, flow_type, payer_acct, payee_acct, amount, rail, slot, offset_s`, with `Intents.concat(parts) -> Intents`, `sorted() -> Intents` (stable sort by `slot`, then `offset_s`) and `validate()` (raises `ValueError` on `amount <= 0`, `slot` outside 0 to 95, or `offset_s` outside 0 to 899).
- Produces: `settle_day(balance, acct_type, deposit_for_cash, vault_for_deposit, intents, upi_limit, tech_u, tech_rate, withdrawal_paise, next_payment_id, next_journal_id) -> Settled`. It mutates `balance` in place.
- `Settled` holds three groups of arrays: `payments` (`payment_id, slot, offset_s, rail, status, amount, payer_acct, payee_acct, journal_id, kind, flow_type`), `journal` (`journal_id, payment_id, kind, flow_type, slot, offset_s`) and `postings` (`journal_id, line_no, account_id, delta, balance_after`). `journal_id` is −1 on a declined payment.

Rules, applied to each intent in sorted order:

1. `UPI_P2M` with `amount > upi_limit` gives `DECLINED_LIMIT`.
2. `UPI_P2M` with `tech_u[i] < tech_rate` gives `DECLINED_TECH`.
3. `CASH_PAYMENT` with too little cash first attempts a withdrawal of `withdrawal_paise` from `deposit_for_cash[payer_acct]`. If the deposit and the bank's vault both cover it, the withdrawal is recorded as its own payment (rail `ATM`, kind `CASH_WITHDRAWAL`, flow `CASH_CONVERSION`, same slot and offset) immediately before the purchase.
4. A payer balance below `amount` gives `DECLINED_FUNDS`.
5. Otherwise post the lines for the kind and mark `SUCCESS`.

- [ ] **Step 1: Write the failing test**

```python
import numpy as np
import pytest
from hypothesis import given, settings, strategies as st
from arthasim.engine.intents import Intents, Rail, Status
from arthasim.engine.settlement import settle_day
from arthasim.ledger.journal import Kind, FlowType

# accounts: 0,1,2 deposits of persons A,B,C; 3 cash of A; 4 vault cash; 5 cash of merchant
TYPE = np.array([1, 1, 1, 2, 2, 2], dtype=np.int64)
DEP_FOR_CASH = np.array([-1, -1, -1, 0, -1, -1], dtype=np.int64)
VAULT_FOR_DEP = np.array([4, 4, 4, -1, -1, -1], dtype=np.int64)


def run(balance, rows, limit=10_000_000, tech=None, rate=0.0, wd=2000):
    cols = list(zip(*rows))
    it = Intents(*[np.array(c, dtype=np.int64) for c in cols]).sorted()
    it.validate()
    tech_u = np.ones(len(rows)) if tech is None else np.array(tech, dtype=np.float64)
    bal = np.array(balance, dtype=np.int64)
    return bal, settle_day(bal, TYPE, DEP_FOR_CASH, VAULT_FOR_DEP, it, limit, tech_u, rate, wd, 0, 0)


def pay(payer, payee, amt, slot, rail=Rail.UPI_P2M, off=0):
    return (Kind.PAYMENT, FlowType.CONSUMPTION, payer, payee, amt, rail, slot, off)


def test_slot_order_decides_who_has_funds():
    bal, s = run([100, 0, 0, 0, 0, 0], [pay(1, 2, 50, slot=2), pay(0, 1, 80, slot=1)])
    assert s.payments["status"].tolist() == [Status.SUCCESS, Status.SUCCESS] and bal.tolist()[:3] == [20, 30, 50]
    bal, s = run([100, 0, 0, 0, 0, 0], [pay(1, 2, 50, slot=1), pay(0, 1, 80, slot=2)])
    assert s.payments["status"].tolist() == [Status.DECLINED_FUNDS, Status.SUCCESS]
    assert s.payments["journal_id"].tolist() == [-1, 0]


def test_exact_balance_limit_and_tech_decline():
    bal, s = run([100, 0, 0, 0, 0, 0], [pay(0, 1, 100, 1)])
    assert bal[0] == 0 and s.payments["status"][0] == Status.SUCCESS
    _, s = run([100, 0, 0, 0, 0, 0], [pay(0, 1, 60, 1)], limit=50)
    assert s.payments["status"][0] == Status.DECLINED_LIMIT
    _, s = run([100, 0, 0, 0, 0, 0], [pay(0, 1, 60, 1)], tech=[0.001], rate=0.01)
    assert s.payments["status"][0] == Status.DECLINED_TECH
    bal, s = run([100, 0, 0, 0, 0, 0], [pay(0, 1, 60, 1, rail=Rail.NACH_CR)], limit=50, tech=[0.001], rate=0.01)
    assert s.payments["status"][0] == Status.SUCCESS


def test_cash_purchase_triggers_withdrawal():
    cash = (Kind.CASH_PAYMENT, FlowType.CONSUMPTION, 3, 5, 500, Rail.CASH, 10, 0)
    bal, s = run([5000, 0, 0, 100, 9000, 0], [cash])
    assert s.payments["kind"].tolist() == [Kind.CASH_WITHDRAWAL, Kind.CASH_PAYMENT]
    assert s.payments["rail"].tolist() == [Rail.ATM, Rail.CASH]
    assert bal.tolist() == [3000, 0, 0, 1600, 7000, 500]
    bal, s = run([1000, 0, 0, 100, 9000, 0], [cash])
    assert s.payments["status"].tolist() == [Status.DECLINED_FUNDS] and bal.tolist() == [1000, 0, 0, 100, 9000, 0]
    bal, s = run([5000, 0, 0, 100, 1000, 0], [cash])          # vault too low: no withdrawal
    assert s.payments["status"].tolist() == [Status.DECLINED_FUNDS] and bal.tolist() == [5000, 0, 0, 100, 1000, 0]


def test_rejects_bad_intents():
    for row in (pay(0, 1, 0, 1), pay(0, 1, -5, 1), pay(0, 1, 5, 96), pay(0, 1, 5, 1, off=900)):
        with pytest.raises(ValueError):
            run([100, 0, 0, 0, 0, 0], [row])


@settings(max_examples=100, deadline=None)
@given(st.lists(st.tuples(st.integers(0, 2), st.integers(0, 2), st.integers(1, 300), st.integers(0, 95))
                .filter(lambda t: t[0] != t[1]), min_size=1, max_size=60))
def test_money_is_conserved_and_never_negative(rows):
    bal, s = run([500, 500, 500, 0, 0, 0], [pay(p, q, a, sl) for p, q, a, sl in rows])
    assert bal.sum() == 1500 and bal.min() >= 0
    assert s.postings["delta"].sum() == 0
    assert (np.diff(s.payments["slot"]) >= 0).all()
```

- [ ] **Step 2: Run** `pytest tests/test_settlement.py -v`. Expected: FAIL, modules not found.
- [ ] **Step 3: Implement.** `settle_day` is one `@njit` loop writing into pre-allocated output arrays sized `2 * n` payments and `5 * n` postings, trimmed on return. The three array groups are returned as dicts of NumPy arrays.
- [ ] **Step 4: Run** `pytest tests/test_settlement.py -v`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "feat: intents and settlement kernel"`.

### Task 7: Minimal world build

**Files:**
- Create: `src/arthasim/build/world.py`
- Test: `tests/test_build.py`

**Interfaces:**
- Consumes: `Config`, `ParamRegistry`, `rng`, `InstrumentBook`.
- Produces: `build_state(config, params, seed) -> WorldState`. Entity ids are contiguous in this order: persons, employers, merchants, banks (`SYNB01` onward), boundary bank `SYNX00`, central bank, boundary entity.
- `WorldState` fields: `book`; `kind` and `sector` per entity (`sector`: `HOUSEHOLD=1, FIRM=2, BANK=3, CENTRAL_BANK=4, BOUNDARY=5`); `person_ids`, `person_bank` (index into `bank_ids`), `person_deposit`, `person_cash`, `person_employer` (−1 if none), `person_salary`, `person_digital`, `pan_like`; `employer_ids`, `employer_deposit`, `employer_payday` (1 to 28), `employer_payroll`; `merchant_ids`, `merchant_deposit`, `merchant_cash`; `bank_ids`, `bank_codes`, `bank_reserve`, `bank_vault`, `equity`; `boundary_deposit`; `deposit_for_cash`, `vault_for_deposit`; `currency_issued`; `posted_total`.

Build rules: banks are assigned by `spike.bank_shares`, truncated and renormalised to `config.banks`. A person is salaried with probability `spike.salaried_share` when `employers > 0`. Salary and opening deposit are lognormal; opening cash is fixed. An employer opens with twice its monthly payroll. Each bank's vault opens with `spike.vault_cash_per_customer_paise` per customer. Its reserves open at deposits issued plus `spike.bank_equity_paise`, and its equity is `spike.bank_equity_paise` plus vault cash, so the balance sheet balances and reserves cannot go negative. Employers and merchants are assigned to banks by the same shares. The boundary entity holds a deposit at `SYNX00` equal to 24 times total monthly payroll times `spike.employer_revenue_multiple`. `pan_like` is `SY`, one digit, `P`, one letter, four digits, one letter.

- [ ] **Step 1: Write the failing test**

```python
import re
import numpy as np
import pathlib
from arthasim import Config, ParamRegistry
from arthasim.build.world import build_state
from arthasim.ledger.invariants import check_day
import polars as pl

P = ParamRegistry.load(pathlib.Path(__file__).parents[1] / "params" / "registry.yaml")
EMPTY_J = pl.DataFrame(schema={c: pl.Int64 for c in ["journal_id", "ts", "kind", "flow_type", "payment_id"]})
EMPTY_P = pl.DataFrame(schema={c: pl.Int64 for c in ["journal_id", "line_no", "account_id", "delta_paise", "balance_after_paise"]})


def invariants_hold(s):
    check_day(s.book, EMPTY_J, EMPTY_P, s.posted_total, list(s.bank_ids), s.equity, s.currency_issued, s.sector)


def test_counts_accounts_and_balance_sheets():
    s = build_state(Config.tier("XS"), P, seed=7)
    assert (len(s.person_ids), len(s.employer_ids), len(s.merchant_ids)) == (10_000, 100, 300)
    assert list(s.bank_codes) == ["SYNB01", "SYNB02", "SYNB03", "SYNX00"]
    assert (s.book.balance[s.person_deposit] > 0).all() and (s.book.balance[s.person_cash] == 100_000).all()
    assert abs((s.person_employer >= 0).mean() - 0.6) < 0.02
    assert abs(np.bincount(s.person_bank, minlength=3)[:3] / 10_000 - np.array([0.5, 0.3, 0.2])).max() < 0.02
    assert set(np.unique(s.employer_payday)) <= set(range(1, 29))
    invariants_hold(s)


def test_identifiers_cannot_be_real():
    s = build_state(Config.tier("XS"), P, seed=7)
    real_pan = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
    assert not any(real_pan.match(p) for p in s.pan_like)
    assert all(re.match(r"^SY[0-9]P[A-Z][0-9]{4}[A-Z]$", p) for p in s.pan_like)
    assert len(set(s.pan_like)) == len(s.pan_like)


def test_seed_determinism():
    a, b = (build_state(Config.tier("XS", persons=500), P, seed=7) for _ in range(2))
    c = build_state(Config.tier("XS", persons=500), P, seed=8)
    assert np.array_equal(a.book.balance, b.book.balance) and list(a.pan_like) == list(b.pan_like)
    assert not np.array_equal(a.book.balance, c.book.balance)


def test_degenerate_configs():
    s = build_state(Config.tier("XS", persons=200, banks=1), P, seed=7)
    assert list(s.bank_codes) == ["SYNB01", "SYNX00"]
    invariants_hold(s)
    s = build_state(Config.tier("XS", persons=200, employers=0), P, seed=7)
    assert (s.person_employer == -1).all() and len(s.employer_ids) == 0
    invariants_hold(s)
```

- [ ] **Step 2: Run** `pytest tests/test_build.py -v`. Expected: FAIL, module not found.
- [ ] **Step 3: Implement.** Every draw uses a named stream (`build.bank`, `build.salaried`, `build.employer`, `build.salary`, `build.opening`, `build.digital`, `build.payday`, `build.pan`) with `day = 0`. `pan_like` uniqueness comes from deriving the digits and letters from the person's index, not from random draws.
- [ ] **Step 4: Run** `pytest tests/test_build.py -v`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "feat: minimal world build"`.

### Task 8: Income and consumption modules

**Files:**
- Create: `src/arthasim/modules/income.py`, `src/arthasim/modules/consumption.py`
- Test: `tests/test_modules.py`

**Interfaces:**
- Consumes: `WorldState`, `ParamRegistry`, `rng`, `Intents`.
- Produces: `income.intents(state, params, seed, day: date) -> Intents` and `consumption.intents(state, params, seed, day: date, persons=None) -> Intents`. `persons` is an optional array of person indices; `None` means everyone.

Income rules: on day-of-month 1, the boundary deposit pays each employer `round(spike.employer_revenue_multiple * payroll)` by `NEFT`, flow `TRANSFER`, slot 32. An employer with zero payroll gets no top-up. On an employer's payday, each of its staff receives salary by `NACH_CR`, flow `WAGE`, in a keyed slot from 36 to 47.

Consumption rules: each person makes `poisson(spike.purchases_per_day)` purchases. Purchase `k` uses `index = k` on streams `cons.merchant`, `cons.amount`, `cons.slot`, `cons.offset`. The merchant is uniform over merchants. The amount is lognormal, rounded to paise, floor 100. Digital persons pay by `UPI_P2M` from deposit to the merchant's deposit; others pay `CASH` from cash to the merchant's cash. The slot is uniform from 28 to 87.

- [ ] **Step 1: Write the failing test**

```python
import datetime as dt
import pathlib
import numpy as np
from arthasim import Config, ParamRegistry
from arthasim.build.world import build_state
from arthasim.engine.intents import Rail
from arthasim.ledger.journal import Kind, FlowType
from arthasim.modules import income, consumption

P = ParamRegistry.load(pathlib.Path(__file__).parents[1] / "params" / "registry.yaml")
S = build_state(Config.tier("XS"), P, seed=7)
D = dt.date(2025, 4, 10)


def test_payroll_only_on_payday_and_matches_salaries():
    paid = np.zeros(len(S.person_ids), dtype=np.int64)
    for dom in range(1, 31):
        it = income.intents(S, P, 7, dt.date(2025, 4, dom))
        wage = it.flow_type == FlowType.WAGE
        assert ((it.slot[wage] >= 36) & (it.slot[wage] <= 47)).all() and (it.rail[wage] == Rail.NACH_CR).all()
        idx = np.searchsorted(S.person_deposit, it.payee_acct[wage])
        np.add.at(paid, idx, it.amount[wage])
        top = it.flow_type == FlowType.TRANSFER
        assert top.sum() == (len(S.employer_ids) if dom == 1 else 0)
    assert np.array_equal(paid, np.where(S.person_employer >= 0, S.person_salary, 0))


def test_consumption_volume_amounts_and_rails():
    it = consumption.intents(S, P, 7, D)
    it.validate()
    assert abs(len(it.amount) / 10_000 - 1.2) < 0.04
    assert it.amount.min() >= 100 and abs(np.median(it.amount) / 20_000 - 1.0) < 0.05
    digital_dep = set(S.person_deposit[S.person_digital].tolist())
    upi = it.rail == Rail.UPI_P2M
    assert set(it.payer_acct[upi].tolist()) <= digital_dep and (it.kind[upi] == Kind.PAYMENT).all()
    assert (it.kind[~upi] == Kind.CASH_PAYMENT).all() and (it.rail[~upi] == Rail.CASH).all()
    assert ((it.slot >= 28) & (it.slot <= 87)).all()


def test_subset_equals_slice_of_full_run():
    full = consumption.intents(S, P, 7, D)
    sub = consumption.intents(S, P, 7, D, persons=np.arange(100))
    payers = set(S.person_deposit[:100].tolist()) | set(S.person_cash[:100].tolist())
    mask = np.isin(full.payer_acct, list(payers))
    for f in ("kind", "payer_acct", "payee_acct", "amount", "rail", "slot", "offset_s"):
        assert np.array_equal(np.sort(getattr(full, f)[mask]), np.sort(getattr(sub, f)))
    again = consumption.intents(S, P, 7, D)
    assert np.array_equal(full.amount, again.amount)
```

- [ ] **Step 2: Run** `pytest tests/test_modules.py -v`. Expected: FAIL, modules not found.
- [ ] **Step 3: Implement.** Both functions are vectorised: draw the purchase count per person, then loop over `k` up to the maximum count and build rows for persons with `count > k`. `person_deposit` is ascending by construction, which the payroll test relies on.
- [ ] **Step 4: Run** `pytest tests/test_modules.py -v`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "feat: income and consumption modules"`.

### Task 9: Scheduler, store, World and Run

**Files:**
- Create: `src/arthasim/engine/scheduler.py`, `src/arthasim/store/parquet.py`, `src/arthasim/world.py`
- Modify: `src/arthasim/__init__.py` (export `World`, `Run`)
- Test: `tests/test_run.py`

**Interfaces:**
- Consumes: everything from Tasks 1 to 8.
- Produces: `World.build(config, seed) -> World`, `world.date`, `world.step(days=1) -> None`, `world.run(until) -> Run`; `Run.open(path)`, `run.path`, `run.manifest`, `run.tables() -> list[str]`, `run.table(name) -> pl.LazyFrame`, `run.sql(query) -> pl.DataFrame`.

Day loop: build intents from `income` and `consumption`, concatenate, sort, draw `tech_u` on stream `settle.tech`, call `settle_day`, then at end of day post one `INTERBANK_SETTLEMENT` entry whose lines are each bank's net deposit change from the day's `PAYMENT` postings (skipped when all are zero), update `posted_total`, run `check_day`, and buffer rows. `ts` is epoch microseconds for the day's midnight in Asia/Kolkata plus `slot * 900 + offset_s` seconds.

Store layout under `<out_dir>/<run_id>/`, where `run_id = f"{tier}-seed{seed}-{config.hash()[:8]}"`:

- `payments/month=YYYY-MM/part-N.parquet`, and the same for `journal` and `postings`. One part file per flush, read back in month then part order. A flush happens at each month end and at the end of every `step` or `run` call.
- `persons.parquet`, `orgs.parquet`, `banks.parquet`, `accounts.parquet`, written at build.
- `run_manifest.json` with `run_id, seed, config_hash, registry_version, code_version, tier, start, end, days, payments, wall_seconds, content_hash` (a dict of table name to SHA-256 over the table's Arrow IPC bytes, parts read in order).

`payments` columns: `payment_id, intent_ts, settle_ts, rail, status, amount_paise, payer_account_id, payee_account_id, payer_bank, payee_bank, journal_id, purpose`. `rail`, `status` and `purpose` are stored as their enum names. `journal_id` is null when declined. `accounts` columns follow spec section 13.3.

- [ ] **Step 1: Write the failing test**

```python
import polars as pl
import pytest
from arthasim import Config, World, Run


def cfg(tmp_path, **kw):
    base = dict(persons=500, employers=10, merchants=30, out_dir=str(tmp_path))
    base.update(kw)
    return Config.tier("XS", **base)


def test_three_day_run_tables_and_manifest(tmp_path):
    run = World.build(cfg(tmp_path), seed=7).run(until="2025-04-03")
    assert set(run.tables()) == {"payments", "journal", "postings", "persons", "orgs", "banks", "accounts"}
    pay = run.table("payments").collect()
    assert pay.columns == ["payment_id", "intent_ts", "settle_ts", "rail", "status", "amount_paise",
                           "payer_account_id", "payee_account_id", "payer_bank", "payee_bank",
                           "journal_id", "purpose"]
    ok = pay.filter(pl.col("status") == "SUCCESS")
    assert ok["journal_id"].null_count() == 0
    assert pay.filter(pl.col("status") != "SUCCESS")["journal_id"].null_count() == pay.height - ok.height
    assert pay["payment_id"].is_unique() and pay["settle_ts"].is_sorted()
    sums = run.sql("select journal_id, sum(delta_paise) s from postings group by 1 having sum(delta_paise) <> 0 "
                   "and journal_id not in (select journal_id from journal where kind = 3)")
    assert sums.height == 0
    m = run.manifest
    assert m["seed"] == 7 and m["days"] == 3 and m["payments"] == pay.height and m["end"] == "2025-04-03"
    assert Run.open(run.path).manifest == m


def test_same_seed_same_content_other_seed_differs(tmp_path):
    a = World.build(cfg(tmp_path / "a"), seed=7).run(until="2025-04-05").manifest["content_hash"]
    b = World.build(cfg(tmp_path / "b"), seed=7).run(until="2025-04-05").manifest["content_hash"]
    c = World.build(cfg(tmp_path / "c"), seed=8).run(until="2025-04-05").manifest["content_hash"]
    assert a == b and a["payments"] != c["payments"]


def test_split_run_equals_single_run_across_month_boundary(tmp_path):
    one = World.build(cfg(tmp_path / "one", start="2025-04-25"), seed=7).run(until="2025-05-05")
    w = World.build(cfg(tmp_path / "two", start="2025-04-25"), seed=7)
    w.step(4)
    two = w.run(until="2025-05-05")
    for t in ("payments", "journal", "postings"):
        assert one.table(t).collect().equals(two.table(t).collect())
    months = one.table("payments").select(pl.col("settle_ts").cast(pl.Datetime("us", "Asia/Kolkata"))
                                          .dt.strftime("%Y-%m").unique()).collect()
    assert sorted(months.to_series().to_list()) == ["2025-04", "2025-05"]
    assert one.manifest["days"] == 11


def test_existing_run_directory_is_not_overwritten(tmp_path):
    World.build(cfg(tmp_path), seed=7).run(until="2025-04-02")
    with pytest.raises(FileExistsError):
        World.build(cfg(tmp_path), seed=7)


@pytest.mark.parametrize("kw", [{"banks": 1}, {"employers": 0}])
def test_degenerate_configs_run(tmp_path, kw):
    run = World.build(cfg(tmp_path, **kw), seed=7).run(until="2025-04-04")
    assert run.manifest["days"] == 4 and run.table("payments").collect().height > 0
```

- [ ] **Step 2: Run** `pytest tests/test_run.py -v`. Expected: FAIL, `World` not importable.
- [ ] **Step 3: Implement.** `run(until)` is inclusive of `until` and writes the manifest when it returns. `run.sql` registers every table as a DuckDB view over its Parquet files. `World.build` creates the run directory and raises `FileExistsError` if it exists.
- [ ] **Step 4: Run** `pytest tests/ -v`. Expected: PASS for the whole suite.
- [ ] **Step 5: Commit** `git commit -am "feat: scheduler, store, World and Run"`.

### Task 10: Exit gate

**Files:**
- Create: `scripts/bench.py`, `docs/phase0_results.md`
- Test: `tests/test_gate.py`

**Interfaces:**
- Consumes: `World`, `Run`.
- Produces: `python scripts/bench.py --tier XS --days 90 --seed 7 --out runs`, which prints and returns a dict with `days, payments, wall_seconds, payments_per_second, peak_rss_mb, payments_per_person_day`.

- [ ] **Step 1: Write the failing test**

```python
import pytest
from arthasim import Config, World


@pytest.mark.slow
def test_phase0_gate(tmp_path):
    runs = [World.build(Config.tier("XS", out_dir=str(tmp_path / d)), seed=7).run(until="2025-06-29")
            for d in ("a", "b")]
    a, b = (r.manifest for r in runs)
    assert a["days"] == 90
    assert a["content_hash"] == b["content_hash"]
    assert 1.0 <= a["payments"] / (10_000 * 90) <= 1.6
```

- [ ] **Step 2: Run** `pytest tests/test_gate.py -v -m slow`. Expected: PASS if Tasks 1 to 9 are correct. An `InvariantError` here is a defect in an earlier task: fix it there, with a test that reproduces it.
- [ ] **Step 3: Implement `scripts/bench.py`** using `time.perf_counter` and `resource.getrusage`. Register the `slow` marker in `pyproject.toml`.
- [ ] **Step 4: Run** `python scripts/bench.py --tier XS --days 90 --seed 7 --out runs`. Expected: the six numbers print and no exception is raised.
- [ ] **Step 5: Write `docs/phase0_results.md`** with the six numbers, the share of payments by status, a pass or fail against each exit criterion in spec section 18, and the measured 90-day figure scaled linearly to 12 months at tiers XS, S and M beside the spec section 16 targets (5 minutes, 2 hours, 24 hours).
- [ ] **Step 6: Commit** `git commit -am "feat: phase 0 gate and results"`.

---

## What follows this plan

Phase 1 is five subsystems. Each gets its own plan, written after this gate passes, because the measured throughput decides how its modules are built.

| Plan | Covers | Depends on |
| :--- | :--- | :--- |
| 1a. World build | Synthetic population, households, social graph, organisations, 12 banks and 2 NBFCs, accounts, identifiers | Phase 0 |
| 1b. Behaviour | Life course with alignment, income for everyone, shocks, category consumption, rail choice, deposits, cash returning to banks; full instrument set and invariant 6 columns | 1a |
| 1c. Data products | Observer views, inspector, monthly state snapshots, statement lines, export | 1b |
| 1d. Scenarios and experiments | Macro paths, the eight phase 1 interventions, checkpoints, fork, `Experiment`, metrics | 1b |
| 1e. Calibration and validation | Pin appendix A to primary sources, `calibrate`, `validate`, acceptance checks, tier S gate | 1c, 1d |
