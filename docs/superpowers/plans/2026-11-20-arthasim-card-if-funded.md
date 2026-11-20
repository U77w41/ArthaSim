# arthasim Card Only If Funded Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Payers use their debit card only when their deposit balance at the start of the day covers the purchase.

**Architecture:** One change in `Consumption.intents`' rail helper; the bench gains a funds-decline rate by rail.

**Tech Stack:** Python 3.11+, NumPy, pytest.

**Spec:** `docs/superpowers/specs/2026-11-20-card-if-funded-design.md`.

## Global Constraints

- Earlier constraints hold. `choose_rail` keeps its signature and draws; no new registry parameter.

## Review Focus

1. Several card purchases by one payer on one day are each checked against the morning balance, so some still fail (accepted in the design).
2. Medical payments at a pharmacy also go through the same helper, so they follow the rule too.

---

### Task 1: Funded card rule

**Files:** Modify `src/arthasim/modules/spending.py`; Test `tests/test_spending.py`.

- [ ] **Step 1: Write the failing test** `test_card_only_when_deposit_covers_amount`: build a 5,000-person tier S world in `tmp_path`, run `Budget().monthly` for April; set every person deposit balance to 0 and compute `Consumption().intents` for 2025-04-10 → no `DEBIT_CARD` rows; set them to 10**12 → some `DEBIT_CARD` rows; set each to a random level between 0 and 2,000,000 paise drawn from `np.random.default_rng(0)` → every `DEBIT_CARD` row's payer deposit balance is at least its amount, and some cash rows come from card holders at card-accepting merchants whose balance was short.
- [ ] **Step 2: Run** `pytest tests/test_spending.py -q`. Expected: the new test fails (card rows with a zero balance).
- [ ] **Step 3: Implement**: in `rail_for`, pass `k.person_has_card[person] & funded`, where `funded` is the payer having a deposit whose start-of-day balance covers `amount`.
- [ ] **Step 4: Run** `pytest tests/test_spending.py -q`, then `pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat: pay by card only when the account covers it`.

### Task 2: Measure and write up

**Files:** Modify `scripts/bench.py`, `docs/phase1b1_results.md`, `docs/superpowers/ledger.md`.

- [ ] **Step 1:** add `declined_funds_by_rail` to the bench (per rail, the share of its attempts declined for funds).
- [ ] **Step 2:** run `pytest -m slow -q` (3 passed) and the bench (tier S, 90 days, seed 7); compare with the margin-0.15 run from before this change, using the same bench script for both.
- [ ] **Step 3:** add a "Card only if funded" section to the results: by-rail decline rates and rail mix before and after, overall funds declines, life stages, and recipients with a card and no UPI; ledger entry.
- [ ] **Step 4: Commit** `docs: card only if funded results`.
