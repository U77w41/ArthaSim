# Plan 1c, data products: design

22 November 2026. The project owner agreed the shape in conversation: who it is for, the IDs, the scope and the behaviour of each call. They then told the builder to carry on without asking, deciding from the real world and public evidence. Everything marked **Decided overnight under the user's standing instruction** was settled that way, after a builder check, and is for the project owner to review.

## Intent

A finished run today is a folder of truth tables that you can read with `run.table` and `run.sql`. Plan 1c turns it into what people use. That means what one bank, a payment switch or the bureau would see, a trace of one person, outcome numbers, and files to hand to others. It also fixes the store so tier M fits in memory.

Who it is for, in the project owner's order:

1. **Researchers working in Python, first.** They open a run, follow people, compare banks and compute outcomes.
2. **A bank dataset for partners, next.** It is one bank's view written to files that can be handed out.

So the Python calls are the core. The bank view is built to partner standard from the start, because retrofitting that later would cost more than doing it once.

Blueprint section 14.1 lists the phase 1 calls this plan makes work: `Run.open(path)`, `run.table`, `run.sql` (these three exist), `run.view("bank", bank=...)` and the switch and bureau views, `run.inspect(entity_id)`, `world.watch(entity_id, callback)`, `run.metric` and `run.export(dest, view=...)`. The phase 0 plan's list for 1c is observer views, inspector, monthly state snapshots, statement lines and export.

## Goals

- Every call above works on a tier S run, and the results doc shows each one with its runtime.
- **Bank view.** It shows only what that bank holds: its customers' KYC fields, their accounts, payments from the bank's side, statement lines with narrations, and month-end balances. The other side of a payment appears as a handle and a bank code, never as a person or a simulator ID of another bank's account.
- **Switch view.** It shows the payments on one network, with handles, banks, amount, time, status and merchant category, and no balances or KYC.
- **Bureau view.** It has consumer, tradeline, enquiry and score tables with their columns. They stay empty until loans exist (phase 3), because a real bureau holds no file on anyone who has never applied for credit.
- **Truth view.** It shows everything.
- **Inspector.** It returns one entity's profile at a date, a timeline of payments and life events, a passbook, month-end net worth and their social links.
- **Watch.** A callback during a run receives each day's activity for one entity.
- **Metrics.** There are five built-in outcome measures, user metrics can be registered, and they share one return contract that plan 1d's `effect(metric)` will use.
- **Export.** It writes a view to Parquet. In a bank export, customers and accounts carry the bank's own numbers, never the simulator's IDs.
- **Monthly snapshot.** Every account's closing balance is recorded at each month end.
- **Store.** Memory no longer grows with the size of a month. The content hash is computed as rows are written, in the same format as today.
- **No change to the simulation.** Every existing table keeps its content hash except `persons`, `accounts` and `instruments`, which change on purpose (see Data changes).

## Non-goals

- **UPI Lite.** It gets its own plan after this one. It changes the simulation (a wallet instrument, a new ledger shape, bank balance sheets, settlement netting). Researchers don't need it for any call here, and leaving it out lets this plan prove the data is unchanged.
- **Account aggregator and regulator views.** They are not in the phase 1 call list. The AA view needs consent records first.
- **Task builders (`tasks.*`), `run.validate`, `Experiment`, `fork_at`, checkpoints.** These belong to phase 2, plan 1e and plan 1d.
- **Hiding information from a determined user.** Views guard against mistakes, not against someone reading the Parquet files directly. A hook in phase 2 is user code in the same process.
- **CSV export, coarser geography for public release, legal review.** These come later, if release becomes a goal.
- **A version-independent content hash.** Row hashes come from Polars `hash_rows`, which can differ between Polars versions. That is unchanged here, and the manifest records the Polars version so hashes are compared like for like.

## Anti-goals

- A view that reveals the other side of a payment through an ID, a handle that encodes an ID, or a narration that carries the simulator's internal record of why a payment was made (its `purpose`).
- A view whose SQL can reach truth tables by name.
- Any change to payments, journal, postings or the other existing fact tables.
- A results doc with any statement that has not been re-queried.

## Constraints

