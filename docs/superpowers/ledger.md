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
- Finding: funds declines fall from 21.5% to 5.4% of attempts. Of what remains over 90 days, households with no income cause 33% (plan 1d) and households with income 67%, mostly because an allowance has no margin over expected spending and recipients run short late in each cycle. The success measure in the design is only partly met.

## Final review (household allowance)

- A fresh reviewer read the whole branch: no critical findings, one important. Fixed: the results doc said households with no income were the main source of the remaining declines; they cause 33% (half in June). Numbers re-run before restating them.
- Deferred minors:
  - card holders without UPI get cash but pay by card;
  - payers paid mostly in cash send digital allowances from deposits their income rarely refills;
  - the pre-withdrawal is sized at the start of the day and is all-or-nothing;
  - test gaps: allowances over the UPI limit, withdrawal ordering, shared fixture state;
  - the design still says the automatic withdrawal covers cash allowances;
  - rounding can exceed a payer's surplus by up to 2 paise.
- Rulings on items the reviewer set aside: remittances received are not pooled as income; recipients get no margin over expected spending; the need includes telecom for people without a mobile. All three follow the approved design. The fixed ₹2,000 automatic withdrawal and unmodelled IMPS limits are kernel scope.

# Allowance margin execution ledger

Plan: `docs/superpowers/plans/2026-11-20-arthasim-allowance-margin.md`. Spec: `docs/superpowers/specs/2026-11-20-allowance-margin-design.md`.

## Tasks

- Task 1 (margin parameter, `household_scale`, `allowance_need`): red (import error), green 16 passed; whole suite 118 passed.
- Ruling: `test_margin_parameter` reads the value through `P.get` — `ParamRegistry.table()` holds values as text, so the planned comparison with 0.15 could never pass — cost if wrong: none.
- Ruling: `tests/test_build_1b.py` pins the registry at 89 rows; now 90 — the plan missed it — cost if wrong: none.
- Task 2 (sweep): slow gates 3 passed in 64 s; bench gains `--set KEY=VALUE`, `recipient_declined_by_days_since_allowance` and `allowance_scaled_households`; margin swept over 0, 0.10, 0.15 and 0.20; margin 0 reproduces the earlier run exactly.
- Finding: the margin is a small lever. Funds declines fall from 5.36% to 5.05% at 0.15; late-cycle declines fall by a third; households scaled down rise from 4% to 22%. What remains is spread across payment methods. The value stays at 0.15.

## Final review (allowance margin)

- A fresh reviewer read the branch: no critical findings, one important. Two minors were re-graded as important because they were false statements in the results.
- Fixed in the results doc:
  - it said recipients get more; 18% of them get less (reproduced: 4,888 of 26,665, decline rate 11.2% to 14.9%);
  - it said early-cycle declines barely move; they fall 14 to 19%;
  - it did not name the period or the denominator of each row.
- Deferred minors: `--set` errors on a missing `=` or an unparsed `1e-1`; a test uses an import placed below it.
- Rulings on items the reviewer set aside: padding earners' need follows the approved design and goes to the project owner as a decision; run manifests do not record parameter overrides (predates this branch); no range check on the margin (no parameter has one); the margin pads the head's bills too (per design).

# Margin from leftover surplus execution ledger

Plan: `docs/superpowers/plans/2026-11-20-arthasim-margin-from-leftover.md`. Spec: the revised design in `docs/superpowers/specs/2026-11-20-allowance-margin-design.md`.

- Task 1 (two-stage pooling): red (import error); the Hypothesis property test found an overflow warning at a margin of 5e-324, fixed by dividing only where the result is below 1; green 20 passed; whole suite 122 passed.
- Ruling: the pair amount keeps the earlier order of operations, `(shortfall * scale + margin request * margin scale) * surplus / total surplus`. That keeps a margin of 0 bit-identical to earlier runs — cost if wrong: none.
- Ruling: the import placed below its first use in `tests/test_allowance.py` moved to the top, since those import lines were being rewritten anyway (a deferred minor) — cost if wrong: none.
- Task 2 (sweep): slow gates 3 passed in 62 s; the margin-0 run's content hash equals both earlier runs; at 0.15, funds declines are 4.93% and households scaled down stay at 4.0%.
- Finding: 249 recipients (0.9%) receive less across runs at 0 and 0.15. In 247 of them the payment failed for the payer's funds; in 2 the amount was smaller because the budget moved. The deferred minors from the first margin review stand, except the import, now fixed.

## Final review (margin from leftover surplus)

