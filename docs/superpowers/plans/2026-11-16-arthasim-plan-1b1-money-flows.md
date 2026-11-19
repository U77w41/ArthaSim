# arthasim Plan 1b-1 (Money Flows) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On the plan 1a world, every earning group is paid, households budget and spend by category at merchants near them, payers choose a rail the merchant accepts, and cash returns to banks, for 90 simulated days at tier S with every invariant passing.

**Architecture:** Behaviour lives in modules with two hooks: `monthly` updates state at the start of each month, `intents` emits the day's payment intents. The scheduler runs the world's module list; the settlement kernel and ledger gain one journal kind (cash deposit), a purpose code on every payment, and the column half of the flow-matrix invariant.

**Tech Stack:** Python 3.11+, NumPy, Numba, Polars, PyArrow, DuckDB, Pydantic 2, PyYAML, pytest, Hypothesis.

**Spec:** `docs/simulation_architecture_v2.md`, sections 6, 7.2, 7.3, 8.3 to 8.5, 8.8 and 14.2. Repo path of this plan: `docs/superpowers/plans/2026-11-16-arthasim-plan-1b1-money-flows.md`.

## Global Constraints

- Everything in the earlier plans' Global Constraints still holds: integer paise, keyed randomness only, no `np.random` or `random` under `src/`, Asia/Kolkata, a failed invariant stops the run, category orders from `build/categories.py`.
- The whole existing suite stays green. Tier XS keeps the spike builder and the two spike modules.
- Every payment carries a `Purpose`. `UNSPECIFIED` is allowed only for intents built without one in tests.
- Modules read state and emit intents. Only the settlement kernel and end-of-day jobs change balances.
- Every new number is a registry parameter with status `assumption`.
- Stream names carry the module prefix: `income.`, `remit.`, `budget.`, `cons.`, `cash.`.

## Scope

- **In:** money flows on a population whose life stages do not change.
- **Out, with reason:**
  - Life-course transitions, alignment, hiring and layoffs, annual increments, account opening during a run, and `entity_state_monthly` are plan 1b-2. They need mutable person state, which is a subsystem of its own.
  - UPI Lite needs a wallet instrument and matters mainly for what each observer sees, so it comes with the views in plan 1c.
  - Card settlement through an acquirer (T+1 payable) comes with cards in phase 3. Here a debit-card payment moves deposits at once.
  - A government entity comes with DBT in plan 1d. Pensions are paid from the boundary.
  - Firms have no costs yet, so merchant deposits only grow.

## Review Focus

1. A purchase whose payer can use no digital rail at that merchant falls back to cash, and a banked payer short of cash withdraws first (Tasks 1 and 8).
2. A household with zero income spends its floor from savings and is not divided by zero (Task 7).
3. A month with 28, 30 or 31 days pays each non-salaried earner exactly the configured number of times (Task 5).
4. A world that starts mid-month runs the monthly hooks on its first day (Tasks 4 and 10).
5. A split run and a single run give the same content hash, now that hashing is by month (Task 10).

## File Structure

| File | Responsibility |
| :--- | :--- |
| `src/arthasim/engine/intents.py` (modify) | New rails, `Purpose`, `Intents.purpose`, frame adapters |
| `src/arthasim/ledger/journal.py`, `invariants.py` (modify) | `CASH_DEPOSIT`, new flow types, flow-matrix columns |
| `src/arthasim/engine/settlement.py` (modify) | Cash deposit, purpose passthrough, withdrawal rail |
| `src/arthasim/behaviour.py` | `BehaviourState` |
| `src/arthasim/build/pipeline.py`, `build/world.py` (modify) | Boundary cash, biller cash, withdrawal rail, behaviour state |
| `src/arthasim/modules/base.py`, `spike.py` | `BehaviourModule`; spike modules as classes |
| `src/arthasim/modules/income_flows.py` | `Income` |
| `src/arthasim/modules/remittances.py` | `Remittances` |
| `src/arthasim/modules/budget.py` | `household_budget`, `Budget` |
| `src/arthasim/modules/spending.py` | `choose_rail`, `Consumption` |
| `src/arthasim/modules/cash.py` | `CashManagement` |
| `src/arthasim/engine/scheduler.py`, `world.py`, `store/parquet.py` (modify) | Module loop, monthly table, hashing by month |
| `tests/world_fixture.py` | Shared small world for tests |
| `docs/phase1b1_results.md` | Gate result |

---

### Task 1: Ledger vocabulary, cash deposits and purposes

**Files:**
- Modify: `src/arthasim/engine/intents.py`, `src/arthasim/ledger/journal.py`, `src/arthasim/ledger/invariants.py`, `src/arthasim/engine/settlement.py`, `src/arthasim/engine/scheduler.py`, `src/arthasim/modules/income.py`, `src/arthasim/modules/consumption.py`
- Test: `tests/test_ledger_1b.py`

**Interfaces:**
- `Kind.CASH_DEPOSIT = 5`. Shape: three lines. `CASH` −x; `DEPOSIT` +x with the same holder; `CASH` +x whose holder is the deposit's issuer.
- `FlowType`: `EARNINGS = 6, PENSION = 7, REMITTANCE = 8`.
- `Rail`: `UPI_P2P = 6, DEBIT_CARD = 7, IMPS = 8, AEPS = 9, BRANCH = 10`.
- `Purpose` (in `engine/intents.py`): `UNSPECIFIED = 0, SALARY = 1, EARNINGS = 2, PENSION = 3, EMPLOYER_REVENUE = 4, REMITTANCE = 5, GROCERY = 10, FOOD = 11, FUEL = 12, PHARMACY = 13, APPAREL = 14, ELECTRONICS = 15, TRANSPORT = 16, SERVICES = 17, OTHER = 18, UTILITIES = 19, TELECOM = 20, MEDICAL = 21, CASH_WITHDRAWAL = 30, CASH_DEPOSIT = 31`. Merchant category `k` maps to purpose `10 + k`.
- `Intents` gains a ninth field `purpose`, optional, filled with zeros when omitted.
- `settle_day(..., withdraw_rail=None)`: an optional array indexed by cash account giving the rail of an automatic withdrawal, `ATM` when omitted. `Settled.payments` gains `purpose`. An automatic withdrawal has purpose `CASH_WITHDRAWAL`.
- Kernel rules: the UPI limit and technical decline apply to `UPI_P2M` and `UPI_P2P`. A `CASH_DEPOSIT` intent has the cash account as payer and the deposit as payee; it declines for funds when cash is short.
- The `payments.purpose` column now holds the `Purpose` name. The spike income module sets `SALARY` and `EMPLOYER_REVENUE`; the spike consumption module sets `OTHER`.

- [ ] **Step 1: Write the failing test**