- Same seed, same output. New identifiers come from keyed draws on their own streams (`rng.bits`), so they never shift a simulation draw. There is no `np.random` under `src/`.
- A run split across `step` calls must give the same tables and hashes as a single run.
- `tests/test_build_1b.py` pins the registry row count. This plan adds no registry rows, because merchant category codes, identifier formats and the row-group size are code constants and not model parameters.
- A separate session is building plan 1d's government transfers (DBT). Its draft spec (`docs/superpowers/specs/2026-11-22-government-transfers-design.md` on its branch) adds:
  - a government entity and its balance account;
  - a new ledger kind, rail (APBS) and three purposes;
  - a fact table, `truth_dbt_monthly`;
  - registry rows.

  It changes payments, journal and postings on purpose.

  > **Decided overnight under the user's standing instruction:**
  > - The store goes first in this plan. It is the part most likely to conflict, and it doesn't depend on anything else.
  > - Whichever plan lands second rebases.
  > - The "no change" check is against `main` as it stands when this branch merges. If DBT has landed, the comparison run is redone on that `main` tip, not against commit 1b5d045.
  > - The running hash need not survive a checkpoint. A resumed run uses the from-disk hash (section 2).
  >
  > Cost if wrong: one extra bench run at merge time.

## Approaches considered

Three choices about the build. The project owner left the how to the builder, and these are the calls made:

| Choice | Options | Call |
| :--- | :--- | :--- |
| How views get their data | (A) A view is a set of queries over the run's existing files, run when read. (B) Write each observer's tables during the run. (C) Build them on first use and cache them in the run folder. | **A.** Nothing extra is written during a run, and a view can't fall out of step with the truth tables. A scan costs little: one person's payments over 90 days at tier S took 0.4 s. B makes every run pay for twelve banks' copies. C can be added later if A turns out too slow. |
| How rows reach disk | (A) Keep one file open per table and month, and write rows in chunks as they come. (B) Write a new file every few days. | **A.** Memory depends on the chunk size, not the month. Files stay one per month, plus one more for each extra `step` call that lands inside the month, as today. |
| How the content hash is computed | (A) Hash rows as they are written, in today's format. (B) A new streaming format. (C) Re-read the files after the run in small pieces. | **A.** The branch's hashes must equal `main`'s for every unchanged table, which proves the data didn't change. B changes every hash value. C adds a pass over every file each time a run stops. |

Decisions the project owner made in conversation:

- Researchers in Python come first, a partner bank dataset next.
- **IDs: both.** Views in Python carry the simulator's IDs, so they join straight to truth tables and labels. `export` writes each bank's own customer and account numbers instead.
- UPI Lite moves to its own plan, and the bureau view ships with empty credit tables. Overnight this became an empty consumers table too (see the bureau view).
- Opaque handles replace the VPAs that embed an `entity_id`, and merchants, billers and employers get handles.
- The narration, metric, watch and inspector behaviour is as described below.

## Measured starting point

From a tier S, 90-day, seed 7 run of `main` (commit 1b5d045) on an Apple M5 with 16 GB and Python 3.12:

- 15,260,566 payment attempts. Simulation 21.9 s, total 28.0 s. Peak memory 1,718 MB. Earlier results docs report 2.1 to 2.7 GB for the same command, and the figure varies from run to run.
- One month (May 2025) in memory is 5,143,600 payments (407 MB), 4,928,732 journal entries (197 MB) and 10,162,962 postings (407 MB). All of it is buffered before it is written. Tier M has ten times the persons, so about 10 GB a month.
- The content hash already reads one month at a time, so its memory is one month of one table.
- Accounts: 214,312, of which 111,781 are deposits and 102,505 are cash in hand. Instruments: 43,832 VPAs, all held by persons.
- Disk: payments 255 MB, postings 380 MB, journal 56 MB for 90 days.

## Design

### 1. Store: rows written as they come

> **Changed after measurement.** PyArrow's single-threaded writer (approach A) made the simulation about 70% slower at tier S: 16.7 s against 9.8 s for 90 days, in alternating runs. So each chunk of `ROW_GROUP_ROWS` (1,000,000) rows is now written as a complete Polars file, `part-N.parquet`, under a temporary name that is renamed when the file is done. That is approach B, counted in rows rather than days.
>
> - Memory is still bounded by the chunk size.
> - The cost is about five payment files a month at tier S instead of one.
> - The rest of this section describes the original approach A.

- `Store.add(table, month, frame)` queues a frame. When a table's queued rows reach `ROW_GROUP_ROWS` (a code constant of about 500,000, the builder's to tune), they are written as one row group to that table's open file for the month. A Parquet writer (PyArrow `ParquetWriter`, zstd) stays open per table and month.
- At the end of a month, and at the end of every `step` or `run` call, all queued rows are written and the files are closed. A later call that lands in the same month opens the next `part-N` file, as today.
- Memory for queued rows is bounded by `ROW_GROUP_ROWS` per table, not by the month.
- Dimension tables are written as today, whole, at build and at every flush.
- Reading (`table_files`, `read_table`) does not change.

