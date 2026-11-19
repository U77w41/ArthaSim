# Plan 1a results

Gate run on 16 November 2026: tier S (100,000 adults, two archetype districts), 30 simulated days from 2025-04-01, seed 7.
Command: `python scripts/bench.py --tier S --days 30 --seed 7 --out runs`.
Machine: the Linux sandbox this was built in. Rerun on your own machine for local numbers.

## The world that was built

| Item | Count |
| :--- | ---: |
| Persons | 100,000 |
| Scale factor (real adults per simulated adult) | 50 |
| Households | 38,250 |
| Employers | 677 |
| Merchants | 2,500 |
| Banks and NBFCs | 12 and 2, plus the boundary bank |
| Accounts (all instruments) | 211,208 |
| Household edges | 205,810 |
| Co-worker edges | 125,914 |
| Neighbour edges | 153,000 |
| Remittance edges | 4,979 |
| Share of persons without a bank account | 11.5% |

## Fit to the district marginals

Sum of absolute share errors per margin. The gate limit is 0.01.

| District | Age band | Sex | Education | Life stage, women | Life stage, men |
| :--- | ---: | ---: | ---: | ---: | ---: |
| metro_archetype | 0.0001 | 0.0000 | 0.0002 | 0.0003 | 0.0001 |
| rural_archetype | 0.0003 | 0.0000 | 0.0002 | 0.0004 | 0.0004 |

Largest error: 0.0004.

## Timing and memory

| Metric | Value |
| :--- | ---: |
| Build time | 1.62 s |
| Simulation time, 30 days | 7.746 s |
| Total, including tables, hashing and manifest | 11.75 s |
| Payment attempts | 3,750,496 |
| Payment attempts per second | 484,185 |
| Payment attempts per person per day | 1.25 |
| Peak memory | 1805 MB |

| Status | Share of attempts |
| :--- | ---: |
| SUCCESS | 66.8% |
| DECLINED_FUNDS | 32.8% |
| DECLINED_TECH | 0.4% |
| DECLINED_LIMIT | 0.0% |

## Exit criteria

| Criterion | Result | Evidence |
| :--- | :--- | :--- |
| Tier S builds with largest fit error under 0.01 | Pass | 0.0004; asserted in `tests/test_gate_1a.py` |
| The phase 0 day loop runs 30 days with every invariant passing | Pass | `tests/test_gate_1a.py` and this run finished with no `InvariantError` |
| Two builds with the same seed give identical tables | Pass | `tests/test_gate_1a.py` compares the content hash of all twelve tables |
| Build time, run time and peak memory recorded | Pass | Tables above |

## What this does and does not show

- The build is internally consistent: margins fit, every salaried person has an employer in their own district and sector, every locality has a grocery, and no identifier matches a real format.
- It is not a picture of any real place. Both districts are archetypes and every parameter added in this plan has status `assumption`. Real district files replace them in plan 1e.
- The day loop is still the phase 0 loop. Only salaried persons are paid, purchases pick merchants at random across both districts, and merchant UPI acceptance is ignored. Plan 1b replaces it.
- Households mix sexes but not generations, and merchants have no owners. Both need microdata.
- Memory: a month of rows is still buffered and hashed in one piece. That holds at tier S and must change before tier M.
