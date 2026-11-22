# Plan 1d-1, government transfers: design

22 November 2026. The approach and the behaviour rules were played back to the project owner and approved. After a builder check, the owner went offline. Their standing instruction was to decide everything else the way the real system works, backed by open data. Decisions taken under that instruction are marked **Decided overnight**, each with its source and its cost if wrong. Source notes with every URL and derivation are in `docs/sources/dbt.md`.

## Intent

People with no earnings of their own have no money of their own in ArthaSim.

On `main` (commit `1b5d045`, tier S, 90 days from 1 April 2025, seed 7), 4.72% of payment attempts fail for insufficient funds. Households with no earned income cause 45.4% of those failures. In April, 3,349 of 38,250 households have no earned income, three-quarters of them in the metro district. Their adults are mostly:
- women homemakers aged 21–59 (2,270);
- students (1,445);
- people aged 60 or over who are not "retired" and so get no pension (900);
- job seekers (545).

In India many such people receive direct benefit transfers (DBT) from the government.

Plan 1d-1 adds the government to the world and pays three DBT schemes every run, on real dates and in real amounts, into beneficiaries' bank accounts. The project owner wants **realistic accounts first**: the money in people's accounts should look and move the way it does in India. Policy experiments with transfers come later, in a separate plan (1d-2: scenarios and experiments), whose `DBTTransfer` intervention will reuse what this plan builds.

Decisions by the project owner:

- DBT is its own plan, aimed at realistic accounts. Scenarios and experiments follow as their own plan.
- Three schemes:
  - **PM-Kisan**;
  - a **social old-age pension**: central NSAP plus a state top-up;
  - a **generic state cash transfer to women**, standing in for Ladki Bahin, Ladli Behna, Gruha Lakshmi and their kind.
- The government enters the ledger **as the architecture describes** (approach A below).
- The behaviour rules as played back:
  - eligibility is checked monthly;
  - who is covered is decided once, by a fixed draw;
  - payment goes by APBS, with a purpose per scheme;
  - an eligible payee without an account gets one;
  - transfers count as income for budgets and allowances at their monthly value, kept apart from earned income;
  - contributory pensions stay where they are, and there is no tax yet;
  - "households with no income" keeps meaning no earned income.

## Goals

- A government entity in its own sector, holding a balance at the central bank.
- A new journal kind, the government transfer: government balance down, beneficiary's deposit up, the beneficiary's bank's reserves up. The settlement kernel, the Python reference journal and every invariant know its shape.
- The three schemes pay eligible, covered people on their dates by a new rail, `APBS`, each with its own purpose.
- Eligibility follows each month's life state and earned income.
- Budgets and allowances count transfers as income.
- A new truth table records, each month, who is eligible for each scheme and who is enrolled.
- Every invariant passes. The same seed gives the same content hashes, and a split run equals a single run.
- `scripts/bench.py` reports:
  - the money each scheme moves;
  - funds declines for households with no earned income, both as a share of all declines and as their own rate.

## Non-goals

- Tax, and any other government receipt. The government only pays.
- Moving contributory pensions to the government. Retired people keep their pension from the boundary.
- Other schemes:
  - MGNREGA, a wage for work, which belongs with casual earnings;
  - maternity benefit, since there are no births yet;
  - widow and disability pensions, since there is no marital status or disability;
  - scholarships and unemployment allowances, which are small, irregular and run in few states;
  - the LPG subsidy, and in-kind transfers such as the public distribution system.
- Odisha's Subhadra, which pays ₹5,000 twice a year rather than monthly.
- Failed or returned DBT credits, for example from Aadhaar seeding errors or closed accounts, and credits paid late. Every credit lands on its day.
- The `DBTTransfer` intervention, scenarios, checkpoints and experiments (plan 1d-2).
- Fitting coverage to beneficiary counts by simulation, and fixing the income levels that decide who falls under nominal income caps (plan 1e).
- Amounts that change mid-year. For example, Ladli Behna rose to ₹1,500 in December 2025; the registry holds each value as at 2025-26 budget estimates.
- e-KYC, applications and verification delays. An eligible, covered person is enrolled in the month they become eligible.
- Narrating DBT credits in statement lines. That is plan 1c's statement code, which is not on `main` yet. A hand-over note lists the new purposes, rail, kind and table for it (**Decided overnight**; cost if wrong: DBT statement lines carry a generic narration until 1c adds one).