### 2. Content hash: computed as rows are written, same format

Today, for each fact table, the hash is one SHA-256 over all months in order. Each month contributes its name, then the schema, then the row hashes of every row under seed 0, then the row hashes of every row under seed 1 (`_ipc_bytes`). Dimension tables are hashed whole.

The new store produces exactly the same digests without holding a month:

- Each fact table has a running SHA-256. When a month opens, it takes the month's name and the schema.
- As each chunk is written, its seed-0 row hashes go straight into the running hash. Its seed-1 row hashes (8 bytes a row) are appended to a temporary spool file for that table and month.
- When the month closes, the spool is streamed into the running hash and deleted.
- The manifest after a `step` or `run` call uses a copy of each running hash, with the open month's spool appended to the copy. So a run that stops mid-month still gets a correct hash, and the running hash carries on unchanged.
- `content_hash(path, name)` stays as the from-disk version, rewritten to stream row groups (two passes per month: seed 0, then seed 1). Tests check that the live hash equals the from-disk hash, and that the from-disk hash equals today's implementation, kept in the tests as a reference.
- The from-disk version is also what a run resumed in a new process would use (plan 1d), because a SHA-256 object cannot be saved.
- The manifest records `polars_version` alongside the hashes.

Empty months behave as today: a table with no rows in a month gets no folder and contributes nothing to the hash.

### 3. Data changes

Every existing fact table is unchanged. Three dimension tables change, and two tables are new.

**`instruments`** (changes on purpose):

- **VPA** is now opaque: a 16-hex-digit token from stream `id.vpa`, keyed on the account, followed by `@synNN` (the bank). Today's `p<entity_id>@synNN` gives away who the other side is. Persons with UPI keep a VPA. UPI-accepting merchants and all billers gain one.
- **ACCOUNT_NO** is new, one for every deposit account: persons, organisations and the boundary account. It is the bank's own account number: the bank code, a hyphen, and a 16-hex-digit token from stream `id.account_no`, keyed on the account. It is unique (a test checks) and doesn't encode simulator IDs. It is also the handle the other side of a NEFT, IMPS or NACH payment sees, as a real account number is.
- **TERMINAL** is new, one for each card-accepting merchant: a token from stream `id.terminal`.
- DEVICE, DEBIT_CARD, MOBILE and BRANCH are unchanged.

**Every token is now a keyed one-way hash** (changed after the final review):
- **What changes.** The VPA, ACCOUNT_NO, customer number and TERMINAL above, and the existing uid, mobile, device and card tokens, are now each a keyed BLAKE2b digest of the id. The key comes from the run seed and the stream.
- **Why.** The earlier counter-based mix could be inverted to the simulator ID.
- **What else changes.** The format stays as it was, but the values of `persons.uid_token` and `persons.mobile_token`, and of the DEVICE, DEBIT_CARD and MOBILE instruments, change too.
- **What stays.** `pan_like` (plan 1a) still encodes the person's place in the population. Re-keying it needs a format-preserving permutation and is left for the release review.

**`accounts`** (changes on purpose):

- It gains `opening_balance_paise`, the balance when the account was opened. With it, the balance at any moment is the last posting's `balance_after_paise`, or the opening balance if there is no earlier posting.

**`persons`** (changes on purpose):

- It gains `birth_year`, so KYC carries a date of birth at month precision (the model has no day). It is worked out at build from the build age and the ageing rule. The life course adds a year in each person's birth month, and not on the first simulated day, so a person's first birthday in the run is the first time their birth month comes round after the start month:

  `birth_year = start.year − age_at_build − (1 if birth_month > start.month else 0)`

- A test checks that every `entity_state_monthly` age equals `month.year − birth_year − (1 if month.month < birth_month else 0)`.

> **Decided overnight under the user's standing instruction:** real KYC always holds a date of birth (RBI KYC Master Direction; it is on every officially valid document), and age is among the strongest features in partner credit and fraud models. Today the persons table has only the month of birth. Cost if wrong: none to the simulation; the persons hash changes, as documented.

**`bank_customers`** (new dimension, truth layer):

