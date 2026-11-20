# arthasim UPI Only If Funded Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Payers use UPI at merchants, billers and online only when their deposit balance at the start of the day covers the amount.

**Architecture:** In `Consumption.intents`, the `funded` mask already used for cards also gates the UPI flag passed to `choose_rail` and the online-order mask.

**Tech Stack:** Python 3.11+, NumPy, pytest.

**Spec:** `docs/superpowers/specs/2026-11-20-upi-if-funded-design.md`.

## Global Constraints

- `choose_rail` keeps its signature and draws; P2P UPI is unchanged; no new registry parameter.

## Review Focus

1. An unfunded online order becomes an offline purchase; if the district has no merchant of that category, the purchase is dropped, as offline purchases already are.
2. Two debits on one day are each checked against the morning balance (accepted for cards).

---

### Task 1: Funded UPI rule

**Files:** Modify `src/arthasim/modules/spending.py`; Test `tests/test_spending.py`.

- [ ] **Step 1: Write the failing test** `test_upi_only_when_deposit_covers_amount` (same world set-up as the card test): every deposit at 0 → no `UPI_P2M` and no `DEBIT_CARD` rows, and no row pays the e-commerce biller; every deposit at 10**12 → `UPI_P2M` rows at merchants, at billers and online; random balances from `np.random.default_rng(1)` up to 2,000,000 paise → every `UPI_P2M` and `DEBIT_CARD` row's payer deposit balance is at least its amount.
- [ ] **Step 2: Run** `pytest tests/test_spending.py -q`. Expected: the new test fails (UPI rows with a zero balance).
- [ ] **Step 3: Implement** the gate on `k.person_upi[person]` in `rail_for` and on the online mask.
- [ ] **Step 4: Run** `pytest tests/test_spending.py -q`, then `pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat: pay by UPI only when the account covers it`.

### Task 2: Measure and write up

**Files:** Modify `docs/phase1b1_results.md`, `docs/superpowers/ledger.md`.

- [ ] **Step 1:** run `pytest -m slow -q` (3 passed) and the bench (tier S, 90 days, seed 7); compare with the card-only run from the previous change.
- [ ] **Step 2:** add a "UPI only if funded" results section (funds declines by rail, rail mix, life stages, days since allowance, before and after) and a ledger entry.
- [ ] **Step 3: Commit** `docs: UPI only if funded results`.