```python
import numpy as np
import pytest
from arthasim.engine.intents import Intents, Purpose, Rail, Status
from arthasim.engine.settlement import settle_day
from arthasim.ledger.instruments import InstrumentBook, InstrumentType as T
from arthasim.ledger.journal import FlowType, Journal, Kind, LedgerError

# accounts: 0 deposit A, 1 deposit B, 2 cash A, 3 vault, 4 cash merchant, 5 deposit merchant
TYPE = np.array([1, 1, 2, 2, 2, 1], dtype=np.int64)
DEP_FOR_CASH = np.array([-1, -1, 0, -1, 5, -1], dtype=np.int64)
VAULT_FOR_DEP = np.array([3, 3, -1, -1, -1, 3], dtype=np.int64)


def row(kind, flow, payer, payee, amount, rail, purpose, slot=10):
    return (kind, flow, payer, payee, amount, rail, slot, 0, purpose)


def run(balance, rows, withdraw_rail=None, limit=10_000_000, tech=None, rate=0.0):
    it = Intents(*[np.array(col, dtype=np.int64) for col in zip(*rows)]).sorted()
    it.validate()
    bal = np.array(balance, dtype=np.int64)
    tech_u = np.ones(len(rows)) if tech is None else np.array(tech, dtype=np.float64)
    return bal, settle_day(bal, TYPE, DEP_FOR_CASH, VAULT_FOR_DEP, it, limit, tech_u, rate, 2000, 0, 0,
                           withdraw_rail=withdraw_rail)


def test_enums():
    assert (Kind.CASH_DEPOSIT, FlowType.EARNINGS, FlowType.PENSION, FlowType.REMITTANCE) == (5, 6, 7, 8)
    assert (Rail.UPI_P2P, Rail.DEBIT_CARD, Rail.IMPS, Rail.AEPS, Rail.BRANCH) == (6, 7, 8, 9, 10)
    assert (Purpose.UNSPECIFIED, Purpose.GROCERY, Purpose.OTHER, Purpose.CASH_DEPOSIT) == (0, 10, 18, 31)
    assert Intents(*[np.array([1])] * 8).purpose.tolist() == [0]


def test_reference_journal_cash_deposit():
    b = InstrumentBook()
    dep = b.add(T.DEPOSIT, holder=1, issuer=9, opening_paise=0)
    cash = b.add(T.CASH, holder=1, issuer=99, opening_paise=800)
    vault = b.add(T.CASH, holder=9, issuer=99, opening_paise=100)
    other = b.add(T.CASH, holder=2, issuer=99, opening_paise=500)
    b.freeze()
    j = Journal(b)
    j.post(0, Kind.CASH_DEPOSIT, FlowType.CASH_CONVERSION, 1, [(cash, -300), (dep, 300), (vault, 300)])
    assert (b.balance[cash], b.balance[dep], b.balance[vault]) == (500, 300, 400)
    for lines in ([(cash, -300), (dep, 300), (vault, 200)], [(other, -300), (dep, 300), (vault, 300)],
                  [(cash, -900), (dep, 900), (vault, 900)], [(dep, -100), (cash, 100), (vault, 100)]):
        with pytest.raises(LedgerError):
            j.post(0, Kind.CASH_DEPOSIT, FlowType.CASH_CONVERSION, 2, lines)


def test_kernel_cash_deposit_and_purpose():
    deposit = row(Kind.CASH_DEPOSIT, FlowType.CASH_CONVERSION, 4, 5, 600, Rail.BRANCH, Purpose.CASH_DEPOSIT)
    bal, s = run([0, 0, 0, 1000, 700, 0], [deposit])
    assert bal.tolist() == [0, 0, 0, 1600, 100, 600] and s.payments["status"].tolist() == [Status.SUCCESS]
    assert s.payments["purpose"].tolist() == [Purpose.CASH_DEPOSIT]
    assert s.postings["delta"].tolist() == [-600, 600, 600]
    bal, s = run([0, 0, 0, 1000, 500, 0], [deposit])
    assert s.payments["status"].tolist() == [Status.DECLINED_FUNDS] and bal.tolist() == [0, 0, 0, 1000, 500, 0]


def test_upi_p2p_rules_card_and_withdrawal_rail():
    p2p = row(Kind.PAYMENT, FlowType.REMITTANCE, 0, 1, 60, Rail.UPI_P2P, Purpose.REMITTANCE)
    assert run([100, 0, 0, 0, 0, 0], [p2p], limit=50)[1].payments["status"][0] == Status.DECLINED_LIMIT
    assert run([100, 0, 0, 0, 0, 0], [p2p], tech=[0.001], rate=0.01)[1].payments["status"][0] == Status.DECLINED_TECH
    card = row(Kind.PAYMENT, FlowType.CONSUMPTION, 0, 5, 60, Rail.DEBIT_CARD, Purpose.GROCERY)
    assert run([100, 0, 0, 0, 0, 0], [card], limit=50, tech=[0.001], rate=0.01)[1].payments["status"][0] == Status.SUCCESS
    cash = row(Kind.CASH_PAYMENT, FlowType.CONSUMPTION, 2, 4, 500, Rail.CASH, Purpose.FOOD)
    rails = np.full(6, int(Rail.ATM), dtype=np.int64)
    rails[2] = Rail.AEPS
    s = run([5000, 0, 100, 9000, 0, 0], [cash], withdraw_rail=rails)[1]
    assert s.payments["rail"].tolist() == [Rail.AEPS, Rail.CASH]
    assert s.payments["purpose"].tolist() == [Purpose.CASH_WITHDRAWAL, Purpose.FOOD]
    assert run([5000, 0, 100, 9000, 0, 0], [cash])[1].payments["rail"].tolist() == [Rail.ATM, Rail.CASH]
```

- [ ] **Step 2: Run** `pytest tests/test_ledger_1b.py -v`. Expected: FAIL, `Purpose` cannot be imported.
- [ ] **Step 3: Implement.** Add the `CASH_DEPOSIT` shape to both `check_shape` and the vectorised `shapes` invariant. End-of-day interbank netting still uses `PAYMENT` postings only.
- [ ] **Step 4: Run** `pytest -q`. Expected: PASS for the whole suite.
- [ ] **Step 5: Commit** `git commit -am "feat: cash deposits, purposes and new rails"`.

### Task 2: Flow-matrix columns

**Files:**
- Modify: `src/arthasim/ledger/invariants.py`
- Test: `tests/test_flow_columns.py`

**Interfaces:**
- `sector_balance(postings, book, sector_of) -> int64 array` indexed by sector code: for each posting, `+delta` to the holder's sector and `−delta` to the issuer's sector. It is the day's change in each sector's net financial position.
- `check_flow_columns(journal, postings, book, sector_of) -> None`: for every sector, the column sum of `flow_matrix` must equal `sector_balance`. Raises `InvariantError("flow_columns", ...)`.
- `check_day` calls it last.

- [ ] **Step 1: Write the failing test**

```python
import numpy as np
import polars as pl
import pytest
from arthasim.ledger.instruments import InstrumentBook, InstrumentType as T
from arthasim.ledger.invariants import InvariantError, check_day, check_flow_columns, sector_balance
from arthasim.ledger.journal import FlowType, Journal, Kind

HOUSEHOLD, FIRM, BANK, CENTRAL = 1, 2, 3, 4
A, SHOP, BANK1, BANK2, CB = 0, 1, 7, 8, 9
SECTOR = np.zeros(10, dtype=np.int8)
SECTOR[[A, SHOP, BANK1, BANK2, CB]] = [HOUSEHOLD, FIRM, BANK, BANK, CENTRAL]


def world():
    b = InstrumentBook()
    acct = {"dep_a": b.add(T.DEPOSIT, A, BANK1, 5000), "cash_a": b.add(T.CASH, A, CB, 400),
            "dep_shop": b.add(T.DEPOSIT, SHOP, BANK2, 0), "cash_shop": b.add(T.CASH, SHOP, CB, 0),
            "vault1": b.add(T.CASH, BANK1, CB, 3000), "vault2": b.add(T.CASH, BANK2, CB, 3000),
            "res1": b.add(T.RESERVE, BANK1, CB, 3000), "res2": b.add(T.RESERVE, BANK2, CB, 1000)}
    b.freeze()
    return b, Journal(b), acct


def test_a_mixed_day_passes_and_balances_by_sector():
    b, j, a = world()
    j.post(0, Kind.PAYMENT, FlowType.CONSUMPTION, 1, [(a["dep_a"], -700), (a["dep_shop"], 700)])
    j.post(0, Kind.CASH_PAYMENT, FlowType.CONSUMPTION, 2, [(a["cash_a"], -300), (a["cash_shop"], 300)])
    j.post(0, Kind.CASH_WITHDRAWAL, FlowType.CASH_CONVERSION, 3, [(a["dep_a"], -1000), (a["cash_a"], 1000), (a["vault1"], -1000)])
    j.post(0, Kind.CASH_DEPOSIT, FlowType.CASH_CONVERSION, 4, [(a["cash_shop"], -200), (a["dep_shop"], 200), (a["vault2"], 200)])
    j.post(0, Kind.INTERBANK_SETTLEMENT, FlowType.SETTLEMENT, -1, [(a["res1"], -700), (a["res2"], 700)])
    jr, po = j.drain()
    total = np.zeros(len(b.balance), dtype=np.int64)
    np.add.at(total, po["account_id"].to_numpy(), po["delta_paise"].to_numpy())
    check_day(b, jr, po, total, bank_entities=[BANK1, BANK2], equity={BANK1: 1000, BANK2: 4000},
              currency_issued=6400, sector_of=SECTOR)
    net = sector_balance(po, b, SECTOR)
    assert (net[HOUSEHOLD], net[FIRM], net[BANK], net[CENTRAL]) == (-1000, 1000, 0, 0)


def test_columns_catch_wealth_with_no_flow_behind_it():
    b, _, a = world()
    journal = pl.DataFrame({"journal_id": [0], "ts": [0], "kind": [int(Kind.CASH_WITHDRAWAL)],
                            "flow_type": [int(FlowType.CASH_CONVERSION)], "payment_id": [0]})
    postings = pl.DataFrame({"journal_id": [0], "line_no": [0], "account_id": [a["cash_a"]],
                             "delta_paise": [500], "balance_after_paise": [900]})
    with pytest.raises(InvariantError) as e:
        check_flow_columns(journal, postings, b, SECTOR)
    assert e.value.name == "flow_columns"
    empty = journal.clear(), postings.clear()
    check_flow_columns(*empty, b, SECTOR)
```

