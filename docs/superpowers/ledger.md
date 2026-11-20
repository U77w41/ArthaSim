# Phase 0 execution ledger

Plan: `docs/superpowers/plans/2026-11-15-arthasim-phase-0-spike.md`

## Rulings

- Ruling: the `Config` field is `tier_name`, not `tier` — the plan lists both a field and a classmethod called `tier`, which cannot coexist on one class, and the spec fixes the classmethod `Config.tier(name)` — cost if wrong: one rename; the manifest key stays `tier`.

## Tasks

- Task 1 (skeleton, Config): red (collection error), green 3 passed.
- Task 2 (parameter registry): red (import error), green 3 passed.
- Task 3 (keyed random numbers): red (module missing), green 4 passed.
- Task 4 (instruments, journal): red (modules missing), green 3 passed.
- Task 4 note: `InstrumentBook.add_many` added beside `add` for the vectorised build (additive).
- Task 5 (invariants): red (module missing), green 4 passed.
- Ruling: `flow_matrix` covers income and expenditure flows only (PAYMENT and CASH_PAYMENT entries) — a cash withdrawal or interbank settlement is an asset swap, and its holder-side postings do not sum to zero by design — cost if wrong: the stock-change rows arrive with the column check in plan 1b anyway.
- Task 6 (intents, settlement kernel): red (modules missing), green 5 passed. `Settled` also carries `next_payment_id` and `next_journal_id` (additive). `acct_type` stays in the `settle_day` signature as planned; the kernel does not need it.
- Task 7 (world build): red (module missing), green 4 passed. `WorldState` also carries `employer_bank`, `merchant_bank`, `bank_of_account`, `central_bank_id`, `boundary_id`, `start` (additive).
- Ruling: when `config.banks` exceeds the length of `spike.bank_shares`, the last share is repeated before renormalising — the plan only says "truncated and renormalised" — cost if wrong: bank market shares at tiers with more than three banks, which phase 1 replaces anyway.
- Task 8 (income, consumption): red (modules missing), green 3 passed.
- Task 9 (scheduler, store, World, Run): red (World not importable); first green attempt 5 of 6.
- Ruling: in `tests/test_run.py` the uniqueness assertion is `n_unique() == height` — the plan's `Series.is_unique()` returns a boolean mask in Polars, not a scalar, so the planned assertion could never run — cost if wrong: none, the property tested is the same.
- Task 9 defect: `Run.sql` used `con.execute(query).pl()`, which DuckDB 2.0 does not have; now `con.sql(query).pl()`. The earlier "feat: scheduler, store, World and Run" commit went in with this test still red; this commit fixes it. Suite: 35 passed.
- Task 10 (exit gate): gate test passed first run, as the plan expects when tasks 1 to 9 are correct; `scripts/bench.py` written and run; results in `docs/phase0_results.md`. `bench.py` writes into a fresh `bench-<timestamp>` folder under `--out` so it never collides with an existing run (additive), and also reports build time, total time and status shares.

## Final state

- Suite: 35 fast tests and 1 slow gate test, all passing.
- No independent review has been run. This harness has no subagent tool, so the whole-branch review the plan calls for is still open.

# Plan 1a execution ledger

Plan: `docs/superpowers/plans/2026-11-15-arthasim-plan-1a-world-build.md`

## Tasks

- Task 1 (tier S config, 44 registry rows): red (3 failed), green; whole suite passing.
- Task 2 (categories, marginals, priors): red (modules missing), green 3 passed. `OTHER_SERVICES = 9` added to categories (additive).
- Task 3 (IPF, integerise): red (module missing), green 4 passed.
- Task 4 (person synthesis): red (module missing), green 3 passed.
- Task 5 (households): red (module missing), green 4 passed.
- Task 6 (attributes, starting pay): red (modules missing), green 4 passed.
- Task 7 (employers, merchants, billers): red (module missing), green 3 passed. Employers are cut at the first one whose cumulative capacity covers the group, so none is left empty and nothing needs dropping.
- Task 8 (identifiers, banks, accounts): red (modules missing), green; whole suite 63 passed. `rng.bits` added for opaque tokens (additive).
- Ruling: in `tests/test_banking.py` the expected number of distinct sample branch codes is 60, not 240 — the sample uses `ids % 12`, `ids % 2` and `ids % 20`, which share factors, so only 60 combinations occur — cost if wrong: none, uniqueness of real branch codes is by construction (bank, district, locality).
- Task 9 (social graph): red (module missing), green 4 passed.
- Task 10 (pipeline, tables, World integration): red (3 failed, tier S could not build), green 3 passed; whole suite passing. Entity kinds BILLER and NBFC added; `build_spike_state` is the phase 0 builder under its new name; `PopulationBundle` also carries second-account ids, biller and NBFC ids and identifier tokens (additive).
- Task 11 (exit gate): gate test passed first run; `scripts/bench.py` extended; results in `docs/phase1a_results.md`.

