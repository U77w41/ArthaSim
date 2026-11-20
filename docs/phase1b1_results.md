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

## Fix: household allowance (20 November 2026)

Design: `docs/superpowers/specs/2026-11-19-household-allowance-design.md`. Plan: `docs/superpowers/plans/2026-11-19-arthasim-household-allowance.md`.

Each month, every adult's need is their share of the household budget, plus the utilities bill and medical costs for the head. Members whose income exceeds their need cover the members who fall short, pro rata to their surplus. Salaried payers pay the day after payday; others on a fixed day of their own. A recipient who pays by UPI gets UPI or IMPS; anyone else gets cash, and a banked payer short of cash withdraws the difference first. Payments carry purpose `ALLOWANCE`.

Same gate run as above (tier S, 90 days from 2025-04-01, seed 7), before and after the change, on an Apple M5 (10 cores, 16 GB, macOS 27.2, Python 3.12). The run before the change reproduces the sandbox run above exactly: 15,022,751 payment attempts and the same status shares.

| Status | Before | After |
| :--- | ---: | ---: |
| SUCCESS | 78.3% | 94.4% |
| DECLINED_FUNDS | 21.5% | 5.4% |
| DECLINED_TECH | 0.3% | 0.3% |

| Life stage | Declined for funds, before | After |
| :--- | ---: | ---: |
| Homemaker | 73% | 15% |
| Studying | 71% | 19% |
| Seeking work | 70% | 20% |
| Retired | 13% | 1.5% |
| Farm | 9% | 5% |
| Casual | 6% | 2.5% |
| Gig | 3% | 1% |
| Salaried | 2% | 1.5% |
| Self-employed | 1% | 0.5% |

Homemakers, students and job seekers, by month and by whether their household has any income:

| Month | Household has income | Household has none |
| :--- | ---: | ---: |
| April | 17% | 23% |
| May | 8% | 61% |
| June | 8% | 78% |

- Allowances are 1.25% of payment attempts (191,000 in 90 days, ₹142 crore). 97.7% succeed; 2.1% fail for funds, mostly cash allowances.
- April is higher because allowances arrive after payday, so members first spend down their opening balances. From May, non-earners who live with an earner fail about 8% of the time.
- What remains, over the 90 days (822,832 insufficient-funds declines): households where nobody earns (6.6% of households) cause 33%, up from 8%; non-earners in households with income 46%; everyone else in households with income 21%. In June the split is even: 128,443 declines from households with no income, 127,366 from households with income.
- Households with no income: their members run out of savings within two months. Government transfers (DBT, plan 1d) fix this part only.
- Households with income: the allowance equals the recipient's expected spending with no margin, so recipients run short late in each cycle. In June, non-earners fail 3% of attempts in the 10 days after their allowance, 6% at 10 to 19 days, 10% at 20 to 24, 18% at 25 to 29, and 36% at 30 days or more (May has 31 days). The review found two smaller causes: households whose surplus cannot cover every shortfall, and card holders without UPI, who receive cash but pay by card from an account nothing refills.
- So the design's success measure is only partly met. Declines for homemakers, students and job seekers fall from about 70% to 15 to 20%, but what remains does not come mostly from households with no income.
- Median spending to income, households with income: April 0.595, May 0.673, June 0.697 (before: 0.53, 0.512, 0.515).
- Cost: 2% more payment attempts (15,344,393), 3% more simulation time (18.0 s against 17.5 s for 90 days), peak memory 2,278 MB against 2,200 MB.

Command: `python scripts/bench.py --tier S --days 90 --seed 7 --out runs`; `declined_funds_by_life_stage` and `declined_funds_no_income_households` are now in its output.

## Allowance margin (20 November 2026)

Design: `docs/superpowers/specs/2026-11-20-allowance-margin-design.md`. Plan: `docs/superpowers/plans/2026-11-20-arthasim-allowance-margin.md`.

Every adult's need is padded by `transfer.allowance_margin` before pooling. Recipients ask for more than their expected spending, and earners keep the same headroom on their own spending before passing on the rest. Where earners cannot cover everyone, that headroom comes out of what recipients get (see below). Same gate run and machine as above, swept with `--set transfer.allowance_margin=M`. A margin of 0 reproduces the run without it exactly (15,344,393 attempts).

| Margin | 0 | 0.10 | 0.15 | 0.20 |
| :--- | ---: | ---: | ---: | ---: |
| Declined for funds, all attempts | 5.36% | 5.10% | 5.05% | 5.05% |
| Homemakers | 15.4% | 14.7% | 14.6% | 14.7% |
| Students | 19.1% | 18.5% | 18.5% | 18.5% |
| Job seekers | 19.9% | 19.3% | 19.3% | 19.3% |
| Retired | 1.5% | 1.2% | 1.1% | 1.1% |
| Recipients, 0 to 9 days after their allowance | 3.2% | 2.9% | 2.8% | 2.7% |
| 10 to 19 days | 6.3% | 5.4% | 5.2% | 5.1% |
| 20 to 24 days | 10.9% | 8.6% | 8.2% | 8.1% |
| 25 to 29 days | 19.0% | 14.2% | 13.1% | 12.6% |
| 30 days or more | 36.0% | 29.4% | 28.8% | 27.4% |
| Households scaled down (June) | 4.0% | 17.9% | 22.1% | 27.9% |
| Share of funds declines from households with no income | 32.9% | 34.6% | 34.9% | 34.9% |

Rows cover all 90 days, except "Households scaled down", which is June. "Recipients" are homemakers, students and job seekers, counted from the last allowance they received. "Households scaled down" is the share of households with both surplus and shortfall (not of all households) whose earners cannot cover every shortfall in full.

- The margin cuts late-cycle declines by about a third (25 to 29 days: 19% to 13% at 0.15) and early ones by 14 to 19%. The overall rate falls only from 5.36% to 5.05% because the margin changes only what recipients receive, and their payments are about a fifth of all attempts.
- Not every recipient gains. Comparing each recipient across the runs at 0 and 0.15 (May and June):
  - 4,888 of 26,665 recipients (18%) receive 10.7% less, and their decline rate rises from 11.2% to 14.9%. These are households that tip from full cover to scaled cover.
  - 99 of them receive nothing.
  - The other 21,777 receive more, and their decline rate falls from 7.2% to 4.7%.
- Gains flatten above 0.10. The cost is more households scaled down: the padded need of earners leaves less surplus to pass on.
- The value stays at 0.15, as designed, pending a decision on how the margin is paid. As built, any margin moves money away from recipients in households that are already stretched, so the size alone cannot fix that. 0.15 is slightly better than 0.10 late in the cycle and scales down under a quarter of the households that have both surplus and shortfall. Both values are assumptions for plan 1e to calibrate.
- What remains for homemakers, students and job seekers in households with income (June, margin 0.15) is spread across payment methods. Their cash purchases fail 4.9% of the time if banked and 6.7% if not, UPI purchases 7.7%, and debit-card purchases 25.5%. The card rate is the known gap: card holders without UPI receive their allowance in cash. A margin is not the lever for the rest.
- Cost: negligible (17.7 s for 90 days; 0.05% more attempts).

Commands: `python scripts/bench.py --tier S --days 90 --seed 7 --out runs --set transfer.allowance_margin=M`. `recipient_declined_by_days_since_allowance` and `allowance_scaled_households` are now in the output.

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