Anti-goals, outcomes that would be failures even if the code ran:

- A government transfer that fails for lack of government funds.
- A transfer paid twice: once as a transfer and again by the income module as earnings or pension.
- A change in which households count as having no income, which would make before and after figures incomparable.
- Account ownership drifting away from its 89% target because of DBT.

## Approaches considered

| Approach | Trade-off | Verdict |
| :--- | :--- | :--- |
| **A. As the architecture describes.** The government holds a balance at the central bank. A government transfer is a new journal kind with three postings: government balance down, beneficiary deposit up, beneficiary bank's reserves up. One new branch in the settlement kernel, new shape rules in the invariants, a new sector in the flow matrix. | Transfers create deposits and reserves as real DBT does: the Union government banks with the RBI and pays through PFMS and APBS, so the beneficiary bank's reserves rise. Broad money rises by what is paid, and the sector accounts show the government paying. Tax and central-bank operations can later use the same balance. It changes the kernel, the shapes and the invariants, the most tested parts of the code. | **Chosen by the project owner** |
| **B. The government as an ordinary depositor.** A deposit at a "treasury" bank entity. Transfers are plain payments, and end-of-day netting moves reserves. | No kernel or invariant changes. But government money sits in a commercial bank, transfers only reshuffle reserves, and tax and monetary operations would need rebuilding later. | Dropped |
| **C. Pay from the boundary with DBT purposes.** | Cheapest, and statements look the same. But there is no government in the ledger at all. | Dropped |

## The government in the ledger

### Entity, sector and balance

- `EntityKind.GOVERNMENT` and `Sector.GOVERNMENT` are new. The government is one entity, standing for central and state governments together; the purpose tells the schemes apart. Its entity id comes after the boundary's.
  - **Decided overnight.** Sector accounts in phase 1 have no use for separate levels of government.
  - Cost if wrong: splitting centre and states later means a second entity and balance, with no change to the journal kind.
- `InstrumentType.GOVERNMENT` is new: the government balance, held by the government and issued by the central bank (architecture section 7.1). There is exactly one.
- The balance opens at zero and may go negative. A negative balance stands for central-bank financing (ways and means advances) until tax exists. The `non_negative` invariant covers deposits and cash only, so it does not apply here. Nothing ever declines a government transfer for funds.
- Dimension tables:
  - `orgs` gains one row of kind `GOVERNMENT`;
  - `accounts` gains one row of type `GOVERNMENT`, subtype `treasury`;
  - in `payments`, a government transfer's `payer_bank` is null. The government banks with the central bank, which has no bank code.
- These are population builds only. The spike world (tier XS) has no government.

### The government transfer

`Kind.GOVERNMENT_TRANSFER` (6) and `FlowType.SOCIAL_BENEFIT` (10) are new. The kind has exactly three postings, in this order:

| Line | Account | Delta |
| :--- | :--- | :--- |
| 0 | Government balance | −a |
| 1 | Beneficiary's deposit | +a |
| 2 | Reserve balance of the bank that issued that deposit | +a |

The shape rule requires all of the following:
- three lines, of types GOVERNMENT, DEPOSIT and RESERVE;
- line 0 negative;
- lines 1 and 2 each equal to −(line 0);
- the line-2 reserve held by the issuer of the line-1 deposit.

Both `Journal.check_shape` (the Python reference) and the vectorised `_check_shapes` enforce it.

**Settlement kernel.**
- A government-transfer intent always succeeds: no funds check and no technical decline. The kernel posts the three lines in one journal entry.
- It finds the reserve account through a new per-account lookup, `reserve_for_deposit`. The lookup is built with the book and grown by `open_accounts`, like the other per-account arrays.
- The payment row records the government balance as payer account and the deposit as payee account.

**End of day.** Interbank netting nets `PAYMENT` entries only, so it skips government transfers. Their reserves have already moved.

**Invariants.**

