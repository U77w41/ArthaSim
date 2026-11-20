# arthasim Flexible Automatic Withdrawal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The automatic withdrawal before a short cash payment takes the usual amount, what the account holds if less, or enough if the payment needs more.

**Architecture:** One branch of the compiled settlement kernel changes; `settle_day` gains `withdrawal_note`; the scheduler passes the new registry parameter.

**Tech Stack:** Python 3.11+, NumPy, Numba, pytest.

**Spec:** `docs/superpowers/specs/2026-11-20-flexible-withdrawal-design.md`.

## Global Constraints

- New parameter `cash.withdrawal_note_paise`: value 10000, unit `paise`, as_of 2026-11, source `flexible withdrawal placeholder`, status `assumption`, role `input`. Journal kinds and posting shapes do not change.

## Review Focus

1. The vault must hold the whole withdrawal; there is no partial withdrawal from a short vault (as today).
2. A usual amount that is not a multiple of the note size is used as given when the account covers it.

---

### Task 1: Kernel rule

**Files:** Modify `src/arthasim/engine/settlement.py`, `src/arthasim/engine/scheduler.py`, `params/registry.yaml`; Test `tests/test_settlement.py`, `tests/test_build_1b.py` (registry count 90 → 91).

- [ ] **Step 1: Write the failing tests.** In `test_cash_purchase_triggers_withdrawal`, the deposit-1,000 case now withdraws 1,000 and pays (`[0, 0, 0, 600, 8000, 500]`); add a deposit-300 case that still fails. Add `test_withdrawal_covers_a_large_purchase` (deposit 9,000, cash 100, purchase 3,500 → withdraws 3,400; `[5600, 0, 0, 0, 5600, 3500]`) and `test_withdrawal_rounds_to_notes` (note 100: deposit 1,550, cash 0, purchase 300 → withdraws 1,500; deposit 9,000, purchase 3,450 → withdraws 3,500). Registry count 91 and `P.get("cash.withdrawal_note_paise") == 10_000`.
- [ ] **Step 2: Run** `pytest tests/test_settlement.py tests/test_build_1b.py -q`. Expected: failures on the new cases.
- [ ] **Step 3: Implement** the rule in `_settle`, the `withdrawal_note` argument (default 1), the scheduler argument and the registry row.
- [ ] **Step 4: Run** the two files, then `pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat: automatic withdrawal adapts to the account and the purchase`.

### Task 2: Measure and write up

**Files:** Modify `docs/phase1b1_results.md`, `docs/superpowers/ledger.md`.

- [ ] **Step 1:** run `pytest -m slow -q` (3 passed) and the bench; compare with the UPI-only run.
- [ ] **Step 2:** results section "Flexible automatic withdrawal" (cash declines, withdrawals by rail with count and average, overall, life stages) and a ledger entry.
- [ ] **Step 3: Commit** `docs: flexible withdrawal results`.
