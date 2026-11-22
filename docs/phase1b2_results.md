# Plan 1b-2 results: the life course

Gate run on 22 November 2026: tier S (100,000 adults; the metro district stands for urban India, the rural one for rural India), 12 simulated months from 2025-04-01 to 2026-03-31, seed 7.
Commands: `PYTHONPATH=src pytest -m slow -q tests/test_gate_1b2.py`, and `python scripts/bench.py --tier S --days 90 --seed 7 --out runs` on `main` (before) and on the branch (after), then `--days 365` on the branch.
Machine: Apple M5, 16 GB, Python 3.12, `PYTHONPATH=src` from a scratch virtual environment.

## The gate

Every month, in every one of the 44 cells (2 districts × 2 sexes × 11 five-year age groups), the number of people in each life stage equals its PLFS-based target exactly. The run covers 365 days. The test takes 98.5 s. The three earlier gates (phase 0, 1a, 1b-1) still pass with the life course running.

## Cost against plan 1b-1

| Metric | `main`, 90 days | Branch, 90 days | Branch, 365 days |
| :--- | ---: | ---: | ---: |
| Build time | 1.7 s | 1.1 s | 1.0 s |
| Simulation time | 20.1 s | 19.2 s | 84.2 s |
| Total, including tables, hashing and manifest | 25.8 s | 23.0 s | 93.0 s |
| Payment attempts | 15,417,445 | 15,260,636 | 62,137,692 |
| Payment attempts per second | 767,228 | 796,069 | 737,758 |
| Peak memory | 2,094 MB | 2,501 MB | 2,573 MB |

The monthly life-course step adds no measurable time: a full year at tier S takes about a minute and a half, against the 2-hour target. Peak memory is about 400 MB higher, and the cause has not been looked into. It does not grow over the year: 2,501 MB after 90 days, 2,573 MB after 365.

| Status | `main`, 90 days | Branch, 90 days | Branch, 365 days |
| :--- | ---: | ---: | ---: |
| SUCCESS | 95.9% | 95.1% | 95.1% |
| DECLINED_FUNDS | 3.9% | 4.7% | 4.7% |
| DECLINED_TECH | 0.2% | 0.2% | 0.2% |

Funds declines rise by 0.9 points because the population changed, not because of the monthly moves. The build now takes its life stages from PLFS instead of the placeholder rows. That gives more homemakers, fewer retired people with pensions, and fewer gig workers. Total monthly income in April is 5.5% lower, even after the April raises, and more adults depend on an allowance. Each stage's own decline rate barely moves in the first 90 days:

| Life stage | People, `main` | People, branch (April 2025) | Declined, `main` 90 days | Declined, branch 90 days | Declined, branch 365 days |
| :--- | ---: | ---: | ---: | ---: | ---: |
| Homemaker | 20,739 | 27,333 | 11.6% | 12.5% | 12.9% |
| Salaried | 21,466 | 19,559 | 0.6% | 0.8% | 0.4% |
| Self-employed | 14,144 | 13,646 | 0.2% | 0.4% | 0.2% |
| Farm | 10,712 | 12,953 | 3.1% | 3.2% | 1.8% |
| Casual | 10,048 | 10,347 | 0.6% | 0.6% | 0.3% |
| Retired | 9,198 | 5,451 | 0.8% | 0.8% | 0.3% |
| Studying | 6,514 | 6,513 | 15.4% | 16.4% | 20.4% |
| Seeking | 3,622 | 2,134 | 16.3% | 16.2% | 17.0% |
| Gig | 3,557 | 2,064 | 0.6% | 0.5% | 0.2% |

On the branch the life stage is read from `entity_state_monthly` for the payment's month. On `main` it is the build's stage.

## Rural women's work follows the bulletins

The share of rural women who work, against the PLFS monthly bulletins (CWS worker-population ratio, rural women aged 15 and over):