- A fresh reviewer read the whole branch and found it ready to merge: no critical or important findings, six minors. Its checks: 20,000 random households with zero violations; margin 0 bit-identical across three runs; every table figure reproduced.
- Fixed: one minor re-graded as important, following the precedent that false statements in the results are important. The doc said recipients' payments were "about a fifth" of attempts (a quarter) and that the margin changes "only what recipients receive". It also raises allowance failures for the payer's funds, from 2.1% to 2.6%. Rows added for that and for allowance volume (₹142 to ₹169 crore at 0.15). The reviewer's volume figure was ten times too small; it was recomputed before use.
- Deferred minors:
  - the property test does not pin the pro rata split or the per-payer bound;
  - the 249 figure covers three life stages (all recipients: 337 of 43,945);
  - the margin-short row includes stage-1 scaled households;
  - the `allowance_pairs` docstring describes only stage 1;
  - repeated code in the bench helpers.

# Card only if funded execution ledger

Plan: `docs/superpowers/plans/2026-11-20-arthasim-card-if-funded.md`. Spec: `docs/superpowers/specs/2026-11-20-card-if-funded-design.md`.

- Task 1 (funded card rule): red (card rows with every deposit at zero), green; whole suite 123 passed.
- Task 2 (measure): bench gains `declined_funds_by_rail`; slow gates 3 passed in 63 s; before (main at c5666ce) and after run with the same bench script. Debit-card funds declines fall from 8.3% to 0.2%, and overall funds declines from 4.93% to 4.79%. Recipients with a card and no UPI: 5.8% to 4.8%.

## Final review (card only if funded)

- A fresh reviewer found the code correct and every figure reproducible: start-of-day balance confirmed in the scheduler, and UPI counts identical before and after. One important finding: the results put all remaining card declines down to a second card purchase. The 663 left follow an earlier same-day card purchase in 349 cases, UPI purchases in 248, a cash withdrawal in 64 and a bank transfer in 2. This was re-queried and fixed.
- Deferred minors:
  - one test assertion cannot fail without the rule, and UPI-gating or `>` mutants pass the test file;
  - "a tenth" of card purchases moving to cash is 8.7%, and about a third of those fail in cash;
  - the new bench key is not named in the results.
- Noted, out of scope: medical bills paid in cash fail about 66% of the time, before and after this change.

# UPI only if funded execution ledger

Plan: `docs/superpowers/plans/2026-11-20-arthasim-upi-if-funded.md`. Spec: `docs/superpowers/specs/2026-11-20-upi-if-funded-design.md`.

- Task 1 (funded UPI rule): red (UPI rows with every deposit at zero), green; the card check became a shared `funded(person, amount)` helper for UPI, card and online orders; whole suite 124 passed.
- Task 2 (measure): slow gates 3 passed in 66 s; bench compared with the card-only run.
- Result: UPI funds declines fall from 7.5% to 0.3%, and overall funds declines from 4.79% to 4.35%. About 56% of the purchases that moved to cash fail there. About 29,500 cash purchases that used to succeed now fail, because the moved ones spent the cash first.

## Final review (UPI only if funded)

- A fresh reviewer found the code correct. P2P UPI and the random draws are untouched: funded payers' rows are identical, row by row, before and after. Every figure reproduces.
- Fixed:
  - the results said two thirds of moved purchases fail in cash. Re-queried: about 56%, plus about 29,500 cash purchases that used to succeed now fail;
  - the results and the design said an unfunded payer might move to card. The same check gates cards, so none do (re-graded from minor, as a false statement).
- Deferred minors:
  - no test pins that an unfunded online order becomes a shop purchase rather than disappearing;
  - online orders fall 8.8% (123,041 to 112,165), which the results do not mention;
  - P2P UPI funds declines rise from 0.46% to 0.52% through extra withdrawals, although the rule leaves P2P alone.

# Flexible automatic withdrawal execution ledger

Plan: `docs/superpowers/plans/2026-11-20-arthasim-flexible-withdrawal.md`. Spec: `docs/superpowers/specs/2026-11-20-flexible-withdrawal-design.md`.

- Task 1 (kernel rule): red (`settle_day` had no `withdrawal_note`), green; `settle_day` takes `withdrawal_note` (default 1) and the scheduler passes `cash.withdrawal_note_paise`; the existing withdrawal test's deposit-1,000 case now pays; whole suite 126 passed.
- Task 2 (measure): slow gates 3 passed in 63 s. Funds declines fall from 4.35% to 3.85%, and withdrawals rise by about 10%.

## Final review (flexible automatic withdrawal)

- A fresh reviewer found it ready to merge: no critical or important findings. It checked edge cases, mutation tests and the ledger shape, and every figure reproduces. After the change, no automatic withdrawal is followed by a failed purchase; before, 43,581 were.
- Deferred minors:
  - no test pins that the scheduler passes the note size;
  - a usual amount that is not a whole number of notes is rounded down when the account barely covers it (only with overridden values);
  - `withdrawal_note` below 1 is not rejected (0 raises a division error mid-run);
  - the allowance module keeps its own ₹100 note constant;
  - tier XS spike runs change too (90 days, seed 7: 1,146,684 attempts against 1,144,327; funds declines 21.9% against 22.4%), so `phase0_results.md` no longer reproduces exactly;
  - no upper limit per withdrawal (largest automatic withdrawals ₹1,17,500 by ATM and ₹88,800 by AePS);
  - the results do not mention the 43,581 to 0 change;
  - the `settle_day` docstring omits the conditions for a withdrawal.
