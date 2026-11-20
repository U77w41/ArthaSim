# arthasim Margin From Leftover Surplus Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The allowance margin is paid only from surplus left after every shortfall is covered, so no recipient receives less than without a margin.

**Architecture:** `allowance_pairs` gains a `margin` argument and a second stage; `allowance_need` returns the unpadded need again. The bench reports households that cannot pay the full margin. Same branch as the first margin build (`feat/allowance-margin`).

**Tech Stack:** Python 3.11+, NumPy, pytest, Hypothesis (existing dev dependency).

**Spec:** `docs/superpowers/specs/2026-11-20-allowance-margin-design.md` (revised Design section).

## Global Constraints

- Earlier constraints hold. `transfer.allowance_margin` stays 0.15. Days, rails and withdrawals do not change.

## Review Focus

1. Rounding: a payer's total can exceed their surplus by under 0.5 paise per recipient, as before (accepted earlier).
2. Run-to-run comparisons of who receives more: budgets move with balances, so two runs at different margins can differ slightly for reasons other than the rule; the guarantee is per month's state (Task 1 property test), not across runs.

---

### Task 1: Two-stage pooling

**Files:** Modify `src/arthasim/modules/allowance.py`; Test `tests/test_allowance.py`.

**Interfaces:**
- Produces: `allowance_pairs(household_of_person, income, need, margin: float = 0.0) -> (payer, recipient, amount)`; `margin_scale(household_of_person, income, need, margin) -> np.ndarray` (per household, `min(1, leftover / total margin request)`, 1.0 where there is no request); `allowance_need(world)` returns `person_need(...)` without the margin; `Allowance.monthly` passes `params.get("transfer.allowance_margin")` as `margin`. `household_scale` unchanged (stage 1).

- [ ] **Step 1: Write the failing tests**: `test_margin_paid_from_leftover` (earner 100,000/40,000, recipients 0/40,000 and 30,000/40,000, margin 0.15 → pairs `[(0, 1, 45_000), (0, 2, 15_000)]`); `test_stretched_household_gets_no_margin` (same pairs at margin 0 and 0.15 when surplus < shortfall); `test_margin_never_lowers_an_allowance` (Hypothesis: households of 1 to 5 adults, incomes 0 to 200,000, needs 1,000 to 100,000, margin 0 to 0.5; every recipient's total at the margin is at least their total at 0, less one paisa per pair for rounding); rewrite `test_nobody_gives_and_receives` (earner 1,000/100, middle 105/100, recipient 0/100, margin 0.15 → the middle person never receives, recipient total 115); `test_allowance_need_applies_margin` becomes `test_allowance_need_is_unpadded`; `test_month_pays_every_pair_once_inside_households` passes the registry margin to `allowance_pairs`; `test_margin_scale` (leftover 10,000 against requests 12,000 → 10/12; no request → 1.0).
- [ ] **Step 2: Run** `pytest tests/test_allowance.py -q`. Expected: failures on the new tests (unexpected keyword `margin`, missing `margin_scale`).
- [ ] **Step 3: Implement** per the spec's Design section.
- [ ] **Step 4: Run** `pytest tests/test_allowance.py -q`, then `pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat: pay the allowance margin from leftover surplus`.

### Task 2: Sweep and write up

**Files:** Modify `scripts/bench.py`, `docs/phase1b1_results.md`, `docs/superpowers/ledger.md`.

- [ ] **Step 1:** add `allowance_margin_short_households` to the bench (of households with a recipient in the last month, the share whose leftover cannot pay the full margin); `allowance_scaled_households` keeps its stage-1 meaning.
- [ ] **Step 2:** run `pytest -m slow -q` (expected 3 passed) and the sweep at margins 0, 0.10, 0.15 and 0.20 (expected: margin 0 identical to the earlier margin-0 run, 15,344,393 attempts).
- [ ] **Step 3:** compare each recipient's May and June allowances between margins 0 and 0.15, as the review did, and report how many receive less and why.
- [ ] **Step 4:** replace the "Allowance margin" results section with the new table and findings, keeping one paragraph on the first build and why it was replaced; append to the ledger.
- [ ] **Step 5: Commit** `docs: margin from leftover surplus results`.
