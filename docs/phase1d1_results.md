# Plan 1d-1 results: government transfers

Benchmarks run on 23 November 2026: tier S (100,000 adults; scale factor 50), seed 7, from 1 April 2025, for 90 days and for 365 days (to 31 March 2026).

**Commands.** `python scripts/bench.py --tier S --days 90 --seed 7` and `--days 365`. "Before" is `main` at `1b5d045`, exported with `git archive` into a scratch directory. "After" is this branch.

**Query.** Every figure below was re-queried from the run directories with one script, applied the same way to both sides, and agrees with the bench's own output where both report it.

**Machine.** Apple M5 (10 cores, 16 GB), macOS 27.2, Python 3.12.15, scratch virtual environment, `PYTHONPATH=src`.

Design: `docs/superpowers/specs/2026-11-22-government-transfers-design.md`. Plan: `docs/superpowers/plans/2026-11-22-arthasim-plan-1d1-government-transfers.md`. Sources: `docs/sources/dbt.md`.

## Funds declines

| | 90 days, before | 90 days, after | 365 days, before | 365 days, after |
| :--- | ---: | ---: | ---: | ---: |
| Payment attempts | 15,260,566 | 15,282,932 | 62,136,003 | 62,256,321 |
| Declined for funds | 720,197 | 630,506 | 2,888,257 | 2,411,292 |
| Share of attempts | 4.72% | 4.13% | 4.65% | 3.87% |

Funds declines fall by 89,691 (12.5%) over 90 days and by 476,965 (16.5%) over the year. Attempts rise slightly (0.15% and 0.19%), because transfers raise the budgets of the households that receive them.

By the payer's life stage, share of attempts declined for funds:

| Life stage | 90 days, before | After | 365 days, before | After |
| :--- | ---: | ---: | ---: | ---: |
| Homemaker | 12.5% | 10.3% | 12.9% | 10.1% |
| Studying | 16.4% | 15.9% | 20.4% | 19.4% |
| Seeking | 16.2% | 15.4% | 17.0% | 16.0% |
| Farm | 3.2% | 2.7% | 1.8% | 1.5% |
| Retired | 0.8% | 0.8% | 0.3% | 0.3% |

Other stages are unchanged to within 0.01 point.

By month, over the year:

| Month | Apr | May | Jun | Jul | Aug | Sep | Oct | Nov | Dec | Jan | Feb | Mar |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Before | 5.4% | 4.0% | 4.9% | 5.0% | 5.0% | 4.9% | 4.7% | 4.6% | 4.5% | 4.4% | 4.4% | 4.2% |
| After | 5.1% | 3.3% | 4.0% | 4.1% | 4.0% | 4.0% | 3.9% | 3.8% | 3.7% | 3.6% | 3.6% | 3.4% |

## Households with no earned income

"No income" means no earned income (`truth_household_monthly.income_paise = 0`), as before, so both runs count the same households. There are 3,349 in April, 3,525 in June and 3,133 in March, of 38,250 households, identical in both runs.

| | 90 days, before | 90 days, after | 365 days, before | 365 days, after |
| :--- | ---: | ---: | ---: | ---: |
| Attempts by their members | 725,085 | 727,354 | 2,752,757 | 2,766,601 |
| Declined for funds | 326,917 | 264,286 | 1,990,776 | 1,663,593 |
| Their own decline rate | 45.1% | 36.3% | 72.3% | 60.1% |
| Their share of all funds declines | 45.4% | 41.9% | 68.9% | 69.0% |

Their members' rates, over the year:
- homemakers 73.4% → 56.3%;
- students 76.4% → 73.9%;
- job seekers 55.3% → 52.5%.

- Over 90 days, their declines fall by 19.2% and everyone else's by 6.9%. Over the year both fall by about 16.5%, so their share of all declines stays at 69%. The pension, PM-Kisan and transfers to women in earning households lower other people's declines too.
- In March, 1,326 of the 3,133 households with no earned income (42%) have a member enrolled in a scheme. Of the 1,807 without one:
  - 1,405 have a member who is eligible but not covered, usually a woman homemaker;
  - the other 402 have nobody eligible for anything: their members are students, job seekers and men keeping house.
- Transfers do not make these households solvent. Their budget is at least the floor of ₹2,500 a month per adult (`consumption.floor_per_adult_paise`), above the average women's transfer of ₹1,401 or a pension of ₹1,000–1,300. So their savings still run down, more slowly: their decline rate over the whole year (60.1%) is far above that over the first 90 days (36.3%).

## Money moved

| Scheme | Credits, 90 days | Rupees, 90 days | Credits, 365 days | Rupees, 365 days | People paid in the year | Average credit |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| Women's transfer | 11,945 | ₹1.67 crore | 47,363 | ₹6.64 crore | 4,841 | ₹1,401 |
| PM-Kisan | 0 | 0 | 18,445 | ₹3.69 crore | 7,011 | ₹2,000 |
| Old-age pension | 4,742 | ₹50.7 lakh | 19,695 | ₹2.11 crore | 1,758 | ₹1,071 |
| Total | 16,687 | ₹2.18 crore | 85,503 | ₹12.44 crore | | |