| Invariant | Effect |
| :--- | :--- |
| Shapes | The new kind's rule, as above |
| Stock and flow | Unchanged |
| Non-negative | Unchanged; the government balance is not a deposit |
| Bank balance sheet | Holds without change: reserves and deposit liabilities both rise by a |
| Cash conservation | Unchanged; no cash moves |
| Flow rows and columns | The flow matrix includes lines 0 and 1 of each government transfer under `SOCIAL_BENEFIT`. The reserve line is left out, as cash withdrawals are: for the bank it is an asset matched by a new liability, not income. The government sector's net position falls by a and households' rises by a; banks and the central bank net to zero. Rows and columns both balance. |

Broad money, meaning deposits and cash held outside banks, rises by every rupee paid.

### Rail and purposes

- `Rail.APBS` (11): the Aadhaar Payment Bridge System, which NPCI runs for DBT credits to Aadhaar-seeded accounts.
- Purposes `DBT_PM_KISAN` (7), `DBT_OLD_AGE_PENSION` (8) and `DBT_WOMEN` (9). These values are unused, between `ALLOWANCE` (6) and `GROCERY` (10).

## Schemes

Two notes apply throughout:
- **Earned income** means `monthly_income_paise`: earnings, salary or contributory pension, never transfers.
- **Per-member income** means a household's earned income divided by its adults plus dependants.

### PM-Kisan

- **Who.** A household with at least one own-account farmer (life stage farm, not a helper), standing for a landholding farmer family.
- **Excluded**, following the scheme's operational guidelines:
  - any member salaried in public administration, standing for a serving government employee;
  - any member whose earned income is over ₹7 lakh a year, standing for an income-tax payer;
  - any retired member with a pension of ₹10,000 a month or more.
- **Payee.** The household's eldest own-account farmer; ties go to the lowest entity id. Chosen afresh each month.
- **Amount and dates.** ₹2,000 per instalment, on the national release dates:

  | Instalment | Date |
  | ---: | :--- |
  | 20th | 2 August 2025 |
  | 21st | 19 November 2025 |
  | 22nd | 13 March 2026 |
  | 23rd | 20 June 2026 |

  A run past the last listed date gets no further instalments until the list grows. The 90-day bench (1 April to 29 June 2025) contains no instalment; a 12-month run from April 2025 has three.
- **Coverage.** 0.66, one fixed draw per household.
  - **Decided overnight.** 9.7 crore families were paid in August 2025, against 14.645 crore operational holdings in the Agriculture Census 2015-16.
  - Cost if wrong: farm households' PM-Kisan income is off in proportion. It is ₹500 a month per enrolled household, small against farm earnings.
- **Taxpayer threshold.**
  - **Decided overnight.** Instalments in 2025-26 check assessment year 2025-26, that is income earned in 2024-25. Under that year's new regime, the section 87A rebate made income up to ₹7 lakh tax-free.
  - Cost if wrong: a few high-earning farm households are wrongly included or excluded.
- **Monthly value for budgets.** ₹500 (₹6,000 a year over 12 months), counted for the payee every month the household is enrolled, including months with no instalment.

### Social old-age pension

- **Who.** A person aged 60 or over whose life stage is not retired, in a BPL household. Retired people have a contributory pension in this model and do not qualify.
- **BPL list.**
  - **Decided overnight.** Real BPL lists come from the 2002 BPL census and SECC 2011. They are years old, fixed between revisions, and their size was set near the official poverty headcount.
  - The model draws its list once, at build. A household is BPL if its per-member earned income is among the poorest persons up to the Rangarajan Expert Group's 2011-12 headcount: 30.9% of persons in the rural district and 26.4% in the metro district.
  - The list stays fixed for the run.
  - Because it is share-based, it does not depend on the level of simulated incomes, which plan 1e has yet to calibrate.
  - Cost if wrong: if today's lists are smaller (poverty has fallen since 2011-12), the pension reaches somewhat more elderly people than it should.
- **Amount.**
  - The central NSAP share is ₹200 a month at ages 60–79 and ₹500 from 80.
  - A state top-up of ₹800 brings it to ₹1,000 or ₹1,300 a month.
  - **Decided overnight.** PIB (November 2025) gives state top-ups from ₹50 to ₹5,700 a month, and an average pension around ₹1,100 in many states.
  - Cost if wrong: about ₹100 a month per pensioner.