| Month | Bulletin WPR | Change since April | Simulated working share (18+) | Change since April |
| :--- | ---: | ---: | ---: | ---: |
| Apr 2025 | 36.8% | | 47.0% | |
| May | 35.2% | −1.6 | 45.4% | −1.6 |
| Jun | 33.6% | −3.2 | 43.7% | −3.2 |
| Jul | 35.5% | −1.3 | 45.8% | −1.2 |
| Aug | 35.9% | −0.9 | 46.3% | −0.7 |
| Sep | 36.3% | −0.5 | 46.7% | −0.3 |
| Oct | 36.9% | +0.1 | 47.4% | +0.4 |
| Nov | 38.4% | +1.6 | 49.0% | +2.1 |
| Dec | 38.6% | +1.8 | 49.3% | +2.3 |
| Jan 2026 | 38.0% | +1.2 | 48.7% | +1.7 |
| Feb | 38.4% | +1.6 | 49.2% | +2.2 |
| Mar | 37.3% | +0.5 | 48.1% | +1.1 |

The level is higher than the bulletin's for two reasons. The model counts usual status, which includes subsidiary work: PLFS 2025 puts rural women's usual-status worker rate at 44.9% against 36.8% weekly. And the population is 18 and over, without the 15–17-year-olds who are mostly at school. The monthly changes track the bulletin's to within 0.6 points. They drift upward by about half a point by March because the fixed population ages by a year and the targets follow each person's age.

## Urban gross flows against the published panel

Quarter-apart moves among urban people (the metro district), by the PLFS panel's six states, pooled over the nine pairs of months three apart. They are compared with the pooled quarterly matrix from MoSPI's urban panel (QB October–December 2024, Table 5, four quarter pairs). Each cell is published % / simulated % of the row; a published `*` counts as 0. A published "stay" includes the residual that the bulletin leaves out of the six columns ("had work but did not work").

Men:

| From \ to | own | helper | regular | casual | unemployed | nlf |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| own | 97.3 / 97.8 | 0.4 / 0.1 | 0.9 / 1.0 | 0.4 / 0.4 | 0.4 / 0.3 | 0.5 / 0.5 |
| helper | 3.2 / 7.5 | 94.3 / 87.5 | 0.0 / 0.6 | 0.0 / 1.1 | 0.0 / 1.0 | 2.4 / 2.5 |
| regular | 0.7 / 1.0 | 0.0 / 0.0 | 97.5 / 97.0 | 0.4 / 0.5 | 1.0 / 0.8 | 0.4 / 0.6 |
| casual | 1.4 / 1.9 | 0.0 / 0.1 | 1.1 / 1.4 | 91.0 / 91.4 | 4.8 / 3.6 | 1.7 / 1.7 |
| unemployed | 2.3 / 3.8 | 1.2 / 0.2 | 5.8 / 8.1 | 9.9 / 12.6 | 78.5 / 72.9 | 2.3 / 2.4 |
| nlf | 0.4 / 1.3 | 0.2 / 0.0 | 0.5 / 2.0 | 0.5 / 0.7 | 0.4 / 0.4 | 98.0 / 95.5 |

Women:

| From \ to | own | helper | regular | casual | unemployed | nlf |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| own | 91.0 / 92.0 | 0.4 / 0.2 | 1.2 / 1.0 | 0.4 / 0.7 | 0.0 / 0.2 | 7.1 / 6.0 |
| helper | 1.8 / 7.0 | 87.8 / 81.7 | 0.0 / 1.0 | 0.0 / 1.0 | 0.0 / 0.2 | 10.5 / 9.2 |
| regular | 0.6 / 1.0 | 0.0 / 0.1 | 96.3 / 94.8 | 0.0 / 0.2 | 0.8 / 0.9 | 2.2 / 3.0 |
| casual | 0.0 / 2.5 | 0.0 / 0.3 | 0.0 / 0.9 | 79.7 / 82.3 | 6.8 / 3.8 | 13.6 / 10.2 |
| unemployed | 0.0 / 2.1 | 0.0 / 0.0 | 4.7 / 5.6 | 3.5 / 4.5 | 82.4 / 80.4 | 9.4 / 7.5 |
| nlf | 0.4 / 0.9 | 0.3 / 0.1 | 0.4 / 0.6 | 0.2 / 0.3 | 0.2 / 0.2 | 98.4 / 97.9 |

The salaried, own-account and casual rows match within about a point. The simulation has more churn out of unemployment, from helper to own-account, and out of nlf among men. Three things drive that:
- **Seasonal targets.** Alignment has to deliver the seasonal and age-driven targets, so it adds moves.
- **Helpers.** They are few (see below), so each family business that closes turns its helpers into own-account workers, and that is a large share of a small row.
- **Students.** Among men, nlf includes students leaving study for jobs. The published panel covers ages 15 and over, so most of its students stay at school.