- One row per (bank, entity) with a deposit account at that bank: `bank_code`, `entity_id`, `customer_no`. The customer number is `CIF`, the bank code, a hyphen and a token from stream `id.customer_no` keyed on (bank, entity). A person with accounts at two banks has two customer numbers.
- Rebuilt at every flush, like `accounts`, so customers who open an account mid-run appear.

**`balances_monthly`** (new fact table, truth layer):

- One row per account per month, `account_id`, `month`, `balance_paise`, the closing balance after the month's last day.
- Written when a month's last day has been simulated, for every account in the book. A run that stops mid-month has no row for that month. That is split-safe.
- At tier S it is about 215,000 rows a month.

The boundary bank (`SYNX00`) is not a bank anyone can take a view of, but its deposit account still gets an ACCOUNT_NO, so the payments it makes and receives have a handle.

### 4. Handles and narrations

A payment's other side, as seen by an observer, is a handle plus a bank code. Which handle depends on the rail:

| Rail | Other side's handle | Bank code |
| :--- | :--- | :--- |
| UPI_P2M, UPI_P2P | Its VPA, or its ACCOUNT_NO if it has none (pay to account) | Its bank |
| NEFT, IMPS, NACH_CR | Its ACCOUNT_NO | Its bank |
| DEBIT_CARD | The merchant's TERMINAL | The merchant's bank |
| ATM (withdrawal) | An ATM terminal ID made from the account's home branch: `ATM` + the branch code | The account's own bank |
| AEPS (withdrawal) | A micro-ATM terminal ID made the same way: `MATM` + the branch code | The account's own bank |
| BRANCH (deposit) | The account's home branch code, or the bank code where the account has no branch (organisations) | The account's own bank |
| CASH | Not visible to any bank or switch | |

> **Decided overnight under the user's standing instruction:** ATM and AePS withdrawals name a terminal, not a branch. On a real ATM network the switch and the issuer see the terminal ID and the acquirer. AePS runs on a business correspondent's micro-ATM in the customer's area. Making the terminal from the home branch (bank, district, locality) gives each locality its own terminal, needs no new data, and keeps where a withdrawal happened for later fraud work. Withdrawals happen at the person's own bank in the model. Cost if wrong: an off-us ATM model would need real terminal entities and their own acquirer bank.

**Narration remarks per rail** are one mapping in code, `{rail: purposes that carry a remark}`. It covers:
- NACH_CR with SALARY and PENSION;
- APBS with the three DBT schemes, which real DBT credits name (the DBT spec asks for this).

> **Decided overnight under the user's standing instruction (after the DBT plan, 1d-1, landed on `main` first):**
> - **The other side of an APBS credit is `PFMS`**, the Public Financial Management System that the government pays transfers through. It has no bank code, because the government banks with the central bank.
> - **The switch view gains an `apbs` network.** APBS is run by NPCI and routes credits by the beneficiary's Aadhaar number, so the payee's handle there is their `uid_token` and the payer's is `PFMS`.
> - Example narration: `APBS/CR/000000076602/PFMS/DBT_WOMEN`.
>
> Cost if wrong: narration text and one switch network.

**Merchant category code (MCC)** comes from the payee organisation's category, using ISO 18245 codes:

| Category | MCC |
| :--- | :--- |
| grocery | 5411 |
| food | 5812 |
| fuel | 5541 |
| pharmacy | 5912 |
| apparel | 5651 |
| electronics | 5732 |
| transport | 4121 |
| services | 7299 |
| other | 5999 |
| telecom | 4814 |
| electricity | 4900 |
| ecommerce | 5399 |
| amc | 6211 |

Each code was checked against Citi's published Merchant Category Codes list (the Visa and Mastercard codes):

| MCC | Description |
| :--- | :--- |
| 5411 | Grocery Stores, Supermarkets |
| 5812 | Eating Places and Restaurants |
| 5541 | Service Stations |
| 5912 | Drug Stores and Pharmacies |
| 5651 | Family Clothing Stores |
| 5732 | Electronics Sales |
| 4121 | Taxicabs and Limousines |
| 7299 | Other Services, not elsewhere classified |
| 5999 | Miscellaneous and Specialty Retail Stores |
| 4814 | Telecommunication Services |
| 4900 | Utilities |
| 5399 | Miscellaneous General Merchandise Stores |
| 6211 | Securities Brokers and Dealers |

Payments to persons and employers have no MCC. The codes are labels, not model numbers, so they live in code and not in the registry.

