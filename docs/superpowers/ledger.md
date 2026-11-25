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

# Safe partner exports execution ledger

Plan: `docs/superpowers/plans/2026-11-23-arthasim-safe-partner-exports.md`. Spec: `docs/superpowers/specs/2026-11-23-safe-partner-exports-design.md`. Results: `docs/phase1c2_results.md`.
Run on an Apple M5 with Python 3.12 (numba 0.68.1, polars 2.1.0, duckdb 2.0.1), from a scratch virtual environment with `PYTHONPATH=src`. Built on branch `claude/suspicious-wilbur-1ca482` in its own git worktree, from `main` at `b188ed0`. Executed inline (native), with one fresh Opus review of the whole branch.

The project owner decided the shape in conversation:
- a partner may have the code;
- approach A, a release secret in `Config`;
- SipHash-2-4 for secret runs, accepting slower release runs;
- `uid_token` for customers with an APBS credit or an AePS withdrawal at the bank.

A builder-check subagent read the first draft. It raised three questions:
- **The legal premise.** The KYC rule also allows voluntary Aadhaar, and AePS needs the link. The owner chose APBS or AePS.
- **The 64-bit cap and invertibility of the mixer.** The owner chose SipHash.
- **Export row order revealing `entity_id` rank.** I settled this myself: the export sorts by the bank's own numbers.

## Tasks

| Task | Commits | Tests |
| :--- | :--- | :--- |
| 1. Release secret in `Config` | `fac31be` | 15 passed |
| 2. SipHash-2-4 keyed draws | `8ead617` | 8 passed |
| 3. Keyed `pan_like`, identifier keys | `81a893d` | 21 passed; full suite 317 |
| 4. World with a secret, bench `--release` | `1088dab` | full suite 324 |
| 5. `uid_token` in bank `customers` | `3acab98` | 31 passed |
| 6. Export flag, keyed `source_run`, row order | `c28bf49` | full suite 331 |
| 7. Benches, slow gates, results | this commit | 6 slow gates pass (289 s) |

## Rulings

- **Task 5.** The `aadhaar` CTE uses `union`, not `union all`. A duplicate row would duplicate customers in the left join, and the plan's "distinct holder from a union all" means the same thing. Cost if wrong: none.
- **Task 7, folder name.** The plan expected the plain bench's folder to be `S-seed7-08112731`. But `bench.py` puts a timestamped `out_dir` into the config, and `out_dir` is in the config hash, so bench folders always differ from run to run. I checked instead that the branch computes `08112731` for the baseline's settings, on top of the pinned hash tests. Cost if wrong: none.
- **Task 7, `geo`.** The spec says every table's hash differs with a secret. `geo` is built from the config with no draws, so it is equal in both runs. Cost if wrong: none.
- **Task 7, timing.** The first `main` baseline (10.7 s of simulation) came from a quieter machine. The slowdown is measured from interleaved runs of `main`, the plain branch and the secret branch. With a secret, simulation is 33% slower, against the spec's estimate of 25–30%. Cost if wrong: the owner may want the figure re-measured on an idle machine.

## Citation

The KYC citation was checked word for word on rbi.org.in, in the Master Direction updated as on 14 August 2025:
- paragraph 16(a)(i) covers a section 7 benefit or subsidy;
- paragraph 16(a)(ii) covers voluntary submission to a bank;
- Explanation 1 requires redaction where authentication is not required.

The fetch tools returned only a summary and a CAPTCHA page for the PDF. The text was read from the HTML page in the built-in browser.

## Final review

A fresh Opus reviewer read the branch `b188ed0..58a0055`, ran the fast suite (331) and the slow gates (6), and checked the cryptography, the keying coverage, the byte identity of runs without a secret, the `uid_token` rule and the export order independently. Verdict: "with fixes". There was no critical finding, one important finding and seven minor ones.

**Fixed**, each with a test:
- **The release secret in validation errors.** A pydantic error echoed its input, so a malformed secret printed in full and a valid one leaked its last 22 digits through a model-level error. `Config` now sets `hide_input_in_errors`. The test `test_errors_never_print_the_secret` failed first, then passed.
- **The README of exports from runs written before this change** claimed `pan_like` was keyed. I re-graded this minor to important under the "false promise" anti-goal. The README now describes `pan_like` as the run made it. The test `test_readme_describes_pan_like_as_the_run_made_it` failed first, then passed.
- **The results note's claim that no derived key reaches an export.** I re-graded this minor to important under the rule that every statement in a results note is re-queried. The export leak test now checks the derived keys. It passed first time: the code was right, and the claim lacked a test.

Suite after fixes: 333 passed.

**Rulings on the reviewer's "declined to judge" list:**
- **`ref` order.** It is a non-goal, and the reviewer measured no rank leak in it: 51.4% ascending.
- **`source_content_hash`.** It shows only `geo` across secrets.
- **Tracebacks with locals and pickles.** They are outside the spec's surfaces.
- **`model_copy` bypassing validation.** It is not a supported way to set the secret.
- **The KYC wording.** It was read word for word.
- **Bureau and switch export order.** The spec limits reordering to bank exports.
- **The 33% slowdown.** It is the owner's call.

**Deferred minors:**
- an overlong secret fails late with a BLAKE2b error;
- the under-32 rule is not tested on its own;
- stale `seed: int` annotations;
- no domain tag on the source label key.

# Plan 1d-2 (scenarios and experiments) execution ledger

Plan: `docs/superpowers/plans/2026-11-24-arthasim-plan-1d2-scenarios-experiments.md`. Spec: `docs/superpowers/specs/2026-11-23-scenarios-experiments-design.md`. Sources: `docs/sources/macro.md`. Results: `docs/phase1d2_results.md`.
Run on an Apple M5 with Python 3.12 (numba 0.68.1, polars 2.1.0, duckdb 2.0.1), from a scratch virtual environment with `PYTHONPATH=src`. Built on branch `claude/nostalgic-wescoff-b80231` in its own git worktree, from `main` at `21eecc9`. Executed inline (native), with one fresh Opus review of the whole branch.

The project owner chose to record macro paths only (approach A). The owner handed the rest of the how to this session: decide the way the real system works, from public evidence, and record each decision with its source. The spec marks those decisions **Decided**.

A builder-check subagent read the spec first. It raised three points, each settled in the spec without the owner:
- **The window an effect measures.** Effects default to the arms' window, from `intervene_at` to `end`.
- **A 100% pay cut.** It cannot be reversed, so a pay cut's rate must be under 1.
- **`Targets` keeping the build's registry.** It now follows the live one.

