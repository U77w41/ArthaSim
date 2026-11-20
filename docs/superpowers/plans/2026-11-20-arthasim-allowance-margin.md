# arthasim Allowance Margin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every adult's need is inflated by a registry margin before allowance pooling, so recipients stop running short late in each cycle.

**Architecture:** One registry parameter and one change of input in `Allowance.monthly`. Two small helpers make the margin and the household scale reusable by the bench, which gains a `--set` option for parameter sweeps and two metrics.

**Tech Stack:** Python 3.11+, NumPy, Polars, DuckDB, pytest (existing stack).

**Spec:** `docs/superpowers/specs/2026-11-20-allowance-margin-design.md`. Builds on `docs/superpowers/specs/2026-11-19-household-allowance-design.md`.

## Global Constraints

- Earlier plans' Global Constraints hold: integer paise, keyed randomness only, a failed invariant stops the run.
- New parameter: `transfer.allowance_margin`, value 0.15, unit `''`, as_of 2026-11, source `allowance margin placeholder`, status `assumption`, role `input`.
- Shortfall, surplus, scaling, pay days and rails do not change. Only the need passed to `allowance_pairs` does.

## Review Focus

1. A person whose income lies between their need and their need plus margin receives an allowance and gives none (Task 1, `test_nobody_gives_and_receives`).
2. Households where the margin turns full cover into scaled cover: reported as `allowance_scaled_households` (Task 2), not tested.
3. A registry without the new row fails loudly at the first monthly hook, not silently with margin 0 (the registry's `get` raises on a missing id; no test needed).

---

### Task 1: Margin parameter and helpers

**Files:**
- Modify: `params/registry.yaml` (append the row from Global Constraints after `transfer.remittance_share`)
- Modify: `src/arthasim/modules/allowance.py`
- Test: `tests/test_allowance.py`

**Interfaces:**
- Produces:
  - `household_scale(household_of_person: np.ndarray, income: np.ndarray, need: np.ndarray) -> np.ndarray`: per household, `min(1, total surplus / total shortfall)`; 1.0 where total shortfall is 0. `allowance_pairs` uses it.
  - `allowance_need(world) -> np.ndarray`: per person, `person_need(...) * (1 + transfer.allowance_margin)`, from `world.state.behaviour` and the district's utilities share. `Allowance.monthly` uses it.

- [ ] **Step 1: Write the failing tests** (in `tests/test_allowance.py`; replace the `u = ...` / `need = person_need(...)` lines in `test_month_pays_every_pair_once_inside_households` with `need = allowance_need(W)`)

```python
import polars as pl
from arthasim.modules.allowance import allowance_need, household_scale


def test_margin_parameter():
    row = P.table().filter(pl.col("id") == "transfer.allowance_margin")
    assert row.height == 1 and row["value"][0] == 0.15 and row["status"][0] == "assumption"


def test_household_scale():
    scale = household_scale(np.array([0, 0, 1, 1, 2, 3]), np.array([30_000, 0, 10_000, 0, 0, 10_000]),
                            np.array([10_000.0, 10_000.0, 5_000.0, 10_000.0, 5_000.0, 5_000.0]))
    assert scale.tolist() == [1.0, 0.5, 0.0, 1.0]


def test_nobody_gives_and_receives():
    # Income 105 against need 100 padded by 15%: a recipient of 10, not a payer of 5.
    p, r, a = allowance_pairs(np.array([0, 0]), np.array([1_000, 105]), np.array([100.0, 100.0]) * 1.15)
    assert list(zip(p.tolist(), r.tolist(), a.tolist())) == [(0, 1, 10)]


def test_allowance_need_applies_margin():
    Budget().monthly(W, dt.date(2025, 4, 1))
    beh, h = S.behaviour, B.households
    kinds = np.array([d.kind for d in B.districts])
    u = np.where(kinds[B.persons.district] == "metro", P.get("consumption.category_shares.metro")[9],
                 P.get("consumption.category_shares.rural")[9])
    plain = person_need(beh.person_budget, beh.budget, beh.medical_due, h.head, u)
    assert np.allclose(allowance_need(W), plain * 1.15)
```

- [ ] **Step 2: Run to verify they fail**

Run: `pytest tests/test_allowance.py -q`
Expected: `ImportError: cannot import name 'allowance_need'`.

- [ ] **Step 3: Add the registry row, `household_scale` and `allowance_need`; use them in `allowance_pairs` and `Allowance.monthly`**

- [ ] **Step 4: Run to verify they pass, then the whole suite**

Run: `pytest tests/test_allowance.py -q`, then `pytest -q`
Expected: 16 passed; whole suite 118 passed, 3 deselected.

- [ ] **Step 5: Commit**

```bash
git add params/registry.yaml src/arthasim/modules/allowance.py tests/test_allowance.py
git commit -m "feat: allowance margin"
```

### Task 2: Sweep, measure and write up

**Files:**
- Modify: `scripts/bench.py`
- Modify: `docs/phase1b1_results.md`, `docs/superpowers/ledger.md`

**Interfaces:**
- Consumes: `household_scale`, `allowance_need` (Task 1).
- Produces: `bench.py --set KEY=VALUE` (repeatable; value parsed with `yaml.safe_load`, applied with `Config.with_params`); output keys `allowance_scaled_households` (of households with both surplus and shortfall at the last simulated month, the share with scale below 1) and `recipient_declined_by_days_since_allowance` (homemakers, students and job seekers: share of their payment attempts declined for funds, bucketed 0-9, 10-19, 20-24, 25-29, 30+ days since their last successful allowance received; allowance and cash purposes excluded).

- [ ] **Step 1: Extend `scripts/bench.py`** as above.

- [ ] **Step 2: Run the slow gates**

Run: `pytest -m slow -q`
Expected: 3 passed.

- [ ] **Step 3: Run the sweep**

Run: `python scripts/bench.py --tier S --days 90 --seed 7 --out runs --set transfer.allowance_margin=M` for M in 0, 0.1, 0.15, 0.2.
Expected: four runs with no `InvariantError`; margin 0 reproduces the earlier "after" run (15,344,393 attempts, DECLINED_FUNDS 5.36%).

- [ ] **Step 4: Update the results and ledger**

In `docs/phase1b1_results.md`, add "Allowance margin (20 November 2026)" after the household allowance section: a table by margin of DECLINED_FUNDS, declines for homemakers, students and job seekers, declines by days since allowance, `allowance_scaled_households`, and the share of declines from households with no income; then the chosen margin and why. Append an "Allowance margin execution ledger" to `docs/superpowers/ledger.md`.

- [ ] **Step 5: Commit**

```bash
git add scripts/bench.py docs/phase1b1_results.md docs/superpowers/ledger.md
git commit -m "docs: allowance margin sweep and results"
```
