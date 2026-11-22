# Plan 1b-2, life course: design

Approved 21 November 2026, after a builder check.

## Intent

Today a person's situation never changes during a run: nobody is hired, laid off, switches job, gets a raise, ages or opens an account. Plan 1b-2 makes it change, month by month, the way India's labour market does.

The project owner wants each district's life-stage shares on target every month, and the simulation as close to real life as published Indian data allows. Their decisions:

- The two districts stand for **urban India** (the metro district) and **rural India** (the rural district). That is the level at which the Periodic Labour Force Survey (PLFS) publishes annual, quarterly and monthly figures; no current source gives labour figures for a single district.
- Targets **follow the seasons**: they track the PLFS monthly bulletins, so rural women move between farm work and domestic duties around the harvests.
- Movers are chosen by **rates, then exact alignment** (see Approaches).

## Goals

- At the start of every month, each (district, sex, age group) cell's count of people in each life stage equals that month's target exactly. Age groups are PLFS's five-year groups from 20–24 to 60–64, plus 18–19 and 65 and over: eleven per district and sex. Per-district shares by sex are the sums, so they are exact too.
- Who moves follows published Indian transition rates, conditional on age, sex, education, time in the current stage and the stage last left. People move in both directions, so hires and layoffs both happen in a month whose totals do not change.
- Salaried people are hired by, laid off by and switch between employers; each employer's payroll follows its staff.
- Salaried pay rises once a year, in the employer's raise month.
- People without a bank account open one during a run: always when they take a salaried job, otherwise at a published trend rate.
- Two new truth tables: `life_events` (one row per event) and `entity_state_monthly` (one row per person per month).
- Every ledger invariant passes; the same seed gives the same content hash; a split run equals a single run.

## Non-goals

- Births, deaths, marriages, people turning 18, and moves between districts or households. The population is fixed for a run. Over 12 months real India adds about 2% new adults and loses under 1%.
- Seasonal earnings within a stage (fewer paid days in a lean month). The seasons move people between stages here; paid days are a later income change.
- Arrears: raises and dearness-allowance increases paid late with back pay (central government DA, for example, was raised 55% to 58% on 1 October 2025 with effect from 1 July, arrears paid with the October salary). Raises here are paid from the month they take effect.
- Updating the social graph. Co-worker and remittance edges stay as built.
- Replacing the other placeholder marginals (age, education, household size), and forming households by occupation. They wait for plan 1e.
- Calibrating transition rates by simulation. Published rates are used as they are; alignment holds the totals.

## Approaches considered

| Approach | Trade-off | Verdict |
| :--- | :--- | :--- |
| Rates, then exact alignment: each person's chance of each move from published rates; in each cell the expected moves are raked so the totals after the moves equal the targets; movers for each move are drawn by weighted sampling | Totals exact; gross flows keep the published pattern; reuses `build.ipf` and `build.ipf.integerise` | Chosen by the project owner |
| Rates nudged to targets: a monthly correction to every rate so expected totals hit the targets, then independent draws | Simpler per person; totals miss by chance (about 0.1 point a month at tier S, 0.5 in a 5,000-person world) | Dropped |
| Targets only: move just enough people to close each gap | Net moves only, so no layoffs in a month with flat hiring | Dropped |

Two mechanics had their own choices (calls made here):

| Choice | Options | Call |
| :--- | :--- | :--- |
| Opening accounts mid-run | (a) The account book grows: instruments are appended after the build. (b) Every unbanked adult gets a reserved, unopened account at build. | (a). Phase 3 needs it anyway (each loan and card balance is a new instrument), and (b) fixes the bank before the person knows their employer. |
| Where live person state lives | (a) Update in place the arrays the modules already read. (b) Move live state into a new object and change every module to read it. | (a), plus a small `LifeState` for what is new. The modules re-read these arrays every month or day, so they need no change. |

## Data

All sources are free to read. The extracts, with every URL, table and page, go into the repo under `docs/sources/` (three files: annual report, bulletins, transition rates). Values the code reads go into data files under `params/lifecourse/` with the same references, status `unverified` (transcribed and cross-checked by script, not yet checked by a person).