- [ ] **Step 2: Run** `pytest tests/test_flow_columns.py -v`. Expected: FAIL, `check_flow_columns` cannot be imported.
- [ ] **Step 3: Implement** the two functions and the call in `check_day`.
- [ ] **Step 4: Run** `pytest -q`. Expected: PASS for the whole suite.
- [ ] **Step 5: Commit** `git commit -am "feat: flow-matrix column invariant"`.

### Task 3: Build extensions and behaviour state

**Files:**
- Create: `src/arthasim/behaviour.py`, `tests/world_fixture.py`
- Modify: `src/arthasim/build/world.py`, `src/arthasim/build/pipeline.py`, `params/registry.yaml`, `tests/test_config_s.py` (the row-count assertion becomes `>= 61`)
- Test: `tests/test_build_1b.py`

**Interfaces:**
- `BehaviourState`: per-household arrays `income, balance, budget, medical_due` (`int64`) and `buffer_months, stress` (`float64`); per-person `person_budget` (`int64`). All start at zero.
- `WorldState` gains `boundary_cash` (account id, −1 for spike), `biller_deposit`, `biller_cash`, `withdraw_rail` and `behaviour`. The last four are `None` for spike worlds.
- Population build rules: the boundary entity gets a cash account opening at `flows.boundary_cash_months` times the sum of all persons' monthly income; its deposit opens at that amount times `spike.employer_revenue_multiple`. Each biller gets a cash account at zero. `withdraw_rail` is `ATM` for the cash account of a person with a debit card and `AEPS` otherwise.

New registry entries, all `role: input`, `status: assumption`:

| id | value |
| :--- | :--- |
| `flows.boundary_cash_months` | 36 |
| `income.pay_events_per_month` | {self_employed: 26, gig: 4, farm: 1, casual: 22} |
| `income.cash_share` | {self_employed: 0.5, gig: 0.1, farm: 0.6, casual: 0.9} |
| `income.event_sigma` | 0.3 |
| `income.pension_day` | 1 |
| `transfer.remittance_share` | 0.20 |
| `consumption.buffer_target_months` | 3.0 |
| `consumption.spend_share` | 0.85 |
| `consumption.floor_per_adult_paise` | 250000 |
| `consumption.dependant_weight` | 0.5 |
| `consumption.adjust_min` | 0.6 |
| `consumption.adjust_max` | 1.15 |
| `consumption.category_shares.metro` | [0.28, 0.12, 0.06, 0.05, 0.07, 0.04, 0.09, 0.10, 0.08, 0.07, 0.04] |
| `consumption.category_shares.rural` | [0.38, 0.08, 0.06, 0.06, 0.07, 0.03, 0.08, 0.07, 0.08, 0.05, 0.04] |
| `consumption.purchases_per_month` | [12, 8, 3, 1.5, 0.7, 0.15, 10, 2, 3] |
| `consumption.ticket_sigma` | 0.6 |
| `consumption.local_share` | 0.7 |
| `consumption.online_share` | 0.25 |
| `rail.choice.upi_preference` | 0.85 |
| `rail.choice.card_preference` | 0.5 |
| `shock.medical_monthly_prob` | 0.01 |
| `shock.medical_median_paise` | 800000 |
| `shock.medical_sigma` | 1.0 |
| `shock.stress_bonus` | 0.3 |
| `cash.merchant_float_paise` | 500000 |
| `cash.person_deposit_threshold_paise` | 2000000 |
| `cash.person_keep_paise` | 500000 |
| `cash.person_deposit_daily_prob` | 0.2 |

The eleven category shares are the nine merchant categories, then utilities, then telecom.

- [ ] **Step 1: Write `tests/world_fixture.py` and the failing test**

```python
# tests/world_fixture.py
import functools
import tempfile
from arthasim import Config, World


@functools.lru_cache(maxsize=None)
def small_world(persons=5_000, seed=7):
    """A population world shared by tests that only read state or call module hooks."""
    out = tempfile.mkdtemp(prefix="arthasim-test-")
    return World.build(Config.tier("S", persons=persons, out_dir=out), seed=seed)
```

```python
# tests/test_build_1b.py
import numpy as np
from arthasim import Config, World
from arthasim.engine.intents import Rail
from arthasim.ledger.instruments import InstrumentType as T
from helpers import P
from world_fixture import small_world


def test_new_accounts_lookups_and_state():
    s = small_world().state
    b, book = s.population, s.book
    income = int(b.attributes.monthly_income_paise.sum())
    assert book.type[s.boundary_cash] == T.CASH and book.holder[s.boundary_cash] == s.boundary_id
    assert book.opening[s.boundary_cash] == 36 * income
    assert book.opening[s.boundary_deposit] == round(36 * income * P.get("spike.employer_revenue_multiple"))
    assert len(s.biller_cash) == 4 and len(s.biller_deposit) == 4 and (book.opening[s.biller_cash] == 0).all()
    assert s.currency_issued == int(book.opening[book.type == T.CASH].sum())
    card = b.banking.person_has_card
    assert (s.withdraw_rail[s.person_cash[card]] == Rail.ATM).all()
    assert (s.withdraw_rail[s.person_cash[~card]] == Rail.AEPS).all()
    households = len(b.households.adults)
    for name in ("income", "balance", "budget", "medical_due", "buffer_months", "stress"):
        assert getattr(s.behaviour, name).shape == (households,)
    assert s.behaviour.person_budget.shape == (5_000,) and P.table().height == 89


def test_spike_world_has_none_of_this(tmp_path):
    s = World.build(Config.tier("XS", persons=300, employers=5, merchants=20, out_dir=str(tmp_path)), seed=7).state
    assert s.behaviour is None and s.withdraw_rail is None and s.boundary_cash == -1 and s.biller_cash is None
```

- [ ] **Step 2: Run** `pytest tests/test_build_1b.py -v`. Expected: FAIL, `boundary_cash` missing.
- [ ] **Step 3: Implement.** The scheduler passes `state.withdraw_rail` to `settle_day`.
- [ ] **Step 4: Run** `pytest -q`. Expected: PASS for the whole suite.
- [ ] **Step 5: Commit** `git commit -am "feat: boundary cash, biller cash and behaviour state"`.

### Task 4: Module framework

**Files:**
- Create: `src/arthasim/modules/base.py`, `src/arthasim/modules/spike.py`
- Modify: `src/arthasim/engine/intents.py` (frame adapters), `src/arthasim/engine/scheduler.py`, `src/arthasim/world.py`
- Test: `tests/test_module_framework.py`