## Tasks

| Task | Commits | Tests |
| :--- | :--- | :--- |
| 1. Macro series, metadata tables, atomic rewrites | `8326aa8` | 30 passed; full suite 340 |
| 2. Live parameters | `0229cb3` | full suite 344 |
| 3. Save and load | `44ed1aa` | 8 passed |
| 4. Fork, monthly checkpoints, `run.fork_at` | `dc49b5e` | full suite 356 |
| 5. Interventions, `Scenario`, `where` | `ef8ff7a` | 21 passed |
| 6. Applying parameters, rails, macro paths, module swaps | `b9184af` | full suite 385 |
| 7. Income shocks | `53ffbf3` | full suite 390 |
| 8. Expense shocks and scenario DBT | `ceef8ec` | 20 passed |
| 9. Windowed runs and the t interval | `10e0223` | full suite 406 |
| 10. Experiments, sweeps, reports | `1869d73` | full suite 426 |
| 11. Bench, gate, results script, results | `7d04b2f` and this commit | 2 slow gates pass (122 s) |

The reference hashes of `main` were recorded before any code changed: 18 tables, from `scripts/bench.py --tier S --days 90 --seed 7`. After the branch, all 18 are equal.

## Rulings

- **Task 3.** `RunningHash.clone` landed with Task 3's hashing change rather than Task 4's. It is in the same file and only fork uses it. Cost if wrong: none.
- **Task 5.** `DBTTransfer` accepts an amount whose paise are within 1e-6 of a whole number, not the plan's 1e-9. Float error in amounts above about ₹10 lakh exceeds 1e-9 (1234567891.0000002), and ₹2,000.555 is still refused. Cost if wrong: none.
- **Task 7.** `test_layoff_shift_is_clamped` passed at RED: with no layoffs, the shift was empty and the comparison trivial. It now also checks that layoffs happened and that some cell's shift exceeds its June target, so the clamp is exercised. Cost if wrong: none.
- **Task 11.** `scripts/phase1d2_results.py` gained `--persons`, used only for a 2,000-person smoke run before the tier S runs. Cost if wrong: none; the results use tier S's defaults.

## Findings

- **Watchers missed life-course events on the 1st of a month.** This was on `main`. `World._day` kept one frame per table name for watchers, so the `dbt` module's `life_events` frame replaced the life course's. A watched person who retired on 1 May 2025 got no event in the callback (a probe at 2,000 persons from 28 April). Intervention events were not passed to watchers either. The final review's fix pass fixed both (see below).
- **A checkpoint save costs about 0.73 s at tier S, against the spec's estimate of under 0.2 s.**
  - 0.58 s is the flush a save makes first, which rebuilds the accounts, instruments and bank-customer tables and writes the manifest.
  - 0.06 s is the pickle.
  - That is about 11% of a month's simulation.
- **One test passes by design before its feature exists.** `test_expense_shock_at_rate_zero_changes_nothing` asserts that nothing changes. It guards the baseline's draws once the shock exists.
- **Fast suite time.** It went from 98 s to 174 s across the branch, mostly from the new tests. The 12 checkpoint tests alone take about 20 s.

## Final review

A fresh Opus reviewer read `21eecc9..f911afe` in two passes. It ran the new test files (63 passed), re-queried the results doc from the saved runs, and checked behaviours with probe scripts in the scratchpad. Verdict: "with fixes". It found two critical issues, two important ones and nine minor ones.

**Fixed.** Each code fix has a test that failed first, then passed.
- **The results doc's consumption baseline was ten times too large.** It read ₹3,611.46 crore; 361,145,627,221.8 paise is ₹361.15 crore. The row's own +0.46% fits only the correct figure. Corrected, and recomputed from the saved JSON.
- **A module swap shared the caller's module object, so experiment results depended on the worker count.** With one worker, every seed's world ran the same object, and its state carried from seed to seed. The reviewer reproduced it: a module that stops after 40 days gave 580 payments instead of 19,131 in seed 2. The world now runs its own pickled copy from `apply`.
  - `test_a_stateful_module_does_not_carry_between_seeds` failed first: the caller's module had run 62 days.
  - `test_module_swap_from_its_month_start` now checks the world's copy.
- **A scenario with a module swap was applied twice after a fork or a load.** Swaps matched by object identity, and fork and load copy the module. Swaps now match by their module's pickled state at `apply`. `test_a_scenario_with_a_module_swap_matches_after_fork_and_load` failed first, with two `SetHook` rows.
- **`Experiment` ran `apply`'s checks only inside each seed, after the prefix, and a failed run left its folder.** Construction now checks:
  - registry ids;
  - population-only kinds on a spike config;
  - DBT scheme names, built-in and repeated;
  - module names.

  A failed run removes its folder. Tests: `test_apply_checks_run_at_construction` and `test_a_failed_run_leaves_no_folder`, both failed first.
- **Re-graded from minor: a save, fork or load folder inside the folder it links from.** Linking walked into its own copy, so `world.save(world.path / "ck")` would recurse until it failed. Such folders are now refused, except under the run's `checkpoints/`. `test_destinations_inside_the_run_folder_are_refused` failed first.
- **Re-graded from minor: watchers never saw intervention events.** This closes the finding above. Watchers now get every module's rows of a table. `test_watchers_see_life_course_and_shock_events` failed first, with no `RETIRED` event.
- **Re-graded from minor: `view`, `inspect` and `export` on a windowed `Run` silently read the whole run.** So a user metric reading through a view measured whole runs under `window="arms"`. They now raise. `test_a_window_refuses_views_inspection_and_export` failed first.
- **The results doc had no per-file hash table,** which the spec asks for. It now has an appendix with the SHA-256 of all 108 files.

Suite after the fixes: 441 passed, every fast test and all eight slow gates, in 581 s.

**Rulings on the reviewer's "declined to judge" list:**
- **A `MacroPath` after a `SetPolicyRate` replaces the shifted path from its own dates on,** as the spec says. Stands; cost: none in phase 1.
- **`_CODE_VERSION` is unchanged.** Checkpoints are new on this branch, so none older exist. Stands; cost: a later change to pickled classes must bump it.
- **DuckDB `where` could call file functions.** The expression is the user's own code. Stands; cost: none unless `where` strings come from untrusted sources.
- **Disk growth with the copy fallback** is what the spec prescribes. Stands.
- **A 0.73 s checkpoint** is the owner's call. It is recorded in the results and the findings.
- **The watcher miss on `main`** is now fixed (above).
- **The profile split was not re-measured by the reviewer.** It was measured in this session, at tier S at the end of April. Stands.
- **A `SetPolicyRate` dated before the series' first step raises at its date, not at `apply`.** This needs a start before 7 February 2025. Deferred as minor.

