# arthasim Household Allowance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Earners pass a monthly allowance to household members whose own income falls short of their spending need, so non-earners can pay, and family transfers appear in the payments table.

**Architecture:** A new behaviour module `Allowance` runs after `Budget` and before `Consumption`. Its `monthly` hook computes each adult's need from the budget state, pools surplus against shortfall inside each household, and stores (payer, recipient, amount, day) pairs; its `intents` hook emits the day's pairs on a rail that follows the recipient. Two pure functions carry the rule so it can be tested on tiny arrays.

**Tech Stack:** Python 3.11+, NumPy, Polars, pytest (existing stack; nothing new).

**Spec:** `docs/superpowers/specs/2026-11-19-household-allowance-design.md`. Context: `docs/phase1b1_results.md` ("Finding: non-earning members cannot pay").

## Global Constraints

- Everything in the earlier plans' Global Constraints still holds: integer paise, keyed randomness only (`arthasim.engine.rng`), no `np.random` or `random` under `src/`, a failed invariant stops the run.
- Modules read state and emit intents. Only the settlement kernel changes balances.
- No new registry parameters. Read the utilities share from `consumption.category_shares.metro` / `.rural` at position `UTILITIES` (9) from `modules/spending.py`.
- Stream names start with `allow.`.
- New enum members: `Purpose.ALLOWANCE = 6`, `FlowType.HOUSEHOLD_TRANSFER = 9`.
- Slots for allowance payments are 48 to 79; offsets 0 to 899.
- The whole existing suite stays green. Tier XS (spike builder, spike modules) is untouched.

## Review Focus

1. A household where nobody has surplus (all non-earners, or a single adult) produces no pairs and no division by zero (Task 1, `test_no_surplus_no_pairs`).
2. A head of household with no income living with an earner gets their share plus the utilities bill and medical costs (Task 1, `test_person_need`, `test_pairs_cover_shortfall`).
3. When shortfalls exceed surplus, every shortfall is scaled by the same factor and no payer gives more than their surplus (Task 1, `test_pairs_scaled_when_short`).
4. A salaried payer whose employer pays on the 28th in a 28-day February pays on the 28th, after the salary slots (Task 2, `test_allowance_day`).
5. A recipient with UPI whose payer has no UPI gets IMPS if the payer is banked, else cash; an amount above the UPI limit goes by IMPS (Task 2, `test_rails_follow_recipient`).

---

### Task 1: Pooling rule and enums

**Files:**
- Modify: `src/arthasim/engine/intents.py` (add `Purpose.ALLOWANCE = 6`)
- Modify: `src/arthasim/ledger/journal.py` (add `FlowType.HOUSEHOLD_TRANSFER = 9`)
- Create: `src/arthasim/modules/allowance.py`
- Test: `tests/test_allowance.py`