- **When.** The 5th of each month.
  - **Decided overnight.** States pay on their own calendars, monthly or quarterly. No single published day exists, and early in the month is the common pattern.
  - Cost if wrong: credits land a few days earlier or later within the month.
- **Coverage.** 0.5, one fixed draw per person.
  - **Decided overnight.** About 16 crore people were aged 60 or over in 2025, interpolated between MoSPI's 2021 and 2031 figures. About 30% of them are poor, which makes about 4.8 crore. The 2.21 crore IGNOAPS beneficiaries are 0.46 of that, rounded up for pensions states pay from their own schemes. LASI found about 30% of BPL elderly receiving IGNOAPS in 2017-18, before later expansion.
  - Cost if wrong: elderly people's transfer income is off in proportion.

### State cash transfer to women

- **Who.** A woman aged 21 to 60 whose household's earned income is under ₹2.5 lakh a year, with no member salaried in public administration. These are the Ladli Behna and Subhadra age range, with Ladki Bahin's income cap and exclusion. The cap is nominal, as in the real schemes.
- **Amount.** Each covered woman gets one of six monthly amounts, fixed for the run, standing for the state she lives in. It is drawn once per person with weights equal to beneficiaries implied by PRS's table of the 12 state schemes (budget estimate ÷ (benefit × 12), 2025-26):

  | Monthly amount | Implied beneficiaries (lakh) | Where it comes from |
  | ---: | ---: | :--- |
  | ₹1,000 | 363.2 | Chhattisgarh, Tamil Nadu, West Bengal at its general rate |
  | ₹1,250 | 157.8 | Assam, Madhya Pradesh |
  | ₹1,500 | 200.8 | Maharashtra, Himachal Pradesh |
  | ₹2,000 | 119.2 | Karnataka |
  | ₹2,100 | 19.8 | Haryana |
  | ₹2,500 | 61.6 | Delhi, Jharkhand |

  The weighted mean is ₹1,405.
  - **Decided overnight.** Real accounts show the amount of the state's scheme, not an average.
  - Cost if wrong: individual amounts are off, but the total stays near PRS's ₹1.68 lakh crore across about 10 crore women.
- **When.** The 10th of each month.
  - **Decided overnight.** Ladli Behna was usually credited around the 10th. Other states vary.
  - Cost if wrong: credits land a few days earlier or later within the month.
- **Coverage.** 0.4, one fixed draw per person.
  - **Decided overnight.** About 12 crore beneficiaries (EAC-PM, 2026) out of roughly 37.5 crore women aged 21–60 is 0.32 of all such women. If about three-quarters are under the caps, coverage of the eligible is about 0.4. That reflects the share of women living in a state with a scheme, times take-up.
  - Cost if wrong: the number of women paid is off in proportion.
- **Income levels.** Simulated incomes run high, so fewer women fall under the nominal cap than would in India. In the April baseline, 19% of metro and 34% of rural women aged 21–60 are under it. Women in households with no earned income all qualify. The results report the share of women aged 21–60 paid against the real 0.32; calibrating incomes is plan 1e.
- **Overlap with the pension.** A woman of exactly 60 can draw both the women's transfer and the old-age pension.
  - **Decided overnight.** Ladki Bahin excludes only women drawing ₹1,500 or more from another scheme, and the pension is ₹1,000–1,300.
  - Cost if wrong: a handful of women aged 60 get ₹1,000–1,300 a month too much.

## Rules common to all schemes

**Order.** A new module, `GovernmentTransfers` (name `dbt`), runs monthly after `lifecourse` and before `budget`. The module list becomes `lifecourse, income, remittances, dbt, budget, allowance, consumption, cash`.

**Each month, in `monthly`:**

1. **Eligibility.** Each scheme's rule is applied to the month's state, after the life course has run. It uses earned income and the build's BPL list.
2. **Coverage.** Covered means `uniform(seed, "dbt.<scheme>.cover", entity, 0) < coverage`. The entity is the person, or the household for PM-Kisan; the women's amount tier is drawn the same way. The draw does not depend on the month, so the same people are covered whenever they are eligible.
3. **Enrolment.** Enrolled means eligible and covered.
4. **Accounts.** An enrolled payee without a bank account opens one that month through `open_accounts`. It is a zero-balance account at a bank drawn as for voluntary openings (`pick_banks`). The opening is logged as `ACCOUNT_OPENED` in `life_events`, with event ids continuing the life course's counter.
5. **Transfer income.** Each person's monthly transfer income is the sum of the monthly values of the schemes they are enrolled in. It is held on the behaviour state, apart from `monthly_income_paise`.
6. **Truth table.** One row per eligible payee per scheme goes into `truth_dbt_monthly` (see "New table").