**Reference number (`ref`).** It is shared by every observer of a payment, as a UPI RRN is: `payment_id` written as 12 digits. A real RRN is 12 digits, seen by payer, payee and switch alike, and asked for in NPCI's complaint form (HDFC Bank and Paytm UPI help pages). Partners can't reach the truth tables, and labels handed to them will be keyed on `ref`.

**Narration** is built only from what the bank sees: the rail, the direction (DR/CR), `ref` and the other side's handle. NACH credits also carry the payer's remark, SALARY or PENSION, as real payroll and pension files do. This is the only use of `purpose`.

> **Decided overnight under the user's standing instruction:** fields separated by slashes, in the order rail, direction, reference, other side, remark. There is no national narration template. RBI fixes the UTR format but not narrations, and banks differ: HDFC uses slashes, ICICI hyphens, Axis spaces. The common pattern is rail, then DR/CR, then reference, then counterparty name or VPA, then a remark, for example `NEFT CR-<IFSC>-<employer>-SALARY` (StatementFlow and Terra Insight guides to Indian narration codes; NPCI's UPI consolidated circular asks members to show the payer PSP's details but sets no template). Real narrations also carry the other side's name. The simulation has no names, so the handle stands in for one. Cost if wrong: narration text only, and nothing reads it.

Examples:

```
UPI/DR/000000001023/p_41c2…@syn01
NEFT/CR/000000004410/SYNX00-9be0…
NACH/CR/000000000377/SYNB03-e19a…/SALARY
POS/DR/000000002051/t_7f30…
ATM/WDL/000000002052/SY03002 0004
CASH DEP/000000002313/SY03002 0004
```

The builder settles the exact text within these rules.

### 5. Views

`run.view(kind, asof=None, **scope)` returns a `View` with `tables()`, `table(name, asof=None) -> pl.LazyFrame` and `sql(query) -> pl.DataFrame`.

**How a view works:**

- A view is a dictionary of named SQL definitions. Each definition reads the run's Parquet files directly (`read_parquet([...])`), with the joins and filters written inline.
- `view.sql(query)` opens a DuckDB connection in which only the view's own table names exist, so a query can't reach a truth table by name.
- `view.table(name)` returns DuckDB's lazy Polars frame (`relation.pl(lazy=True)`, available in the installed DuckDB 2.0.1) over the same definition.
- `asof` is a date. Everything up to and including that day is visible. `table(name, asof=...)` overrides the view's own `asof`. What `asof` filters:

  | Table | Rows kept |
  | :--- | :--- |
  | Payments, statement lines | Timestamp before the start of the next day (IST) |
  | `balances_monthly` | Months that ended on or before `asof` |
  | Accounts, instruments | Accounts opened on or before `asof` |
  | Customers | Customers whose first account at the bank opened on or before `asof` |

  The hook context in phase 2 will use this.
- **Views read closed files.** Every `step` or `run` call ends by closing all open files and writing the manifest. So `Run.open(world.path)` between calls sees everything simulated so far. Inside a call, the current month's rows are in an open file or still in memory, and no view sees them.

  > **Decided overnight under the user's standing instruction:** phase 2's hook context gets its own live source then. A fraud hook runs per slot and needs rows from earlier slots of the same day, which only exist in memory while the day settles, so no file layout could serve it. The view class takes its data as a list of sources (today, file lists), so a live source can be added later without changing the store. Cost if wrong: phase 2 adds an in-memory source to the view class.
- Views, `inspect` and `export` need a population-built run (tier S and above). On a spike run (tier XS) they raise an error that says so. `table`, `sql`, `metric` and `watch` work on both.
- Unknown kinds, unknown scope values and the boundary bank raise `ValueError` listing what is allowed.

**Bank view:** `run.view("bank", bank="SYNB03")`. Customers are the persons and organisations holding a deposit account issued by that bank.

