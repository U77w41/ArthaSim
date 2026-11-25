# Calibration and validation: results

Measured on 25 November 2026 at tier S (100,000 adults, each standing for 50), on an Apple M5 with Python 3.12, numpy 2.5.5, numba 0.68.1, polars 2.1.0, duckdb 2.0.1 and optuna 5.1.0, with `PYTHONPATH=src` from a scratch virtual environment.
- **Before:** `main` at `29dd4a6`.
- **After:** this branch, `claude/zealous-saha-789ebb`.

Spec: `docs/superpowers/specs/2026-11-24-calibration-validation-design.md`. Plan: `docs/superpowers/plans/2026-11-24-arthasim-plan-1e-calibration-validation.md`. Sources: `docs/sources/calibration.md`. Ledger: the "Plan 1e" section of `docs/superpowers/ledger.md`.

Commands:
- `python scripts/calibrate.py --trials 400 --workers 3` (stage 1), then `python scripts/calibrate.py --around params/calibration/stage1.yaml --width 0.25 --trials 200 --sampler-seed 1 --workers 3` (stage 2, the committed fit);
- `python scripts/phase1e_results.py`: tier S, seed 7, 1 April to 30 November 2025, once with the committed fit and once with registry defaults, each validated with the core suite;
- `python scripts/phase1e_results.py --part seed --seed 8` (the committed fit at seed 8) and `python scripts/phase1e_results.py --part seed --seed 7 --fitted params/calibration/stage1.yaml` (stage 1's fit at seed 7), each validated, with the month-start decomposition;
- `python -m pytest -m slow tests/test_gate_1e.py`;
- `python scripts/bench.py --tier S --days 90 --seed 7` on `main` and on the branch.

Every figure below comes from those commands' output and from the committed calibration files and reports. The results script was run twice, before and after the final review's fixes; the figures are from the second run except where a section says otherwise.

## What changed

- **The registry is pinned to sources.** It has 184 rows, up from 134: 50 targets, holdouts and appendix A rows. Every target and holdout cites its document and URL, and `docs/sources/calibration.md` gives each figure's table and page and every derivation. No value of the 134 earlier rows changed (a test pins their registry version against `main`'s).
- **`calibrate(config, params, ...)`** fits free parameters by simulation with Optuna's TPE sampler and returns a `CalibrationResult` (`best`, `apply`, `save`, `load`, `report`). The committed fit is `params/calibration/fitted.yaml`, applied with `CalibrationResult.load(path).apply(config)`. Registry defaults are unchanged, so default runs are not calibrated.
- **`run.validate(suite="core")`** runs 4 hard checks, 24 target checks and 2 holdouts (`params/validation/core.yaml`) and writes `validation_report.parquet` into the run. A report is removed when its world runs on, forks or loads, so it never describes another run.
- **A slow gate,** `tests/test_gate_1e.py`, validates a calibrated tier S run from April to November 2025.
- **The run manifest records the config** (without any release secret), so a stored run can be rebuilt and validated.

## Sources

| Status | `main` | Branch |
| :--- | ---: | ---: |
| `verified` (read in the primary document named) | 2 | 50 |
| `unverified` | 17 | 9 |
| `assumption` | 115 | 125 |

On the branch, 37 rows are targets, 2 holdouts and 145 inputs; on `main` every row was an input. Of the 17 rows `unverified` on `main`, 7 are now `verified` (for example `rail.upi.limit_paise` and `inclusion.account_ownership`), 3 are `assumption` because their values are derived or chosen (`life.study.max_age`, `life.within.farm_nonfarm`, `life.switch.monthly_prob`), and 7 stay `unverified`.

Nine figures the design doc's appendix A carried turned out to be something else when read in the source:
- PLFS has no "graduates aged 21–29" table, and neither 49.6% (urban regular) nor 62.7% (rural self-employed) appears in the report.
- PMJDY's 81.2% operative and 8.2% zero-balance are from August 2022. The window has 73.6% and 9.15%.
- The "+32%" Diwali UPI uplift compares Diwali 2026 with an ordinary day of 2025.
- AIDIS's ₹15.9 and ₹27.2 lakh are gross assets, not net worth.
- The SIP figure is September 2026.
- The fraud loss's "22.68 lakh complaints" are all cybercrime incidents; the loss belongs with 19,18,865 complaints.