**Interfaces:**
- `BehaviourModule` with class attribute `name`, and methods `monthly(self, world, month: date) -> None` (default no-op) and `intents(self, world, day: date) -> Intents | pl.DataFrame` (default empty).
- `Intents.from_frame(df)` and `Intents.to_frame()`, with columns named after the fields.
- `SpikeIncome` (`name = "spike_income"`) and `SpikeConsumption` (`name = "spike_consumption"`) wrap the phase 0 functions.
- `World.modules`: a list the caller may change before running. Until Task 10 every world gets the two spike modules.
- `run_day(world, day)` replaces the old signature. It calls every module's `monthly`, in list order, on day 1 of a month and on the world's first simulated day, before any `intents`. "First simulated day" is per world, so `step` followed by `run` does not call it twice.
- `react` from the spec is not built in this plan; nothing here needs it.

- [ ] **Step 1: Write the failing test**

```python
import datetime as dt
import numpy as np
import polars as pl
from arthasim import Config, World
from arthasim.engine.intents import Intents, Purpose, Rail
from arthasim.ledger.journal import FlowType, Kind
from arthasim.modules.base import BehaviourModule


class Gift(BehaviourModule):
    name = "gift"

    def __init__(self, as_frame=False):
        self.months, self.as_frame = [], as_frame

    def monthly(self, world, month):
        self.months.append(month)

    def intents(self, world, day):
        s = world.state
        it = Intents(kind=[Kind.PAYMENT], flow_type=[FlowType.REMITTANCE], payer_acct=[s.boundary_deposit],
                     payee_acct=[s.person_deposit[s.person_deposit >= 0][0]], amount=[12_345],
                     rail=[Rail.NEFT], slot=[30], offset_s=[0], purpose=[Purpose.REMITTANCE])
        return it.to_frame() if self.as_frame else it


def cfg(tmp_path, **kw):
    base = dict(persons=1_000, out_dir=str(tmp_path))
    base.update(kw)
    return Config.tier("S", **base)


def gifts(run):
    return run.table("payments").filter((pl.col("purpose") == "REMITTANCE") & (pl.col("rail") == "NEFT")).collect()


def test_custom_module_and_monthly_hook(tmp_path):
    world = World.build(cfg(tmp_path, start="2025-04-29"), seed=7)
    gift = Gift()
    world.modules.append(gift)
    g = gifts(world.run(until="2025-05-02"))
    assert g.height == 4 and (g["status"] == "SUCCESS").all() and (g["amount_paise"] == 12_345).all()
    assert gift.months == [dt.date(2025, 4, 29), dt.date(2025, 5, 1)]


def test_frame_modules_and_adapters(tmp_path):
    world = World.build(cfg(tmp_path), seed=7)
    world.modules.append(Gift(as_frame=True))
    assert gifts(world.run(until="2025-04-02")).height == 2
    it = Intents(kind=[1, 2], flow_type=[2, 2], payer_acct=[5, 6], payee_acct=[7, 8], amount=[10, 20],
                 rail=[2, 1], slot=[3, 4], offset_s=[0, 9], purpose=[10, 11])
    frame = it.to_frame()
    assert frame.columns == ["kind", "flow_type", "payer_acct", "payee_acct", "amount", "rail", "slot",
                             "offset_s", "purpose"]
    assert np.array_equal(Intents.from_frame(frame).amount, it.amount)
    assert Intents.from_frame(frame.drop("purpose")).purpose.tolist() == [0, 0]


def test_default_modules_and_base_class(tmp_path):
    spike = World.build(Config.tier("XS", persons=300, employers=5, merchants=20, out_dir=str(tmp_path)), seed=7)
    assert [m.name for m in spike.modules] == ["spike_income", "spike_consumption"]
    base = BehaviourModule()
    assert base.monthly(spike, dt.date(2025, 4, 1)) is None and len(base.intents(spike, dt.date(2025, 4, 1))) == 0
```

- [ ] **Step 2: Run** `pytest tests/test_module_framework.py -v`. Expected: FAIL, `arthasim.modules.base` not found.
- [ ] **Step 3: Implement** as described under Interfaces.
- [ ] **Step 4: Run** `pytest -q`. Expected: PASS for the whole suite.
- [ ] **Step 5: Commit** `git commit -am "feat: behaviour module framework"`.

### Task 5: Income for every earning group

**Files:**
- Create: `src/arthasim/modules/income_flows.py`
- Test: `tests/test_income_flows.py`

**Interfaces:**
- `Income(BehaviourModule)`, `name = "income"`. Reads life stage and monthly income from `world.state.population`.

Rules:
- **Employer revenue.** On day 1 the boundary deposit pays each employer with payroll `round(spike.employer_revenue_multiple * payroll)` by `NEFT`, flow `TRANSFER`, purpose `EMPLOYER_REVENUE`, slot 32.
- **Salaries.** On the employer's payday each staff member is paid monthly income by `NACH_CR`, flow `WAGE`, purpose `SALARY`, keyed slot 36 to 47.
- **Pensions.** On `income.pension_day` each retired person gets monthly income, flow `PENSION`, purpose `PENSION`: by `NACH_CR` from the boundary deposit if banked, else in cash from the boundary cash account.
- **Other earners** (self-employed, gig, farm, casual). With `f = income.pay_events_per_month[stage]`, `D` the days in the month and a keyed phase `phi` in `[0, D)` (stream `income.phase`, `day = 0`), day `d` is a pay day when `floor((d + phi) * f / D) > floor((d - 1 + phi) * f / D)`. That gives exactly `f` pay days a month. Each pays `income / f * exp(sigma * z - sigma**2 / 2)`, at least 100 paise, flow `EARNINGS`, purpose `EARNINGS`. It is cash from the boundary cash account when the person is unbanked or a keyed draw falls below `income.cash_share[stage]`; otherwise it comes from the boundary deposit by `UPI_P2P` if the person has UPI, else `NEFT`. Keyed slot 40 to 79.

- [ ] **Step 1: Write the failing test**