| Table | Rows | Columns |
| :--- | :--- | :--- |
| `customers` | One per customer | `entity_id`, `customer_no`, `kind` (person or organisation kind), and the KYC fields. Persons: sex, `birth_year`, `birth_month`, district, locality, `has_pan`, `pan_like`, `mobile_token`. Organisations: district, locality, sector or category. No Aadhaar token, education, household, life stage, income or traits. |
| `accounts` | The bank's deposit accounts | `account_id`, `account_no`, `entity_id`, `customer_no`, `subtype`, `opened_on`, `status`, `opening_balance_paise` |
| `instruments` | Instruments on those accounts | As in the truth table |
| `payments` | Every attempt touching one of its accounts. The payer's bank sees all attempts, declines included. The payee's bank sees successes only. Cash-to-cash payments are not seen. A payment within the bank (both sides) gives two rows. | `payment_id`, `ref`, `ts`, `rail`, `status`, `amount_paise`, `direction`, `account_id`, `account_no`, `entity_id`, `customer_no`, `counterparty_handle`, `counterparty_bank`, `mcc`, `device_token` (the payer's, when the bank's customer pays by UPI) |
| `statement_lines` | One per posting on its accounts | `account_id`, `account_no`, `entity_id`, `customer_no`, `ts`, `payment_id`, `ref`, `rail`, `direction`, `amount_paise`, `balance_after_paise`, `counterparty_handle`, `counterparty_bank`, `narration` |
| `balances_monthly` | Its accounts | `account_id`, `account_no`, `month`, `balance_paise` |

There is no `purpose`, no other bank's `account_id` or `entity_id`, and no `journal_id`. Where the other side is the same bank's customer, the counterparty is still shown as a handle, as on a real statement.

> **Decided overnight under the user's standing instruction:** the bank's customer table has no Aadhaar token (`uid_token`). The RBI KYC Master Direction (2016, as amended in 2019) requires customers who are not DBT beneficiaries to redact the Aadhaar number they submit, so a bank does not keep it in general. The simulation has no DBT or Aadhaar seeding yet (plan 1d), so no account is seeded. Cost if wrong: one column to add back once seeding exists.
>
> **Also decided overnight:** occupation and declared income are left out. The blueprint (section 5.2) marks work as "inferred from credits" for a bank, and the simulation has no account-opening declaration to copy from. Cost if wrong: a declared-occupation column is a later addition and needs a rule for when it goes stale.

**Switch view:** `run.view("switch", network="upi")`. The networks are `upi` (UPI_P2M, UPI_P2P), `imps`, `nach`, `card` (DEBIT_CARD), `atm` and `aeps`. The default is `upi`. NEFT is run by the central bank, not a switch, so it has no switch view.

| Table | Columns |
| :--- | :--- |
| `payments` | `payment_id`, `ref`, `ts`, `rail`, `status`, `amount_paise`, `payer_handle`, `payer_bank`, `payee_handle`, `payee_bank`, `mcc`, `payer_device_token` (UPI only) |

All attempts on the network are included, declines too. Handles follow the table in section 4, applied to each side. For ATM and AePS the payer's handle is their debit card token, falling back to their ACCOUNT_NO for ATM and their `uid_token` for AePS (AePS authenticates with Aadhaar). The payee handle is the terminal ID from section 4.

**Bureau view:** `run.view("bureau")`.

| Table | Rows | Columns |
| :--- | :--- | :--- |
| `consumers` | Persons with at least one tradeline or enquiry, so empty until phase 3 | `pan_like`, `birth_year`, `birth_month`, `sex`, `district`, `mobile_token` |
| `tradelines` | Empty until phase 3 | `pan_like`, `lender_code`, `product`, `month`, `sanctioned_paise`, `balance_paise`, `dpd` |
| `enquiries` | Empty until phase 3 | `pan_like`, `lender_code`, `product`, `ts` |
| `scores` | Empty until phase 3 | `pan_like`, `month`, `score` |

Phase 3 may change these columns.

> **Decided overnight under the user's standing instruction:** in phase 1 the bureau view is empty, including `consumers`. The conversation had proposed "persons with a PAN". However, a credit bureau holds a file only on people reported by its member lenders, who are those who applied for or took credit. Deposit accounts are not reported (ICICI Bank, "Credit Information Bureau and CIBIL"; TransUnion CIBIL FAQ, "credit score and loan basics"). Someone who has never borrowed has no file and an NA/NH score. Nobody in the simulation borrows until phase 3, so the real bureau would show nothing. Cost if wrong: researchers can't try the bureau view's identity fields until phase 3, which is one filter to change.

**Truth view:** `run.view("truth")` returns every run table under its own name, the same as `run.table` and `run.sql`.

### 6. Inspector

`run.inspect(entity_id)` returns an `EntityTrace`. It works for persons and organisations, and raises `KeyError` for an unknown ID. It is a truth-level tool: it shows `purpose` and the other side's entity and account. It reads through DuckDB with filters on the entity's accounts.