## The calibration

Fitted on worlds of 10,000 persons (tier S's districts), each trial running April to November 2025 for seeds 1, 2 and 3 and scored on May to November.

| | Stage 1 | Stage 2 (committed) |
| :--- | ---: | ---: |
| Free parameters | 14 | 16 |
| Trials | 400 | 200 |
| Wall time, 3 workers | 5,588 s | 2,939 s |
| Best loss (trial, counting from 1) | 1.700 (393) | 0.877 (200) |

The loss is the mean squared error in tolerances: 1 means every fitted target at its band's edge. Stage 1 ended with `earn.sigma` and `open.deposit_months_of_income` near their floors and the consumption Gini above its band, so stage 2 lowered those floors, added the returns to education (as a scale) and `consumption.buffer_target_months`, and searched around stage 1's fit, starting from it. Stage 2's first trial reran stage 1's best proposal in fresh worker processes and returned the same loss to the last digit (1.6999856529352055), with every statistic equal. Stage 2's best came at its last trial, so a longer search might have gone lower.

Fitted values (stage 2):

| Parameter | Registry default | Fitted |
| :--- | ---: | ---: |
| `earn.base_paise` | 1,200,000 | 985,804 |
| `earn.premium.metro` | 0.25 | 0.105 |
| `earn.sigma` | 0.45 | 0.105 |
| `earn.return_by_education`, scale | ×1 | ×0.384 |
| `earn.stage_multiplier` self-employed / farm / casual | 0.9 / 0.5 / 0.4 | 1.007 / 0.899 / 0.525 |
| `consumption.spend_share` | 0.85 | 0.902 |
| `consumption.purchases_per_month`, scale | ×1 | ×2.454 |
| `consumption.ticket_sigma` | 0.6 | 1.277 (upper bound 1.3) |
| `consumption.buffer_target_months` | 3.0 | 3.269 |
| `rail.choice.upi_preference` | 0.85 | 0.438 |
| `attr.digital.upi_threshold` | 0.45 | 0.280 |
| `rail.choice.card_preference` | 0.5 | 0.0219 |
| `spike.cash_withdrawal_paise` | 200,000 | 722,478 |
| `open.deposit_months_of_income` | 0.8 | 0.0791 |

Full bounds, scores and the loss path are in `params/calibration/fitted_report.md` and `stage1_report.md`. Stage 2 searched bounds narrowed around stage 1's values, so lowering the space's floor for `open.deposit_months_of_income` to 0.02 did not reach stage 2, whose floor for it was 0.068. Two stage 2 values are within 5% of their narrowed bounds, on each parameter's own scale: `earn.base_paise` (985,804 against 1,019,943) and `attr.digital.upi_threshold` (0.280 against 0.287). With its best at its last trial, stage 2 had not converged. At 10,000 persons, 13 of the 16 fitted target components were inside their bands; the three outside were the consumption Gini (0.280 and 0.335) and UPI P2M payments under ₹500 (0.969).

## The gate: the core suite on a calibrated tier S run

Seed 7 (not a calibration seed), 1 April to 30 November 2025, window May to November. 86,818,159 payment attempts.

**Hard checks:** none fails; 15 of the 16 hard rows pass. The ledger re-check holds in every month and at every month end, April to November; the rebuild of April matches all 8 fact tables and 7 dimension tables; none of the 781,845 identifiers checked (PAN-shaped, Aadhaar and mobile tokens, branch codes, account and customer numbers, cards, VPAs) is in a real format; the registry is the one the run was made with. The flow-matrix invariant is `skipped`: no table records each holder's sector, and the run checked it every day.

**Target checks and holdouts,** calibrated against the same run with registry defaults:

| Check | Component | Published | Band | Calibrated | | Default | |
| :--- | :--- | ---: | :--- | ---: | :--- | ---: | :--- |
| `labour.stages` (largest gap) | each area and sex | 0 | at most 0.02 | 0.000 | pass | 0.000 | pass |
| `labour.ur` | rural | 0.024 | 0.014 to 0.034 | 0.022 | pass | 0.022 | pass |
| | urban | 0.048 | 0.038 to 0.058 | 0.048 | pass | 0.048 | pass |
| `labour.ur.educated` | rural | 0.060 | 0.040 to 0.080 | 0.027 | fail | 0.027 | fail |
| | urban | 0.072 | 0.052 to 0.092 | 0.051 | fail | 0.051 | fail |
| `labour.ur.graduate_15_29` | rural | 0.215 | 0.185 to 0.245 | 0.082 | fail | 0.082 | fail |
| | urban | 0.232 | 0.202 to 0.262 | 0.127 | fail | 0.127 | fail |
| `labour.share.regular_salaried` | rural | 0.141 | 0.111 to 0.171 | 0.145 | pass | 0.145 | pass |
| | urban | 0.476 | 0.446 to 0.506 | 0.485 | pass | 0.485 | pass |
| `labour.share.self_employed` | rural | 0.624 | 0.594 to 0.654 | 0.619 | pass | 0.619 | pass |
| | urban | 0.404 | 0.374 to 0.434 | 0.398 | pass | 0.398 | pass |
| `pay.regular_monthly` (₹) | rural | 17,841 | 16,057 to 19,625 | 18,656 | pass | 32,823 | fail |
| | urban | 26,247 | 23,622 to 28,872 | 24,543 | pass | 58,995 | fail |
| `pay.casual_daily` (₹) | rural | 433 | 390 to 476 | 415 | pass | 553 | fail |
| | urban | 549 | 494 to 604 | 550 | pass | 1,002 | fail |
| `pay.self_employed_monthly` (₹) | rural | 12,266 | 10,426 to 14,106 | 13,362 | pass | 15,659 | fail |
| | urban | 23,012 | 19,560 to 26,464 | 21,229 | pass | 44,137 | fail |
| `consumption.mpce` (₹, uprated) | rural | 4,314 | 3,883 to 4,746 | 4,432 | pass | 6,284 | fail |
| | urban | 7,346 | 6,612 to 8,081 | 6,747 | pass | 16,096 | fail |
| `consumption.gini` | rural | 0.237 | 0.207 to 0.267 | 0.283 | fail | 0.387 | fail |
| | urban | 0.284 | 0.254 to 0.314 | 0.337 | fail | 0.437 | fail |
| `consumption.food_share` | rural | 0.470 | 0.440 to 0.500 | 0.461 | pass | 0.460 | pass |
| | urban | 0.397 | 0.367 to 0.427 | 0.402 | pass | 0.402 | pass |
| `payments.upi_p2m_per_adult` (a month) | all | 12.2 | 9.1 to 15.2 | 12.9 | pass | 7.9 | fail |
| `payments.upi_p2p_per_adult` | all | 7.1 | 5.4 to 8.9 | 1.16 | fail | 0.82 | fail |
| `payments.debit_card_per_adult` | all | 0.107 | 0.080 to 0.134 | 0.127 | pass | 0.983 | fail |
| `payments.atm_per_adult` | all | 0.441 | 0.331 to 0.551 | 0.414 | pass | 1.475 | fail |
| `payments.atm_ticket` (₹) | all | 5,286 | 4,229 to 6,343 | 5,986 | pass | 3,022 | fail |
| `payments.debit_card_ticket` (₹) | all | 3,420 | 2,565 to 4,275 | 70 | fail | 368 | fail |
| `payments.p2m_under_500` | all | 0.860 | 0.810 to 0.910 | 0.968 | fail | 0.722 | fail |
| `payments.p2p_under_500` | all | 0.590 | 0.540 to 0.640 | 0.168 | fail | 0.066 | fail |
| `payments.month_start_spike` | all | 1.286 | 1.186 to 1.386 | 1.166 | fail | 1.159 | fail |
| `balances.basic_mean` (₹) | all | 4,808 | 3,606 to 6,010 | 5,705 | pass | 14,151 | fail |
| `accounts.zero_balance` | all | 0.0915 | 0.0615 to 0.1215 | 0.004 | fail | 0.003 | fail |
| `accounts.inoperative` | all | 0.264 | 0.214 to 0.314 | 0.130 | fail | 0.088 | fail |
| `holdout.festival_uplift` | all | 1.031 | 1.016 to 1.046 | 0.963 | fail | 0.965 | fail |
| `holdout.dbt_cashout` | 0–5 days | 0.179 | 0.099 to 0.259 | 0.241 | pass | 0.295 | fail |
| | 6–15 days | 0.234 | 0.154 to 0.314 | 0.152 | fail | 0.178 | pass |
| | 16–30 days | 0.173 | 0.093 to 0.253 | 0.165 | pass | 0.153 | pass |

Targets with monthly values use May to November: the P2M target is the months' mean UPI volume times 0.63, divided by 1,016.1 million adults.

In all, 27 of the 42 target and holdout components pass on the calibrated run and 12 checks fail; with registry defaults, 14 components pass and 21 checks fail. The committed fit at seed 8 fails the same 12 checks. Calibration brought every fitted check except two into its band at tier S: pay (all six components), MPCE, UPI P2M, debit card and ATM counts, the ATM ticket and the basic-account balance. The two exceptions, the Gini and P2M tickets under ₹500, were already outside their bands at 10,000 persons.

## Known gaps

The gate passes because every failing check is listed in the suite with a ruling (`gap:`), and every listed check fails. A gap stays a failure in the report. Eight were predicted, from the code and the uncalibrated bench run, before the gate's first run; all eight failed:

| Check | Why |
| :--- | :--- |
| `labour.ur.educated`, `labour.ur.graduate_15_29` | Life stages carry no education gradient beyond the build's priors |
| `payments.upi_p2p_per_adult` | The model's P2P flows are allowances, remittances and some earnings; informal person-to-person payments are not modelled |
| `payments.debit_card_ticket` | The rail choice does not depend on the amount, so cards carry ordinary small purchases |
| `payments.p2p_under_500` | Simulated P2P payments are mostly large allowances and earnings |
| `payments.month_start_spike` | Employer paydays are drawn uniformly over days 1–28 for each employer, not at the turn of the month (see below) |
| `accounts.zero_balance` | Every account opens with a deposit or a DBT credit, and withdrawals leave the part below a whole note |
| `holdout.festival_uplift` | The model has no festival behaviour |

Four were not predicted:
- **`consumption.gini`:** a calibration finding. Two searches could not bring consumption inequality into the band, even with pay dispersion and the returns to education fitted low.
- **`payments.p2m_under_500`:** a calibration finding. The UPI P2M count needs many purchases a month, which makes tickets small; the rail choice does not depend on the amount.
- **`accounts.inoperative`:** 13.0% of basic accounts had no transaction their holder made over May to November, against 26.4% inoperative for two years in PMJDY. The model has no account that is opened and then never used. This check was on the predicted list at first and was taken off before the gate's first run, because the uncalibrated run had 28% of basic accounts idle in a single month.
- **`holdout.dbt_cashout`:** the 6–15 day share is 0.152 against a band from 0.154 (0.150 at seed 8); the 0–5 and 16–30 day shares pass. The fit moved it out of its band: with stage 1's fit it passes at seed 7 (0.160). With registry defaults it is the 0–5 day share that fails (0.295). Cash comes out only to cover cash payments, never because a credit landed.

Two of the predicted failures did not fail the way the prediction said:
- **The month-start spike depends on the seed.** Paydays are uniform for each employer, but employer sizes are skewed, so the statistic follows where a few large employers' paydays fall. Purchases do not follow pay, and allowances are paid the day after the payer's payday. Value on the 1st to 3rd over the 10th to 25th, May to November:

  | Run | Spike | Salaries | Allowances (all rails) | UPI P2M | Largest employer's payday |
  | :--- | ---: | ---: | ---: | ---: | :--- |
  | Committed fit, seed 7 | 1.166 | 2.63 | 1.66 | 0.985 | the 2nd (3,407 salaried) |
  | Committed fit, seed 8 | 0.884 | 0.40 | 0.64 | 0.987 | the 25th (2,301 salaried) |
  | Stage 1's fit, seed 7 | 1.220 | 2.62 | 1.71 | 0.985 | the 2nd |

  Stage 1's fit passed the check at seed 7 (1.220, inside 1.186 to 1.386). The prediction's reason, uniform paydays, stands; its wording, that salaries cause no month-start rise, was wrong at seed 7.
- **The festival ratio** is below 1 (0.963), not merely flat: simulated monthly spending does not depend on the month's length, so a 31-day month's value per day is about 30/31 of a 30-day month's. With the statistic's weighting, October's total is 0.995 of the mean of September's and November's (0.963 × 31 / 30).

## The model drifts over the window

The window's averages hide a trend. Month by month on the calibrated tier S run:

| Month | Basic-account mean balance (₹) | MPCE rural (₹) | MPCE urban (₹) | UPI P2M per adult | Regular pay, rural (₹) |
| :--- | ---: | ---: | ---: | ---: | ---: |
| May | 2,962 | 3,744 | 5,705 | 12.0 | 18,575 |
| June | 3,629 | 3,989 | 6,099 | 12.3 | 18,633 |
| July | 4,520 | 4,271 | 6,491 | 12.6 | 18,663 |
| August | 5,595 | 4,468 | 6,877 | 13.1 | 18,666 |
| September | 6,615 | 4,681 | 7,132 | 13.3 | 18,685 |
| October | 7,678 | 4,851 | 7,366 | 13.5 | 18,681 |
| November | 8,868 | 5,023 | 7,560 | 13.6 | 18,692 |

Pay is steady, but balances triple and spending rises a third over seven months: households open with 0.08 months of income in the bank (the fitted value), save towards their buffer target, and spend more as buffers fill. The basic-account balance passes on its seven-month mean (₹5,705), while May (₹2,962) and November (₹8,868) are both outside the band. A model that started near its buffer target, or calibration over a later window, would show whether this is the start-up transient or a trend that keeps going.

## Default runs are unchanged

`scripts/bench.py --tier S --days 90 --seed 7`: all 20 content hashes on the branch equal `main`'s, with 15,282,932 payment attempts in both. Apart from timings, memory and the run path, the only field the bench prints that differs is `checkpoint_mb` (170.7 against 170.8): each checkpoint pickles the registry, which now has 50 more rows (about 19 KB).

## Costs

| | Calibrated | Default |
| :--- | ---: | ---: |
| Payment attempts, April to November | 86,818,159 | 41,368,818 |
| Simulation, first and second run of the results script | 58.0 s, 117.1 s | 31.0 s, 57.0 s |
| `run.validate("core")`, same two runs | 69.8 s, 129.9 s | 29.8 s, 54.0 s |

The two runs of the same command differ by about a factor of two; the machine was not otherwise measured, so treat the timings as rough. The calibrated world makes 2.1 times as many payment attempts as the default one: purchases a month are scaled by 2.45 to reach the UPI P2M count. The gate test took 128.1 s when green (its first, red run 128.7 s). Calibration trials averaged 14.0 s (stage 1) and 14.7 s (stage 2) at 10,000 persons with three workers; part of that time other runs shared the machine.

## Phase 1's exit criterion

Architecture section 18 asks that "Phase 1 acceptance checks pass at tier S". On the committed calibration no hard check fails (the flow-matrix re-check is skipped) and 12 of the 26 target and holdout checks fail, so the criterion is **not met**. The failures are listed above with their causes. Nine need behaviour the model does not have: an education gradient in unemployment (2 checks), informal P2P transfers (2), rail choice that depends on the amount (1), paydays at the turn of the month (1), accounts left empty or unused (2) and festival spending (1). One is the DBT cash-out holdout, missed by 0.2 points in one of its three windows, which the fit moved out of its band. Two, the consumption Gini and P2M tickets under ₹500, are calibration findings: two searches could not fit them.