**Deferred minors:**
- A pay cut is restored after a helper round trip, which is rare. A flip resets pay, and the restore should check for it.
- `link_tree` falls back to a copy on any `OSError`. That is unreachable without a race.
- `world.set_hook` on a fresh world that starts mid-month raises; `SetHook(date=None)` works.
- Report gaps:
  - no line for an intervention dated after `end`;
  - the `ChangeRailRule` line says "the parameter" rather than its id;
  - "selected nobody" is printed for a layoff whose selected people were not salaried.
- The default experiment digest covers only a module's class name, so experiments differing only in a module's settings collide with `FileExistsError`.
- Scenario DBT credits reuse the `dbt.slot` and `dbt.offset` streams, so a person paid by two schemes on one day gets equal timestamps.
- A `SetPolicyRate` dated before the series' first step (above).

# Cheaper monthly checkpoints execution ledger

A follow-up to plan 1d-2's finding that a monthly checkpoint costs about 0.73 s at tier S. The task was to make it cheaper without changing any output byte.

Run on an Apple M5 with Python 3.12 (numba 0.68.1, polars 2.1.0, duckdb 2.0.1), from a scratch virtual environment with `PYTHONPATH=src`. Built on branch `claude/bold-archimedes-55440a` in its own git worktree, from `main` at `9c1ffe2`. Executed inline (native), test first. Tests: `tests/test_account_tables.py`, 17 of them.

## Where a save's time went on `main`

One flush at tier S at the end of April, best of three, from a profile in the scratchpad:

| Step | Time |
| :--- | ---: |
| Flush | 577 ms |
| — rebuilding the three account tables | 463 ms |
| — writing them | 44 ms |
| Content hashes of every table | 63 ms, made twice per checkpoint |
| Pickle | 62 ms |

In the rebuild, the per-id BLAKE2b digests behind account numbers, customer numbers, VPAs and terminals took about 320 ms of 610 ms under cProfile. The two-column `np.unique` for bank customers took 77 ms, and `branch_code` took 53 ms.

## Findings

- **Accounts open on the 1st of every month at tier S.** In the bench run, 183 accounts opened on 1 May and 232 on 1 June; DBT opened 32 and 49 of them. None opened in April. So at the May checkpoint the three tables really have changed since they were last written. A marker that only skips unchanged tables saves nothing there; the rebuild itself had to get cheaper.
- **The identifiers of existing accounts never change.** Each is a pure function of the seed and its key. A rebuild made all of them again: 268,660 digests at the end of April.
- **`main` hashed every dimension table twice per checkpoint,** once for the manifest and once for `checkpoint.json`. Only the account tables and the two metadata tables can change after the build.
- **Only `life.accounts.open_accounts` changes the account tables' inputs during a run.** An AST scan of `src/` found no other writer, direct or through a local alias. A module swapped in with `SetHook(kind="module")` can write them all the same.

## Changes

- **A marker per account table.** `pipeline.account_marker(state)` is a SHA-256 over every array `account_frames` reads: the book, opening dates, bank links, banking flags, tokens, districts, localities and merchant acceptance. `World.build` and `World._flush` write the three tables with it. A flush rebuilds them only when the marker differs from the one the store last wrote.
- **The store keeps the markers.** `Store.write_dimension(name, frame, marker)` records the marker with the file's stamp: device, inode, size and modification time. `Store.marker(name)` returns it only while that file is still in place. The store is never pickled, so a loaded or forked world, which gets a new store, rewrites the three tables from its own state when it opens. Rewrites still go through a temporary name and `os.replace`.
- **An identifier memo.** `identifiers.IdentifierMemo` keeps each account number, customer number, VPA and terminal by kind and key (id and bank index). The kind names the bank codes. It serves one seed. A warm rebuild makes only the new accounts' identifiers. The memo lives on the world and is never pickled, so `world.pkl` does not grow.
- **Dimension hashes once per file.** `Store.dimension_hash(name)` caches a dimension or metadata table's content hash by the same file stamp. A rewritten table is still hashed from disk, never from the frame in memory.
- **The same values, made faster.**
  - Bank customers take one `np.unique` over a single int64 per (bank, entity) pair. It gives the same rows in the same order as the two-column `np.unique`.
  - `branch_code` formats each distinct branch once.
  - The instruments' `kind` and `value` columns are built from object arrays instead of per-row list comprehensions.

## Rulings

- **The marker is a digest of the inputs, not the number of accounts or a counter** as the brief suggested. A swapped-in module that changes who has UPI without opening an account would leave a count-based marker unchanged and the instruments table stale. `test_a_banking_flag_changed_without_opening_an_account_rewrites_the_tables` guards this. A counter would also have to be bumped by every future writer. The cost at tier S is 10.5 ms a flush (best of five), over 16.0 MB of arrays and 5.4 MB of strings, and it grows with the population. `test_the_marker_reads_everything_the_account_tables_are_made_from` runs `account_frames` and the marker against a recording stand-in for the state, and fails if the tables read anything the marker does not. Cost if wrong: a stale table, which that test and the byte comparisons below are there to catch.
- **Object arrays (tokens, bank codes) are hashed by content.** They are joined by NUL when no string holds one, else hashed as their `repr`, with a tag byte and the count. Their pointers would miss an in-place change. Cost if wrong: none found; `test_the_marker_tells_apart_string_lists_that_join_alike` covers the encoding.
- **`macro_paths` and `interventions_log` are still rewritten at every flush.** They are a few hundred bytes each. Skipping them would need markers for the registry and the log, for a few milliseconds. Cost if wrong: a few milliseconds a flush.
- **Rewritten tables are hashed from disk.** Hashing the frame in memory would save about 32 ms in a month where accounts opened, but disk stays the only source for dimension hashes. Cost if wrong: 32 ms a month.
- **Five of the 17 tests passed at RED by design.** They guard behaviour the change must keep:
  - rewriting when an account opens;
  - rewriting when a flag changes;
  - month ends matching a full rebuild;
  - the forced rewrite on load and fork;
  - the per-row `branch_code` format.

  `test_the_marker_tells_apart_string_lists_that_join_alike` was written after its helper. It was then run against a naive join and failed. It also caught a real gap: `[]` and `[""]` encoded alike until the count was added. Cost if wrong: none.