## Events over the year

| Event | Total | Per month (May to March) |
| :--- | ---: | :--- |
| HIRED | 3,191 | 170 to 429 |
| LAID_OFF | 859 | 39 to 109 |
| LEFT_JOB (salaried to studying or homemaker) | 976 | 43 to 148 |
| RETIRED | 707 | 56 to 71 |
| JOB_SWITCH | 2,302 | 175 to 236 |
| STARTED_WORK | 6,056 | 229 (May) to 854 (July) |
| STOPPED_WORK | 5,452 | 289 (November) to 805 (May) |
| CHANGED_WORK | 6,522 | 476 to 645 |
| LEFT_STUDY / STARTED_STUDY | 490 / 157 | |
| STARTED_SEEKING / STOPPED_SEEKING | 285 / 279 | |
| LEFT_RETIREMENT | 74 | |
| RAISE | 19,275 | 13,555 on the first day (April raise month) |
| ACCOUNT_OPENED | 1,684 | 121 to 182 |
| BECAME_OWN_ACCOUNT / BECAME_HELPER | 347 / 79 | |

Work stops in May and June and restarts in July, the agricultural season the bulletins show. There are on average 19,437 salaried people. Against them:

| Flow | Per year | Benchmark |
| :--- | ---: | :--- |
| Job switches | 11.8% | Aon 2025: 12.8% voluntary attrition (16.2% less 3.4% involuntary) |
| Layoffs | 4.4% | Aon: 3.4% involuntary |
| Hires | 16.4% | |

Raises (mean 8.9%) reach almost every salaried person once. People hired or switching jobs in their employer's raise month skip it, since their pay was just set.

## Accounts

Account ownership rises from 91.1% of adults in April to 92.8% in March: 1,684 accounts opened. The share without an account at the end falls from 11.5% on `main` (the build's placeholder ownership rates, fixed for the run) to 7.2%. Every hire without an account opens one in the month they are hired, and their first salary lands in it; a fast test checks this.

## Helpers

The build makes 1,878 adults unpaid family helpers, 7.1% of the farm and self-employed. That is 30% of the count PLFS's age-specific helper shares imply for these people (6,340). Helpers exist only where the household has an own-account member in the same stage, and households are formed without regard to work. The design expected about 40%.

## Finding: a layoff does not squeeze spending

The 803 people laid off during the year are younger (28.6 against 37.1 for all salaried), lower paid (₹40,100 against ₹54,200 a month) and newer in their jobs (median 22 against 61 months). Their payments fail for lack of funds 1.5% of the time in the month before the layoff and 0.4% in the month of it. They also make 9% fewer attempts.

The cause: `Budget` sets each household's spending from its income and balance at the start of every month. When income stops, spending stops with it, and the household lives off its balance. Nothing in the model is committed spending that keeps going after a job loss (rent, loan instalments, school fees). So the moves have no money stress. The higher rate in the month before comes from who gets laid off: young, low-paid, recently hired people with thin balances.

Making layoffs bite needs committed outgoings. That belongs with arrears and credit, not this plan.

## Funds declines by month

| Month | Apr | May | Jun | Jul | Aug | Sep | Oct | Nov | Dec | Jan | Feb | Mar |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Declined for funds | 5.4% | 4.0% | 4.9% | 5.0% | 5.0% | 4.9% | 4.7% | 4.6% | 4.5% | 4.4% | 4.4% | 4.2% |

The median ratio of a household's spending to its income keeps climbing over the year: 0.62 in April, 0.75 in June, 0.83 in September, 0.88 in December, 0.91 in March. `main` shows the same climb over its 90 days (0.62, 0.70, 0.73), so it comes from the budgeting rule, not from the life course. Declines fall slowly as balances build up.

## What this run cannot show

- No births, deaths or new adults: the population ages by a year (mean age 41.0 to 42.0) and the targets follow each person's age.
- Rural flows use the urban panel's rates. Alignment sets the rural totals, and the return weight brings the same people back each season. Whether the same rural women really move in and out each year is not checked.
- Every figure here is from one seed.
