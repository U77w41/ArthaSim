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

The slow gate `tests/test_gate_1d2.py` checks the same thing. The SHA-256 of every file is listed in the appendix.

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

After this plan, a later change rewrites the account tables only when their inputs have changed (ledger, "Cheaper monthly checkpoints execution ledger"). In one bench run each (tier S, 90 days, seed 7), the two monthly checkpoints took 1.53 s in all before it and 0.50 s after, about 0.25 s a month. All 180 Parquet files and all 20 content hashes are byte-identical.

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
| Consumption | ₹361.15 crore | +₹1.676 crore | ₹1.669 to ₹1.682 crore | +0.46% |
| Funds declines (count) | 383,209.7 | −6,111.3 | −6,396.1 to −5,826.5 | −1.59% |

Amounts are for the 100,000 simulated adults; multiply by 50 for the population they stand for.

After this plan, a later fix gave scenario DBT schemes their own streams for credit times. Re-run with it, the baselines and the APBS credit effect are identical, and every other effect moves by less than 0.1%. Funds declines become −6,112.2 (−1.60%), and the cash interval's top ₹1.618 crore. See the ledger's "Plan 1d-2 deferred minors tidy-up".

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

- **Fast suite:** 433 passed (333 on `main`). With the eight slow gates, 441 passed in 581 s.
- **Slow gates:** the two new gates pass in 122 s:
  - a resume at tier S is byte-identical;
  - a two-seed experiment with a DBT tranche on 15 June 2025 returns a cash-withdrawal effect with an interval, and its APBS difference equals the payees in each seed.

## Limits

- **Macro paths have no effect yet.** By the owner's choice, `MacroPath` and `SetPolicyRate` change the recorded paths and nothing reads them in phase 1.
- **Ten seeds.** The interval is a Student-t interval on ten differences. With skewed differences its coverage would be off. The report states n.
- **Checkpoint cost.** A monthly checkpoint costs about 0.73 s at tier S, mostly the flush of the account tables, against the spec's estimate of under 0.2 s. Rewriting those tables only when they have changed would recover most of it. A later change does this; see the note under Costs.
- **One world shape.** The experiment's effects are for this model's farmers and its rules for spending transfer income. They are not estimates for India; plan 1e calibrates and validates the model.

## Appendix: the hash of every data file

SHA-256 of each Parquet file of the plain run. The resumed run's files have the same hashes, line for line (compared with `cmp` on the two lists).

