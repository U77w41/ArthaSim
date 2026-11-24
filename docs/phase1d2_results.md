# Scenarios and experiments: results

Measured on 24 November 2026 at tier S (100,000 adults, each standing for 50), on an Apple M5 with Python 3.12, numpy 2.5.5, numba 0.68.1, polars 2.1.0 and duckdb 2.0.1, with `PYTHONPATH=src` from a scratch virtual environment.
- **Before:** `main` at `21eecc9`.
- **After:** this branch.

Spec: `docs/superpowers/specs/2026-11-23-scenarios-experiments-design.md`. Plan: `docs/superpowers/plans/2026-11-24-arthasim-plan-1d2-scenarios-experiments.md`.

Commands:
- `python scripts/bench.py --tier S --days 90 --seed 7` on `main` and on the branch;
- `python scripts/phase1d2_results.py --part checkpoint`;
- `python scripts/phase1d2_results.py --part experiment --seeds 1-10`, once with `--workers 4` and once with `--workers 1`.

The runs went one after another, so their timings do not overlap. Every figure below was re-queried from those runs' folders. The experiment's per-seed differences were recomputed with SQL on the payment files.

## What changed

- **Checkpoints.**
  - `world.save(path)` and `World.load(path)` work at any month end. `world.fork()` copies a world in memory, and `run.fork_at(date)` starts a new world from the run's own checkpoint.
  - Every run keeps a checkpoint at each month end, in `<run>/checkpoints/<YYYY-MM>/`. `checkpoints=False` turns this off.
  - A checkpoint holds neither the release secret nor any key derived from it. Loading one from a run that had a secret needs the secret again.
- **Interventions.** `ParamOverride`, `ChangeRailRule` (the UPI per-transaction limit), `MacroPath`, `SetPolicyRate`, `IncomeShock` (layoffs and pay cuts), `ExpenseShock` (medical), `DBTTransfer` and `SetHook` (a behaviour module swap). They are applied with `world.apply`, or as a `Scenario` passed to `world.run`.
- **Experiments.**
  - `Experiment(config, baseline, treatments, seeds, intervene_at, end).run(workers)` returns an `ExperimentResult`.
  - `effect(metric, by=...)` gives the mean paired difference across seeds with a Student-t interval, over the arms' window by default.
  - `sweep(param_id, values)` reruns the experiment at each value of one parameter. `report(path)` writes Markdown.
- **Two new run tables.** `macro_paths` holds the RBI repo-rate and CPI paths from `docs/sources/macro.md`, with any changes. `interventions_log` has one row per applied intervention.

## A run without a scenario is unchanged

The branch's 90-day bench run has the same content hash as `main`'s for all 18 of `main`'s tables. The two new tables, `macro_paths` and `interventions_log`, are the only additions. Both runs make 15,282,932 payment attempts.

| | `main` | Branch |
| :--- | ---: | ---: |
| Simulation, 90 days | 21.2 s | 19.7 s |
| Peak memory | 839 MB | 1,026 MB |
| Monthly checkpoints | none | two, 1.47 s and 170.7 MB in all |

Simulation time excludes the checkpoints. The branch was not slower, though with one run each the 1.5 s gap means little. Peak memory rose by 187 MB. That is most likely the monthly checkpoint, which pickles a 78 MB world and rebuilds the account tables; it was not measured separately.

## A resumed run is byte for byte an uninterrupted one

Two runs at tier S, seed 7, from 1 April 2025:
- **Plain:** an uninterrupted run to 31 July 2025.
- **Resumed:** a run to 31 May (61 days), `save`, `World.load`, then a run on to 31 July.

| | |
| :--- | :--- |
| Parquet files | 108 in each run (dimension and metadata tables, and four months of each fact table) |
| Files with equal SHA-256 | all 108 |
| Manifest content hashes | equal |
| Manifest fields that differ | `run_id` (`plain`, `resumed`); `source_label`; `wall_seconds` (27.713, 27.942); `forked_from` (null, `{"run_id": "saved", "month": "2025-05", "how": "load"}`) |

The slow gate `tests/test_gate_1d2.py` checks the same thing.

### Costs

At the end of May, at tier S:

| | |
| :--- | ---: |
| `world.pkl` | 77.7 MB |
| `checkpoint.json` | 2.8 kB |
| `save` | 0.74 s |
| `fork` | 1.30 s |
| `World.load`, including re-hashing the 61 days from disk | 3.24 s |

The checkpoint folder's `run/` holds hard links to the run's own files, so it adds almost no disk.

A save takes longer than the spec estimated (under 0.2 s a month). A profile of one save at the end of April:
- **0.58 s:** the flush a save must make first, which rewrites the accounts, instruments and bank-customer tables and the manifest;
- **0.064 s:** dimension content hashes;
- **0.060 s:** the pickle, as the spec estimated;
- **0.018 s:** the hard links.