| What | Source | Basis |
| :--- | :--- | :--- |
| Annual life-stage shares | PLFS Annual Report, January–December 2025 (revised PDF of 29 May 2026), Table 15: persons by usual status (ps+ss), detailed activity codes, by industry (agriculture / secondary / tertiary), by five-year age group from 15–19 to 65+, for rural male, rural female, urban male, urban female | Usual status, ps+ss |
| Annual weekly-status reference | Same report, Tables 30 and 31: LFPR and WPR in current weekly status (CWS), ages 15+, 2025 | CWS |
| Monthly seasonal path | PLFS monthly bulletins, April 2025 to March 2026: LFPR, WPR and UR, CWS, ages 15+, for the same four groups (no gaps, no revisions) | CWS |
| Quarterly composition | PLFS quarterly bulletins, April–June 2025 to January–March 2026: workers by status (self-employed, regular, casual) and share in agriculture, same four groups | CWS |
| Gross flows | PLFS Quarterly Bulletin October–December 2024, Appendix Table 5: urban persons 15+ by activity in adjacent quarters, four quarter pairs, by sex (own-account, helper, regular, casual, unemployed, not in labour force). Rows pooled over the four pairs give quarterly transition probabilities. | CWS, quarterly, urban |
| Who is more likely to move | Bhattacharya (2021), arXiv 2110.05482, Table 7: effects on the quarterly probability of losing and gaining work, by sex, of age under 21, age 21–30, graduate, child under 5 in the household, and quarters in the current state | CWS, quarterly, urban |
| Gig work | NITI Aayog (2022): gig workers were 2.6% of the non-farm workforce in 2020-21, projected 6.7% in 2029-30 | |
| Raises and switches | Aon salary survey: 8.9% average raise in 2025; attrition 16.2% in 2025 (involuntary 3.4%). Naukri survey (2023): 56% of employees are on an April–March appraisal cycle. Michael Page: 25–40% pay rise for junior professionals who switch | Formal private sector |
| Accounts | Global Findex 2025 (PIB factsheet): 89% of Indian adults have an account, men and women equally, up from 53% in 2014 | |
| Superannuation | Central government 60; private-sector default 58 (Industrial Employment Standing Orders); EPS pension at 58 | |

What the data shows that shaped the design:

- **The swing is rural.** Over the 12 months the share of rural women working (CWS) moves 5.0 points, from 33.6% in June 2025 to 38.6% in December; rural men 1.9 points. Urban swings are 0.9 points, about what sampling error alone gives.
- **Usual status and weekly status differ a lot for rural women**: 44.9% work on the usual-status measure and 36.8% in the weekly measure, because many work part of the year. MoSPI's notes on May and June 2025 say unpaid helpers on family farms moved to domestic duties after the rabi harvest.
- **Nothing publishes rural or seasonal gross flows**, monthly matrices, or flows that split students from homemakers. The only published matrices are urban and quarterly. This is the main gap; alignment fills it for totals, and the rules below choose who.
- **Unpaid helpers are a large group**: 13.6% of rural women aged 15+ are helpers on family farms, unpaid.

## Design

### Life stages from PLFS codes

| Model stage | PLFS usual-status codes |
| :--- | :--- |
| salaried | 31 (regular wage or salary), any industry |
| casual | 41, 51 (casual labour), any industry |
| farm | 11, 12, 21 (own-account, employer, helper) in agriculture (NIC 01–03) |
| gig | NITI Aayog's definition: a share of all non-farm workers (codes 11–51 outside agriculture), interpolated to the run's year (about 4.9% in 2025), taken out of non-farm own-account workers. For urban men that is 3.4% of the population; for rural women 0.6%. The same share applies in both districts. |
| self_employed | 11, 12, 21 outside agriculture, less gig |
| seeking | 81 (unemployed) |
| studying | 91 |
| homemaker | 92, 93 (domestic duties), 95 (unable to work), 97 (others): every adult outside the labour force who is not studying and has no unearned income |
| retired | 94 (pensioners, rentiers, remittance recipients) |