## Measured gain

`scripts/bench.py --tier S --days 90 --seed 7`. The first `main` run came first, alone; the other four were interleaved, at a load average of 3 to 6:

| Run | `checkpoint_seconds` (two checkpoints) | `total_seconds` | `build_seconds` |
| :--- | ---: | ---: | ---: |
| `main` | 1.56 | 25.11 | 2.20 |
| branch | 0.47 | 21.52 | 1.60 |
| `main` | 1.47 | 23.10 | 1.67 |
| branch | 0.48 | 21.50 | 1.59 |
| `main` | 1.46 | 22.86 | 1.68 |

Each checkpoint's steps, from two runs of each to 29 June, in ms:

| | `main`, end of April | branch, end of April | `main`, end of May | branch, end of May |
| :--- | ---: | ---: | ---: | ---: |
| Whole save | 729, 739 | 189, 174 | 748, 866 | 306, 311 |
| Flush | 584, 586 | 107, 92 | 590, 701 | 217, 219 |
| Content hashes for `checkpoint.json` | 65, 66 | 1.0, 1.0 | 67, 68 | 1.3, 1.3 |
| Pickle | 60, 65 | 61, 62 | 59, 63 | 56, 59 |
| Hard links | 18, 19 | 18, 19 | 30, 31 | 30, 30 |

The end of April skips the rebuild, since no account opened after the build. Its flush still hashes every dimension once (69 to 85 ms), because it is the world's first flush. The end of May rebuilds with a warm memo. Against a month's simulation at tier S (6.6 s in `docs/phase1d2_results.md`), a checkpoint falls from about 11% to 3–5%. What is left is the pickle (about 60 ms), the hard links (18 to 30 ms) and, in a month where accounts opened, a flush of about 220 ms: the warm rebuild, writing the three tables and hashing them from disk.

Best of five at the end of April, on a quieter machine: the marker takes 10.5 ms, and a rebuild with a warm memo takes 53.7 ms, against 463 ms for a rebuild on `main`.

## Verification

- **Content hashes.** All 20 tables in every bench run equal `main`'s (`content_hash` from `bench.py`). So does every other field the bench prints except timings, memory and the run path.
- **Bytes.** Every Parquet file in the branch's bench folder is byte-identical to `main`'s: 84 in the run and 96 in the two checkpoints' `run/` folders. The 5 JSON files (3 manifests, 2 `checkpoint.json`) are equal once the fields that also differ between two `main` runs are left out: `run_id`, `source_label`, `wall_seconds`, `config_hash` and `config`. `world.pkl` was not compared, since it holds timings.
- **In the tests,** a warm memo's tables equal a plain rebuild's byte for byte, after new accounts open. The flushed tables equal a full rebuild at each step and at month ends, and each checkpoint's tables equal those its loaded world rewrites.
- **Fast suite:** 450 passed (433 before, plus 17).
- **Slow gates** (`-m slow`): 8 passed in 222 s.

# Plan 1d-2 deferred minors tidy-up

The seven minors deferred by plan 1d-2's final review (above). Built on branch `claude/gallant-nightingale-adfe1a` from `main` at `9c1ffe2`, executed inline. Each fix has a test that failed first, then passed.

## Fixes

- **A pay cut reversed onto fresh pay after a helper round trip.**
  - The life course's three helper flips now stamp `life.pay_set`: to helper, back to own-account, and a helper whose household lost its business. So `_restore` sees that the pay was reset.
  - `pay_set` is otherwise read only for raise tenure. Raises go only to the salaried, who are never helpers, so a run without a scenario is unchanged.
  - `test_a_pay_cut_is_not_restored_after_a_helper_round_trip` forces both flips with parameter overrides. It failed with the round-trippers in `PAY_RESTORED`.