**Payees are banked from the start.**
- **Decided overnight.** Every real DBT payee has an Aadhaar-seeded bank account, and PMJDY grew around DBT. The account-ownership target (89%) already includes them.
- So the build applies the same eligibility and coverage rules to the start month's state before it assigns accounts. Every enrolled payee then has an account.
- To keep ownership on target, each unbanked enrolee swaps with a banked, non-salaried, non-enrolled person in the same district, chosen by a keyed draw. The enrolee gets the account, the other person loses theirs. Salaried people always keep their salary account. If a district runs out of such people (only in tiny worlds), the extra accounts stay.
- After the build, only people who become eligible during the run open accounts, through step 4 above.
- Cost if wrong: unbanked people are slightly more concentrated among those who get no DBT than in reality.

**The month's state table follows DBT.** `entity_state_monthly` is written once every module's `monthly` hook has run, rather than inside the life course's. A person who opens an account for DBT is then shown with it in that month's row. **Decided overnight**, to keep the two tables consistent.

**Each day, in `intents`.** On a scheme's pay day there is one intent per enrolled payee:
- kind `GOVERNMENT_TRANSFER`, flow `SOCIAL_BENEFIT`;
- from the government balance to the payee's primary deposit;
- rail `APBS`, with the scheme's purpose and the payee's amount;
- a slot from 24 to 39 (06:00 to 09:59), drawn per person and day.

On the slots: **Decided overnight.** APBS credits are bulk files that sponsor banks submit and NPCI settles in batches, and beneficiaries typically see them early in the day. No published time distribution exists. Cost if wrong: DBT credits sit at the wrong hours in intraday patterns.

A run that starts mid-month skips pay days before its first day; nobody is paid arrears.

**Budgets and allowances count transfers.**
- `Budget` sets each household's budget from earned income plus its members' transfer income.
- `Allowance` computes each member's shortfall and surplus from earned income plus transfer income. A woman receiving ₹1,500 needs ₹1,500 less from the household's earners.
- `truth_household_monthly` keeps `income_paise` as earned income and gains `transfer_income_paise`.
- "Households with no income" in the bench and the results means `income_paise = 0`, as before.
- The bench's allowance diagnostics (`_mixed_households` and the two shares built on it) use the same income as `Allowance`.

## New table

`truth_dbt_monthly`, truth layer, partitioned by month. It has one row per eligible payee per scheme per month, written in `monthly`, with these columns:
- `entity_id`;
- `month`;
- `scheme`: `PM_KISAN`, `OLD_AGE_PENSION` or `WOMEN`;
- `enrolled`: boolean;
- `monthly_value_paise`: zero when not enrolled;
- `opened_account`: true when enrolment made the payee open an account this month.

It joins `FACT_TABLES`, and content hashes cover it.

## Parameters

There are about 17 new registry rows with prefix `dbt.`, and the row-count test in `tests/test_build_1b.py` moves with them. Each has a source from `docs/sources/dbt.md` and a status: `unverified` (transcribed from a published source) or `assumption` (derived or chosen there).