**Helpers are unpaid, and only inside a family business** (decided by the project owner). Code 21 people in farm or self_employed carry a `helper` flag and have no income of their own; the farm's or business's earnings stay with the own-account member. A person entering farm or self_employed is a helper with the probability PLFS gives for their (district, sex, age group), but only if someone in their household already works on their own account in the same stage; otherwise they enter as own-account and earn. The build applies the same rule, assigning own-account status first within each household. Households are formed without regard to work, so there will be fewer helpers than PLFS reports (a rough count suggests about 40% of its share); in exchange every helper has a family farm or business, and the household's income includes it. When the last own-account member of a household leaves the stage, its helpers become own-account. The Income module needs no change: it already skips earners with zero income.

### Targets

Targets are shares by (district kind, sex, age) and month, built by a script from the source tables and stored in `params/lifecourse/targets.yaml`.

1. **Annual shares by age.** For each of the four groups, Table 15's five-year columns give the share of each stage at each age. Ages 18–19 take the mean of the 15–19 and 20–24 columns (the 15–19 column is mostly 15–17-year-old students); 65 and over use the 65+ column.
2. **Monthly working total.** For month m, the working share in each age group is scaled by the same factor for its (district, sex): `(W + WPR_m − WPR_2025) / W`, where W is the group's usual-status working share for ages 15+, WPR_m the month's CWS worker rate and WPR_2025 the 2025 CWS annual rate from Table 31. For rural women this gives a 15+ working share of 44.9% in April 2025, 41.7% in June and 46.7% in December.
3. **Monthly seeking.** Seeking scales the same way with the unemployed share of the population, `LFPR − WPR`, from the bulletin against the annual CWS value.
4. **Quarterly composition.** Within work, farm, casual and salaried shift with the deviation, from the mean of the four quarters, of the agriculture share, the casual share and the regular-wage share; self_employed and gig take the rest in their annual proportion. Each quarter's deviation sits at the quarter's middle month and is interpolated linearly month by month in between, so there are no jumps on quarter days.
5. **Outside the labour force.** Studying and homemaker absorb the change in proportion to their size; retired stays at its annual share.
6. **Counts.** A cell's target for a stage is the sum, over the people in the cell, of the share for each person's age, integerised so the cell's targets add up to its size (`integerise`). Ageing therefore moves targets smoothly as people cross age groups.
7. **Months outside April 2025 to March 2026** use the same calendar month inside the window.

Because the population is 18+ and its age structure is still a placeholder, district shares are what PLFS age-specific rates imply for this population, not the PLFS 15+ headline shares. That keeps the age profile right (a 19-year-old is usually studying, a 62-year-old often retired) and avoids forcing a fixed population to hold shares that only births and deaths keep steady in reality.

### The build

- The build fits the **start month's** targets, so the first month needs no moves. The life-stage margin becomes (age band, sex, stage) from the targets, using the model's five age bands, which the build already fits, in place of the placeholder `life_stage` rows by sex and the `age_life_stage` prior.
- Exact ages within a band are drawn conditional on stage, from the PLFS age profile, so a 24-year-old is rarely a student.
- The build then runs one alignment pass for the start month (the same raking and choosing as the monthly cycle, writing no events), so every five-year cell starts exactly on target.
- Months in the current stage are drawn as if long-standing: geometric with the stage's monthly base exit rate, capped by age (no one has studied longer than they have been 15, or worked longer than they have been 18 or their education's start age).
- `inclusion.account_ownership` becomes 0.89 in both districts (Findex 2025; no rural and urban split is published).
- Helpers are flagged (by the family-business rule above) and have zero income.
- Each employer gets a raise month: April with probability 0.56, otherwise one of the other eleven months with equal probability.
- Each person gets a birth month.

### Monthly cycle

A new module `LifeCourse` runs first in the population module list, before `Income`, so every module that reads person state sees the month's state. It has a monthly hook only and emits no payment intents. On the run's first simulated day it applies raises due that month and writes the first `entity_state_monthly` rows; from the second month on, at the start of each month:

1. **Ageing.** People whose birth month it is get a year older.
2. **Transition probabilities.** Each person gets a monthly probability of moving to each other stage (next section).
3. **Raking.** In each (district, sex, age group) cell, the expected moves form a matrix with current counts as row totals. It is raked (IPF) so its column totals equal the targets, keeping the published pattern of gross flows as far as the targets allow, then rounded to whole people with both totals exact. A target reachable by no allowed move gets a small floor on the cells that can reach it.
4. **Choosing movers.** Within each stage, the people to make each move are drawn by weighted sampling without replacement, weights equal to each person's probability of that move, using keyed random draws. Likelier movers are chosen more often but not always.
5. **Job changes.** For salaried people who stay salaried, a monthly job-switch probability; layoffs are the moves out of salaried.
6. **Employers, pay and accounts** follow (below), then raises due this month.
7. **Tables.** Events for every change; one `entity_state_monthly` row per person.

### Transition probabilities

- **Base rates.** The pooled quarterly urban matrix by sex (QB October–December 2024, Table 5), converted to monthly: a row's total exit probability q becomes `1 − (1 − q)^(1/3)`, split across destinations in the quarterly proportions. Rural districts use the same rates, since no rural flows are published; alignment supplies the rural seasonal totals.
- **Mapping to stages.** Own-account and helper rows serve farm, self_employed and gig. Moves into self-employment are split between farm, self_employed and gig by the destination stages' shares for the person's (district, sex, age). The not-in-labour-force row serves studying, homemaker and retired, and moves into it are split by the person's age-specific shares of those three.
- **Negligible cells.** A `*` in the published table (under 0.05% of persons, rounded away) counts as 0.025%, so the move is rare but possible.
- **Moves the table lumps together.** The published table has one self-employment block and one not-in-labour-force state, so moves inside them need their own rates. Without them, alignment would route these changes through jobs and write false hires and job exits.
  - **Leaving study.** The monthly probability of leaving studying at each age comes from the PLFS age profile: the fall in the studying share from one five-year group to the next, spread over the five years, divided by the studying share. Leavers' destinations are in proportion to the rise in each other stage's share between the same two groups. For urban women finishing study at 20–24, about two thirds go to homemaker and a third to work; for urban men nearly all go to work or seeking. This replaces the not-in-labour-force row for students.
  - **Between farm, self_employed and gig.** 0.5% a month each way between farm and the non-farm stages (ICRISAT's village studies: a third of farmers left farming over seven years, about 0.5% a month), and 1% a month between self_employed and gig (an assumption).
  - **Helper to own-account.** 0.5% a month (an assumption); the helper flag clears and pay starts from the Mincer equation. Own-account to helper 0.1% a month.
  - **Homemaker and retired.** 0.1% a month each way (an assumption); the age profile of retired comes through the targets.
- **Who.** Bhattacharya's Table 7 effects (on the quarterly probability of losing or gaining work, by sex) are added before conversion: age under 21, age 21–30, graduate, child in the household (`dependants > 0`), and quarters in the current stage (2, 3 or more). Marriage and employment history are not in the model and are left out. The effects are measured against people one quarter into a stage, while the published rows average over everyone, so they are **centred**: each month, for each (sex, row), the mean effect over the people currently in that row is subtracted, so the row's average stays at the published rate and the effects only rank people. Probabilities are clipped to [0.001, 0.95].
- **Coming back.** A move back to the stage a person left within the last 12 months has its probability multiplied by a return weight, so the seasonal movers are the same people (MoSPI's notes describe the same helpers moving out and back). No Indian estimate exists; the value is an assumption, 5.
- **Retirement.** Salaried people only: in the month a salaried person turns 58 (60 if their employer's sector is public administration), their probability of moving to retired is 0.5, an assumption in line with PLFS, where the urban male salaried share falls from 33.7% at 55–59 to 14.5% at 60–64. Other workers retire at the published rates. Alignment holds the 55–59, 60–64 and 65+ shares at PLFS's levels.
- **Structural zeros.** No move into studying from age 35, matching Table 15, where the share is nil from 35. Retired has no age floor: code 94 includes remittance recipients and rentiers, about 1% of rural women aged 25–44.

### Employers and pay

- **Hire.** A person moving into salaried takes a sector: their last salaried sector if they had one within 12 months, else a draw from the district kind's salaried sector shares. The employer is drawn among employers of that (district, sector), weighted by vacancies (capacity minus staff) plus one, so employers can grow. They are paid on the employer's payday, a full month's salary in the month they join.
- **Pay on entry.** Salaried, self_employed, gig, farm and casual pay comes from the existing Mincer equation (`starting_pay`) with a fresh keyed draw and the stage multiplier. Someone returning within 12 months to the stage they left gets their previous pay in it. Helpers get zero. Retired get the existing pension rule. Studying, seeking and homemaker get zero.
- **Job switch.** A monthly probability of 1.1% for salaried people (Aon's 2025 voluntary attrition, 16.2% less 3.4% involuntary, per month), times 1.5 under age 30 (EPFO's new and rejoining members are mostly young). The new employer is drawn as for a hire, from the same sector with probability 0.7, else any sector. New pay is the old pay times a lognormal factor, median 1.15 and sigma 0.15, an assumption below the recruiter figures, which cover professionals only.
- **Layoffs** are moves from salaried into seeking. Each employer gets a keyed monthly shock that multiplies its staff's probability of leaving (lognormal, sigma 0.5), so some months a firm lays off several people at once.
- **Payroll.** Each employer's payroll is recomputed after every change, so the employer revenue paid on the 1st follows its staff.
- **Raises.** At the start of an employer's raise month, each salaried person's pay rises by a draw with mean 8.9% (Aon 2025) and standard deviation 4 points, floored at 0. This includes the first simulated month, so the build's pay is the pay before that year's raise. Other earners' pay does not change, since the model has no price path yet.

### Accounts

- **When.** A person moving into salaried without an account opens one that month (a salary account: at the employer's bank with probability `inclusion.salary_account_at_employer_bank`, else the usual district pick). Other unbanked adults open one with a monthly probability of 1.5% (an assumption, giving about 2 points a year at 89% ownership; Findex shows 3.6 points a year from 2014 to 2024, slowing).
- **What.** Zero opening balance (basic savings and Jan Dhan accounts need none). A debit card with probability `inclusion.debit_card_share`; UPI if the person has a mobile and enough digital literacy (the build's rule); automatic withdrawals by ATM with a card, else AePS.
- **How.** The account book gains an `extend` step after the build. Appending a deposit also extends every per-account array the day loop reads: balance, type, holder, issuer, opening, posted total, deposit for cash, bank of account, vault for deposit, withdrawal rail. A zero-balance deposit changes no bank's balance sheet, so every invariant holds unchanged.
- **Tables.** The `accounts` and `instruments` tables are rewritten at every flush with every account so far, each with its true `opened_on`.

### Tables

`life_events`, truth layer, partitioned by month:

| Column | Notes |
| :--- | :--- |
| `event_id` | Sequential within a run |
| `date`, `entity_id` | First of the month the change takes effect |
| `event` | `HIRED`, `LAID_OFF`, `LEFT_JOB` (salaried to studying or homemaker), `RETIRED`, `JOB_SWITCH`, `STARTED_WORK` (into farm, casual, self_employed or gig), `STOPPED_WORK` (out of those), `CHANGED_WORK` (between those), `STARTED_STUDY`, `LEFT_STUDY`, `STARTED_SEEKING`, `STOPPED_SEEKING`, `RAISE`, `ACCOUNT_OPENED`. Every stage change gives exactly one event, by a fixed (from, to) table. |
| `from_stage`, `to_stage` | Null for events that are not stage changes |
| `employer_from`, `employer_to` | Entity ids, nullable |
| `income_before_paise`, `income_after_paise` | |
| `account_id` | For `ACCOUNT_OPENED` |

`entity_state_monthly`, truth layer, partitioned by month, one row per person at the start of each simulated month after the life course has run: `entity_id`, `month`, `age`, `life_stage`, `months_in_stage`, `helper`, `sector`, `employer_entity_id`, `monthly_income_paise`, `has_account`, `primary_bank`, `has_upi`, `has_card`.

`persons` keeps only what never changes. `age`, `life_stage`, `sector`, `employer_entity_id`, `monthly_income_paise`, `has_account` and `primary_bank` move to `entity_state_monthly`; `birth_month` is added. The architecture already says time-varying attributes never sit on the entity row.

### What other modules see

| Module or part | What it reads | Effect |
| :--- | :--- | :--- |
| `Income` | life stage, income, employer, salary, payroll, `person_deposit` | New state each month; laid-off people get no salary, new hires a full month's |
| `Budget` | household income, age | Household budgets follow income changes; the elderly medical rate follows age |
| `Allowance` | income, employer payday | Pairs and amounts recomputed monthly from the new incomes |
| `Remittances` | income | A migrant who loses work sends nothing |
| `Consumption`, `CashManagement` | `person_deposit`, UPI and card flags | New accounts are used from the day they open |
| Settlement kernel | per-account arrays | Extended with each new account |
| `World` | module list | `lifecourse` first; `tests/test_money_flows.py` pins the list |
| Store | fact tables | `life_events` and `entity_state_monthly` join `FACT_TABLES`; content hashes cover them |
| `scripts/bench.py` | life stage by payer | Reads the stage for the payment's month from `entity_state_monthly` |

Tier XS keeps the spike builder and its two modules, with no life course.

### Randomness

Stream names start with `life.`. Monthly draws are keyed on the first day of the calendar month, as `Budget` does, so a run that starts mid-month draws the same moves. Same seed, same output; a split run equals a single run.

## Success measure

A new slow gate: one 12-month run at tier S, April 2025 to March 2026, seed 7.

- Every month, every cell's stage counts equal the targets exactly.
- Every invariant passes; a second run gives the same content hashes (or the split-run check at 5,000 persons in the fast suite, if two 12-month runs are too slow).

Reported in `docs/phase1b2_results.md`, not gated:

- Monthly working share for rural women against the bulletin path.
- Simulated quarterly gross flows in the urban district against the published urban matrix.
- Events per month: hires, layoffs, switches, raises, accounts opened; switches against Aon's attrition; account ownership over the year.
- Funds declines by month, and for people in the month after a layoff.
- Cost: time and memory against plan 1b-1.

## Calls for the project owner to check

1. Usual status (ps+ss) is the annual basis, because only it is published by age and detailed code. It counts as workers people whose main activity is domestic duties but who work 30 days or more in a year; the seasonal path then moves some of them out of work in lean months.
2. Homemaker also holds people unable to work and "others" (codes 95, 97): about 3–4% of adults. They have no income either way.
3. Decided: helpers are unpaid and exist only where the household has an own-account member in the same stage. Rural women moving in and out of family farm work with the seasons then do not change household income. Matching helper shares exactly needs households formed by occupation (plan 1e).
4. Urban targets follow the monthly bulletin too, as decided, although urban moves under 1 point are mostly sampling noise. This adds a little churn there.
5. Rural districts use the urban flow rates for who moves, since none are published for rural India.
6. Assumptions with no Indian source: the return weight (5), retirement at superannuation (0.5), the moves inside self-employment and between homemaker and retired, helper to own-account, the job-switch pay factor, the employer layoff shock, the raise spread, the non-April raise months, and the 1.5% monthly account-opening rate.
7. Account ownership at build becomes 89% in both districts.
8. Alignment is by PLFS five-year age group, not the model's five age bands, so the 60–64 and 65+ shares, and those around retirement age, are held too: 44 cells per month instead of 20.
9. Gig follows NITI Aayog's definition, 4.9% of all non-farm workers in 2025, about three times as many as a share of own-account workers alone would give.

## Left to the builder

- The rounding method that keeps both row and column totals exact.
- File layout: suggested `src/arthasim/life/` for targets, rates, alignment, jobs and accounts, and `src/arthasim/modules/lifecourse.py` for the module.
- Registry ids for the new parameters (prefix `life.`), and the format of the target and source files.
- The derivation script for `params/lifecourse/targets.yaml` (`scripts/derive_targets.py`), run once and committed with its output.
