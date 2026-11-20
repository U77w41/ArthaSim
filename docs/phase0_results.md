# Phase 0 results

Gate run on 15 November 2026: tier XS (10,000 persons), 90 simulated days from 2025-04-01, seed 7.
Command: `python scripts/bench.py --tier XS --days 90 --seed 7 --out runs`.
Machine: the Linux sandbox this was built in. Rerun on your own machine for local numbers.

Note, 20 November 2026: the flexible automatic withdrawal changed the settlement engine that tier XS also uses. The same command now gives 1,146,684 payment attempts and 21.9% funds declines. See `phase1b1_results.md`, "Flexible automatic withdrawal".

## Measured

| Metric | Value |
| :--- | ---: |
| Days simulated | 90 |
| Payment attempts | 1,144,327 |
| Simulation wall time | 1.748 s |
| Payment attempts per second | 654,649 |
| Peak memory | 601 MB |
| Payment attempts per person per day | 1.271 |
| Total time including build, hashing and manifest | 2.98 s |
| Output size on disk | 43 MB |

| Status | Share of attempts |
| :--- | ---: |
| SUCCESS | 77.0% |
| DECLINED_FUNDS | 22.4% |
| DECLINED_TECH | 0.6% |
| DECLINED_LIMIT | 0.0% |

The high share of insufficient-funds declines is expected in the spike. Forty percent of persons have no income here, so they spend down their opening balance and then fail. Plan 1b gives everyone an income.

## Exit criteria (blueprint section 18)

| Criterion | Result | Evidence |
| :--- | :--- | :--- |
| 90 simulated days pass all invariants | Pass | `tests/test_gate.py` and the bench run finished with no `InvariantError`; the checks run after every simulated day |
| Identical output for identical seed | Pass | `tests/test_gate.py` compares the content hash of every table across two runs; `tests/test_run.py` also shows a different seed gives different payments |
| Throughput measured | Pass | Table above |

Phase 0 covers invariants 1 to 5 and the row sums of invariant 6. The column sums of invariant 6 and invariant 7 are outside this phase, as the plan states.

## Against the blueprint's targets (section 16)

The 90-day figure is scaled linearly in days and persons. That scaling is an assumption, not a measurement.

| Tier | 12 simulated months, extrapolated | Target | Margin |
| :--- | ---: | ---: | ---: |
| XS (10,000 persons) | 7 s | 5 min | 42x |
| S (100,000 persons) | 71 s | 2 h | 102x |
| M (1,000,000 persons) | 12 min | 24 h | 122x |

## What this does and does not show

- The engine design holds at this size: vectorised intents, a compiled settlement loop, and daily invariant checks are fast enough to leave a wide margin.
- The margin will shrink. The spike has two simple behaviour modules; phase 1 adds life course, categories, more rails and views.
- Memory will not scale as it stands. A month of rows is buffered before each flush, and the content hash reads whole tables into memory. Both need to become incremental before tier M. This belongs in plan 1c.
- Nothing here says the behaviour is realistic. Every `spike.*` parameter is a placeholder with status `assumption`.

## Revised targets

No change. The section 16 targets stand and should be measured again at the end of plan 1b.