| Row | Value | Status |
| :--- | :--- | :--- |
| PM-Kisan amount | ₹2,000 per instalment (appendix A's `dbt.pm_kisan`) | unverified |
| PM-Kisan dates | The four listed above | unverified |
| PM-Kisan coverage | 0.66 | assumption |
| PM-Kisan pension exclusion | ₹10,000 a month | unverified |
| Taxpayer threshold | ₹7 lakh a year | assumption |
| Old-age minimum age | 60 | unverified |
| Old-age central amount | ₹200 under 80, ₹500 from 80 | unverified |
| Old-age state top-up | ₹800 | assumption |
| BPL headcount shares | Rural 0.309, metro 0.264 | unverified |
| Old-age coverage | 0.5 | assumption |
| Old-age pay day | 5 | assumption |
| Women's ages | 21 to 60 | unverified |
| Women's amount tiers | Six amounts with weights | assumption |
| Women's income cap | ₹2.5 lakh a year | unverified |
| Women's coverage | 0.4 | assumption |
| Women's pay day | 10 | assumption |
| DBT slot window | 24 to 39 | assumption |

## Randomness

Stream names start with `dbt.`:
- coverage and amount-tier draws are keyed on the entity alone;
- the build's account swap is keyed on the person;
- slot draws are keyed on the person and the day;
- bank choice for accounts opened during the run is keyed on the person and the first day of the month, as the life course's openings are.

Same seed, same output; a split run equals a single run.

## What other parts see

| Part | Change |
| :--- | :--- |
| `build/pipeline.py`, `build/banking.py` | Government entity, sector and balance; BPL list; enrolment at build and the account swap; `reserve_for_deposit` |
| `ledger/` | New instrument type, kind and flow type; the shape rule; the flow matrix |
| `engine/settlement.py`, `engine/scheduler.py` | Kernel branch; `reserve_for_deposit` passed in; netting unchanged |
| `engine/intents.py` | `Rail.APBS`; three purposes |
| `life/accounts.py` | `open_accounts` grows `reserve_for_deposit` |
| `modules/lifecourse.py` | `entity_state_monthly` written after every module's `monthly` hook |
| `behaviour.py`, `modules/budget.py`, `modules/allowance.py` | Per-person transfer income; budgets and allowances count it |
| `world.py` | Module list; `truth_household_monthly` gains a column; the government in the dimension frames |
| `store/parquet.py` | `truth_dbt_monthly` joins `FACT_TABLES` |
| `scripts/bench.py` | New figures (below); a "government" purpose group |
| Tests | `test_money_flows.py` (module list), `test_build_1b.py` (row count), enum-value tests |

**Parallel work.** Plan 1c (data products) is being built in parallel and touches `params/registry.yaml`, the row-count test, `world.py`, the store and the bench too. Whichever plan merges second rebases. A note in the sessions' shared notes folder lists for 1c what this plan adds.

## Success measure

**Fast tests:**
- the shape rule, including rejection of each malformed variant;
- the kernel posts a government transfer and never declines it;
- the invariants hold with transfers in the day;
- each scheme's eligibility and exclusion rules;
- the BPL list's shares;
- coverage stays with the same people from month to month;
- every enrolee is banked at build and account ownership is unchanged by the swap;
- account opening for people enrolled during the run;
- budgets and allowances count transfer income;
- determinism, and a split run equalling a single run.

**A slow gate.** A 12-month run at tier S from April 2025, seed 7, which may share the life-course gate's run. In it:
- PM-Kisan pays on exactly 2 August 2025, 19 November 2025 and 13 March 2026;
- every enrolled payee is paid on every pay day of their scheme;
- the government balance equals minus the total paid;
- every invariant passes.

**Bench additions.** `scripts/bench.py` reports:
- per scheme: credits, rupees paid and distinct beneficiaries;
- the government balance at the end;
- accounts opened for DBT during the run;
- in the last month, the share of women aged 21–60, of people aged 60 and over, and of farm households enrolled;
- funds declines by payers in households with no earned income, both as a share of all funds declines (already reported) and as their own decline rate (new);
- the number of such households.

**Results doc.** `docs/phase1d1_results.md` gives these figures before (on `main`) and after, for the 90-day bench and for a 365-day run. Every figure is re-queried. It covers:
- funds declines overall;
- funds declines for households with no earned income;
- money moved by scheme;
- enrolment shares against the published figures;
- cost in time and memory.

Funds declines from households with no earned income are expected to fall but not vanish. Students and job seekers get no transfer, and coverage is partial.

## Left to the builder

- File layout. Suggested: `src/arthasim/modules/dbt.py` for the module and scheme definitions, with eligibility functions the build can call too.
- How a scheme is represented. It should be a list of scheme definitions the module holds (eligibility, payee, amount, monthly value, pay days, purpose, coverage), so plan 1d-2's `DBTTransfer` can add one at run time.
- Where government state lives: the entity, balance account and BPL list.
- Registry ids, and whether related values share a row.
- Whether the slow gate shares the life-course gate's 12-month run.
- The bench's output format for the new figures.