- Every credit succeeded, by APBS.
- PM-Kisan paid on 2 August 2025, 19 November 2025 and 13 March 2026: 18,445 credits, about 6,148 households per instalment. The 90-day window has no release date.
- The government's balance ends at −₹12.44 crore, exactly minus what it paid. At the scale factor of 50, that is ₹622 crore a year for the 5 million adults the two districts stand for.
- DBT credits are 0.11% of attempts over 90 days and 0.14% over the year.
- The average women's credit (₹1,401) matches the beneficiary-weighted mean of PRS's state amounts (₹1,405). The average pension credit (₹1,071) is close to the average of around ₹1,100 that PIB reports.
- Transfer income counted in budgets is ₹1.00 to ₹1.05 crore a month.
- Allowances paid over the year fall by ₹0.97 crore (₹845.95 crore → ₹844.98 crore), much less than the ₹6.64 crore paid to women. A transfer counts as household income, so it also raises the household's budget and each member's need.

## Enrolment against published figures

In the last simulated month:

| Group | Eligible | Enrolled | Share of the group enrolled | Published |
| :--- | ---: | ---: | ---: | :--- |
| Women aged 21–60 (39,585), women's transfer | 9,743 | 3,904 | 9.9% (10.5% in June 2025) | About 32%: close to 12 crore women (EAC-PM 2026) of roughly 37.5 crore aged 21–60 |
| People aged 60+ (15,216), old-age pension | 3,428 | 1,709 | 11.2% (11.4% in June 2025) | IGNOAPS alone: 2.21 crore of about 16 crore, about 14% |
| Households with an own-account farmer (10,370), PM-Kisan | 9,210 | 6,035 | 58.2% (58.6% in June 2025) | 9.7 crore of 14.645 crore holdings, 66% |

- **Women's transfer.** It reaches a third of the published share. Only 24.6% of simulated women aged 21–60 are eligible, mostly because few have household earned income under the ₹2.5 lakh cap, against most women in India. Simulated incomes run high: the median rural household earns ₹24,141 a month in April. Coverage then takes 0.4 of the eligible. Every woman in a household with no earned income is under the cap. Calibrating incomes is plan 1e, and the nominal cap will follow it.
- **Old-age pension.** Eligibility is BPL by rank, so it does not depend on the income level. 22.5% of people aged 60+ are eligible (non-retired, BPL), and half are covered.
  - The simulation has many more contributory pensioners than India: a third of its people aged 60+ (33.0% in April, 31.9% in March) are "retired" with a pension, against 8.6% with a work-related pension in LASI.
  - So fewer elderly people are left for the social pension.
- **PM-Kisan.** It is 8 points below the published 66%. Exclusions remove 11.2% of farm households: a government employee, a member earning over ₹7 lakh a year, or a pensioner on ₹10,000 or more. Coverage (0.66) applies to the rest.

## Accounts

- **At build.** Account ownership in April is 91.13% in both runs. The build banks every enrolled payee by swapping with non-enrolled, non-salaried account holders in the same district, so ownership is unchanged by DBT.
- **Build versus April.** The build enrols 10,906 payees and April enrols 10,839. The 67 enrolled at build but not in April lose eligibility when the first month's raises push their household over a cap; they keep the account the swap gave them. Nobody enrolled in April is unbanked, so no account opens for DBT that month.
- **During the year.** 307 people opened an account in the month they were enrolled (80 in the first 90 days). Account openings over the year are 1,947 against 1,684, and ownership in March is 93.07% against 92.81%.

## Cost

| | 90 days, before | 90 days, after | 365 days, before | 365 days, after |
| :--- | ---: | ---: | ---: | ---: |
| Build | 0.54 s | 0.58 s | 0.87 s | 0.58 s |
| Simulation | 9.61 s | 9.81 s | 48.77 s | 43.03 s |
| Total, including tables, hashing and manifest | 11.69 s | 11.99 s | 55.17 s | 48.70 s |
| Peak memory | 2,763 MB | 2,676 MB | 2,930 MB | 2,843 MB |

DBT has no measurable cost: run-to-run variation is larger than any difference. The first 90-day run on `main` in this session took 21.2 s of simulation, because it compiled the settlement kernel; it is not used here.

## Gates

- The fast suite passes (218 tests).
- All five slow gates pass (141 s), including the new `tests/test_gate_1d1.py`. That gate runs 12 months at tier S and checks:
  - PM-Kisan pays on exactly its three dates;
  - in every month, every enrolled payee is paid, and only they are, with the scheme's amount and day;
  - every DBT credit is a successful APBS credit;
  - the government's balance equals minus the total paid.

## What this does and does not show

- Government money now reaches people who have no earnings. Funds declines fall by a sixth over a year, and the ledger stays closed with the government's balance as the source.
- Every new parameter is `unverified` or `assumption`. Coverage values are derived from published counts, not fitted.
- Students and job seekers get no transfer, so households made only of them still fail most payments after a few months.
- Real DBT has failed and returned credits; here every credit lands.
- All figures are from one seed.