```python
import datetime as dt
import numpy as np
from arthasim.build import categories as c
from arthasim.engine.intents import Intents, Purpose, Rail
from arthasim.ledger.journal import FlowType, Kind
from arthasim.modules.income_flows import Income
from world_fixture import small_world

W = small_world()
S, B = W.state, W.state.population
STAGE, INC = B.persons.life_stage, B.attributes.monthly_income_paise
BANKED = S.person_deposit >= 0
ACCT_PERSON = np.full(len(S.book), -1, dtype=np.int64)
ACCT_PERSON[S.person_cash] = S.person_ids
ACCT_PERSON[S.person_deposit[BANKED]] = S.person_ids[BANKED]


def month(year, mon, days):
    return Intents.concat([Income().intents(W, dt.date(year, mon, d)) for d in range(1, days + 1)])


IT = month(2025, 4, 30)
PAYEE = ACCT_PERSON[IT.payee_acct]
TO_PERSON = PAYEE >= 0
GOT = np.zeros(len(INC), dtype=np.int64)
np.add.at(GOT, PAYEE[TO_PERSON], IT.amount[TO_PERSON])


def test_salaries_and_pensions_are_exact():
    sal, ret = STAGE == c.SALARIED, STAGE == c.RETIRED
    assert np.array_equal(GOT[sal], INC[sal]) and np.array_equal(GOT[ret], INC[ret])
    pension = IT.purpose == Purpose.PENSION
    assert pension.sum() == ret.sum() and (IT.flow_type[pension] == FlowType.PENSION).all()
    assert (IT.flow_type[IT.purpose == Purpose.SALARY] == FlowType.WAGE).all()
    assert (GOT[np.isin(STAGE, [c.STUDYING, c.SEEKING, c.HOMEMAKER])] == 0).all()


def test_other_earners_are_paid_the_configured_number_of_times():
    events = {c.SELF_EMPLOYED: 26, c.GIG: 4, c.FARM: 1, c.CASUAL: 22}
    for year, mon, days in ((2025, 4, 30), (2025, 5, 31), (2026, 2, 28)):
        it = month(year, mon, days)
        earn = it.flow_type == FlowType.EARNINGS
        count = np.bincount(ACCT_PERSON[it.payee_acct[earn]], minlength=len(INC))
        for stage, f in events.items():
            assert (count[STAGE == stage] == f).all()
    for stage in events:
        g = STAGE == stage
        assert abs(GOT[g].sum() / INC[g].sum() - 1.0) < 0.10


def test_cash_and_digital_split():
    cash = IT.kind == Kind.CASH_PAYMENT
    assert (IT.payer_acct[cash] == S.boundary_cash).all() and (IT.rail[cash] == Rail.CASH).all()
    earn = (IT.flow_type == FlowType.EARNINGS) & TO_PERSON
    person = np.maximum(PAYEE, 0)
    assert cash[TO_PERSON & ~BANKED[person]].all()
    casual = earn & (STAGE[person] == c.CASUAL) & BANKED[person]
    assert abs(cash[casual].mean() - 0.9) < 0.03
    digital = earn & ~cash
    upi = B.banking.person_upi[PAYEE[digital]]
    assert (IT.payer_acct[digital] == S.boundary_deposit).all()
    assert (IT.rail[digital][upi] == Rail.UPI_P2P).all() and (IT.rail[digital][~upi] == Rail.NEFT).all()


def test_revenue_topups_validity_and_determinism():
    IT.validate()
    assert (IT.purpose == Purpose.EMPLOYER_REVENUE).sum() == (S.employer_payroll > 0).sum()
    assert (IT.purpose != Purpose.UNSPECIFIED).all()
    assert np.array_equal(month(2025, 4, 30).amount, IT.amount)
```

