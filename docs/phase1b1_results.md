# Plan 1b-1 results

Gate run on 16 November 2026: tier S (100,000 adults, two archetype districts), 90 simulated days from 2025-04-01, seed 7.
Command: `python scripts/bench.py --tier S --days 90 --seed 7 --out runs`.
Machine: the Linux sandbox this was built in (1 CPU, 3 GB RAM). Rerun on your own machine for local numbers.

## Timing and memory

| Metric | Value |
| :--- | ---: |
| Build time | 1.5 s |
| Simulation time, 90 days | 32.945 s |
| Total, including tables, hashing and manifest | 48.1 s |
| Payment attempts | 15,022,751 |
| Payment attempts per second | 455,995 |
| Payment attempts per person per day | 1.669 |
| Peak memory | 1979 MB |

12 simulated months at tier S, extrapolated linearly: 2 min, against the 2-hour target. Tier M would take about 22 min on the same basis, but memory would not fit: a month of rows is still buffered in one piece.

## Money flows

| Status | Share of attempts |
| :--- | ---: |
| SUCCESS | 78.3% |
| DECLINED_FUNDS | 21.4% |
| DECLINED_TECH | 0.2% |
| DECLINED_LIMIT | 0.0% |

| Purpose group | Share of attempts |
| :--- | ---: |
| Income (salary, earnings, pension, employer revenue, remittance) | 12.8% |
| Spending (11 categories plus medical) | 82.2% |
| Cash withdrawals and deposits | 5.0% |

| Rail | Share of attempts |
| :--- | ---: |
| CASH | 64.8% |
| UPI_P2M | 23.0% |
| DEBIT_CARD | 2.8% |
| ATM | 2.2% |
| NEFT | 1.9% |
| UPI_P2P | 1.9% |
| BRANCH | 1.6% |
| AEPS | 1.1% |
| NACH_CR | 0.6% |
| IMPS | 0.0% |

Median ratio of a household's successful spending to its income, households with income: April 0.53, May 0.512, June 0.515 (June has 29 of 30 days).

Cash held at the end: persons ₹52.0 crore, merchants ₹3.2 crore, bank vaults ₹580.2 crore. The boundary holds ₹7,580.5 crore, which is 36 months of the sample's income by construction.

## Finding: non-earning members cannot pay

21% of payment attempts fail for insufficient funds. Broken down by the payer's life stage:

| Life stage | Share of their attempts declined |
| :--- | ---: |
| Homemaker | 74% |
| Studying | 71% |
| Seeking work | 71% |
| Retired | 13% |
| Farm | 9% |
| Casual | 6% |
| Gig | 3% |
| Salaried | 2% |
| Self-employed | 1% |

86% of all insufficient-funds declines are made by homemakers, students and job seekers. The cause is a gap in the model, not a bug: each adult spends their share of the household budget from their own accounts, but income lands only in earners' accounts and nothing moves it within the household. Earners accumulate while other members run dry. This also explains why median spending is about half of income although the spending share is 85%.

The fix is a monthly allowance from earners to the other adults in their household, paid by UPI or cash. It would also add family transfers, a benign pattern a mule detector has to tell apart from layering. It is not in this plan.

## Exit criteria

| Criterion | Result | Evidence |
| :--- | :--- | :--- |
| Tier S runs 90 days with every invariant passing, including the flow-matrix columns | Pass | `tests/test_gate_1b1.py` and this run finished with no `InvariantError` |
| Two runs with the same seed give identical tables | Pass | `tests/test_gate_1b1.py` compares content hashes |
| Every earning group is paid and every purchase has a category | Pass | No payment has purpose `UNSPECIFIED`; all income and spending purposes occur |
| Throughput, memory and a money-flow summary are recorded | Pass | This file |

## What this does and does not show

- Money now moves the way the plan describes, and the ledger stays closed with income from outside the sample.
- Every parameter added in this plan has status `assumption`. Shares by rail, purpose and status are outputs of placeholders, not calibrated figures.
- Firms have no costs, so merchant and employer balances only grow.
- Person state does not change: nobody is hired, laid off or ages. That is plan 1b-2.
