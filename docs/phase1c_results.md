# Plan 1c results: data products

Measured on 23 November 2026 at tier S (100,000 adults), seed 7, from 1 April 2025, on an Apple M5 with 16 GB, Python 3.12, polars 2.1.0 and duckdb 2.0.1, with `PYTHONPATH=src` from a scratch virtual environment.

- **Before:** `main` at `e9fd517` (plan 1d-1, government transfers), exported with `git archive`.
- **After:** this branch, rebased onto that commit.

Commands:
- `python scripts/bench.py --tier S --days 90 --seed 7`, run four times in turn: `main`, branch, `main`, branch.
- `--days 365` once on the branch.
- `python scripts/data_products_demo.py <365-day run> --bank SYNB01`, which times each call. SYNB01 is the largest bank.

Every figure below was re-queried from those runs by one script.

## Each call, on a year at tier S

The 365-day run has 62,256,321 payment attempts.

| Call | Seconds | Rows |
| :--- | ---: | ---: |
| `Run.open` | 0.000 | |
| `run.table("payments")`, UPI_P2M count | 0.021 | 1 |
| `run.sql`, status counts | 0.057 | 4 |
| `run.view("bank", bank="SYNB01")`: `customers` | 0.028 | 26,319 |
| `accounts` | 0.028 | 26,319 |
| `payments` | 2.371 | 8,258,200 |
| `statement_lines` | 4.813 | 8,219,430 |
| `balances_monthly` | 0.051 | 313,038 |
| `run.view("switch")`, UPI counts by rail and status | 0.739 | 8 |
| `run.view("switch", network="atm")` `payments` | 0.788 | 2,077,691 |
| `run.view("bureau")` `consumers` | 0.011 | 0 |
| `run.inspect(2)` | 0.013 | |
| `profile()` | 0.390 | 2 accounts |
| `timeline()` | 0.514 | 637 |
| `passbook()` | 0.579 | 741 |
| `net_worth()` | 0.022 | 12 |
| `ego_network()` | 0.008 | 14 |
| `run.metric("txn_volume", by="month")` | 0.508 | 12 |
| `run.metric("decline_rate", by="month")` | 0.509 | 12 |
| `run.metric("consumption", by="month")` | 0.652 | 12 |
| `run.metric("cash_withdrawal", by="month")` | 0.238 | 12 |
| `run.metric("deposit_balance")` | 0.047 | 12 |
| `run.export(dest, view="bank", bank="SYNB01")` | 13.100 | 6 tables |

- **`watch`** is tested in the fast suite and in the slow gate. It changes no content hash, so it has no timing row here.
- **Memory:** the demo process as a whole peaked at 5,042 MB.
- **Export:** the bank export is 521.7 MB in 39 Parquet files, plus a manifest and a README.
  - Its tables: `accounts` and `customers` (26,319 rows each), `instruments` (109,581), `balances_monthly` (313,038), `payments` (8,258,200) and `statement_lines` (8,219,430).
  - The three fact tables have one folder per month.
  - The manifest's keys are `asof`, `scope`, `source_content_hash`, `source_run`, `tables` and `view`. There is no run ID and no seed.

## Memory and runtime before and after

| Tier S, 90 days | `main` run 1 | `main` run 2 | Branch run 1 | Branch run 2 |
| :--- | ---: | ---: | ---: | ---: |
| Payment attempts | 15,282,932 | 15,282,932 | 15,282,932 | 15,282,932 |
| Build time | 0.54 s | 0.55 s | 0.89 s | 0.90 s |
| Simulation time | 9.62 s | 9.65 s | 10.83 s | 10.83 s |
| Total, including tables, hashing and manifest | 11.65 s | 11.70 s | 12.17 s | 12.19 s |
| Peak memory | 3,082 MB | 2,796 MB | 999 MB | 1,024 MB |

**Memory.** Peak memory falls by about two-thirds. `main` holds a whole month of payments, journal and postings before writing them. The branch writes every million rows of a table as a complete file and keeps each fact table's content hash as it goes.

**Time.** Simulation takes about 1.2 s (12%) longer. The cause has not been isolated: hashing a month of payments, journal and postings costs about 0.1 s in isolation. Total time is 0.5 s (4%) longer. The work after the last day (total less build and simulation) takes 1.5 s on `main` and 0.45 s on the branch: `main` reads every fact table back from disk to hash it, while the branch has already hashed it. Build time is 0.35 s longer; the build now also makes account and customer numbers, terminals and keyed tokens.

**A full year on the branch:** 365 days take 46.0 s of simulation and 47.3 s in total, with peak memory 1,173 MB. That is 62,256,321 attempts, 1,352,311 a second.

**The writer we didn't keep.** The first version of the store kept one open PyArrow writer per table and month, as the spec first chose. In the same alternating comparison it took 16.7 s and 16.8 s of simulation, against `main`'s 9.7 s and 10.0 s. PyArrow's writer took about 1.2 s for a month of payments, where Polars takes about 0.2 s. So each chunk is now a complete Polars file.

## Nothing else changed

Content hashes of the branch's first 90-day run against `main`'s first:

| Table | Same as `main` |
| :--- | :--- |
| payments, journal, postings | yes |
| truth_household_monthly, life_events, entity_state_monthly, truth_dbt_monthly | yes |
| households, orgs, banks, edges, geo, truth_person_latent | yes |
| persons | no, on purpose |
| accounts | no, on purpose |
| instruments | no, on purpose |
| balances_monthly, bank_customers | new |

What differs in the three changed tables:

- **`persons`** gains `birth_year`. `uid_token` and `mobile_token` change value, because tokens are now keyed one-way hashes. Every other column equals `main`'s.
- **`accounts`** without its new `opening_balance_paise` column equals `main`'s.
- **`instruments`:**
  - The BRANCH rows are identical to `main`'s.
  - DEVICE, DEBIT_CARD and MOBILE cover the same accounts as on `main` (43,816, 64,261 and 82,228), with new token values.
  - The persons' VPAs cover the same 43,816 accounts. Merchants and billers bring the total to 45,500 VPAs.
  - New: 111,863 ACCOUNT_NO rows (one per deposit account) and 437 TERMINAL rows.

The branch's 90-day run folder holds no `.spool` directory and no `.tmp` file. All six slow gates pass on the branch in 148.7 s: phase 0, 1a, 1b-1, 1b-2, 1c and 1d-1. The fast suite passes: 299 tests.

## Disk

Tier S, 90 days, in MB, with the number of files in brackets.

| Table | `main` | Branch |
| :--- | ---: | ---: |
| payments | 267.5 (3) | 267.5 (15) |
| postings | 401.0 (3) | 401.0 (28) |
| journal | 61.0 (3) | 61.0 (15) |
| instruments | 3.4 | 5.2 |
| accounts | 0.6 | 1.3 |
| persons | 2.7 | 2.8 |
| balances_monthly | | 2.1 (2) |
| bank_customers | | 1.3 |

Every other table is the same size on both. Fact tables now have about one file per million rows, against one file a month on `main`, and the same total size.

## What each observer sees

SYNB01's statement lines over the year, one narration per rail:

| Rail | Lines | Example narration |
| :--- | ---: | :--- |
| UPI_P2M | 5,704,405 | `UPI/DR/000002858939/b_5645a70da7e51766@syn02` |
| DEBIT_CARD | 673,431 | `POS/DR/000002858909/t_5d5fea7422160206` |
| ATM | 526,233 | `ATM/WDL/000002858979/ATMSY010000000` |
| UPI_P2P | 334,071 | `UPI/CR/000002859155/SYNX00-2a03c7dab6aad66f` |
| BRANCH | 248,432 | `CASH DEP/000002955719/SYNB01` |
| AEPS | 247,075 | `AEPS/WDL/000002858999/MATMSY010000014` |
| NEFT | 244,302 | `NEFT/CR/000002859091/SYNX00-2a03c7dab6aad66f` |
| NACH_CR | 157,068 | `NACH/DR/000002947338/SYNB03-81a330a8ee11adbb/SALARY` |
| IMPS | 62,871 | `IMPS/DR/000002859305/SYNB01-1fdff286d1d1f87e` |
| APBS | 21,542 | `APBS/CR/000031656940/PFMS/DBT_OLD_AGE_PENSION` |

- **NACH line.** The example is a salary debit from an employer's account at SYNB01, so the other side is that employee's account at SYNB03. The payer's remark (SALARY) appears on both sides.
- **APBS line.** Government transfers arrive from PFMS and name the scheme. Over the year there were:
  - 47,363 DBT_WOMEN credits;
  - 19,695 DBT_OLD_AGE_PENSION credits;
  - 18,445 DBT_PM_KISAN credits.

Payment attempts each switch network sees over the year:

| Network | Attempts |
| :--- | ---: |
| upi | 14,269,468 |
| atm | 2,077,691 |
| card | 1,526,307 |
| aeps | 977,896 |
| nach | 292,710 |
| imps | 133,964 |
| apbs | 85,503 |

The bureau view is empty: nobody borrows until phase 3, and a real bureau holds no file on people who have never applied for credit.

## Metrics

`run.metric("decline_rate", by="month")` over the year:

| Month | Apr | May | Jun | Jul | Aug | Sep | Oct | Nov | Dec | Jan | Feb | Mar |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Declined | 5.32% | 3.52% | 4.22% | 4.35% | 4.28% | 4.23% | 4.12% | 4.03% | 3.90% | 3.84% | 3.82% | 3.62% |

`run.metric("deposit_balance")` gives persons' deposits at each month end. They grow from ₹324 crore at the end of April 2025 to ₹672 crore at the end of March 2026. Balances build up over the year, as plan 1b-2's results also found (`docs/phase1b2_results.md`).

## Review

A fresh Opus reviewer read the whole branch before the rebase and found six Important issues; two Minor ones were re-graded to Important. Each was fixed with a test that failed first:

- a watch callback that raised left the day half-done;
- files still being written were visible under their final names;
- an `asof` cut returned rows in a varying order;
- export ran each table's query once per month;
- spool files were left in finished runs;
- export tokens could be decoded to simulator IDs;
- `deposit_balance` failed before any month closed;
- statement lines joined every payment.

The export of SYNB01 for the year took 134 s in the review and takes 13.1 s now. The rulings and deferred minors are in `docs/superpowers/ledger.md`.

## Limits

- **`pan_like` (plan 1a) still encodes the person's place in the population.** `ref` is the run's payment sequence number. Tokens are keyed by the run seed. So an export is not anonymised against someone who has the simulator's code; its README says so. Before any external release, `pan_like` needs a keyed format-preserving permutation and the token key needs a secret (blueprint section 17).
- **Tier M** is not measured. Memory there is bounded by the million-row chunks per table, not by the month, but no tier M run was made.
- **Bank customers carry no Aadhaar token.** Now that DBT seeds accounts, the KYC rule's exception for DBT beneficiaries would let a bank hold Aadhaar for them. That column is a follow-up.