- Rulings on items the reviewer set aside: small withdrawals that empty nearly empty accounts (5,300 under ₹500), the whole-note cap, no adaptation to a short vault, and the allowance pre-withdrawal staying as it is all follow the approved design.

# Deferred minors tidy-up

- Code (test-first):
  - `settle_day` rejects a `withdrawal_note` below 1;
  - its docstring states when a withdrawal goes ahead;
  - cash-allowance withdrawals read `cash.withdrawal_note_paise` instead of a separate constant;
  - `allowance_pairs` documents both stages and shares one margin-request helper;
  - bench `--set` names a malformed argument and reads values such as `1e-1` as numbers;
  - the bench helpers share one household mask.
- Tests:
  - a randomised check of the withdrawal rule against a plain restatement;
  - every withdrawal in a real run is a whole number of notes (scheduler wiring);
  - funding changes only the rails of unfunded purchases, and unfunded online orders go to shops (this replaces an assertion that could not fail);
  - the allowance's exact pairs and per-payer surplus bound;
  - an allowance over the UPI limit goes by IMPS;
  - each allowance withdrawal settles before the allowance it funds.
  - Mutation checks, each caught by a test: the scheduler dropping the note size, online orders ungated, the vault checked against the shortfall, the usual amount rounded up, and the margin split equally among payers.
- Docs: all figures re-queried before use.
  - card: 36,790 purchases moved and a third failed; the new bench key named;
  - UPI: online order attempts down 8.8% (completed orders down 0.8%), and P2P declines from 0.46% to 0.52%;
  - withdrawal: 43,581 to 0, and the tier XS figures (also noted in `phase0_results.md`);
  - margin: the 249 denominator (337 of 43,945 across all recipients) and the margin-short row note;
  - spec notes where the build departed from the design.
- From the earlier lists:
  - resolved by later changes: card holders without UPI who received cash but paid by card (card only if funded);
  - pinned as designed: a usual amount that is not a whole number of notes is rounded down when the account caps it (property test);
  - left as is: tests that set `small_world`'s budget state in place (order-independent today); and a strict `>` in the funding check, which no test distinguishes and which would change behaviour only for an exact balance.
- After review of this tidy-up:
  - a note size below 1 is also rejected where the allowance module reads it. Before, a population world failed there first with an unclear error;
  - `--set` rejects values that are not finite, such as `nan` or `inf`. These had silently removed every allowance;
  - the online figure now separates attempts from completed orders;
  - the ordering test asserts that it met a same-slot tie;
  - unused test variables removed.
- Left for decisions, since they change outputs:
  - an upper limit per withdrawal;
  - allowance rails that follow where the payer's income lands;
  - an allowance withdrawal that is all-or-nothing and sized from the morning's cash;
  - medical bills paid in cash failing about two thirds of the time.

# Plan 1b-2 (life course) execution ledger

Plan: `docs/superpowers/plans/2026-11-21-arthasim-plan-1b2-life-course.md`. Spec: `docs/superpowers/specs/2026-11-21-life-course-design.md` (approved 21 November 2026).
Run on an Apple M5 with Python 3.12, from a scratch virtual environment with `PYTHONPATH=src`. Built on branch `plan-1b2-life-course` in a git worktree (`.worktrees/`, excluded locally), so the shared checkout never switched branches.

## Tasks