## Final state (plan 1a)

- Suite: 70 fast tests and 2 slow gate tests, all passing.
- No independent review has been run; this harness has no subagent tool.

# Plan 1b-1 execution ledger

Plan: `docs/superpowers/plans/2026-11-16-arthasim-plan-1b1-money-flows.md`

## Tasks

- Task 1 (cash deposits, purposes, new rails): red (collection error), green 4 passed; whole suite 74 passed. Kernel split into small compiled helpers (`_post`, `_record`, `_journal`); behaviour unchanged.
- Task 2 (flow-matrix columns): red (import error), green 2 passed; whole suite 76 passed.
- Task 3 (boundary cash, biller cash, behaviour state): red (2 failed), green; whole suite 78 passed. `tests/test_config_s.py` row count relaxed to >= 61 as planned.
- Task 4 (module framework): red (module missing), green 3 passed; whole suite 81 passed. `World.counters` is now public (was `_counters`) and `World.days_simulated` was added, both for `run_day(world, day)`.
- Task 5 (income for every earning group): red (module missing), green 4 passed. Pensions use the salary slot window (36 to 47); the plan left their slot open.
- Task 6 (remittances): red (module missing), green 2 passed.
- Task 7 (budget, stress, medical shocks): red (module missing), green 3 passed.
- Task 8 (category spending, merchant and rail choice): red (module missing), green 6 passed. A purchase is dropped when its district has no merchant of that category, which only happens in very small worlds; the plan did not cover that case.
- Task 9 (cash management): red (module missing), green 2 passed.
- Task 10 (world integration, monthly table, hashing by month): red (3 failed), first green attempt 3 of 4. The split-run test failed although the tables were equal. Root cause, confirmed on a two-row frame: Polars can serialise equal frames to different IPC bytes when they were joined from different parts (null bitmaps and string buffers). Fix: `content_hash` now hashes the schema plus two 64-bit row hashes per row (`hash_rows`, seeds 0 and 1), month by month. Whole suite 102 passed. Note: the hash is stable within one Polars version, not across versions.
- Task 11 (exit gate): gate test passed first run (95 s for two 90-day tier S runs); `scripts/bench.py` extended with a money-flow summary; results in `docs/phase1b1_results.md`.
- Finding: 21% of payment attempts fail for insufficient funds; 86% of those are by homemakers, students and job seekers, because income reaches only earners and nothing moves money within a household. Reported in the results with a proposed fix (monthly allowance from earners). Not fixed: it is outside this plan.

## Final state (plan 1b-1)

- No independent review has been run; this harness has no subagent tool.
- Final suite: 102 fast tests and 3 slow gate tests (phase 0, 1a, 1b-1) passing on the final commit.

# Household allowance execution ledger

Plan: `docs/superpowers/plans/2026-11-19-arthasim-household-allowance.md`. Spec: `docs/superpowers/specs/2026-11-19-household-allowance-design.md`.
Run on an Apple M5 with Python 3.12, from a scratch virtual environment with `PYTHONPATH=src` (the package is not installed on that machine).

## Tasks

- Task 1 (pooling rule, enums): red (module missing), green 5 passed.
- Ruling: `person_need` drops the planned `household_of_person` parameter — the per-household arrays are indexed through `head`, so it was never read — cost if wrong: one parameter re-added.
- Task 2 (module, days, rails): red (import error), green 11 passed (plan: 10).
- Ruling: a banked payer whose cash on hand is short of the day's cash allowances withdraws the shortfall, rounded up to ₹100, before paying — the spec relied on the kernel's automatic withdrawal, which takes a fixed ₹2,000, so most cash allowances from salaried earners would have failed; pinned by `test_cash_payer_withdraws_shortfall_first` — cost if wrong: extra withdrawal rows and more cash held by recipients.
- Ruling: slot and offset draws are keyed on the (payer, recipient) pair, not the payer alone — two allowances from one payer on one day would otherwise share a timestamp and a technical-decline draw — cost if wrong: none to the money flows.
- Task 3 (world integration): red (module list), green; whole suite 114 passed.
- Ruling: `tests/test_money_flows.py` pins the module list, so its expected list gains `allowance` — the plan missed this test — cost if wrong: none.
- Task 4 (measurement): slow gates 3 passed in 65 s; bench before and after on the same machine; results in `docs/phase1b1_results.md`. `runs/` added to `.gitignore`.
- Finding: funds declines fall from 21.5% to 5.4% of attempts. What remains comes mostly from households with no income (plan 1d) and from the first month, before the first allowance arrives.