So a monthly checkpoint costs about 0.73 s, about 11% of a month's simulation at tier S (6.6 s), and about 85 MB of disk. The flush is the obvious target if that matters; see Limits.

## A paired experiment: ₹2,000 to every own-account farmer

The experiment:
- **Baseline:** no interventions.
- **Arm `dbt_2000`:** `DBTTransfer("DBT_2000", 2000, "life_stage == 'farm' and not helper", ["2025-11-15"])`, a credit of ₹2,000 by APBS on 15 November 2025.
- **Dates:** a shared prefix from 1 April to 31 October 2025, intervening on 1 November, ending on 31 December.
- **Seeds:** 1 to 10.
- **Measured:** 1 November to 31 December.
- **Intervals:** 95%, Student-t with 9 degrees of freedom on the ten per-seed differences.

The payees number 12,824 to 12,954 per seed, a mean of 12,902.2. In every seed, the difference in APBS credits equals that seed's payees exactly. In seed 1 the payees are 1,747 in the metro district and 11,207 in the rural one. The transfer is ₹2.58 crore per seed (12,902.2 × ₹2,000).

| Outcome, 1 Nov to 31 Dec | Baseline (mean) | Effect | 95% interval | Relative |
| :--- | ---: | ---: | :--- | ---: |
| APBS credits | 17,545.0 | +12,902.2 | 12,871.0 to 12,933.4 | +73.5% |
| Cash withdrawals | ₹173.95 crore | +₹1.569 crore | ₹1.520 to ₹1.619 crore | +0.90% |
| — November | ₹86.14 crore | +₹0.975 crore | ₹0.952 to ₹0.998 crore | +1.13% |
| — December | ₹87.81 crore | +₹0.594 crore | ₹0.561 to ₹0.627 crore | +0.68% |
| — rural district | ₹42.46 crore | +₹1.443 crore | ₹1.408 to ₹1.478 crore | +3.40% |
| — metro district | ₹131.49 crore | +₹0.126 crore | ₹0.093 to ₹0.160 crore | +0.10% |
| Consumption | ₹3,611.46 crore | +₹1.676 crore | ₹1.669 to ₹1.682 crore | +0.46% |
| Funds declines (count) | 383,209.7 | −6,111.3 | −6,396.1 to −5,826.5 | −1.59% |

Amounts are for the 100,000 simulated adults; multiply by 50 for the population they stand for.

**What it says.**
- **Cash and spending.** Recipients withdrew ₹1.57 crore in cash, 61% of the transfer, and spent ₹1.68 crore more on goods, services and bills, 65% of it. The two overlap, since withdrawn cash pays for cash purchases.
- **Timing.** Most of the cash effect falls in November, the pay month, because the transfer counts as household income only in the month it is paid (spec, `DBTTransfer`). December's smaller effect comes from the higher balances carried into that month's budget.
- **Place.** The effect is concentrated in the rural district, home to 87% of seed 1's payees.
- **Declines.** Funds declines fall, since recipients have more money in their accounts.
- **Precision.** The intervals are narrow because pairing removes the noise the arms share. The per-seed cash differences range from ₹1.463 to ₹1.664 crore.

**Workers and cost.**

| | 1 worker | 4 workers |
| :--- | ---: | ---: |
| Wall time, 10 seeds | 810.8 s | 394.1 s |
| Peak memory | 1,561 MB (one process) | 199 MB parent, 1,120 MB the largest worker |

Every run of the two experiments has the same content hashes, and every effect above is identical with 1 and 4 workers. Each seed simulates 336 days: 275 for the baseline, and 61 for the arm forked on 1 November.

`ExperimentResult.report` wrote a Markdown report for each run. Its intervention table gives `affected` = 12,954 for seed 1, the payees. It lists the 75 assumption-status parameters the runs read, each with its source. Their values await plan 1e's calibration.

## Tests

- **Fast suite:** 426 passed (333 on `main`), in 174 s.
- **Slow gates:** the two new gates pass in 122 s:
  - a resume at tier S is byte-identical;
  - a two-seed experiment with a DBT tranche on 15 June 2025 returns a cash-withdrawal effect with an interval, and its APBS difference equals the payees in each seed.

## Limits

- **Macro paths have no effect yet.** By the owner's choice, `MacroPath` and `SetPolicyRate` change the recorded paths and nothing reads them in phase 1.
- **Ten seeds.** The interval is a Student-t interval on ten differences. With skewed differences its coverage would be off. The report states n.
- **Checkpoint cost.** A monthly checkpoint costs about 0.73 s at tier S, mostly the flush of the account tables, against the spec's estimate of under 0.2 s. Rewriting those tables only when they have changed would recover most of it.
- **One world shape.** The experiment's effects are for this model's farmers and its rules for spending transfer income. They are not estimates for India; plan 1e calibrates and validates the model.