- Task 1 (PLFS sources, 23 registry rows, loader): red (collection error), green 6 passed; whole suite 140 passed. The YAML was transcribed from `docs/sources/` with a throwaway script; the tests pin spot values and every Table 15 column sum.
- Task 2 (targets): red (import error), green 6 passed (plan: 5; one added for the ends of the age range).
- Task 3 (alignment): red (import error), green 4 passed (two Hypothesis properties, 60 examples each).
- Task 4 (synthesis on the start month's targets): red (`TypeError`), green 7 passed with the old population tests; one test added for `fit_report`'s `stage_target`; whole suite 154 passed.
- Task 5 (transition probabilities): red (import error), green 5 passed.
- Task 6 (helpers, life state, build): red (import error and the persons columns), green; whole suite 161 passed. `income_for`, `draw_sector` and `pick_banks` checked bit-identical against the previous modules. Slow gates still 3 passed.
- Task 7 (accounts opened mid-run): red (no `extend`), green 9 passed with the ledger and invariant tests.
- Task 8 (jobs and pay): red (import error), green 3 passed.
- Task 9 (`LifeCourse`, events, monthly state, world wiring): red (module list), green 3 passed first run; whole suite 169 passed.
- Task 10 (gate, bench, results): the 12-month tier S gate passed first run (98.5 s); all four slow gates pass. Bench before (`main`, from a detached scratch checkout) and after, 90 days, and 365 days on the branch. Results in `docs/phase1b2_results.md`.

## Rulings

- Task 1: the data file nests each block's values under `values:` beside `source`, `table`, `pages` and `status`. That keeps the metadata apart from the group keys for validation. Cost if wrong: none outside the YAML layout.
- Task 2: the plan's test asked for exactly equal shares in June 2026 and June 2025, but the plan also makes the gig share follow the fiscal year. The test now compares the seven other stages, and self-employed plus gig together. Cost if wrong: none; the seasonal path still repeats.
- Task 2: interpolation follows the spec ("Ages 18–19 take the mean of the 15–19 and 20–24 columns; 65 and over use the 65+ column"), not the plan's knots at 17 and 70. The knots are 19, 22, ..., 62, 65, and the study exits use the same knots. Cost if wrong: studying at 18–19 is about 10 points lower than the plan's version.
- Task 2 (inherited from the plan): targets are computed at run time from `params/lifecourse/plfs_2025.yaml`, not stored in a `targets.yaml` as the spec says. The numbers are the same. Cost if wrong: none.
- Task 5: the centring for the not-in-labour-force row leaves out students, whose rows are replaced by the study hazard. Cost if wrong: a small shift in which homemakers and retired people find work.
- Task 6: `initial_life_state` takes the helper flags as an argument, since helpers must be known before income is zeroed and before banking. Cost if wrong: none.
- Task 6: the persons table no longer has `life_stage`, so `test_pipeline` checks `birth_month` instead (Task 9 checks stages in `entity_state_monthly`). Cost if wrong: none.
- Task 6: three tests re-derived for the new population, as the plan allows:
  - remittances count only senders with income;
  - income events are checked for earners with income, and helpers get none;
  - the allowance ordering test forces a same-slot tie, because natural ties (about 1 in 28,800 gifts) no longer occur in April.
  Cost if wrong: the tie is exercised by construction, not by chance.
- Task 8: `firm_shock` reads its sigma from the run's registry held by the targets, since the plan's signature has no params. Cost if wrong: none.
- Task 9: people hired or switching jobs in their employer's raise month skip that month's raise, since their pay was just set. Superseded after the final review (below).
- Task 9: a hire's or switcher's sector becomes their employer's sector. This matters when no employer exists in the drawn sector and the district fallback applies. Cost if wrong: none.
- Task 9: someone returning within 12 months gets their previous income only if it was positive (a former helper gets entry pay). Cost if wrong: none.
- Task 9: a job switch that draws the current employer redraws once. If it is still the same (one employer in the group), there is no switch. Cost if wrong: slightly fewer switches.
- Task 9: `tests/test_allowance.py` also pins the module list and gains `lifecourse`. Cost if wrong: none.

## Findings

- Funds declines rise from 3.9% to 4.7% of attempts. This is because the PLFS population has more homemakers and fewer pensioners than the placeholders, not because of the monthly moves.
- A layoff causes no money stress. The budget follows income from the next month and nothing is committed spending. Laid-off people decline less in the month of the layoff (0.4%) than in the month before (1.5%).
- Helpers come to 30% of PLFS's level (the design expected about 40%), because households are formed without regard to work.
- Peak memory is 2.5 to 2.7 GB at tier S, against 2.1 GB on `main` (it varies run to run and does not grow over a year). The cause has not been looked into.

## Final review (plan 1b-2)

A fresh reviewer (Opus) read the whole branch and returned "with fixes": one critical finding, two important and nine minor. It checked the YAML against `docs/sources/` cell by cell, confirmed every cell on target in runs to 2027, and confirmed the person-state invariants month by month.

Fixed, each with a test that failed first; fast suite 174 passed, slow gates 4 passed:
- **Raking stopped small runs.** The proportional fitting had to converge to 1e-9 within 5,000 iterations. Near the floor it converges very slowly, so worlds of 30 to 500 people, and one of 2,000, stopped with a `ValueError`. `rake` now runs the same steps itself and, after 5,000 iterations, accepts the result if every margin is within half a person; the rounding then makes both margins exact. Tests: the reviewer's three-person repro, a Hypothesis property with exact-zero probabilities and unchanged targets, and a 300-person full year. The reviewer's crash cases (500 people with seeds 1–6; 2,000, 120 and 30 people with seed 7) now all run 365 days.
  - Ruling: where the fitting converges, the result is the same as before. Cost if wrong: in a rare slow cell the flows come from the last iterate rather than the exact fit.
- **Helper flips reversed in the same month.** Helper to own-account and own-account to helper shared one draw, so a helper could flip and flip back (56 cases in a test with both rates at 0.5). They now use separate draws, and nobody flips back in the month they became own-account.
- **Two raises within a year after a switch or a hire.** A raise now needs 12 months since the last one and 6 months since a hire or switch set the pay. The 6 is a new registry row, `life.raise.min_tenure_months` (assumption; 115 rows). This replaces the Task 9 ruling.
  - Ruling: cost if wrong, a hire can wait up to 6 months longer for a first raise than an employer that pro-rates would make them.

The benches were rerun after the fixes and every figure in `docs/phase1b2_results.md` was re-queried. Raises are now 18,772, each to a different person; helper flips back are 60 instead of 79. The other figures barely moved.

Rulings on behaviour the reviewer set aside:
- The quarterly agriculture share, which includes agricultural casual and regular workers, shifts the farm stage, as the spec says. Cost if wrong: farm seasonality slightly overstated.
- The calibration gaps stand as reported findings: helper to own-account churn is 7.3% against 3.2% for urban men, and helpers are 30% of PLFS's level. Calibration is plan 1e.
- The extra memory stands as reported.
- People born in the start month do not age until a year later, because the first simulated day runs no ageing; the build's age is read as the age before this year's birthday. Cost if wrong: 1/12 of people are a year younger in the first year and miss superannuation that year.
- Every move from salaried to seeking is `LAID_OFF`, including quits, as the spec's event table says.
- Young "retired" people (code 94 includes rentiers and remittance recipients) get the existing pension rule.
- `choose_movers` fills destinations in index order, as the plan specifies. Cost if wrong: a slight bias for people likely to make several moves.
- No test compares two full-year runs' hashes. The split-run test and the 1b-1 gate cover determinism.

Deferred minors:
- `life.prob_bounds` is [0.0003, 0.95] where the spec clips to [0.001, 0.95]. The plan applies the effects per month, so 0.0003 is the monthly equivalent; it changes only who moves.
- The test for runs past March 2026 checks only the month labels, not targets or ages past 85 (the reviewer checked both by hand).
- The helper-orphan rule is tested only by "no orphans at the end", not by an orphan being made own-account and paid (the reviewer saw 228 such events at tier S, all paid).
- The build's alignment floor is a constant, so overriding `life.rake.floor` does not reach the build.
- `firm_shock` reads its sigma through the targets' registry rather than a `params` argument.
- `initial_life_state`'s `start` argument is unused, and the months-in-stage cap ignores the education start age the spec mentions.
- The window for reusing the last salaried sector counts from the last stage change, not from leaving salaried work (matters only past 12 months).
- `instrument_id` is renumbered at each flush as new accounts add rows mid-table.
- `rates.py` and `sources.py` import private helpers from other modules.


# Plan 1d-1 (government transfers) execution ledger

Plan: `docs/superpowers/plans/2026-11-22-arthasim-plan-1d1-government-transfers.md`. Spec: `docs/superpowers/specs/2026-11-22-government-transfers-design.md`. Sources: `docs/sources/dbt.md`.
Run on an Apple M5 with Python 3.12, from a scratch virtual environment with `PYTHONPATH=src`. Built on branch `claude/dazzling-rosalind-a3bd01` in its own git worktree. Executed inline (native), with one fresh Opus review of the whole branch.

The project owner approved the scope, the three schemes, the ledger approach (A) and the behaviour rules, then went offline with a standing instruction: decide everything else the way the real system works, from open data. Those decisions are marked "Decided overnight" in the spec, each with its source and its cost if wrong.

## Tasks

- Task 1 (enums, government balance, journal shape, invariants, flow matrix): red (missing enums), green 9 passed; ledger and invariant tests 22 passed.
- Task 2 (kernel and scheduler): red (unknown keyword, wrong postings), green; whole suite 186 passed.
- Task 3 (17 `dbt.` registry rows, scheme rules): red (import error), green 13 passed; a second row-count pin (`tests/test_life_sources.py`) moved to 132; whole suite 194 passed.
- Task 4 (government entity, BPL list, payees banked at build by a swap, frames): red (import error), green 6 passed; whole suite 200 passed.
- Task 5 (`GovernmentTransfers`, `truth_dbt_monthly`, `entity_state_monthly` written after the monthly hooks): red (module order), green 8 passed; tests pinning the module order and the table set updated; whole suite 208 passed.
- Task 6 (budgets and allowances count transfers; `transfer_income_paise`): red, green; whole suite 211 passed.
- Task 7 (bench figures, slow gate `tests/test_gate_1d1.py`): red (KeyError `dbt`), green; gate passed in 48 s; all five slow gates passed in 141 s.
- Task 8: benches before (`main` at `1b5d045`, exported with `git archive`) and after, 90 and 365 days; every figure re-queried with one script; `docs/phase1d1_results.md`.

## Rulings

- Task 2: the accounts table's type-name list gained GOVERNMENT in Task 2 rather than Task 4, because a world holding a government account cannot write its tables without it. Cost if wrong: none.
- The build's swap draw is named `bank.dbt_swap`, as the plan's Task 4 says, although the spec's Randomness section says DBT streams start with `dbt.`. It is a banking-stage draw in `build/banking.py`, and renaming it changes seeded output. Cost if wrong: a naming inconsistency only.
- Rulings on the reviewer's "declined to judge" list:
  - **Account −1 for other kinds.** A payment of any other kind posted to account −1 also wraps to the last account. This predates the plan, and callers guard it.
  - **Budgeting from the 1st.** Budgets count a month's DBT value from the 1st, although credits land later or every four months. The spec decided this.
  - **Mid-month starts.** A run that starts after a pay day budgets that month's transfer though no credit lands. This follows from the no-arrears rule.
  - **Early allowances.** Allowance payers whose surplus comes from DBT may pay before their credit lands: 6 of 38,633, none declined.
  - **Ownership drift.** Ownership rises a quarter point a year through DBT openings. The spec allows openings during the run.
  - **Pay-day overrides.** A pay-day override above 28 skips short months. The registry values are 5 and 10.
  - **Technical-decline keys.** Technical declines are keyed on account id, so the government balance's id shifts the draws for accounts opened later. This predates the plan; at coverage 0, one payment in 381,938 changes outcome against `main`.

## Findings

- Funds declines fall from 4.72% to 4.13% of attempts over 90 days, and from 4.65% to 3.87% over a year.
- Households with no earned income decline 36.3% of the time over 90 days, down from 45.1%, and 60.1% over the year, down from 72.3%. Their share of all funds declines falls over 90 days but stays at 69% over the year, because DBT lowers everyone else's declines by about as much.
- The women's transfer reaches 9.9% of women aged 21–60, against about 32% in India. Simulated incomes run high, so only a quarter of women are under the ₹2.5 lakh cap. Plan 1e calibrates incomes.
- A third of simulated people aged 60+ are "retired" with a contributory pension, against 8.6% in LASI. This leaves fewer elderly people for the social pension (11.2% enrolled).
- Allowances fall by only ₹0.97 crore a year against ₹6.64 crore paid to women, because a transfer also raises the household budget and each member's need.

## Final review (plan 1d-1)

A fresh reviewer (Opus) read the whole branch, ran the fast suite and the new gate, checked each Review Focus item by experiment, and compared the branch at coverage 0 with `main`. Verdict: "with fixes". There was no critical finding, one important finding and six minor ones.

**Fixed**, with a test that failed first: the government-transfer guard. A payee of −1 wrapped to the last account, a deposit with a valid reserve, and the invariants could not see it. The guard now checks that both accounts exist, that the payer is the government balance and the payee a deposit, and that the reserve lookup covers every account. A government transfer is also exempt from the UPI limit and technical declines on any rail. Tests: five bad-account cases and a UPI-rail case. Suite 218 passed. The bench's content hashes are unchanged.

**Deferred minors:**
- At coverage 0 the run is not identical to `main` (one payment in 381,938; see the technical-decline ruling above). The plan's Review Focus 5 overstated it.
- The build banks 67 payees (tier S) who lose eligibility after April's raises. This is recorded in the results doc.
- `entity_state_monthly` is built after day one settles, not just after the monthly hooks. The result is the same today, but the comment in `life/events.py` still says "start of the month".
- Test gaps:
  - the tiny-world swap test does not assert that a district ran short;
  - no in-run test checks that coverage and the women's tier stay with the same people;
  - no PM-Kisan age-tie test.

# Plan 1c (data products) execution ledger

Plan: `docs/superpowers/plans/2026-11-23-arthasim-plan-1c-data-products.md`. Spec: `docs/superpowers/specs/2026-11-22-data-products-design.md`.
Run on an Apple M5 with Python 3.12 (polars 2.1.0, duckdb 2.0.1), from a scratch virtual environment with `PYTHONPATH=src`. Built on branch `claude/gallant-roentgen-ebc4d9` in its own git worktree, then rebased onto `main` at `e9fd517` (plan 1d-1) before the fix pass. Executed inline (native), with one fresh Opus review of the whole branch.

The project owner agreed the shape in conversation: researchers in Python first, then a bank dataset for partners; views carry simulator IDs, exports carry each bank's own numbers. The owner then went offline with a standing instruction to decide the rest from the real world and public evidence. Those decisions are marked "Decided overnight" in the spec, each with its source and its cost if wrong. A builder-check subagent read the spec before planning. Its four questions were settled the same way: views read closed files; KYC holds a birth year; the "no change" check is against the `main` tip at merge; ATM and AePS withdrawals name a terminal.

## Tasks

- Task 1 (incremental store, live content hash in the old format): red (no `arthasim.store.hashing`), green 6 new; suite 180 passed. Tier S, 90 days, seed 7: every manifest hash equalled `main`'s.
- Task 2 (opaque handles, ACCOUNT_NO, TERMINAL, `bank_customers`, `birth_year`, `opening_balance_paise`): red (4 failures), green 4 new and 2 updated pins; suite 184 passed.
- Task 3 (`balances_monthly`, shared fixture run): red (no table), green 2 new; suite 186 passed.
- Task 4 (view machinery, truth view): red (no `arthasim.views`), green 5 new; suite 191 passed.
- Task 5 (bank view, handles, narration, statement lines): red (no `MCC`), green 10 new; suite 201 passed.
- Task 6 (switch and bureau views): red, green 4 new; suite 205 passed.
- Task 7 (inspector): red, green 7 new; suite 212 passed.
- Task 8 (`watch`, `unwatch`): red, green 3 new; suite 215 passed.
- Task 9 (metrics, `register.metric`): red, then an ambiguous GROUP BY alias (fixed with positional grouping), green 21 new; suite 236 passed.
- Task 10 (export, manifest, data dictionary): red, then `fetchone()` missing in DuckDB 2.0 and a test that named a bank with customers, green 7 new; suite 243 passed.
- Task 11 (slow gate `tests/test_gate_1c.py`, `scripts/data_products_demo.py`): the gate passed in 25.7 s; all five slow gates passed in 147 s.
- Rebase onto `e9fd517`: conflicts in `tests/test_pipeline.py` and the store's `FACT_TABLES`, resolved by keeping both sides; suite 287 passed.
- DBT in the views (APBS credits from PFMS with the scheme, an `apbs` switch network, the truth view's asof on `truth_dbt_monthly`): red (narration), green 4 new.
- After the fix pass: suite 299 passed; all six slow gates passed in 220 s.
- After measurement: the store writes complete Polars files per chunk (store test red, one file; green, five); suite 299 passed.

## Rulings

Each line gives the ruling, then what it costs if wrong.

**Task 1**
- The row-group test asserts 5 groups, not the plan's "at least 6". Ten 700-row frames written whenever 1,000 rows are queued make 5 groups of 1,400. Cost: none.
- The live hash feeds the folder name (`month=YYYY-MM`), as the from-disk hash always did. Cost: none.

**Task 2**
- `account_frames` and `population_frames` take the run seed. The new identifiers are keyed, and `WorldState` has no seed. Cost: none.
- A person's VPA is keyed on their deposit account, as the spec says. Cost: none.

**Task 3**
- The store closes every table's hash month at the month end (`Store.end_month`). Otherwise April's `balances_monthly` spool would have lived until the end of May. Cost: none; the digests are unchanged.
- The split-run test counts accounts opened by 30 April, not `len(book)`. Cost: none.

**Task 4**
- Truth-view definitions have no ORDER BY, because plain scans keep file order. The final review overturned this for the tables an `asof` cuts (see below). Cost: none for uncut scans.
- The truth view's `asof` also cuts instruments to accounts opened by then. Cost: none.

**Task 5**
- Statement lines carry a per-account serial number, `line_seq`, rather than an order key built from `journal_id`. Cost: none.
- On a card payment seen from the merchant's side, the other side is the cardholder's card token. Cost: one CASE arm.
- The payer's remark also appears on the payer's own NACH debit line. Cost: narration text only.
- `mcc` appears on UPI_P2M and DEBIT_CARD rows, from the payee's category. Cost: none.

**Task 6**
- ATM and AePS terminals are on-us, at the payer's bank. The payer's handle is their card token, falling back to the account number (ATM) or the uid token (AePS). Cost: off-us ATMs would need acquirer banks.
- Unknown scope arguments raise ValueError. Cost: none.

**Task 7**
- A payment between two of the entity's own accounts is one timeline row with direction SELF. Cost: none.
- A life event's timestamp is IST midnight of its date. Cost: none.
- `passbook` also returns `date`, `line_seq` and the other side's simulator IDs, since the inspector is truth-level. Cost: none.

**Task 8**
- `watch` uses direction SELF, as the timeline does. Cost: none.
- `state` comes on any day the life course ran. Cost: none.

**Task 9**
- A user metric may return a scalar, which is wrapped as a one-row `value` frame. Cost: none.
- `deposit_balance` covers persons' deposits only. Cost: a second metric for firms.

**Task 10**
- The bank view's instruments carry `account_no` and drop `instrument_id`, so an export can still link instruments to accounts. Cost: none.
- An empty fact table exports as one zero-row file, and the manifest records each table's layout. Cost: readers branch on the layout.
- A truth export copies the run's files and rejects `asof`. Cost: use the truth view for a cut.
- The month partition column lives only in the folder name. Cost: none.

**Task 11**
- The gate watches the last 5 of its 90 days. Cost: none.

**DBT integration**
- APBS credits show PFMS as the other side, with no bank code, and the scheme as the remark. The switch view's `apbs` network routes on the payee's Aadhaar token. DBT flows through PFMS, and NPCI's APBS routes on Aadhaar. Cost: narration text and one network.

**After measurement**
- The store writes each chunk of 1,000,000 rows as a complete Polars file, under a temporary name renamed when done, instead of row groups to one open PyArrow writer per month. In alternating tier S 90-day runs, the PyArrow writer took the simulation from 9.8 s (`main`) to 16.7 s. With Polars files it is 10.7 s, with the same memory bound. Cost: about five payment files a month at tier S instead of one.

## Findings

- **Memory.** One month of payments, journal and postings took about 1 GB in memory at tier S before the store change. Peak memory now no longer grows with the month; see `docs/phase1c_results.md` for the measured figures.
- **Narrations.** Real bank narrations have no national template. RBI fixes the UTR format only. The common pattern is rail, direction, reference, the other side and a remark, which the views follow.
- **Bureau.** A credit bureau holds no file on people who have never applied for credit. So the bureau view is empty until phase 3.

## Final review (plan 1c)

A fresh reviewer (Opus) read the whole branch (`1b5d045..6570590`) and returned "with fixes": no Critical, six Important and ten Minor findings. It confirmed at tier S that the unchanged tables are byte-identical to `main`'s.

**Re-grading.** Two minors were re-graded to Important by their effect:
- `deposit_balance` raised an error on a run with no closed month, which plan 1d's short experiment arms would hit.
- Statement lines hash-joined every payment, which made one passbook take 4 GB and was the root of export's memory use.

**Fixed**, each with a test that failed first. Suite 299 passed; all six slow gates passed.
- **A watch callback that raised left the day half-done**, so continuing duplicated it. The callback now runs at the end of the day. Test: `test_raising_callback_leaves_world_ready_to_continue`.
- **Part files were written under their final names**, so a mid-run read or a crash left files without a footer, which broke the whole table. Files are now written as `part-N.parquet.tmp` and renamed on close, and `step`/`run` close files in a `finally`. Test: `test_run_is_readable_while_running_and_after_an_error`.
- **The truth view's `asof` cut returned postings and instruments in a varying order.** Those cuts are semi-joins; they are now explicitly ordered. The check is in the slow gate. On the reviewer's tier S run the cut was red: 23,541,917 rows, in a different order on each call. After the fix it was green.
- **Export ran each fact table's whole query once per month.** Each table is now built once, in an on-disk DuckDB database that can spill. Test: `test_export_reads_each_table_once` went from 23 reads to 6.
- **Statement lines joined every payment.** They now join only their own payments. The slow gate checks one person's statement lines fit in 300 MB with no spilling (red: OutOfMemoryException; green: 170 rows).
- **A run ending mid-month kept its spool in the run folder.** The spool now lives in a temp directory, removed with the store or at exit. Test: `test_finished_runs_keep_no_spool`.
- **Export tokens could be decoded to simulator IDs, the seed shipped in the manifest, and the README overclaimed.** Tokens are now keyed BLAKE2b digests. The manifest names the source run by a 16-hex digest. The README states the limits. Tests: `test_identifier_tokens_are_keyed_one_way_hashes`, `test_export_carries_no_seed_and_says_what_it_protects`.
- **`deposit_balance` raised before any month closed.** It now returns an empty frame. Test: `test_deposit_balance_before_any_month_has_closed`.
- The stale `watch` docstring was corrected in the same edit.

**Rulings on the review.** Each gives the ruling, then what it costs if wrong.
- `pan_like` (plan 1a) still encodes the person's index. Re-keying it needs a format-preserving keyed permutation to stay unique in the PAN shape, and PAN is a cross-institution key that real banks share anyway. The export README says so. Cost: a partner holding truth tables or the code could map `pan_like` to `entity_id`. Fix before any external release.
- `ref` stays the payment ID written as 12 digits. The spec decided this, and labels are keyed on it. Cost: it reveals global payment order and volume.
- The token key derives from the run seed, so someone with the code could brute-force small seeds. Hiding from a determined user is a spec non-goal, and the README says the export is not anonymised against someone with the code. Cost: a partner release needs a secret key (one config field).
- Items the reviewer set aside, ruled as standing:
  - the single boundary account (a model limit);
  - views being readable by file path (spec non-goal);
  - Polars `hash_rows` changing between versions (non-goal; the manifest records `polars_version`);
  - no tier M measurement (the spec targets tier S);
  - the empty bureau view and the narration text (spec decisions);
  - UPI Lite, AA and regulator views, CSV export and legal review (non-goals);
  - `Run.sql` path quoting (it predates this plan).

**Deferred minors:**
- Runs written before plan 1c give unclear errors from views, `inspect` and `deposit_balance`.
- The truth view's `asof` doesn't cut `bank_customers`.
- A run path containing a single quote breaks the SQL.
- `_bank_customers` finds the boundary bank by index, not by code.
- `deposit_balance` on a spike run names groupings nobody asked for.
- The cross-bank "every posting once" check counts rows only.