**Interfaces:**
- Produces:
  - `person_need(person_budget: np.ndarray, budget: np.ndarray, medical_due: np.ndarray, household_of_person: np.ndarray, head: np.ndarray, utilities_share: np.ndarray) -> np.ndarray` (float64, per person). `person_budget`, `utilities_share`, `household_of_person` are per person; `budget`, `medical_due`, `head` are per household (`head[h]` is the head's person index).
  - `allowance_pairs(household_of_person: np.ndarray, income: np.ndarray, need: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]`: `(payer, recipient, amount)`, int64, person indices, amounts > 0 only, sorted by `(payer, recipient)`.

- [ ] **Step 1: Write the failing tests** in `tests/test_allowance.py`

```python
import numpy as np
from arthasim.engine.intents import Purpose
from arthasim.ledger.journal import FlowType
from arthasim.modules.allowance import allowance_pairs, person_need


def test_enum_values():
    assert Purpose.ALLOWANCE == 6 and FlowType.HOUSEHOLD_TRANSFER == 9


def test_person_need():
    need = person_need(person_budget=np.array([30_000, 30_000, 30_000]), budget=np.array([90_000]),
                       medical_due=np.array([5_000]), household_of_person=np.array([0, 0, 0]),
                       head=np.array([0]), utilities_share=np.array([0.1, 0.1, 0.1]))
    assert np.allclose(need, [41_000, 27_000, 27_000])    # head: 27,000 + 9,000 utilities + 5,000 medical


def test_pairs_cover_shortfall():
    # Earner, homemaker, pensioner with a small pension: the pension is topped up, not replaced.
    p, r, a = allowance_pairs(np.array([0, 0, 0]), np.array([100_000, 0, 7_000]),
                              np.array([41_000.0, 27_000.0, 27_000.0]))
    assert list(zip(p.tolist(), r.tolist(), a.tolist())) == [(0, 1, 27_000), (0, 2, 20_000)]


def test_pairs_scaled_when_short():
    # Surplus 10,000 + 5,000; shortfall 20,000 + 10,000; scale 0.5, split 2:1 between payers.
    p, r, a = allowance_pairs(np.array([0, 0, 0, 0]), np.array([30_000, 10_000, 0, 0]),
                              np.array([20_000.0, 5_000.0, 20_000.0, 10_000.0]))
    assert list(zip(p.tolist(), r.tolist(), a.tolist())) == [(0, 2, 6_667), (0, 3, 3_333), (1, 2, 3_333), (1, 3, 1_667)]
    assert a[p == 0].sum() == 10_000 and a[p == 1].sum() == 5_000


def test_no_surplus_no_pairs():
    # Household 0: two non-earners. Household 1: one adult short of need.
    p, r, a = allowance_pairs(np.array([0, 0, 1]), np.array([0, 0, 0]), np.array([10_000.0, 10_000.0, 10_000.0]))
    assert p.size == r.size == a.size == 0 and p.dtype == np.int64
```

- [ ] **Step 2: Run to verify they fail**

Run: `pytest tests/test_allowance.py -v`
Expected: collection error, `ModuleNotFoundError: No module named 'arthasim.modules.allowance'`.

- [ ] **Step 3: Add the enum members and implement both functions** in `src/arthasim/modules/allowance.py`

`person_need`: `person_budget * (1 - utilities_share)`, plus `budget[h] * utilities_share[head[h]] + medical_due[h]` added at `head[h]`. `allowance_pairs`: `shortfall = max(0, need - income)`, `surplus = max(0, income - need)`; per household `scale = min(1, total surplus / total shortfall)` (0 where there is no surplus); for each payer with surplus and recipient with shortfall in the same household, `amount = rint(shortfall[r] * scale * surplus[p] / total_surplus)`. Households have at most 5 adults: pair members by position after a stable sort on household, as `build/graph.py` does for household edges. Keep `amount > 0`.

- [ ] **Step 4: Run to verify they pass**

Run: `pytest tests/test_allowance.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/arthasim/engine/intents.py src/arthasim/ledger/journal.py src/arthasim/modules/allowance.py tests/test_allowance.py
git commit -m "feat: household allowance pooling rule"
```

### Task 2: Allowance module (days, rails, intents)

**Files:**
- Modify: `src/arthasim/modules/allowance.py`
- Test: `tests/test_allowance.py`

**Interfaces:**
- Consumes: `person_need`, `allowance_pairs` (Task 1); `Budget` state in `world.state.behaviour` (`person_budget`, `budget`, `medical_due`); `UTILITIES` from `modules/spending.py`.
- Produces:
  - `allowance_day(payday: np.ndarray, keyed_day: np.ndarray, days_in_month: int) -> np.ndarray`: `min(payday + 1, days_in_month)` where `payday >= 1`, else `keyed_day`.
  - `class Allowance(BehaviourModule)`, `name = "allowance"`. `monthly(world, month)` stores this month's pairs and pay days on the instance; `intents(world, day) -> Intents` emits pairs whose day is `day.day`, and returns `Intents.empty()` if `monthly` has not run.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_allowance.py`)

```python
import calendar
import datetime as dt
from arthasim.engine.intents import Intents, Rail
from arthasim.ledger.journal import Kind
from arthasim.modules.allowance import Allowance, allowance_day
from arthasim.modules.budget import Budget
from helpers import P
from world_fixture import small_world

W = small_world()
S, B = W.state, W.state.population


def _month(year, mon):
    Budget().monthly(W, dt.date(year, mon, 1))
    mod = Allowance()
    mod.monthly(W, dt.date(year, mon, 1))
    days = range(1, calendar.monthrange(year, mon)[1] + 1)
    parts = [(d, mod.intents(W, dt.date(year, mon, d))) for d in days]
    return Intents.concat([it for _, it in parts]), np.concatenate([np.full(len(it), d) for d, it in parts])


def _owner():
    owner = np.full(len(S.book), -1, dtype=np.int64)
    banked = np.flatnonzero(S.person_deposit >= 0)
    owner[S.person_deposit[banked]] = banked
    owner[S.person_cash] = np.arange(len(S.person_cash))
    return owner


def test_allowance_day():
    assert allowance_day(np.array([28, 5, -1]), np.array([3, 3, 17]), 28).tolist() == [28, 6, 17]
    assert allowance_day(np.array([28, 5, -1]), np.array([3, 3, 17]), 31).tolist() == [29, 6, 17]


def test_no_monthly_no_intents():
    assert len(Allowance().intents(W, dt.date(2025, 4, 5))) == 0


def test_month_pays_every_pair_once_inside_households():
    it, _ = _month(2025, 4)
    it.validate()
    beh, h = S.behaviour, B.households
    kinds = np.array([d.kind for d in B.districts])
    u = np.where(kinds[B.persons.district] == "metro", P.get("consumption.category_shares.metro")[9],
                 P.get("consumption.category_shares.rural")[9])
    need = person_need(beh.person_budget, beh.budget, beh.medical_due, h.household_of_person, h.head, u)
    p, r, a = allowance_pairs(h.household_of_person, B.attributes.monthly_income_paise, need)
    owner = _owner()
    got = sorted(zip(owner[it.payer_acct].tolist(), owner[it.payee_acct].tolist(), it.amount.tolist()))
    assert len(got) > 0 and got == sorted(zip(p.tolist(), r.tolist(), a.tolist()))
    assert (it.purpose == Purpose.ALLOWANCE).all() and (it.flow_type == FlowType.HOUSEHOLD_TRANSFER).all()
    assert ((it.slot >= 48) & (it.slot <= 79)).all()


def test_rails_follow_recipient():
    it, _ = _month(2025, 4)
    owner, upi = _owner(), B.banking.person_upi
    payer, rec = owner[it.payer_acct], owner[it.payee_acct]
    to_upi = upi[rec]
    p2p = to_upi & upi[payer] & (it.amount <= P.get("rail.upi.limit_paise"))
    imps = to_upi & ~p2p & (S.person_deposit[payer] >= 0)
    cash = ~(p2p | imps)
    assert (it.rail[p2p] == Rail.UPI_P2P).all() and (it.rail[imps] == Rail.IMPS).all()
    assert (it.rail[cash] == Rail.CASH).all() and (it.kind[cash] == Kind.CASH_PAYMENT).all()
    assert (it.kind[~cash] == Kind.PAYMENT).all()
    assert (it.payer_acct[cash] == S.person_cash[payer[cash]]).all()
    assert (it.payee_acct[~cash] == S.person_deposit[rec[~cash]]).all()


def test_days_salaried_and_keyed():
    it, day = _month(2025, 4)
    payer = _owner()[it.payer_acct]
    sal = S.person_employer[payer] >= 0
    assert (day[sal] == np.minimum(S.employer_payday[S.person_employer[payer[sal]]] + 1, 30)).all()
    assert ((day[~sal] >= 1) & (day[~sal] <= 28)).all()
    may, may_day = _month(2025, 5)
    may_payer = _owner()[may.payer_acct]
    april = dict(zip(payer[~sal].tolist(), day[~sal].tolist()))
    assert all(april.get(q, d) == d for q, d in zip(may_payer.tolist(), may_day.tolist()))
```

- [ ] **Step 2: Run to verify they fail**

Run: `pytest tests/test_allowance.py -v`
Expected: `ImportError: cannot import name 'Allowance'`.

- [ ] **Step 3: Implement `allowance_day` and `Allowance`**

`monthly`: build `utilities_share` per person from the district kind (as `Consumption._setup` does), call `person_need` and `allowance_pairs`, then `allowance_day(payday, keyed, days_in_month)` with `payday = employer_payday[person_employer]` for salaried payers (else -1) and `keyed = 1 + min(floor(rng.uniform(seed, stream_id("allow.day"), payer, 0) * 28), 27)`. `intents`: select today's pairs; rail per the spec (recipient UPI: `UPI_P2P` if payer UPI and amount within `rail.upi.limit_paise`, else `IMPS` if payer banked, else `CASH`; recipient without UPI: `CASH`); digital rows are `Kind.PAYMENT` deposit to deposit, cash rows `Kind.CASH_PAYMENT` cash to cash; slot `48 + min(floor(u * 32), 31)` and offset `min(floor(u * 900), 899)` from streams `allow.slot` and `allow.offset`, keyed on the payer and the day ordinal (`rng.uniform(seed, stream, payer, day.toordinal())`).

- [ ] **Step 4: Run to verify they pass**

Run: `pytest tests/test_allowance.py -v`
Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add src/arthasim/modules/allowance.py tests/test_allowance.py
git commit -m "feat: allowance module with pay days and rails"
```

### Task 3: Wire into the world

**Files:**
- Modify: `src/arthasim/world.py` (module list in `World.__init__`)
- Modify: `tests/test_gate_1b1.py` (expected purposes)
- Test: `tests/test_allowance.py`

**Interfaces:**
- Consumes: `Allowance` (Task 2).
- Produces: population worlds run `[Income, Remittances, Budget, Allowance, Consumption, CashManagement]`.

- [ ] **Step 1: Write the failing test** (append to `tests/test_allowance.py`), and add `"ALLOWANCE"` to the expected purpose set in `tests/test_gate_1b1.py`

```python
import polars as pl
from arthasim import Config, World


def test_world_runs_allowance(tmp_path):
    world = World.build(Config.tier("S", persons=5_000, out_dir=str(tmp_path)), seed=7)
    assert [m.name for m in world.modules] == ["income", "remittances", "budget", "allowance", "consumption", "cash"]
    run = world.run(until="2025-05-31")       # every invariant is checked daily
    rows = run.sql("""
        select pa.household_id as payer_hh, pb.household_id as payee_hh, y.status
        from payments y
        join accounts a on a.account_id = y.payer_account_id join persons pa on pa.entity_id = a.holder_entity_id
        join accounts b on b.account_id = y.payee_account_id join persons pb on pb.entity_id = b.holder_entity_id
        where y.purpose = 'ALLOWANCE'""")
    assert rows.height > 0 and (rows["payer_hh"] == rows["payee_hh"]).all()
    assert (rows["status"] == "SUCCESS").mean() > 0.9
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_allowance.py::test_world_runs_allowance -v`
Expected: FAIL on the module-name list.

- [ ] **Step 3: Insert `Allowance()` after `Budget()`** in `World.__init__`.

- [ ] **Step 4: Run the whole fast suite**

Run: `pytest -q`
Expected: all passed (102 earlier plus 11 new), 3 deselected.

- [ ] **Step 5: Commit**

```bash
git add src/arthasim/world.py tests/test_allowance.py tests/test_gate_1b1.py
git commit -m "feat: run household allowances in population worlds"
```

### Task 4: Measure and write up

**Files:**
- Modify: `scripts/bench.py` (`_GROUPS`, `_money_flow_summary`)
- Modify: `docs/phase1b1_results.md`
- Modify: `docs/superpowers/ledger.md`

**Interfaces:**
- Consumes: Task 3's world.
- Produces: bench output keys `purpose_group_share.transfers` and `declined_funds_by_life_stage` (life stage name to share of that stage's attempts declined for funds).

- [ ] **Step 1: Extend `scripts/bench.py`** and add `runs/` to `.gitignore` (bench output; not ignored today): add `"transfers": ("ALLOWANCE",)` to `_GROUPS`; add `declined_funds_by_life_stage` by joining `payments` to `accounts` (payer) and `persons`, share of `status = 'DECLINED_FUNDS'` per `life_stage`; add `declined_funds_no_income_households`, the share of all funds declines whose payer's household has zero income in `truth_household_monthly` for that month.

- [ ] **Step 2: Run the slow gates**

Run: `pytest -m slow -q`
Expected: 3 passed (phase 0, 1a, 1b-1 with `ALLOWANCE` in the purposes).

- [ ] **Step 3: Run the bench**

Run: `python scripts/bench.py --tier S --days 90 --seed 7 --out runs`
Expected: completes with no `InvariantError`; JSON includes the two new keys.

- [ ] **Step 4: Update the results and ledger**

In `docs/phase1b1_results.md`, under the finding, add "Fix: household allowance (19 November 2026)" with before and after tables for status shares and declines by life stage, the transfers share, the median spend-to-income ratio, the share of remaining declines from zero-income households, and the machine used. Append a "Household allowance execution ledger" section to `docs/superpowers/ledger.md` with red and green per task, as the earlier sections do.

- [ ] **Step 5: Commit**

```bash
git add .gitignore scripts/bench.py docs/phase1b1_results.md docs/superpowers/ledger.md
git commit -m "docs: household allowance results"
```