- [ ] **Step 2: Run** `pytest tests/test_income_flows.py -v`. Expected: FAIL, module not found.
- [ ] **Step 3: Implement** as described under Rules. Streams: `income.slot`, `income.offset`, `income.phase`, `income.noise`, `income.cash`.
- [ ] **Step 4: Run** `pytest tests/test_income_flows.py -v`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "feat: income for every earning group"`.

### Task 6: Remittances

**Files:**
- Create: `src/arthasim/modules/remittances.py`
- Test: `tests/test_remittances.py`

**Interfaces:**
- `Remittances(BehaviourModule)`, `name = "remittances"`.

Rules: each remittance edge whose sender and receiver both have accounts produces one transfer a month, on a keyed day from 1 to 28 that is the same every month (stream `remit.day`, `day = 0`). The amount is `np.rint(transfer.remittance_share * sender's monthly income)`. Kind `PAYMENT`, flow `REMITTANCE`, purpose `REMITTANCE`, keyed slot 40 to 79. The rail is `UPI_P2P` when the sender has UPI and the amount is within `rail.upi.limit_paise`, else `IMPS`.

- [ ] **Step 1: Write the failing test**

```python
import datetime as dt
import numpy as np
import polars as pl
from arthasim.engine.intents import Intents, Purpose, Rail
from arthasim.ledger.journal import FlowType, Kind
from arthasim.modules.remittances import Remittances
from helpers import P
from world_fixture import small_world

W = small_world()
S, B = W.state, W.state.population
INC = B.attributes.monthly_income_paise
EDGES = B.edges.filter(pl.col("type") == 4)
SRC, DST = EDGES["src"].to_numpy(), EDGES["dst"].to_numpy()
OK = (S.person_deposit[SRC] >= 0) & (S.person_deposit[DST] >= 0)


def month(mon):
    days = [(d, Remittances().intents(W, dt.date(2025, mon, d))) for d in range(1, 31)]
    return Intents.concat([it for _, it in days]), np.concatenate([np.full(len(it), d) for d, it in days])


IT, DAY = month(4)


def test_one_transfer_per_eligible_edge():
    assert OK.sum() > 0 and len(IT) == OK.sum()
    assert (IT.kind == Kind.PAYMENT).all() and (IT.flow_type == FlowType.REMITTANCE).all()
    assert (IT.purpose == Purpose.REMITTANCE).all()
    pairs = set(zip(IT.payer_acct.tolist(), IT.payee_acct.tolist()))
    assert pairs == set(zip(S.person_deposit[SRC[OK]].tolist(), S.person_deposit[DST[OK]].tolist()))


def test_amounts_rails_and_stable_day():
    sent = dict(zip(IT.payer_acct.tolist(), IT.amount.tolist()))
    expected = np.rint(0.2 * INC[SRC[OK]]).astype(np.int64)
    assert [sent[a] for a in S.person_deposit[SRC[OK]].tolist()] == expected.tolist()
    sender = np.full(len(S.book), -1, dtype=np.int64)
    sender[S.person_deposit[SRC[OK]]] = SRC[OK]
    upi = B.banking.person_upi[sender[IT.payer_acct]] & (IT.amount <= P.get("rail.upi.limit_paise"))
    assert (IT.rail[upi] == Rail.UPI_P2P).all() and (IT.rail[~upi] == Rail.IMPS).all()
    assert DAY.min() >= 1 and DAY.max() <= 28
    may, may_day = month(5)
    assert dict(zip(IT.payer_acct.tolist(), DAY.tolist())) == dict(zip(may.payer_acct.tolist(), may_day.tolist()))
    IT.validate()
```

- [ ] **Step 2: Run** `pytest tests/test_remittances.py -v`. Expected: FAIL, module not found.
- [ ] **Step 3: Implement** as described under Rules.
- [ ] **Step 4: Run** `pytest tests/test_remittances.py -v`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "feat: remittances"`.

### Task 7: Household budget, stress and medical shocks

**Files:**
- Create: `src/arthasim/modules/budget.py`
- Test: `tests/test_budget.py`

**Interfaces:**
- `household_budget(income, balance, adults, dependants, params) -> (budget, buffer_months, stress)`:
  - `floor = floor_per_adult_paise * (adults + dependant_weight * dependants)`
  - `need = max(spend_share * income, floor)`
  - `buffer_months = balance / need`
  - `adjust = clip(adjust_min + (1 - adjust_min) * buffer_months / buffer_target_months, adjust_min, adjust_max)`
  - `budget = round(max(floor, spend_share * income * adjust))`
  - `stress = clip(1 - buffer_months / buffer_target_months, 0, 1)`
- `Budget(BehaviourModule)`, `name = "budget"`. Its `monthly` fills `world.state.behaviour`:
  - `income` is the sum of members' monthly income. `balance` is the sum of members' cash and primary deposit balances; second accounts are savings and are left out.
  - `budget`, `buffer_months` and `stress` come from `household_budget`. `person_budget` is `budget // adults` for each member.
  - A medical shock hits a household with probability `shock.medical_monthly_prob`, doubled if any member is 60 or older (stream `budget.medical`, keyed on household and `month.replace(day=1).toordinal()`, because the hook receives the first simulated day when a run starts mid-month). `medical_due` is then a lognormal cost of at least 100 paise (`budget.medical_cost`), else 0. A hit adds `shock.stress_bonus` to `stress`, capped at 1.

- [ ] **Step 1: Write the failing test**

```python
import datetime as dt
import numpy as np
from arthasim.modules.budget import Budget, household_budget
from helpers import P
from world_fixture import small_world


def test_budget_formula():
    income = np.array([3_000_000, 3_000_000, 0, 3_000_000])
    balance = np.array([9_000_000, 0, 1_000_000, 90_000_000])
    budget, buffer_months, stress = household_budget(income, balance, np.array([2, 2, 1, 2]),
                                                     np.array([0, 2, 0, 0]), P)
    assert budget.dtype == np.int64 and budget.tolist() == [2_730_000, 1_530_000, 250_000, 2_932_500]
    assert np.allclose(buffer_months, [9 / 2.55, 0.0, 4.0, 90 / 2.55])
    assert stress.tolist() == [0.0, 1.0, 0.0, 0.0]


def test_monthly_hook_fills_state():
    w = small_world()
    s, b = w.state, w.state.population
    hh, n = b.households.household_of_person, len(b.households.adults)
    Budget().monthly(w, dt.date(2025, 4, 1))
    beh = s.behaviour
    income = np.zeros(n, dtype=np.int64)
    np.add.at(income, hh, b.attributes.monthly_income_paise)
    balance = np.zeros(n, dtype=np.int64)
    np.add.at(balance, hh, s.book.balance[s.person_cash])
    banked = s.person_deposit >= 0
    np.add.at(balance, hh[banked], s.book.balance[s.person_deposit[banked]])
    assert np.array_equal(beh.income, income) and np.array_equal(beh.balance, balance)
    assert np.array_equal(beh.person_budget, beh.budget[hh] // b.households.adults[hh])
    assert (beh.budget > 0).all() and ((beh.stress >= 0) & (beh.stress <= 1)).all()
    assert np.isfinite(beh.buffer_months).all() and (beh.medical_due >= 0).all()


def test_medical_shocks_rate_stress_and_determinism():
    w = small_world()
    beh = w.state.behaviour
    rates = []
    for mon in range(4, 10):
        Budget().monthly(w, dt.date(2025, mon, 1))
        rates.append((beh.medical_due > 0).mean())
    assert 0.005 < np.mean(rates) < 0.03
    hit = beh.medical_due > 0
    assert hit.any() and (beh.stress[hit] >= 0.3 - 1e-9).all() and (beh.medical_due[hit] >= 100).all()
    snapshot = beh.medical_due.copy()
    Budget().monthly(w, dt.date(2025, 9, 1))
    assert np.array_equal(beh.medical_due, snapshot)
```

- [ ] **Step 2: Run** `pytest tests/test_budget.py -v`. Expected: FAIL, module not found.
- [ ] **Step 3: Implement** as described under Interfaces.
- [ ] **Step 4: Run** `pytest tests/test_budget.py -v`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "feat: household budget, stress and medical shocks"`.

### Task 8: Spending by category, merchant choice and rail choice

**Files:**
- Create: `src/arthasim/modules/spending.py`
- Test: `tests/test_spending.py`

**Interfaces:**
- `choose_rail(amount, payer_upi, payer_card, merchant_upi, merchant_card, u_upi, u_card, params) -> int64 array` of `Rail` values: `UPI_P2M` when the payer has UPI, the merchant accepts it, the amount is within `rail.upi.limit_paise` and `u_upi < rail.choice.upi_preference`; otherwise `DEBIT_CARD` when the payer has a card, the merchant accepts cards and `u_card < rail.choice.card_preference`; otherwise `CASH`.
- `Consumption(BehaviourModule)`, `name = "consumption"`, with `intents(world, day, persons=None)`. It reads `world.state.behaviour`, so `Budget.monthly` must have run.

Rules. All are flow `CONSUMPTION`, keyed slot 28 to 87. Digital rails pay from the payer's deposit to the payee's deposit as kind `PAYMENT`; cash pays from cash to cash as `CASH_PAYMENT`.
- **Purchases.** For merchant category `k`, a person makes `Poisson(n_k / D)` purchases a day, with `n_k = consumption.purchases_per_month[k]` and `D` the days in the month. Each costs `person_budget * share_k / n_k * exp(sigma * z - sigma**2 / 2)`, at least 100 paise, with the district kind's `share_k` and `sigma = consumption.ticket_sigma`. Purpose is `10 + k`.
- **Merchant.** A candidate is drawn inside the person's district and category: from the person's own locality with probability `consumption.local_share` when that locality has such a merchant, otherwise from the whole district. Each person has a favourite per category, which is that draw made with `day = 0`. A purchase goes to the favourite when a keyed draw is below the person's `habit_strength`, else to a fresh candidate.
- **Online.** For apparel, electronics and other, a person with UPI buys from the e-commerce biller by `UPI_P2M` when a keyed draw is below `consumption.online_share`.
- **Bills.** Once a month, on a keyed day from 1 to 28, each household head pays the electricity biller `budget * share_utilities` (purpose `UTILITIES`), and each person with a mobile pays the telecom biller `person_budget * share_telecom` (purpose `TELECOM`). Both are at least 100 paise. Billers accept UPI and not cards.
- **Medical.** A household with `medical_due > 0` has its head pay that amount, on a keyed day from 1 to 28, to a pharmacy merchant chosen as above (purpose `MEDICAL`).

- [ ] **Step 1: Write the failing test**

```python
import datetime as dt
import numpy as np
from arthasim.build import categories as c
from arthasim.engine.intents import Intents, Purpose, Rail
from arthasim.ledger.journal import FlowType, Kind
from arthasim.modules.budget import Budget
from arthasim.modules.spending import Consumption, choose_rail
from helpers import P
from world_fixture import small_world

W = small_world()
S, B = W.state, W.state.population
O, K, H = B.orgs, B.banking, B.households
Budget().monthly(W, dt.date(2025, 4, 1))
BEH = S.behaviour
PBUD, MED = BEH.person_budget.copy(), BEH.medical_due.copy()     # other test files reuse this world
DAYS = [dt.date(2025, 4, d) for d in range(1, 31)]
IT = Intents.concat([Consumption().intents(W, d) for d in DAYS])
BANKED = S.person_deposit >= 0
ACCT_PERSON = np.full(len(S.book), -1, dtype=np.int64)
ACCT_PERSON[S.person_cash] = S.person_ids
ACCT_PERSON[S.person_deposit[BANKED]] = S.person_ids[BANKED]
PAYER = ACCT_PERSON[IT.payer_acct]
M = len(S.merchant_ids)
ACCT_MERCHANT = np.full(len(S.book), -1, dtype=np.int64)
ACCT_MERCHANT[S.merchant_deposit] = np.arange(M)
ACCT_MERCHANT[S.merchant_cash] = np.arange(M)
MERCHANT = ACCT_MERCHANT[IT.payee_acct]
AT_MERCHANT = MERCHANT >= 0
CAT = IT.purpose - Purpose.GROCERY
METRO = np.array([d.kind for d in B.districts])[B.persons.district] == "metro"
LIMIT = P.get("rail.upi.limit_paise")


def test_choose_rail():
    t, f = np.array([True]), np.array([False])
    amt = np.array([5_000])
    assert choose_rail(amt, t, t, t, t, np.array([0.5]), np.array([0.1]), P).tolist() == [Rail.UPI_P2M]
    assert choose_rail(amt, t, t, t, t, np.array([0.9]), np.array([0.1]), P).tolist() == [Rail.DEBIT_CARD]
    assert choose_rail(amt, t, t, t, t, np.array([0.9]), np.array([0.9]), P).tolist() == [Rail.CASH]
    assert choose_rail(amt, t, f, f, t, np.array([0.1]), np.array([0.1]), P).tolist() == [Rail.CASH]
    assert choose_rail(np.array([LIMIT + 1]), t, f, t, f, np.array([0.1]), np.array([0.1]), P).tolist() == [Rail.CASH]


def test_spend_follows_the_budget():
    IT.validate()
    assert (PAYER >= 0).all() and (IT.flow_type == FlowType.CONSUMPTION).all()
    for metro, key in ((True, "metro"), (False, "rural")):
        rows = METRO[PAYER] == metro
        shares = np.asarray(P.get(f"consumption.category_shares.{key}"))
        budget = PBUD[METRO == metro].sum()
        for k in (0, 1, 6):
            assert abs(IT.amount[rows & (CAT == k)].sum() / (budget * shares[k]) - 1.0) < 0.06
        ordinary = rows & (IT.purpose != Purpose.MEDICAL)
        assert abs(IT.amount[ordinary].sum() / budget - 1.0) < 0.06


def test_merchant_is_in_district_category_and_usually_local():
    assert np.array_equal(O.merchant_district[MERCHANT[AT_MERCHANT]], B.persons.district[PAYER[AT_MERCHANT]])
    shop = AT_MERCHANT & (CAT <= 8)
    assert np.array_equal(O.merchant_category[MERCHANT[shop]], CAT[shop])
    medical = IT.purpose == Purpose.MEDICAL
    assert AT_MERCHANT[medical].all() and (O.merchant_category[MERCHANT[medical]] == 3).all()
    locality = H.locality[H.household_of_person]
    grocery = AT_MERCHANT & (CAT == 0)
    local = (O.merchant_locality[MERCHANT[grocery]] == locality[PAYER[grocery]]).mean()
    assert abs(local - (0.7 + 0.3 / 20)) < 0.04


def test_rails_respect_instruments_and_acceptance():
    upi, card, cash = IT.rail == Rail.UPI_P2M, IT.rail == Rail.DEBIT_CARD, IT.rail == Rail.CASH
    assert (upi | card | cash).all()
    assert K.person_upi[PAYER[upi]].all() and K.person_has_card[PAYER[card]].all()
    assert O.merchant_accepts_upi[MERCHANT[upi & AT_MERCHANT]].all()
    assert O.merchant_accepts_card[MERCHANT[card & AT_MERCHANT]].all() and AT_MERCHANT[card].all()
    assert (IT.kind[cash] == Kind.CASH_PAYMENT).all() and (IT.kind[~cash] == Kind.PAYMENT).all()
    assert cash[~BANKED[PAYER]].all()
    assert np.isin(IT.payer_acct[cash], S.person_cash).all() and np.isin(IT.payer_acct[~cash], S.person_deposit).all()
    can = AT_MERCHANT & K.person_upi[PAYER] & O.merchant_accepts_upi[np.maximum(MERCHANT, 0)] & (IT.amount <= LIMIT)
    assert abs(upi[can].mean() - 0.85) < 0.03


def test_bills_medical_and_online():
    util, tel = IT.purpose == Purpose.UTILITIES, IT.purpose == Purpose.TELECOM
    assert util.sum() == len(H.head) and set(PAYER[util].tolist()) == set(H.head.tolist())
    assert tel.sum() == K.person_has_mobile.sum() and K.person_has_mobile[PAYER[tel]].all()
    assert np.isin(IT.payee_acct[util], [S.biller_deposit[1], S.biller_cash[1]]).all()
    assert np.isin(IT.payee_acct[tel], [S.biller_deposit[0], S.biller_cash[0]]).all()
    assert (IT.purpose == Purpose.MEDICAL).sum() == (MED > 0).sum()
    online = IT.payee_acct == S.biller_deposit[2]
    assert online.any() and K.person_upi[PAYER[online]].all() and (IT.rail[online] == Rail.UPI_P2M).all()
    assert np.isin(CAT[online], [4, 5, 8]).all()
    could = K.person_upi[PAYER] & np.isin(CAT, [4, 5, 8])
    assert abs(online[could].mean() - 0.25) < 0.04


def test_habit_subset_and_determinism():
    grocery = AT_MERCHANT & (CAT == 0) & (B.attributes.habit_strength[PAYER] > 0.9)
    pairs, counts = np.unique(np.stack([PAYER[grocery], MERCHANT[grocery]]), axis=1, return_counts=True)
    total = np.bincount(pairs[0], weights=counts)
    top = np.zeros_like(total)
    np.maximum.at(top, pairs[0], counts)
    regular = total >= 8
    assert regular.sum() > 20 and (top[regular] / total[regular]).mean() > 0.8
    day = DAYS[9]
    full, part = Consumption().intents(W, day), Consumption().intents(W, day, persons=np.arange(200))
    mine = ACCT_PERSON[full.payer_acct] < 200
    for field in ("payee_acct", "amount", "rail", "slot", "purpose"):
        assert np.array_equal(np.sort(getattr(full, field)[mine]), np.sort(getattr(part, field)))
    assert np.array_equal(Consumption().intents(W, day).amount, full.amount)
```

- [ ] **Step 2: Run** `pytest tests/test_spending.py -v`. Expected: FAIL, module not found.
- [ ] **Step 3: Implement** as described under Rules. Build the merchant lookup once per module instance: merchants sorted by (district, category) and by (district, locality, category), with start and count arrays for each. Streams: `cons.count`, `cons.amount`, `cons.local`, `cons.pick`, `cons.habit`, `cons.online`, `cons.upi`, `cons.card`, `cons.slot`, `cons.offset`, `cons.billday`. The purchase index `k` within the day goes into the draw's `index`.
- [ ] **Step 4: Run** `pytest tests/test_spending.py -v`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "feat: category spending with merchant and rail choice"`.

### Task 9: Cash management

**Files:**
- Create: `src/arthasim/modules/cash.py`
- Test: `tests/test_cash.py`

**Interfaces:**
- `CashManagement(BehaviourModule)`, `name = "cash"`.

Rules, read from balances at the start of the day. All are kind `CASH_DEPOSIT`, flow `CASH_CONVERSION`, purpose `CASH_DEPOSIT`, rail `BRANCH`, slot 40, from the holder's cash account to its own deposit.
- A merchant or biller holding more cash than `cash.merchant_float_paise` deposits the excess.
- A banked person holding more than `cash.person_deposit_threshold_paise` deposits everything above `cash.person_keep_paise`, with daily probability `cash.person_deposit_daily_prob` (stream `cash.person`).
- Unbanked persons never deposit.

- [ ] **Step 1: Write the failing test**

```python
import datetime as dt
import numpy as np
from arthasim import Config, World
from arthasim.engine.intents import Purpose, Rail
from arthasim.ledger.journal import FlowType, Kind
from arthasim.modules.cash import CashManagement

DAY = dt.date(2025, 4, 3)


def world(tmp_path):
    return World.build(Config.tier("S", persons=2_000, out_dir=str(tmp_path)), seed=7)


def test_merchants_and_billers_deposit_the_excess(tmp_path):
    w = world(tmp_path)
    s = w.state
    s.book.balance[s.merchant_cash[:3]] = [1_200_000, 500_000, 400_000]
    s.book.balance[s.biller_cash[0]] = 900_000
    it = CashManagement().intents(w, DAY)
    it.validate()
    assert it.payer_acct.tolist() == [s.merchant_cash[0], s.biller_cash[0]]
    assert it.payee_acct.tolist() == [s.merchant_deposit[0], s.biller_deposit[0]]
    assert it.amount.tolist() == [700_000, 400_000]
    assert (it.kind == Kind.CASH_DEPOSIT).all() and (it.flow_type == FlowType.CASH_CONVERSION).all()
    assert (it.rail == Rail.BRANCH).all() and (it.purpose == Purpose.CASH_DEPOSIT).all() and (it.slot == 40).all()


def test_persons_deposit_large_cash_holdings(tmp_path):
    w = world(tmp_path)
    s = w.state
    banked = np.flatnonzero(s.person_deposit >= 0)[:400]
    unbanked = np.flatnonzero(s.person_deposit == -1)[:50]
    s.book.balance[s.person_cash[banked]] = 3_000_000
    s.book.balance[s.person_cash[unbanked]] = 3_000_000
    it = CashManagement().intents(w, DAY)
    assert np.isin(it.payer_acct, s.person_cash[banked]).all() and (it.amount == 2_500_000).all()
    assert abs(len(it) / 400 - 0.2) < 0.08
    person = np.full(len(s.book), -1, dtype=np.int64)
    person[s.person_cash] = s.person_ids
    assert np.array_equal(it.payee_acct, s.person_deposit[person[it.payer_acct]])
    assert len(CashManagement().intents(w, DAY)) == len(it)
    s.book.balance[s.person_cash[banked]] = 2_000_000
    assert len(CashManagement().intents(w, DAY)) == 0
```

- [ ] **Step 2: Run** `pytest tests/test_cash.py -v`. Expected: FAIL, module not found.
- [ ] **Step 3: Implement** as described under Rules. Merchants come before billers, each in index order.
- [ ] **Step 4: Run** `pytest tests/test_cash.py -v`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "feat: cash management"`.

### Task 10: World integration, monthly table and hashing by month

**Files:**
- Modify: `src/arthasim/world.py`, `src/arthasim/store/parquet.py`
- Test: `tests/test_money_flows.py`

**Interfaces:**
- Population worlds get `[Income(), Remittances(), Budget(), Consumption(), CashManagement()]`. Spike worlds keep the two spike modules.
- After the monthly hooks run, a population world writes `truth_household_monthly`, a fact table partitioned by month, with columns `household_id, month, income_paise, balance_paise, buffer_months, stress, budget_paise, medical_due_paise`.
- `content_hash` for a fact table reads one month at a time, in month order, joining that month's parts before hashing. The hash therefore does not depend on how a run was split, and memory is bounded by one month.

- [ ] **Step 1: Write the failing test**

```python
import polars as pl
from arthasim import Config, World
from helpers import P


def cfg(tmp_path, **kw):
    base = dict(persons=5_000, out_dir=str(tmp_path))
    base.update(kw)
    return Config.tier("S", **base)


def test_population_world_runs_on_the_new_modules(tmp_path):
    world = World.build(cfg(tmp_path), seed=7)
    assert [m.name for m in world.modules] == ["income", "remittances", "budget", "consumption", "cash"]
    run = world.run(until="2025-05-20")
    pay = run.table("payments").collect()
    purposes, rails = set(pay["purpose"].unique()), set(pay["rail"].unique())
    assert run.manifest["days"] == 50 and "UNSPECIFIED" not in purposes
    assert {"SALARY", "EARNINGS", "PENSION", "EMPLOYER_REVENUE", "REMITTANCE", "GROCERY", "TRANSPORT",
            "UTILITIES", "TELECOM", "CASH_WITHDRAWAL", "CASH_DEPOSIT"} <= purposes
    assert {"UPI_P2M", "UPI_P2P", "DEBIT_CARD", "CASH", "NACH_CR", "NEFT", "ATM", "AEPS", "BRANCH"} <= rails
    s = world.state
    assert int(s.book.balance[s.merchant_cash].sum()) < 10 * len(s.merchant_cash) * P.get("cash.merchant_float_paise")
    monthly = run.table("truth_household_monthly").collect()
    assert monthly.columns == ["household_id", "month", "income_paise", "balance_paise", "buffer_months",
                               "stress", "budget_paise", "medical_due_paise"]
    assert monthly["month"].unique().sort().to_list() == ["2025-04", "2025-05"]
    assert monthly.height == 2 * len(s.population.households.adults)


def test_unbanked_earners_are_paid_in_cash(tmp_path):
    world = World.build(cfg(tmp_path), seed=7)
    s = world.state
    pay = world.run(until="2025-04-30").table("payments").collect()
    unbanked_cash = s.person_cash[s.person_deposit == -1].tolist()
    income = pay.filter(pl.col("payee_account_id").is_in(unbanked_cash)
                        & pl.col("purpose").is_in(["EARNINGS", "PENSION"]))
    assert income.height > 0 and (income["rail"] == "CASH").all() and (income["status"] == "SUCCESS").all()


def test_mid_month_start_split_run_and_determinism(tmp_path):
    one = World.build(cfg(tmp_path / "one", start="2025-04-20"), seed=7).run(until="2025-05-05")
    assert one.table("truth_household_monthly").collect()["month"].unique().sort().to_list() == ["2025-04", "2025-05"]
    world = World.build(cfg(tmp_path / "two", start="2025-04-20"), seed=7)
    world.step(5)
    two = world.run(until="2025-05-05")
    assert one.manifest["content_hash"] == two.manifest["content_hash"]
    other = World.build(cfg(tmp_path / "three", start="2025-04-20"), seed=8).run(until="2025-05-05")
    assert other.manifest["content_hash"]["payments"] != one.manifest["content_hash"]["payments"]


def test_spike_world_is_unchanged(tmp_path):
    spike = World.build(Config.tier("XS", persons=500, employers=10, merchants=30, out_dir=str(tmp_path)), seed=7)
    run = spike.run(until="2025-04-03")
    assert [m.name for m in spike.modules] == ["spike_income", "spike_consumption"]
    assert "truth_household_monthly" not in run.tables()
    assert set(run.table("payments").collect()["purpose"].unique()) <= {"SALARY", "EMPLOYER_REVENUE", "OTHER",
                                                                         "CASH_WITHDRAWAL"}
```

- [ ] **Step 2: Run** `pytest tests/test_money_flows.py -v`. Expected: FAIL, population worlds still run the spike modules.
- [ ] **Step 3: Implement** as described under Interfaces.
- [ ] **Step 4: Run** `pytest -q`. Expected: PASS for the whole suite. `tests/test_pipeline.py::test_population_world_builds_and_runs` asserts the exact set of tables; add `truth_household_monthly` to that set.
- [ ] **Step 5: Commit** `git commit -am "feat: money-flow modules on population worlds"`.

### Task 11: Exit gate

**Files:**
- Modify: `scripts/bench.py` (for population worlds also report the share of payments by rail and by purpose group, the median ratio of monthly spending to income among households with income, and cash held by persons, merchants and bank vaults at the end)
- Create: `docs/phase1b1_results.md`
- Test: `tests/test_gate_1b1.py`

Exit criteria for this plan:

1. Tier S runs 90 days with every invariant passing, including the flow-matrix columns.
2. Two runs with the same seed give identical tables.
3. Every earning group is paid and every purchase has a category: no payment has purpose `UNSPECIFIED`, and the income and spending purposes all occur.
4. Throughput, memory and a money-flow summary are recorded.

- [ ] **Step 1: Write the failing test**

```python
import polars as pl
import pytest
from arthasim import Config, World


@pytest.mark.slow
def test_plan_1b1_gate(tmp_path):
    runs = [World.build(Config.tier("S", out_dir=str(tmp_path / d)), seed=7).run(until="2025-06-29")
            for d in ("a", "b")]
    a, b = (r.manifest for r in runs)
    assert a["days"] == 90 and a["content_hash"] == b["content_hash"]
    purposes = set(runs[0].table("payments").select(pl.col("purpose").unique()).collect()["purpose"])
    assert "UNSPECIFIED" not in purposes
    assert {"SALARY", "EARNINGS", "PENSION", "REMITTANCE", "GROCERY", "FOOD", "FUEL", "PHARMACY", "APPAREL",
            "ELECTRONICS", "TRANSPORT", "SERVICES", "OTHER", "UTILITIES", "TELECOM", "MEDICAL"} <= purposes
```

- [ ] **Step 2: Run** `pytest tests/test_gate_1b1.py -v -m slow`. Expected: PASS if Tasks 1 to 10 are correct. A failure here is a defect in an earlier task: fix it there with a test that reproduces it.
- [ ] **Step 3: Extend `scripts/bench.py`** as listed under Files.
- [ ] **Step 4: Run** `python scripts/bench.py --tier S --days 90 --seed 7 --out runs`. Expected: the numbers print and no exception is raised.
- [ ] **Step 5: Write `docs/phase1b1_results.md`** with the bench numbers, the share of payments by status, rail and purpose group, the spending-to-income ratio, cash in circulation, the 12-month extrapolation beside the section 16 target, and a pass or fail against each exit criterion.
- [ ] **Step 6: Commit** `git commit -am "feat: plan 1b-1 gate and results"`.

---

## What follows this plan

Plan 1b-2 (life course) makes person state change: monthly transitions with alignment to district targets, hiring, layoffs and job switches, annual increments, account opening during a run, `life_events` and `entity_state_monthly`.