| Method | Returns |
| :--- | :--- |
| `profile(asof=None)` | A dict with the static row (persons or orgs), the `entity_state_monthly` row for `asof`'s month (the last month if `asof` is None; persons only), household members (persons), and each account with its type, bank, handles and balance at `asof` |
| `timeline()` | A frame of payments (any of the entity's accounts, declines included) and life events, in time order: `ts`, `kind` (payment or event), `rail`, `status`, `direction`, `amount_paise`, `account_id`, `counterparty_entity_id`, `counterparty_account_id`, `purpose`, `event`, `detail` |
| `passbook(account_id=None)` | One row per posting on the entity's accounts (or one account), cash in hand included: `ts`, `account_id`, `account_type`, `rail`, `direction`, `amount_paise`, `balance_after_paise`, `counterparty_handle`, `narration` (deposit accounts), `purpose`, `payment_id` |
| `net_worth()` | Per month from `balances_monthly`: `deposits_paise`, `cash_paise`, `total_paise` |
| `loans()` | An empty frame with the loan schema until phase 3 |
| `ego_network(hops=1)` | Edges within `hops` of the entity: `src_entity_id`, `dst_entity_id`, `type`, `hop` |

### 7. Watch

`world.watch(entity_id, callback)` registers a callback, and `world.unwatch(entity_id)` removes every callback for that entity. After each simulated day, once the invariants pass, each watched entity that had any payment attempt or life event that day gets one call with a dict:

- `date`
- `entity_id`
- `payments`: a list of row dicts from the day's payments, each with `direction`
- `events`: a list of life-event row dicts
- `balances`: `{account_id: balance_paise}` at the end of the day
- `state`: the entity's `entity_state_monthly` row on the first day of a month, otherwise `None`

The entity's accounts are found from the live book each day, so accounts opened mid-run are followed. Exceptions raised by the callback propagate and stop the run. Watching reads only the frames the day already produced and draws no random numbers. A test checks that a watched run's content hashes equal an unwatched run's.

### 8. Metrics

`run.metric(name_or_fn, **kwargs) -> pl.DataFrame`. A metric is a function `fn(run, **kwargs)` that returns a Polars frame with one column per grouping and a `value` column. With no grouping it returns one row. `register.metric` is a decorator that registers a function under its name. Registering a name that already exists raises an error. Plan 1d's `effect(metric, by=...)` will call `run.metric(name, by=by)` on each arm and difference the `value` columns.

Built-in metrics:

| Name | `value` | Accepts `by` |
| :--- | :--- | :--- |
| `txn_volume` | Number of payment attempts with `status` (default SUCCESS; `status=None` counts all) | month, rail, bank, district, life_stage |
| `decline_rate` | Share of attempts not SUCCESS | month, rail, bank, district, life_stage |
| `consumption` | Paise of successful payments whose purpose is a spending category (GROCERY to MEDICAL) | month, rail, bank, district, life_stage |
| `cash_withdrawal` | Paise of successful cash withdrawals | month, rail, bank, district, life_stage |
| `deposit_balance` | Paise of persons' deposits at month end (`balances_monthly`); always by month | bank, district, life_stage |

What each grouping means:

- `month`: the payment's IST month.
- `bank`: the payer's bank code, or for `deposit_balance` the account's bank.
- `district`: the paying entity's district (persons or orgs). Payers with no district, such as the boundary, go in a null group.
- `life_stage`: the paying person's stage that month from `entity_state_monthly`. Other payers go in a null group.

`by` takes a string or a list. A grouping a metric doesn't accept raises `ValueError`.

### 9. Export

`run.export(dest, view="bank", asof=None, **scope)` writes a view's tables:

- Fact tables (`payments`, `statement_lines`, `balances_monthly`) go to `dest/<table>/month=YYYY-MM/part-0.parquet`. The others go to `dest/<table>.parquet`.
- The writing is done by DuckDB `COPY`, so memory stays bounded.
- **Observer views (bank, switch, bureau) drop every simulator ID column:** `entity_id`, `account_id`, `payment_id`, `journal_id` and any column ending in `_entity_id` or `_account_id`. Customer and account numbers, handles, `ref`, PAN-like, mobile and uid tokens stay. Real banks see the same handles and tokens, so two banks' exports link as two real banks' data could, through PAN, mobile and VPA, and not through simulator IDs.
- A truth export copies every table as it is.
- `dest/manifest.json` holds:
  - the source `run_id` and its content hashes;
  - the view, scope and `asof`;
  - per table: row count, columns with types, and a content hash computed the same way as the run's. No wall-clock times, so the same run and view give the same manifest.
- `dest/README.md` is a data dictionary: each table and column with a one-line meaning, taken from a description table in code.
- A `dest` that exists and isn't empty raises `FileExistsError`.

### 10. Where the code goes (a proposal; the builder may rearrange)

| File | What |
| :--- | :--- |
| `store/parquet.py` | Incremental writer |
| `store/hashing.py` | Running hash, spool, from-disk hash |
| `build/identifiers.py`, `build/pipeline.py` | Opaque VPA, ACCOUNT_NO, TERMINAL, customer numbers, `opening_balance_paise`, `bank_customers` |
| `world.py` | `balances_monthly` at month end; `watch`/`unwatch`; `Run.view`, `inspect`, `metric`, `export` as thin calls into new modules |
| `views.py` | View class, the SQL definitions, handles, narration, MCC |
| `inspector.py` | `EntityTrace`. Not `inspect.py` or `trace.py`, which shadow standard-library modules. |
| `metrics.py` | Registry, built-ins, `register` |
| `export.py` | Export, manifest, data dictionary |

`arthasim.register` is exported from the package, as in blueprint section 14.3.

## Testing and verification

Test-first, on fast worlds where possible: a few-thousand-person population run of about 35 days that crosses a month end, shared by a module-scoped fixture. Properties to pin:

- **Store.**
  - Written tables equal the old store's.
  - A split run equals a single run (tables and hashes).
  - Queued rows never exceed `ROW_GROUP_ROWS` per table.
  - The live hash equals the from-disk hash, which equals the reference implementation.
- **Bank view.**
  - For every bank and account, the last statement line of each month equals `balances_monthly`.
  - The union of all banks' statement lines is every posting on a non-boundary deposit account, once each.
  - No row carries another bank's `account_id` or `entity_id`.
  - No column is named `purpose` or `journal_id`.
  - Narrations contain no purpose except SALARY or PENSION on NACH credits.
- **Cross-bank.**
  - Every successful payment between two banks appears in both banks' `payments` with the same `ref` and amount, DR at one and CR at the other.
  - The payer's bank sees declines and the payee's bank doesn't.
- **Switch view.** Every UPI attempt appears exactly once.
- **Handles.** No handle contains a simulator ID as text, and ACCOUNT_NO and customer numbers are unique.
- **asof.** No row is dated after `asof`.
- **Inspector.**
  - The passbook's balances chain: each `balance_after` equals the previous one plus the amount.
  - The timeline holds every payment touching the entity's accounts.
  - `net_worth` agrees with `balances_monthly`.
- **Watch.**
  - The callback days and rows match the stored tables for that entity.
  - A watched run's hashes equal an unwatched run's.
- **Metrics.**
  - The built-ins agree with hand-written SQL.
  - Grouped values sum to the ungrouped value.
  - Registration errors fire.
- **Export.**
  - Re-reading gives the view minus simulator IDs.
  - No ID columns remain.
  - The manifest is the same on a second export.
  - A non-empty `dest` fails.
- **No change to the simulation.**
  - On a tier S, 90-day, seed 7 run, every fact table and every dimension except `persons`, `accounts` and `instruments` has the same content hash as the manifest of a run of `main`. That is commit 1b5d045, or the `main` tip at merge time if it has moved.
  - `accounts` without `opening_balance_paise` equals `main`'s.
  - `persons` without `birth_year` equals `main`'s, except for the token values, which are now keyed hashes.
  - The BRANCH instruments equal `main`'s.

Done means the plan's tasks pass test-first, one fresh final review (Opus) has read the whole branch and its findings are fixed, and a results doc (`docs/phase1c_results.md`) shows each call working on a tier S run. That doc reports:

- runtime and peak memory, before (`main`) and after (branch), from `scripts/bench.py --tier S --days 90 --seed 7`;
- a 365-day branch run;
- the hash comparison;
- disk size per table;
- the time each call takes.

## Left to the builder

- `ROW_GROUP_ROWS`, compression, and the spool file's location (inside the run folder, removed at month close).
- The exact narration text, token prefixes and number formats, within the rules above.
- The internal layout of the SQL definitions, and whether `View.table` and `View.sql` share one connection.
- Column order and names not fixed above, and the data-dictionary wording.
- How `watch` finds an entity's rows each day, as long as nothing is computed when no one is watching.