- **`link_tree` copied on any `OSError`.** It now copies only for EXDEV, EPERM (Linux, a file system without hard links), EMLINK and ENOTSUP (macOS's code for the same), and raises anything else.
  - The tests patch `os.link` to refuse with each code. EACCES, ENOSPC and EEXIST failed first, since they were copied.
  - The four copy cases passed at RED by design: they guard the fallback.
- **`world.set_hook` on a fresh world that starts mid-month.** It now passes `date=None` before the first day. `test_set_hook_on_a_fresh_world_that_starts_mid_month` failed with "2025-04-15 is not the 1st".
- **Report gaps.** The per-row lines moved, unchanged, into `_log_lines` (`test_report` passed), and then:
  - an intervention effective after `end` gets one line, "takes effect on …, after the end (…): it did nothing in these runs", in place of the others;
  - a DBT transfer whose first credit falls after `end` says it enrolled its payees but paid no credit;
  - the `ChangeRailRule` line names `rail.upi.limit_paise`;
  - a layoff or pay cut whose selected people include no salaried or earning person says "affected nobody: none of the N selected were salaried" (or "earning");
  - one that selected people but drew none says "affected none of the N selected".
  - Tests: `test_report_lines_for_people_selected_but_not_affected_and_for_dates_after_the_end`, on real log rows from a run, and `test_report_names_a_rail_rule_s_parameter`, on a hand-made row. The scheduler reads the UPI limit every day, so no run leaves a rail rule unread within its window.
- **The default experiment digest.** A module swap's entry now carries the SHA-256 of its module's pickle, so experiments that differ only in a module's settings get different folders.
  - Experiments without a module swap keep their digests. The test checks one against the earlier formula, restated; that assertion passed at RED by design. Its digest, `c9d1032e17d7`, is the same on `main`.
- **Scenario DBT credit times.** A scenario scheme draws its slot and second from its intervention's streams, `<stream>.slot` and `<stream>.offset`. The built-in schemes keep `dbt.slot` and `dbt.offset`.
  - At RED, a ₹500 top-up to everyone aged 60 or more on 5 May paid 78 people who also got the old-age pension that day, and all 78 pairs had equal timestamps. Now none do.
  - The pension's own times are unchanged.
- **A `SetPolicyRate` dated before the series' first step.** `check_policy_rate` replays the pending parameter interventions that act before it, in the order they will act, and refuses it if no rate is in force on its date. `world.apply` and `Experiment` construction call it.
  - A macro path that starts earlier, applied first, makes it valid.
  - Both tests failed first: nothing was raised.
- **Spec.** Its passages on `set_hook`, `SetPolicyRate`, scenario DBT credits and the experiment digest now match the code.

## Checks

- **Baseline.** `scripts/bench.py --tier S --days 90 --seed 7` on `main` and on the branch: all 20 tables have equal content hashes, with 15,282,932 payment attempts each.
- **Suites.** Fast: 448 passed in 199 s (433 before, 15 new). Slow gates: 8 passed in 675 s, run beside the experiment below.

## Rulings

- **`ScenarioScheme` gains a required `stream` field, and `_CODE_VERSION` stays 0.0.1.** The `dbt` module's pickled `_results` can hold `ScenarioScheme`s. They are rebuilt at each month start before any credit, so a checkpoint from before this change still loads and runs. Cost if wrong: a load error naming `stream`.
- **`new_value` and `check_policy_rate` are module functions in `active.py`,** so `Experiment` can call them; `Active._new_value` is gone. Cost if wrong: none.
- **EOPNOTSUPP is not in the copy list.** On Linux it equals ENOTSUP. On macOS, `link(2)` documents ENOTSUP for a file system without links. Cost if wrong: such a file system raises instead of copying.
- **`docs/phase1d2_results.md` keeps its figures, with a note.** Its DBT experiment ran before this change, and the arm's credit times now come from the scheme's own streams. Re-run here (`--part experiment --workers 4 --seeds 1-10`, 481 s):
  - the baselines, the payees and the APBS credit effect are identical;
  - every other effect moves by less than 0.1%. At the doc's rounding, the cash interval's top goes from ₹1.619 to ₹1.618 crore. Funds declines go from −6,111.3 to −6,112.2 (interval −6,397.6 to −5,826.8, relative −1.60%);
  - cost if wrong: none; the doc records the 1d-2 branch.

# Merging the two plan 1d-2 follow-ups

Both follow-up branches were combined on `claude/nostalgic-wescoff-b80231` from `main` at `9c1ffe2`, keeping history linear: a fast-forward to the checkpoint commit (`1f83083`), then the deferred-minors commit (`bc59bab`) cherry-picked on top.
- **Conflict.** Only this ledger, where each branch appended a section. Both are kept, checkpoints first. `src/arthasim/world.py`, which both change, merged without a conflict.
- **Bench** (tier S, 90 days, seed 7; `main` at `9c1ffe2` against the combined tree, one run each): all 20 content hashes are equal, and so is every other field the bench prints except timings, memory and the run path. All 180 Parquet files, in the run and in its two checkpoints, are byte-identical. The two checkpoints took 1.53 s in all on `main` and 0.50 s combined.
- **Results doc.** `docs/phase1d2_results.md` keeps its 0.73 s checkpoint figure for the 1d-2 branch, with a note giving the bench figures above.
- **Fast suite:** 465 passed (433 on `main`, plus 17 from the checkpoint branch and 15 from the minors branch).
- **Slow gates** (`-m slow`): 8 passed in 391 s, run alongside the fast suite.

# Plan 1e (calibration and validation) execution ledger

Plan: `docs/superpowers/plans/2026-11-24-arthasim-plan-1e-calibration-validation.md`. Spec: `docs/superpowers/specs/2026-11-24-calibration-validation-design.md`. Sources: `docs/sources/calibration.md`.
Run on an Apple M5 with Python 3.12 (numpy 2.5.5, numba 0.68.1, polars 2.1.0, duckdb 2.0.1, optuna 5.1.0), from a scratch virtual environment with `PYTHONPATH=src`. Built on branch `claude/zealous-saha-789ebb` in its own git worktree, from `main` at `29dd4a6`. Executed inline (native), with one fresh Opus review of the whole branch.

The project owner handed every decision to this session: decide, ground decisions in open data, and record each as a ruling. Source research was done by eight research subagents (WebSearch and WebFetch), and two sources the fetch tool could not read (PIB release 2257087, and NPCI's daily UPI statistics for May to November 2025) were read in the built-in browser.

## Tasks

| Task | Commits | Tests |
| :--- | :--- | :--- |
| 1. Registry rows and source notes | `a56b4dc` | 6 new; fast suite 470 passed and 1 failed (a DBT row-count pin, fixed in the same commit) |
| 2. Manifest config, `validation_report` table | `241cbc9` | 2 new |
| 3. Statistics | `f18547e` | 11 new |
| 4. Hard checks | `b167f07` | 9 new |
| 5. Suite and `run.validate` | `0291936`, fix `a30d816` (spike runs) | 10 new |
| 6. `calibrate` | `46af518`, `d4c3812`, `8fffa1d` (refinement) | 7 new |
| 7. Scripts, the two-stage calibration | `f2edd5a`, `8fffa1d`, `e826d3a` | stage 1: 400 trials, 5,588 s; stage 2: 200 trials, 2,939 s |
| 8. Gate | `e826d3a` | first run red in 128.7 s (no gaps listed), then green in 128.1 s |
| 9. Bench, results, ledger | this commit | see below |

## Reference hashes (before any change)

`scripts/bench.py --tier S --days 90 --seed 7` on `main` at `29dd4a6`: 15,282,932 payment attempts, content hashes:

- `payments`: `cc2f554316011cc46fa809c1e8a4a77af5152f9e05325314145d0e7c0277851f`
- `journal`: `f0ef951399ab4341c6873f61e858b76e48c9c2066d4502500c423a4b4c50ca0f`
- `postings`: `74ce798fcb093d2d27efca27e2f74deb94ca365bb3529a79e78a0d13d9eca27d`
- `truth_household_monthly`: `1bd546cd83747d60c3bc8937ab202b4fac6f19bcfdf4115104cb924e7b0dbdb4`
- `life_events`: `68f07ac0d5aa5042d7f8c64185caae7f216db871f3c0421ed0e32a40216620b1`
- `entity_state_monthly`: `a4f33c4f10272ef69985ee2018f5b7d150c35cd2ad2f809e10cc631658f578b6`
- `truth_dbt_monthly`: `28c0196d70c98df06093fb823a1a183ac1e80d42ac3d1061963c2f7927b5113a`
- `balances_monthly`: `24d59862c0f10f325e1ab6cb64db90832a7c47fd8b544db6aeedbe3f46bd01cf`
- `persons`: `d7043c310e8c25abc3c7a747c66ad6d043abef843994d482371f7e53bf101e65`
- `households`: `2b2926e62729d8a959d5cad439fd6b3262f6d3342f528ff802ad201b3eee66f5`
- `orgs`: `8f40e101b154f650d6b38c8e06b4563fd4c277de3002516d1a3a1ca35ea205d9`
- `banks`: `12db6f6915295866558074d48844a6be1b2a582a6e719d07efd506a7418d8383`
- `accounts`: `694ca5ebdb85b0e3ccb2fef142c86f705df7c2423ca3e5eb9e4f88fe989776b1`
- `instruments`: `fa00df778819d8d5fcf593323d4f6a144bd848e99f8b71f63f2078641a854878`
- `edges`: `62fab05a272b31009f56defce66bd2d69a216c3b9083cd32ba1e1ac6a53f7f0c`
- `geo`: `fbd6aef95b7265da684dec8bcf92b4d7a543ba8c9c5312e1ce4cc2da036957e6`
- `truth_person_latent`: `957e271936f03523ed5ee0b9698eefb362f7bb4188e9e31dc40c58210dab5c42`
- `bank_customers`: `533859ad5f96f63967b0cd764f01d8bf199ca12eae0a0c6c171d6c1a686dcaa9`
- `macro_paths`: `e2248b03c7d8a6b1f1c99d409aaca793f9ef0d22c20166867af1e1955d3a7171`
- `interventions_log`: `eac724afc9e3fafc0941a00c17b01b63897b1ef7fe63bcc5e9b9839e09f238c7`

## Rulings

Each gives the ruling, its grounds, then what it costs if wrong. The spec marks the same decisions **Decided**.

**Sources and the registry**
- Ruling: `verified` means the figure was read in the primary document named, by this plan's research or an earlier plan's. The research subagents fetched documents with WebFetch and read PDFs as text (`pdftotext`); two sources that refused the fetch tool were read in the built-in browser. A ratio of two counts from one table (PMJDY's zero-balance and operative shares) keeps `verified`; a figure that needs a modelling choice (CPI uprating, the 18+ population, the month-start and festival ratios) is `assumption`. Cost if wrong: a reader may want "verified" to mean checked twice by a person; the source notes say who read what and how.
- Ruling: no existing value changes; only sources and statuses do (pinned by `test_no_value_carried_from_main_changed`, which checks the registry version of the 134 old rows against `main`'s). Cost if wrong: inputs that disagree with their sources stay until a later plan changes them; the one found, `inclusion.debit_card_share` (0.7 of account holders, about 62% of adults, against Findex's 37.6% with a debit card), is a finding.
- Ruling: appendix A figures that the sources contradict enter with the source's figure, and the notes say what the design doc carried:
  - "UR graduates aged 21–29: 22.2%" is in no table of PLFS 2025; the row is `labour.ur.graduate_15_29` (Table 21, rural 21.5%, urban 23.2%);
  - "49.6% urban regular" and "62.7% rural self-employed" are in no cell; the report's 47.6% and 62.4% are used;
  - PMJDY's "81.2% operative" and "8.2% zero balance" are from August 2022; the window's 73.6% and 9.15% (Lok Sabha question 20, 1 December 2025) are used;
  - "festival uplift +32%" measures Diwali 2026 against an ordinary 2025 day, or November 2025 against November 2024; the holdout uses October 2025's UPI value per day against the mean of September and November (1.031);
  - AIDIS's ₹15.9 and ₹27.2 lakh are gross assets, not net worth;
  - the SIP figure is September 2026; the row holds FY 2025-26's months;
  - the fraud amount's 22.68 lakh "complaints" are all cybercrime incidents; the amount goes with 19,18,865 financial-fraud complaints.
  Cost if wrong: none; each is read in the primary document.
- Ruling: rows with no source found stay in the registry, honestly marked: `pay.skill_premium` (`unverified`), `pay.switch_jump` and `fraud.actor_share` (`assumption`), `cc_on_upi.value.monthly` (`unverified`, from a news report of a parliamentary answer). Cost if wrong: none; nothing reads them in phase 1.
- Ruling: the savings-balance check against RBI's BSR-2 is dropped. The table is published only on RBI's DBIE portal, which the research could not read, and the Handbook's population-group table mixes in term deposits. The balance check is PMJDY's average (₹4,808). Cost if wrong: month-end balances of savings accounts other than basic ones go unchecked.
- Ruling: `tests/test_dbt_schemes.py` counts only the `dbt.` rows with role `input` (17), since `dbt.cashout_lag` is a holdout; `test_verified_rows_name_where` also accepts a pointer to the source notes, which give the table and page (`macro.cpi_inflation` relies on that). Cost if wrong: none.

**Targets and the suite**
- Ruling: the metro archetype stands for urban India and the rural one for rural India, as the life course's alignment already has it. National figures weight them 0.36 and 0.64 (MoSPI's reprint of the 2026 population projection). Cost if wrong: a metro district is richer than urban India's average; calibration pulls it toward an average town.
- Ruling: the adult population for per-adult rates is 1,016.1 million: persons 15+ on 1 March 2026 less three fifths of the 15–19 band. Cost if wrong: under 1% high for the fiscal year's midpoint.
- Ruling: HCES rupees are uprated by CPI, April–December 2025 over August 2023 – July 2024 (rural 1.0467, urban 1.0501). Cost if wrong: a few percent on the MPCE target against a ±10% band.
- Ruling: section 15.3's "salary-day inflow spike" is checked as UPI value on the 1st to 3rd over the 10th to 25th (NPCI daily statistics, May–September 2025, 1.286). Salary credits are not published by day. Cost if wrong: the spike measured is spending and transfers after pay, not the credits themselves.
- Ruling: the DBT cash-out holdout is Field and others (2022), Table A.5: the only measured distribution of time to withdrawal. Its population is narrow (poor women at bank kiosks in two Madhya Pradesh districts, 2018–19). Cost if wrong: a holdout that represents its population, not India's.
- Ruling: the flow-matrix invariant (6) is not re-checked from a stored run: it needs each holder's sector, which no table records. It is reported as `skipped`, and the run checked it every day. Cost if wrong: a damaged file that keeps every other invariant but breaks sector flows would pass.
- Ruling: the same-seed check rebuilds the run's first month and compares every fact table's month and every dimension table but the three account tables. It is skipped for forked or loaded runs, runs with an intervention in the first month, and secret runs without the secret. Cost if wrong: a divergence after the first month is left to the split-run and resume tests.
- Ruling: every DuckDB sum in a statistic is over integers (paise, counts), divided afterwards, so DuckDB's parallel float sums cannot make a statistic, and so a calibration, depend on thread timing. Three statistics (`consumption.gini`, `labour.stages`, `holdout.festival_uplift`) add floats in Python in the order rows arrive; the final review repeated them four times and got the same bits, and the calibration replayed exactly. Cost if wrong: a last-digit difference between replays.

**Calibration**
- Ruling: calibration worlds are `Config.tier("S", persons=10_000)`: section 5.4 names XS for calibration trials, but `Config.tier("XS")` is the spike builder. Cost if wrong: fitted values that do not carry to 100,000 persons; the gate checks them there.
- Ruling: Optuna's TPE sampler (Optuna 5.1, `multivariate=True`, 20 random start trials), asked one trial at a time, with each trial's seeds in parallel; Optuna becomes a dependency. Cost if wrong: a different Optuna version proposes other values; the fitted file records the version.
- Ruling: trials run eight months (April to November) and score May to November, not section 15.2's three months. Measured: in a 10,000-person world, basic accounts' mean balance rose from ₹5,975 in May to ₹9,145 in August, and monthly spending rose 20% from May to November; a three-month fit would score levels the gate's window does not have. Cost if wrong: trials take about 2.5 times as long.
- Ruling: the fitted set is a committed overrides file (`params/calibration/fitted.yaml`), applied with `CalibrationResult.load(path).apply(config)`; the registry defaults do not change. Cost if wrong: default runs stay uncalibrated until the owner adopts the fitted values as defaults (a follow-up).
- Ruling: stage 1 ran 400 trials rather than the signature's 200, for 14 free parameters; the committed fit is stage 2's 200 trials (next ruling). Cost if wrong: an hour of compute (stage 1 took 93 minutes: later trials, with more purchases a month, run slower).
- Ruling: a second, refining stage. The first search (`params/calibration/stage1.*`, best loss 1.70 at trial 393, counting from 1) left `earn.sigma` at 0.213 against its 0.2 floor and `open.deposit_months_of_income` at 0.102 against 0.1, with the consumption Gini (0.309 and 0.374 against 0.237 and 0.284, +2.4 and +3.0 tolerances) and the basic-account balance (₹6,339 against ₹4,808, +1.3) above their bands. Under the known-gaps rule a fitted miss is first searched harder, so the floors went to 0.05 and 0.02, the returns to education (scaled) and `consumption.buffer_target_months` joined the space, and 200 more trials (sampler seed 1) searched bounds narrowed around the first fit (`calibration.refine`, width 0.25), starting from it. The committed `params/calibration/fitted.yaml` is that second stage. Cost if wrong: the second stage explores a smaller region than a fresh 16-parameter search would.
- Ruling: `calibration.refine` and its test were written together, so the test was not seen red. Cost if wrong: a refine bug a red run would have shown; the test pins every value it returns.

## Findings so far

- **A calibration replays exactly.** The second stage's first trial, stage 1's best proposal run again in fresh worker processes, scored 1.70, the same loss as in stage 1.

**Process**
- Ruling: the spec's predicted gaps were written before the gate's first run (from the code and the uncalibrated bench run): the month-start spike, zero-balance accounts, unemployment by education and of young graduates, UPI P2P volume, the festival holdout, the debit card ticket and P2P tickets under ₹500. The results compare them with the gate. `accounts.inoperative` was first on the list and was taken off before the gate's first run: the uncalibrated bench run showed 28% of basic accounts idle in a single month, which contradicts the stated reason (that every holder transacts every month). Cost if wrong: none.
- Ruling: Task 3's tests were written before `statistics.py`, while the Task 1 suite ran, but were first run after it existed; they were not seen red. Tasks 1, 2, 4, 5 and 6 were run red first. Cost if wrong: a statistic test that would pass against a wrong implementation; each recomputes its value with an independent query.

## Bench (after Tasks 1–7)

`scripts/bench.py --tier S --days 90 --seed 7` on the branch: all 20 content hashes equal the reference above, with 15,282,932 payment attempts in both. Of the other fields the bench prints, only `checkpoint_mb` differs (170.7 on `main`, 170.8 on the branch), apart from timings, memory and the run path: each checkpoint's `world.pkl` is about 19 KB larger (77,589,724 against 77,608,802 bytes in April), because the pickled registry holds the 50 new rows.

## Slow gates (before the plan 1e gate)

The 8 existing slow gates pass on the branch (391.9 s, run beside the calibration).

## The gate's first run against the predictions

The gate first ran with no `gap:` entries and failed, listing the failing checks. The calibrated tier S run (seed 7, April to November) failed 12 checks:
- the 8 predicted before the run, all of them: `labour.ur.educated`, `labour.ur.graduate_15_29`, `payments.upi_p2p_per_adult`, `payments.debit_card_ticket`, `payments.p2p_under_500`, `payments.month_start_spike`, `accounts.zero_balance`, `holdout.festival_uplift`;
- 2 fitted checks that both calibration stages missed at 10,000 persons too: `consumption.gini` and `payments.p2m_under_500`;
- `accounts.inoperative` (13.0% against 26.4%), taken off the predicted list before the run;
- `holdout.dbt_cashout`, by 0.2 points in its 6–15 day window (0.152 against a band from 0.154).

Ruling: each of the 12 is listed with `gap:` and its ruling in `params/validation/core.yaml`. The two calibration findings were searched twice (600 trials) before listing, as the known-gaps rule requires. A holdout is never fitted, so a holdout failure is listed as a finding, not searched away. No tolerance changed. Cost if wrong: a check listed as a gap that a better model or search would pass; the gate fails as soon as one passes, so the list cannot go stale silently.

A stage 1 preview (tier S, same seed, before stage 2 existed) passed `payments.month_start_spike` (1.22) and `holdout.dbt_cashout`; stage 2's fit moved both just outside their bands. The explanation first written here, that the month-start rise came from allowances and not from pay, was wrong: the final review showed salaries rise at the turn of the month at seed 7 (below).

## Findings

- **Calibration halves pay and consumption and cuts card and ATM use.** With registry defaults the tier S run pays regular workers ₹32,823 (rural) and ₹58,995 (urban) a month against PLFS's ₹17,841 and ₹26,247, and MPCE is ₹6,284 and ₹16,096 against ₹4,314 and ₹7,346 (uprated HCES). The fit brings all six pay components and both MPCE components inside their bands.
- **The fitted world makes 2.1 times as many payment attempts** (86.8 million against 41.4 million, April to November): purchases a month are scaled by 2.45 to reach 12 UPI P2M payments per adult a month. It simulates in 58 s against 31 s.
- **The model is not stationary over the window.** On the calibrated run the basic-account mean balance goes from ₹2,962 in May to ₹8,868 in November and MPCE rises about a third, while pay is flat. The seven-month mean passes; single months do not. Households open with 0.08 months of income in the bank and save toward a buffer of 3.27 months.
- **A calibration replays exactly** (above, "Findings so far").
- **The festival ratio is below 1 in the simulation** (0.963): monthly spending does not depend on the month's length, so a 31-day month's value per day is about 30/31 of a 30-day month's.

## Final state (before review)

- Fast suite: 508 passed, 9 deselected (119.5 s). Slow gates: 9 (8 earlier and `test_gate_1e`), run below.
- Not done: the fitted values are not registry defaults (a decision for the owner); the 12 gaps need model work (follow-ups listed in their rulings).

## Final review (plan 1e)

A fresh Opus reviewer read `29dd4a6..0388a80` in passes, ran the fast suite (508), the plan 1e gate (146.5 s) and the bench (all 20 hashes equal), recomputed statistics with its own queries on the stored calibrated run, and made two more tier S runs (stage 1's fit at seed 7; the committed fit at seed 8). Verdict: "with fixes". Four Critical findings (all false statements, under the owner's rule), three Important and eleven Minor.

**Fixed.** Code fixes have tests; those that passed at red are marked.
- **Critical: false statements in the results doc.**
  - "12 of the 29" target and holdout checks: there are 26 (29 counted the hard checks); and "every hard check passes" is now "no hard check fails (the flow-matrix re-check is skipped)".
  - "Only `checkpoint_mb` differs" in the bench: now "apart from timings, memory and the run path".
  - "Every figure below was taken from those runs' output": the stage 1 figures came from an unlisted preview, and the 128 s was the red gate run. The command list now has `phase1e_results.py --part seed` for seed 8 and for stage 1's fit, the gate command, and says which figures come from which run; the gate's green time (128.1 s) and red time (128.7 s) are both given.
  - **The month-start cause.** The gap ruling, the ledger and the results said salaries cause no month-start rise. At seed 7 the largest employer (3,407 salaried) pays on the 2nd and salary value on the 1st to 3rd is 2.63 times that on the 10th to 25th; at seed 8 the largest pays on the 25th and the spike is 0.884. All three texts now say the statistic follows where a few large employers' paydays fall, with the decomposition (`phase1e_results.py`'s `month_start`) at both seeds and for stage 1.
- **Important: a stale validation report.** A fork carried its parent's report and a world that ran on kept its old one. `World.step`, `World.run` (when a day will run) and `_open` (fork and load) now remove the folder's `validation_report.parquet`. `test_a_report_never_outlives_the_run_it_describes` failed first.
- **Important: the DBT holdout's ruling** named no mechanism or follow-up. It now says the fit moved the holdout out of its band (stage 1's fit passes at 0.160; the committed fit gives 0.152 at seed 7 and 0.150 at seed 8), that cash comes out only to cover cash payments, and names a follow-up. The spec gains a clause: a failing holdout is a finding with a ruling whether a missing mechanism or the fit moved it.
- **Important: statistics with no independent recomputation.** New tests recompute unemployment (overall, educated, young graduates), the self-employed share, the Gini (by pairwise differences), the food share, both tickets, both under-₹500 shares, the month-start spike and the inoperative share, and check that a window with no data gives no component for every statistic. That last test was red for two reasons, both fixed: a window outside the run raised a DuckDB catalog error, and per-adult counts returned zero instead of nothing. One commit (`87c79ed`) went in with that test red; the next (`16c7661`) made it pass.
- **Minor, fixed:**
  - the ledger's "green in 128 s", "trial 400" (stage 1's best was trial 393) and "the committed calibration runs 400 trials" (the committed fit is stage 2's 200), and the spec's matching line;
  - the "every statistic sums integers" ruling now says which three statistics add floats in Python, and that they replayed bit for bit;
  - the festival explanation now uses the statistic's own weighting (October's total 0.995 of its neighbours', not the unweighted 0.998);
  - the ledger re-check fails a month-end table that misses an open account, and reports a posting to an unknown account instead of raising (both tests failed first; the open-month damage test passed at red, guarding existing behaviour);
  - an account or customer number that is all digits fails at any length, as the spec says (test failed first);
  - a saved calibration leaves out `out_dir` (the committed `fitted.yaml` and `stage1.yaml` were rewritten without the machine path; best values, losses and trials unchanged, checked on load);
  - `calibrate(log=...)` rewrites the trials table after every trial, and `scripts/calibrate.py` uses it;
  - the report's bound flag is now "near a bound": within 5% of the range on the parameter's own scale (stage 2: `earn.base_paise` and `attr.digital.upi_threshold`; the results say so, with the narrowed deposit floor);
  - a new hard check, `registry`, compares the run's registry version with the one its config now loads;
  - DBT cash-out counts only withdrawals at or after the credit (`cashout_bins`, with a hand-made test that failed first; d0_5 on the gate run moves from 0.2418 to 0.2407);
  - review-focus tests: three workers with two seeds (passed at red), a determinism skip for an intervention in the first month (passed at red), every free parameter an input `assumption` (passed at red);
  - every gap ruling names a follow-up.

**Rulings on the reviewer's "declined to judge" list.**
- **No reconciliation of `payments` with `journal` and `postings`.** Not among section 7.3's invariants; the settlement writes all three in one step. Stands; follow-up candidate: a hard check that every successful payment has its journal entry.
- **Determinism for runs from older code.** Runs without a recorded config are skipped; `_CODE_VERSION` is static, so a code change that alters output shows as a failure. Stands.
- **Paths from `_ROOT`.** The project's existing pattern. Stands.
- **`labour.stages` nearly a tautology.** It checks that alignment holds at tier S over the window, as the spec defines. Stands.
- **Gaps listed per check, not per component.** A regression in a passing component of a gapped check (for example DBT 0–5 days) is hidden from the gate, though the report shows it. Stands as the spec's design; cost: such a regression is seen only in the report.
- **A simulated May–November spike against a published May–September one, and HCES definitions.** Spec decisions. Stand.
- **Memory of the ledger re-check beyond tier S.** Out of scope.
- **Primary-document figures.** The reviewer checked arithmetic, derivations and the CSV, not the PDFs; the research read them (source notes).
- **Seed sensitivity of the gate.** At seed 8 the committed fit fails the same 12 checks (measured after the fixes).

**Deferred.** None of the reviewer's findings is left open.