| File | SHA-256 |
| :--- | :--- |
| `accounts.parquet` | `76981d98a2789d294c61de1a6207c966fc5c2a4f704cc8c403fdeeec723ed4f5` |
| `balances_monthly/month=2025-04/part-0.parquet` | `77fe6385e32f9343b532eca1551df456056be4167d09a43f36e99d9da7c1b4f0` |
| `balances_monthly/month=2025-05/part-0.parquet` | `70e871e6c50287be4ff621237615765604b99c4ca0213251195d1ba1b9256650` |
| `balances_monthly/month=2025-06/part-0.parquet` | `652c2418cf6e54daee0c6944487130515a941d995bf26c0cb943e0d5a6c7654e` |
| `balances_monthly/month=2025-07/part-0.parquet` | `a2738ad08e7f281afcc8ce449c76c99faddc41690036a8cd9f112a351453ff64` |
| `bank_customers.parquet` | `eacdbe21f6a44b20026deff53fa39e9f104a03078f6afb01c1a74ea19102603f` |
| `banks.parquet` | `722f75e21e3e794da71942b14fd3fbcab8f5d27ce57713145ec3abacf9c2c1df` |
| `edges.parquet` | `7a0147da41ebc077fdb7ef6c3b2e73028600343c889d4f8e697f67934cf43d77` |
| `entity_state_monthly/month=2025-04/part-0.parquet` | `b3eec16ef204f1378a02fa5c0f22b5759206878ccee368b2887b151ee7ea0e40` |
| `entity_state_monthly/month=2025-05/part-0.parquet` | `292cf5ebce89da9bd1110d9e0b7f3e98e9ff8fc0d1d4b539e82ba26a3e7a7a3b` |
| `entity_state_monthly/month=2025-06/part-0.parquet` | `7ed4bcd68dc9b87224e43c739ee0c465bce4e21891a092d1d07ad99b79201c8d` |
| `entity_state_monthly/month=2025-07/part-0.parquet` | `494df797f2a4d63f38233fd967a12e4103b400001f213e667d039c6defa90db8` |
| `geo.parquet` | `c73c65a3964f432ad6191e54887407aecb42f5f9dde743e58cdae28903ed76a6` |
| `households.parquet` | `4fcdf33f0657b11022c2f7cdea86fae727f08bc79f5cb5fdc45fc0a062070c01` |
| `instruments.parquet` | `7dbb2095d1d9c74426ea060e866569d457f8f42a43156c30f2a45dab96473dc0` |
| `interventions_log.parquet` | `b966ecd603747606ad5a971a707b469bdd88d339e800a6b6f7cc1c72ed2f1456` |
| `journal/month=2025-04/part-0.parquet` | `7fd26e2c10aab37c88a4989e2a586662f588ba710a8823d5acf54d49325dc32a` |
| `journal/month=2025-04/part-1.parquet` | `e71a1d96ce2602f3a46fefabdf37fca782f325cacf52d5c6c726836df7b84700` |
| `journal/month=2025-04/part-2.parquet` | `8287e6a88b61101ab45341b0166daf66789d4e56cbc904f4ef4bb5ac52bbb457` |
| `journal/month=2025-04/part-3.parquet` | `868160bae2267a7cd60fa7e8e7224b985053480fec27d55032a30efe0adda87b` |
| `journal/month=2025-04/part-4.parquet` | `220d6b148911af56cfba10d9dd5cae66c8e5c5870a44064cf8bafec50f25d054` |
| `journal/month=2025-05/part-0.parquet` | `19331c8bb8cd771537ae0d609277cd025c4ce51a4fad8ac66dfbd82cdb267647` |
| `journal/month=2025-05/part-1.parquet` | `ec75fa884eeb55b055f7441815ff9c7a6db97f0c5631d1d777ab681ae6d145d5` |
| `journal/month=2025-05/part-2.parquet` | `3b6e9fb5f7423db18cc852d7c64bdd8095c4e31afb505abdbf4becee50da1319` |
| `journal/month=2025-05/part-3.parquet` | `d880277c0eacbd3ad1fc2f92925e0085fb2024728b373ff61cf65443c1eaf048` |
| `journal/month=2025-05/part-4.parquet` | `0f95c6f0a6eb111a8cb3acbcf3417de38969e7c5a5cb46d20b9e087278b643c8` |
| `journal/month=2025-06/part-0.parquet` | `28123ac41c5a638c9f26f7d61bb1cfdee5cd2147ecf93e2fdcd0854fee03170b` |
| `journal/month=2025-06/part-1.parquet` | `a2d168ea06df2804a217c4f604c17145ab80edb8203a5fa04e2000d32e798620` |
| `journal/month=2025-06/part-2.parquet` | `71519a4459affe92fdfc4c85060f909700f5de9f53aa2802807ec0f8c73483c8` |
| `journal/month=2025-06/part-3.parquet` | `675c1a1cd370dc440fdb7880f055b61ea10e7831e83b841436aa703e845c8b7a` |
| `journal/month=2025-06/part-4.parquet` | `554b1097e055878f2da97860c92a80439d557c1cb961f87e48953a4af7c72079` |
| `journal/month=2025-07/part-0.parquet` | `14ed6968bd66cf321786bd6a3fa84a27e82f6c1a95b34ac9ac658627d8d6e90d` |
| `journal/month=2025-07/part-1.parquet` | `06ea1ef6090df50425f3d3aac8b877ebeac4617f6c3e1b60932eea00c7bbaed5` |
| `journal/month=2025-07/part-2.parquet` | `49ec1739e05f9b378b60747a11aac834cd6dbc6acda3d03c174f1f6b1d7bad26` |
| `journal/month=2025-07/part-3.parquet` | `2982a30e77b7b2e2219b99df23c4e65bdbc01f8e9f89e428fb67b536c93f1532` |
| `journal/month=2025-07/part-4.parquet` | `782cd6d4bb9166ace76ac51eb86ca23dbc65798adc5c6be7556c6e6eac8492c2` |
| `life_events/month=2025-04/part-0.parquet` | `02c17002a3f558040618fe94537102b3721974c3ffd55998bf58b2ff4e26a9ec` |
| `life_events/month=2025-05/part-0.parquet` | `a6b10597af41f8e417efd726dfba332d4c911dd22bd61f7a129613b1db62331c` |
| `life_events/month=2025-06/part-0.parquet` | `a7224d16d85ee1ef5c62fc0a8cd3757302f388e7b06255f6bd9a173a1806e7bc` |
| `life_events/month=2025-07/part-0.parquet` | `3a1b0b6b11a2fab3d49dd116c28a9edf582cd5b648ced35ec2ae0dd24914dbcf` |
| `macro_paths.parquet` | `81ed5096aec84b20b1dfd52031a61954c24758eb57f23a009393c8e9a18627e4` |
| `orgs.parquet` | `3cbd795f257e56f2dba79e6bcbc0df63cdda0a70f543a79cff1ee6d0a1f8b99d` |
| `payments/month=2025-04/part-0.parquet` | `2abd637d7faca7ec31accb848de4d47205aa9a625fd9e688d3da6e14b5f7b3c9` |
| `payments/month=2025-04/part-1.parquet` | `13b21c65a421afa06c936b2862cc36387661703cf6ec11f23078052cf7721923` |
| `payments/month=2025-04/part-2.parquet` | `12993d7c789941555cef5ff1ba70bb0e5a131b1bf97b7e868326bb9e854f6f54` |
| `payments/month=2025-04/part-3.parquet` | `24565cb6f85f166a8b6d398f9a14adf72637954dbc136125027563d2a2cca2b1` |
| `payments/month=2025-04/part-4.parquet` | `33984367a7c31bc18ebb2a772cc6f671007a328d828c803a2ff0440be8b76f1d` |
| `payments/month=2025-05/part-0.parquet` | `39ca7e25cb151386b63c455809e463fa827978ed7892bdb07b75185aa8ba7238` |
| `payments/month=2025-05/part-1.parquet` | `14c2b32c90bbfa057e621ba8b120908a9819eae80032ebfcdf752f7a41318caa` |
| `payments/month=2025-05/part-2.parquet` | `01328275e9a5ef1e756978bd0901a703bb7b5e0c4f0bb208877873e32dd12918` |
| `payments/month=2025-05/part-3.parquet` | `c5e7e73c1d2f1fd3f6735580875463db279e3f0d4fd8fd63253185a98416b897` |
| `payments/month=2025-05/part-4.parquet` | `0db9ee974d4551c4ffc7e7e8d64a0a6dfd15ad9e8057f4cac9275fdc4147dfe3` |
| `payments/month=2025-06/part-0.parquet` | `1b0b1438b2418e1fa28ca32d276cf98d19c789aff889db147667e149cf61acc8` |
| `payments/month=2025-06/part-1.parquet` | `0a8bdb6ff21303867e0534f3ec003ed20f2cab9572fb6585aed2ef320c5a8e38` |
| `payments/month=2025-06/part-2.parquet` | `254570da8e4f8beb67d26fd633c5ec30f6b90ff2a5955fa5facd07feda7891fd` |
| `payments/month=2025-06/part-3.parquet` | `b581671693d2c4cd0558abedeaf860c1d83a124649b559508ecb89a03d1efb2f` |
| `payments/month=2025-06/part-4.parquet` | `659e4ba1053196a016568c55886f96eed1b18cc3f62ec0832e5e919f72232e1f` |
| `payments/month=2025-07/part-0.parquet` | `51def6cfae790060a2e08e28ce58dba4c8e61c1b4150801fce4379447881aae6` |
| `payments/month=2025-07/part-1.parquet` | `13d4ced5c75a7f21f96e709c04790276e57823955359c31be79129064ce8e7cf` |
| `payments/month=2025-07/part-2.parquet` | `1bfcc0743a1b519590ed7fe15bfd938cc4b1265377946bd22816d848ba633439` |
| `payments/month=2025-07/part-3.parquet` | `e956d5ae0ad43af8d98075c3cf09a1f0ee81d27e6b41a77dfec7a340c87957aa` |
| `payments/month=2025-07/part-4.parquet` | `028a260ad790f09e91547fdbf4574791c75e418c107dc951767b313774e887ea` |
| `persons.parquet` | `519772ffe4dce325f437baf450d64c9813d94855ee96fcafc0a7433bec679b11` |
| `postings/month=2025-04/part-0.parquet` | `1000a2f960043d8800458d0f9b18746247d03bcd9a70e25e2016c84c87c85d46` |
| `postings/month=2025-04/part-1.parquet` | `a85686e820e0ee190066b6f414e0967420e977884fe5e9810ef9d2685fc81c46` |
| `postings/month=2025-04/part-2.parquet` | `1bbf88c11d69979ac4f8dc89b02339aa8c70f508373c994c37f7b4aa2f52f5cc` |
| `postings/month=2025-04/part-3.parquet` | `1d1c4403c1dd18102f3fef2a39064000fcb1d840b851df9e106fb55840e1f2ff` |
| `postings/month=2025-04/part-4.parquet` | `a5e82aa690dcafab3f9043ab86e26b07ae94d96ea7e37504166cde06727cd2c9` |
| `postings/month=2025-04/part-5.parquet` | `13951c09c9a11434020a474aa1a6f47dd66922314376f49a7732dc5853a6d0a9` |
| `postings/month=2025-04/part-6.parquet` | `2799089e48acdb1f7b85fd37d9983f4196b8037268290979f35ee6048c1e106d` |
| `postings/month=2025-04/part-7.parquet` | `614e174d6a5ce23b8cf38ffb15471ba35f95285f4b9862c543fc4ad49ac1b643` |
| `postings/month=2025-04/part-8.parquet` | `8d730b9b2248bcad52c874de18862b8fcc6a6ac4d2954b2581601443198f888d` |
| `postings/month=2025-05/part-0.parquet` | `fab8dc5ba9ef36065aa16b07c7b957cd45b1991ff2a28c78c37d5db8970051fd` |
| `postings/month=2025-05/part-1.parquet` | `fe66c729e30f90f8be57894ad13bc0918b809f390c6790cbb6338214de52758c` |
| `postings/month=2025-05/part-2.parquet` | `193b7aaff68b2e28f34680b6c17736af33d3f7abc9cbf1653e06a9d62392eda3` |
| `postings/month=2025-05/part-3.parquet` | `8c28c1ffc03590d98984d7da9933020d5dc800954dbc7b595bb782b00410ddd5` |
| `postings/month=2025-05/part-4.parquet` | `2873b12abbd349382729ddf02f49757f6b3431d8a6963a92505ae873d8f79622` |
| `postings/month=2025-05/part-5.parquet` | `017b112a799dd7e3f14924d58db6bb0b4d6377659ce9aa2511c02563cddb1bf1` |
| `postings/month=2025-05/part-6.parquet` | `bde9a93bd01622991605a6c0d6036d7ad3cef6c464af20cb295c35a2c9a277e8` |
| `postings/month=2025-05/part-7.parquet` | `a0a0189d2aaf2a3b5f05004cf613b080ffbc6773d8445bee336b6737df584316` |
| `postings/month=2025-05/part-8.parquet` | `d4ef5b919565c570acf72f9b4e6e6050505316d6cd73b5120d9ac14c97a8ce0f` |
| `postings/month=2025-06/part-0.parquet` | `2855b25d7ddeacc02907dd0851284803cbec640798a778969e5e2852586cc1c6` |
| `postings/month=2025-06/part-1.parquet` | `af90fe67bfbaaf5f8a70fe5810f4e146f3b1867b5c905e95370ce843bdc251fd` |
| `postings/month=2025-06/part-2.parquet` | `3c9f3c96ce46e141d7b0db240d0683a0a3ebf7a81d8ef3ee564f573c4c7daaa3` |
| `postings/month=2025-06/part-3.parquet` | `bc17e1ae2658879e9846ac9f5eb944c61526452a5350e411a1114e02fbc6ed74` |
| `postings/month=2025-06/part-4.parquet` | `3d4c7ceab8c5506618524738a7fc31a63bc4e6d8f9ecbf7c37df75b84b43ab39` |
| `postings/month=2025-06/part-5.parquet` | `d0695c939e6fe4ee99d0dac053724a1e793c2884852f9543dbce06cdce8aa304` |
| `postings/month=2025-06/part-6.parquet` | `c9306becc4ccb8f28d98ac345b9febb94fa6721ae204ef1faff73efd4cbe3500` |
| `postings/month=2025-06/part-7.parquet` | `37a094d276652f429875edf7777b44a0229217fbbe062b289b3dd983973c15d0` |
| `postings/month=2025-06/part-8.parquet` | `5a07fd1ee967dce33c18aa04d607e2f9be3b9772d08156e141a722bae29dfa36` |
| `postings/month=2025-06/part-9.parquet` | `2e137a63af82d2a53c81253c4443b6aeb8b6a8e5e90073f93497712355496226` |
| `postings/month=2025-07/part-0.parquet` | `ccd020c93e961ad077fbcc4998a2f9ffb485e19378c2403580f3dae2ad5fe9fd` |
| `postings/month=2025-07/part-1.parquet` | `49ab1403e6ca4a95c06a0a8c071a7f0b7ee820a84dd32e21bda624071556e7d1` |
| `postings/month=2025-07/part-2.parquet` | `6ebf09a65f5801c6c64bd8d0c77408c92f398a418d7db67c39c4add824b10e89` |
| `postings/month=2025-07/part-3.parquet` | `7c16ab038e7831ac10b474417ef6a4e92f0211dacb1fde6cef615b65df031f52` |
| `postings/month=2025-07/part-4.parquet` | `f32a7e581ec61ca326ee14fdf5ed9be3a5d0eba3e3842533700d8bc0233b6bd3` |
| `postings/month=2025-07/part-5.parquet` | `7d2a996e5daae3bf873c290d1381a1a67f0d2956d5145b075ae2d163969b666f` |
| `postings/month=2025-07/part-6.parquet` | `4066b63feabb9f53b1e1d631cf588d73df92e8752371f2a2a4235c0d4ce6a628` |
| `postings/month=2025-07/part-7.parquet` | `c99923a56f23caf59894c38e49c7c2f526d8a4d52d603735b39c5c1157b0d061` |
| `truth_dbt_monthly/month=2025-04/part-0.parquet` | `16a4a79a27d6b12d19e0a21e1cb3af6d11f76e3b5c9365e3120b4913da9c8a7d` |
| `truth_dbt_monthly/month=2025-05/part-0.parquet` | `f32311535ec83fceabed04db4d190e1869f2668e4052991711361fa25e1532d7` |
| `truth_dbt_monthly/month=2025-06/part-0.parquet` | `6e2b36ac70374a2a5dbecfa25f1628b5b25d6e707f219fa897fcd705570673ec` |
| `truth_dbt_monthly/month=2025-07/part-0.parquet` | `3c7ab1510c310b797ebc88cb9836ced3056c204fd85c3f2bb2c081f76c562f99` |
| `truth_household_monthly/month=2025-04/part-0.parquet` | `06441329c7d6dd51c33f3d38147622d979118e5dd0d0db0b0f63b6008e512d66` |
| `truth_household_monthly/month=2025-05/part-0.parquet` | `5fcecf9ce864bcf347ef0a7de41a4237a1b565b8d83ede1865d609249cb8462b` |
| `truth_household_monthly/month=2025-06/part-0.parquet` | `06fdc632dc463378e6f9b9a314cf1aaae0a36db9ee3f3ed7bca779ff32d4e046` |
| `truth_household_monthly/month=2025-07/part-0.parquet` | `ddbcdf85cf0cfe98974f6abc85206fa3877543e82df77810537a8b328af90a3b` |
| `truth_person_latent.parquet` | `571f206307fdf4b80ba35a04d68a01625358da0646a639e7f54dd57e56c5bb40` |
