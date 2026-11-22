# Plan 1c, data products: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a finished run usable by researchers and partners. The plan adds observer views (bank, switch, bureau, truth), an inspector, a watch callback, metrics and export, on a store whose memory no longer grows with a month.

**Architecture:**
- Views are SQL definitions over the run's Parquet files, run in DuckDB when read. Nothing extra is written per observer.
- The store writes row groups as rows arrive and keeps today's content-hash format, computed live.
- New identifiers (opaque VPA, account and customer numbers, terminals) are keyed draws on their own streams, so the simulation's draws don't change.

**Tech Stack:** Python 3.12, NumPy, Numba, Polars, PyArrow, DuckDB, pytest, Hypothesis.

**Spec:** `docs/superpowers/specs/2026-11-22-data-products-design.md`. Read it first. Section numbers below refer to it.

## Global Constraints

- **Determinism.** Same seed, same output. No `np.random` anywhere under `src/`.
- **Identifiers.** Every new identifier comes from `rng.bits` / `identifiers.token` on its own named stream.
- **Split runs.** A run split across `step` calls equals a single run, in tables and in content hashes.
- **Tables that must not change.** `payments`, `journal`, `postings`, `truth_household_monthly`, `life_events`, `entity_state_monthly`, `households`, `orgs`, `banks`, `edges`, `geo`, `truth_person_latent`.
- **Tables that change on purpose.** Only `persons`, `accounts` and `instruments`, plus the new `balances_monthly` and `bank_customers`.
- **Registry.** No new registry rows. The row count pinned in `tests/test_build_1b.py` must not change.
- **Money and time.** Money is integer paise. Timestamps are Int64 epoch microseconds. Calendar dates and months are IST (Asia/Kolkata).
- **Running tests.** `PYTHONPATH=src <venv>/bin/python -m pytest`. The venv is a scratch virtual environment with numpy, numba, polars 2.1, pyarrow, duckdb 2.0.1, pydantic, pyyaml, pytest and hypothesis. The package is not installed.
- **Commits.** Every commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Execution ledger.** Execution notes go in `docs/superpowers/ledger.md`, under a new heading "Plan 1c data products execution ledger". Record one line per task (red, green, counts), and a ruling with its cost if wrong wherever the plan is departed from.
- **Narration remark mapping.** `{"NACH_CR": {"SALARY", "PENSION"}}`. It is the only use of `purpose` outside truth.
- **Handle formats.**

  | Handle | Format |
  | :--- | :--- |
  | VPA | `<token("p"/"m"/"b", ...)>@syn<NN>` |
  | ACCOUNT_NO | `<bank_code>-<16 hex>` |
  | Customer number | `CIF<bank_code>-<16 hex>` |
  | TERMINAL | `t_<16 hex>` |
  | ATM terminal | `ATM` + branch code |
  | AePS terminal | `MATM` + branch code |
  | `ref` | `payment_id` zero-padded to 12 digits |

- **Merchant category codes.** grocery 5411, food 5812, fuel 5541, pharmacy 5912, apparel 5651, electronics 5732, transport 4121, services 7299, other 5999, telecom 4814, electricity 4900, ecommerce 5399, amc 6211.

## Review Focus

1. **A bank with no customers** (possible in a tiny world). Every bank-view table returns an empty frame with the right columns, and export writes empty tables. Task 5 pins this.
2. **An entity with no bank account** (unbanked person). `inspect` works: passbook of cash only, net worth of cash only, empty bank handles. `watch` fires on their cash payments. Tasks 7 and 8 pin this.
3. **`asof` outside the run** (before the start, or after the end). Before the start gives empty fact tables. After the end gives the whole run. Neither raises. Task 4 pins this.
4. **A run that stopped mid-month** (no `balances_monthly` row for the last month). `profile(asof)` in that month takes balances from postings. `deposit_balance` and `net_worth` simply have no row for the open month. Tasks 3, 7 and 9 pin this.
5. **A view's SQL naming a truth table** (`bank.sql("select * from persons")`). It raises a DuckDB catalog error rather than returning truth rows. Task 4 pins this.

---

## File map

| File | Responsibility |
| :--- | :--- |
| `src/arthasim/store/hashing.py` (new) | `RunningHash` (live, same format), `content_hash` from disk (streaming), `ipc_bytes` |
| `src/arthasim/store/parquet.py` | `Store` with incremental row-group writer, `FACT_TABLES` / `DIM_TABLES` lists, `table_files`, `read_table` |
| `src/arthasim/build/identifiers.py` | `vpa`, `account_no`, `customer_no`, `terminal` (new signatures) |
| `src/arthasim/build/pipeline.py` | `persons.birth_year`; `account_frames` returns accounts (with `opening_balance_paise`), instruments (new kinds), `bank_customers` |
| `src/arthasim/world.py` | `balances_monthly` at month end; `watch`/`unwatch`; `Run.view`, `inspect`, `metric`, `export`; manifest `polars_version` |
| `src/arthasim/views.py` (new) | `View`, `make_view`, SQL definitions, handles, narration, MCC, descriptions |
| `src/arthasim/inspector.py` (new) | `EntityTrace` |
| `src/arthasim/metrics.py` (new) | Registry, built-ins, `register` |
| `src/arthasim/export.py` (new) | `export_view` |
| `tests/reference_hash.py` (new) | Today's `content_hash`, copied verbatim, as the reference |
| `tests/run_fixture.py` (new) | `small_run()`: a shared, cached, read-only population run that crosses a month end |
| `scripts/data_products_demo.py` (new) | Opens a run and times each call (used by the results doc) |

Shared fixture (create in Task 3, used from Task 3 on). Tests do `from run_fixture import small_run` and call `small_run()`. Test snippets below that list `small_run` as a parameter mean that import; they are not pytest fixtures.

```python
# tests/run_fixture.py
@functools.lru_cache(maxsize=None)
def small_run(persons=3_000, seed=7):
    """Population run from 2025-04-20 to 2025-05-25 (crosses one month end), stopped mid-May. Read-only."""
    out = tempfile.mkdtemp(prefix="arthasim-run-")
    world = World.build(Config.tier("S", persons=persons, start="2025-04-20", out_dir=out), seed=seed)
    return world.run(until="2025-05-25")
```

---

### Task 1: Store writes row groups as rows arrive; live content hash in today's format

**Files:**
- Create: `src/arthasim/store/hashing.py`, `tests/reference_hash.py`, `tests/test_store.py`
- Modify: `src/arthasim/store/parquet.py`, `src/arthasim/world.py` (`_day`, `_flush`)

**Interfaces:**
- Produces:
  - `hashing.ipc_bytes(frame: pl.DataFrame) -> bytes`. This is today's `_ipc_bytes`, moved.
  - `hashing.content_hash(path: Path, name: str, fact: bool | None = None) -> str`. It works from disk and streams one row group at a time: a first pass for the seed-0 row hashes, a second for seed 1. `fact=None` decides by membership in `FACT_TABLES`. Task 10 passes `fact` explicitly for export folders.
  - `hashing.RunningHash(spool_dir: Path)` with:
    - `update(month: str, frame: pl.DataFrame)`
    - `digest() -> str`, which doesn't disturb the running state.
  - `Store(path: Path, row_group_rows: int = ROW_GROUP_ROWS)` with:
    - `add(table, month, frame)`
    - `flush()`, which writes everything queued and closes all open files
    - `content_hashes() -> dict[str, str]`, live, for fact tables that have rows
    - `max_queued_rows: int`, the high-water mark of queued rows in any table (for the test)
  - `ROW_GROUP_ROWS = 500_000`.
- `parquet.content_hash` keeps working as a name: re-export it from `hashing`.

- [ ] **Step 1: Copy today's hash as the reference.** Copy `_ipc_bytes` and `content_hash` from `src/arthasim/store/parquet.py` verbatim into `tests/reference_hash.py`, as `reference_content_hash(path, name)`. Import `table_files`, `read_table` and `DIM_TABLES` from `arthasim.store.parquet`.

- [ ] **Step 2: Write the failing tests** in `tests/test_store.py`:

```python
def test_store_writes_row_groups_and_bounds_the_queue(tmp_path):
    store = Store(tmp_path, row_group_rows=1_000)
    frames = [pl.DataFrame({"a": np.arange(i * 700, (i + 1) * 700), "s": ["x"] * 700}) for i in range(10)]
    for f in frames:
        store.add("payments", "2025-04", f)
    store.flush()
    files = table_files(tmp_path, "payments")
    assert len(files) == 1 and pq.ParquetFile(files[0]).num_row_groups >= 6
    assert read_table(tmp_path, "payments").collect().equals(pl.concat(frames))
    assert store.max_queued_rows < 1_000 + 700

def test_second_flush_in_same_month_opens_next_part(tmp_path):
    store = Store(tmp_path)
    store.add("journal", "2025-04", pl.DataFrame({"a": [1, 2]})); store.flush()
    store.add("journal", "2025-04", pl.DataFrame({"a": [3]})); store.flush()
    assert [f.name for f in table_files(tmp_path, "journal")] == ["part-0.parquet", "part-1.parquet"]

def test_live_hash_equals_disk_and_reference(tmp_path):
    # population run of 2,000 persons from 2025-04-25 to 2025-05-06, stepped 3 days then run
    ...
    for t in FACT_TABLES:
        if table_files(run_path, t):
            assert m["content_hash"][t] == content_hash(run_path, t) == reference_content_hash(run_path, t)

def test_split_run_hashes_equal_single_run(tmp_path):
    # one run 2025-04-25..2025-05-06 vs step(3) + step(4) + run(until=2025-05-06): manifests' content_hash equal,
    # and after the first step (mid-April) the manifest hash equals the from-disk hash
    ...

def test_spool_files_are_removed_when_a_month_closes(tmp_path):
    # run 2025-04-25..2025-05-02: no April spool remains; May (still open) may have one
    ...

def test_manifest_records_polars_version(tmp_path):
    ...
    assert m["polars_version"] == pl.__version__
```

- [ ] **Step 3: Run them and see them fail.** Run `pytest tests/test_store.py -v`. Expected: ImportError (no `arthasim.store.hashing`) or assertion failures.

- [ ] **Step 4: Implement.** Writing:
  - Per table, `Store` keeps a list of queued frames and the open `pq.ParquetWriter` with its month. Use compression `zstd`. Write the schema from the first frame's `to_arrow()`.
  - When queued rows reach `row_group_rows`, concatenate and `write_table`.
  - `flush()` writes what's queued and closes every writer.
  - A frame for a new month closes the old month's writer first. The part number is the count of existing `part-*.parquet` in the folder.

  Hashing:
  - `Store` owns one `RunningHash` per fact table. `RunningHash.update` handles a new month: it finishes the previous month by streaming its spool into SHA-256 and deleting it, then feeds the month name and the schema repr.
  - On every frame it feeds `frame.hash_rows(seed=0)` bytes to SHA-256 and appends the `hash_rows(seed=1)` bytes to the spool.
  - `digest()` copies the SHA-256, streams the open spool into the copy, and hex-digests it.
  - Hash in the same order the rows are written.
  - The spool goes in `<run>/.spool/<table>-<month>.bin`.

  World:
  - `World._flush` builds `content_hash` from `store.content_hashes()` for fact tables and from `content_hash(path, t)` for dimension tables. It adds `"polars_version": pl.__version__`.
  - `_day` keeps calling `store.flush()` at month end. Month closure for the hash happens when the next month's first frame arrives, or at `digest()`.

- [ ] **Step 5: Run the tests and see them pass.** Run `pytest tests/test_store.py tests/test_run.py tests/test_pipeline.py tests/test_money_flows.py tests/test_lifecourse.py -v`. Expected: all pass.

- [ ] **Step 6: Run the whole fast suite.** Run `pytest -q`. Expected: 174 + new tests pass.

- [ ] **Step 7: Commit.** Message: `feat: store writes row groups as rows arrive; content hash computed live`.

---

### Task 2: New identifiers, birth year, opening balance, bank customers

**Files:**
- Modify: `src/arthasim/build/identifiers.py`, `src/arthasim/build/pipeline.py` (`population_frames`, `account_frames`), `src/arthasim/store/parquet.py` (`DIM_TABLES` gains `bank_customers`), `src/arthasim/world.py` (`_flush` writes every frame `account_frames` returns)
- Test: `tests/test_identifiers_1c.py` (new), `tests/test_banking.py`, `tests/test_pipeline.py`

**Interfaces:**
- Produces:
  - `identifiers.vpa(seed: int, account_ids, bank_index, prefix: str = "p") -> np.ndarray`. Returns `f"{token(prefix, seed, S('id.vpa'), account_ids)}@syn{b+1:02d}"`.
  - `identifiers.account_no(seed, account_ids, bank_codes) -> np.ndarray`. Returns `f"{code}-{bits:016x}"`, stream `id.account_no`.
  - `identifiers.customer_no(seed, entity_ids, bank_index, bank_codes) -> np.ndarray`. Returns `f"CIF{code}-{bits:016x}"`, stream `id.customer_no`, keyed on `entity_id * 64 + bank_index`.
  - `identifiers.terminal(seed, account_ids) -> np.ndarray`. Returns `token("t", seed, S('id.terminal'), account_ids)`.
  - `account_frames(state, config) -> {"accounts", "instruments", "bank_customers"}`.
- Table changes:
  - `instruments.kind` ∈ {VPA, DEVICE, DEBIT_CARD, MOBILE, BRANCH, ACCOUNT_NO, TERMINAL}.
  - `accounts` gains `opening_balance_paise` (Int64, from `book.opening`) as its last column.
  - `bank_customers`: `bank_code` (String), `entity_id` (Int64), `customer_no` (String), sorted by `bank_code`, `entity_id`. Only non-boundary banks.
  - `persons` gains `birth_year` (Int64) right after `birth_month`, from spec §3: `start.year − age − (birth_month > start.month)`.

- [ ] **Step 1: Write the failing tests:**

```python
def test_handles_are_opaque_unique_and_keyed(tmp_path):
    run = World.build(Config.tier("S", persons=2_000, out_dir=str(tmp_path)), seed=7).run(until="2025-04-02")
    inst = run.table("instruments").collect()
    assert set(inst["kind"].unique()) == {"VPA", "DEVICE", "DEBIT_CARD", "MOBILE", "BRANCH", "ACCOUNT_NO", "TERMINAL"}
    acc = run.table("accounts").collect()
    deposits = acc.filter(pl.col("type") == "DEPOSIT")
    nos = inst.filter(pl.col("kind") == "ACCOUNT_NO")
    assert sorted(nos["account_id"].to_list()) == sorted(deposits["account_id"].to_list())
    assert nos["value"].n_unique() == nos.height
    for kind in ("VPA", "ACCOUNT_NO", "TERMINAL"):
        values = inst.filter(pl.col("kind") == kind)["value"]
        assert not values.str.contains(r"^p\d+@").any()           # the old entity-id VPA is gone
    vpa_accounts = set(inst.filter(pl.col("kind") == "VPA")["account_id"])
    # persons with UPI, UPI-accepting merchants and all billers have a VPA
    ...
    cust = run.table("bank_customers").collect()
    assert cust["customer_no"].n_unique() == cust.height and "SYNX00" not in cust["bank_code"].to_list()

def test_birth_year_matches_monthly_ages(tmp_path):
    run = World.build(Config.tier("S", persons=2_000, start="2025-04-01", out_dir=str(tmp_path)), seed=7) \
        .run(until="2026-04-30")
    ages = run.sql("""select e.age, e.month, p.birth_year, p.birth_month from entity_state_monthly e
                      join persons p using (entity_id)""")
    m_year = ages["month"].str.slice(0, 4).cast(pl.Int64); m_mon = ages["month"].str.slice(5, 2).cast(pl.Int64)
    assert (ages["age"] == m_year - ages["birth_year"] - (m_mon < ages["birth_month"]).cast(pl.Int64)).all()

def test_new_identifiers_do_not_change_simulation(tmp_path):
    # same run as test_handles...: payments, journal and postings hash equal a run with identifiers monkeypatched to
    # return constant strings (proves the new streams draw nothing the simulation uses)
    ...

def test_opening_balance_and_mid_run_accounts(tmp_path):
    # 2,000 persons 2025-04-01..2025-06-02: accounts opened mid-run (opened_on > start) have an ACCOUNT_NO,
    # a bank_customers row, and opening_balance_paise == 0; build accounts' opening_balance_paise == book.opening
    ...
```

  Also update the existing pins:
  - In `tests/test_banking.py:56`, the VPA test becomes: format `^p_[0-9a-f]{16}@syn\d\d$`, and same inputs give the same output.
  - In `tests/test_pipeline.py`, `PERSON_COLUMNS` gains `birth_year` after `birth_month`; the instrument kinds pin is the new set; `run.tables()` gains `bank_customers`.

- [ ] **Step 2: Run the tests and see them fail.** Run `pytest tests/test_identifiers_1c.py tests/test_banking.py tests/test_pipeline.py -v`. Expected: FAIL (new kinds and columns missing).

- [ ] **Step 3: Implement.** Changes in `identifiers.py` and `account_frames`:
  - **ACCOUNT_NO:** for every `book.type == DEPOSIT`.
  - **VPA:** for persons with UPI (prefix `p`), UPI-accepting merchants (`m`) and billers (`b`). The bank is `bank_of_account`.
  - **TERMINAL:** for card-accepting merchants.
  - **Customers:** deposits whose holder kind is person, employer, merchant or biller, and whose bank is not the boundary, give the (bank, entity) pairs, deduplicated.

  Add `birth_year` in `population_frames` from `b.persons.age` at build. `population_frames` runs at build, before any ageing.

- [ ] **Step 4: Run the tests and see them pass.** Run the same command, then `pytest -q`. Expected: all pass.

- [ ] **Step 5: Commit.** Message: `feat: opaque handles, account and customer numbers, birth year, opening balances`.

---

### Task 3: Monthly closing balances

**Files:**
- Modify: `src/arthasim/world.py` (`_day`), `src/arthasim/store/parquet.py` (`FACT_TABLES` gains `balances_monthly`)
- Create: `tests/run_fixture.py` (see the file map), `tests/test_balances_monthly.py`
- Modify: `tests/test_pipeline.py` (`run.tables()` gains `balances_monthly`)

**Interfaces:**
- Produces: the fact table `balances_monthly` with `account_id` (Int64), `month` (String `YYYY-MM`) and `balance_paise` (Int64). There is one row per account in the book at the moment the month's last day finishes, sorted by `account_id`.

- [ ] **Step 1: Write the failing tests:**

```python
def test_closing_balance_is_last_posting_or_previous(small_run):     # small_run from tests/run_fixture.py
    run = small_run()
    bal = run.table("balances_monthly").collect()
    assert bal["month"].unique().to_list() == ["2025-04"]             # May is still open: no row
    assert bal.height == run.table("accounts").filter(pl.col("opened_on") <= date(2025, 4, 30)).collect().height
    last = run.sql("""select p.account_id, arg_max(p.balance_after_paise, j.ts * 1000000 + p.journal_id * 8 + p.line_no) b
                      from postings p join journal j using (journal_id)
                      where j.ts < epoch_us(timestamptz '2025-05-01 00:00:00+05:30') group by 1""")
    joined = bal.join(last, on="account_id", how="left").join(run.table("accounts").collect(), on="account_id")
    expect = pl.coalesce(joined["b"], joined["opening_balance_paise"])
    assert (joined["balance_paise"] == expect).all()

def test_balances_are_written_once_per_month_in_split_runs(tmp_path):
    # 2,000 persons start 2025-04-28: step(2) (ends 04-29), then run to 2025-05-02 -> exactly one 2025-04 row per
    # account; hashes equal a single run's (covered by Task 1's split test once the table exists)
    ...
```

  For the ordering inside a journal entry, use the key `(ts, journal_id, line_no)`. The builder may write the SQL `arg_max` key differently, provided it orders by that key.

- [ ] **Step 2: Run the tests and see them fail.** Run `pytest tests/test_balances_monthly.py -v`. Expected: FAIL (no table).

- [ ] **Step 3: Implement.** In `World._day`, when `self._date.month != day.month` (the month just ended), add `balances_monthly` for `f"{day:%Y-%m}"` from `book.balance` (copied) before `store.flush()`.

- [ ] **Step 4: Run the tests and see them pass.** Run `pytest tests/test_balances_monthly.py tests/test_pipeline.py tests/test_store.py -q`, then `pytest -q`. Expected: all pass.

- [ ] **Step 5: Commit.** Message: `feat: closing balance of every account at each month end`.

---

### Task 4: View machinery and the truth view

**Files:**
- Create: `src/arthasim/views.py`, `tests/test_views.py`
- Modify: `src/arthasim/world.py` (`Run.view`)

**Interfaces:**
- Produces:
  - `class View` with `kind: str`, `scope: dict` and `asof: dt.date | None`, plus:
    - `tables() -> list[str]`
    - `table(name: str, asof: Date | None = None) -> pl.LazyFrame`
    - `sql(query: str) -> pl.DataFrame`
  - `make_view(run: Run, kind: str, asof: Date | None = None, **scope) -> View`
  - `Run.view(kind, asof=None, **scope)` calls `make_view`.
  - Internal, for Tasks 5–7 and 10:
    - `View._definitions(asof) -> dict[str, str]`: table name to a SELECT that uses only `read_parquet([...])` with files from `table_files`.
    - `View.fact_tables: set[str]`: the tables that export partitions by month.
    - `asof_us(asof) -> int`: epoch µs of IST midnight on the day after `asof`.
    - `month_end(asof) -> str`: the last month fully ended on or before `asof`.
- Rules:
  - `sql()` opens a fresh `duckdb.connect()` and creates one `create view <name> as <definition>` per view table. Nothing else is registered.
  - `table()` returns `con.sql(definition).pl(lazy=True)`.
  - Every definition ends in an `ORDER BY` that makes row order deterministic.
  - Views (and `inspect`, `export`) on a spike-builder run raise `ValueError("views need a population-built run")`.
  - An unknown kind raises `ValueError`, naming the kinds `bank`, `switch`, `bureau`, `truth`.

- [ ] **Step 1: Write the failing tests:**

```python
def test_truth_view_matches_run_tables(small_run):
    run = small_run()
    v = run.view("truth")
    assert set(v.tables()) == set(run.tables())
    assert v.table("payments").collect().equals(run.table("payments").collect())
    assert v.sql("select count(*) n from postings")["n"][0] == run.table("postings").collect().height

def test_asof_cuts_fact_tables(small_run):
    v = small_run().view("truth", asof="2025-05-01")
    pay = v.table("payments").collect()
    assert pay["settle_ts"].max() < asof_us("2025-05-01")
    assert v.table("payments", asof="2025-04-19").collect().height == 0          # before the start: empty
    assert v.table("payments", asof="2026-01-01").collect().height == small_run().table("payments").collect().height

def test_view_sql_cannot_name_other_tables(small_run):
    with pytest.raises(duckdb.CatalogException):
        small_run().view("bank", bank="SYNB01").sql("select * from persons")

def test_view_errors(small_run, tmp_path):
    with pytest.raises(ValueError, match="bank, switch, bureau, truth"):
        small_run().view("aa")
    spike = World.build(Config.tier("XS", persons=300, employers=5, merchants=20, out_dir=str(tmp_path)), seed=7) \
        .run(until="2025-04-02")
    with pytest.raises(ValueError, match="population-built"):
        spike.view("truth")
```

  The test `test_view_sql_cannot_name_other_tables` needs a minimal bank view. In this task the bank view may expose only `customers`, with the rest added in Task 5.

  The truth view's `asof` applies:
  - to `payments` (`settle_ts`), `journal` (`ts`) and `postings` (through the journal's `ts`);
  - by month to `life_events` (`date`), `entity_state_monthly` (`month` ≤ the asof month) and `truth_household_monthly`;
  - to `balances_monthly` (`month` ≤ `month_end(asof)`);
  - to `accounts` (`opened_on` ≤ asof).

  Other dimensions are not filtered.

- [ ] **Step 2: Run the tests and see them fail.** Run `pytest tests/test_views.py -v`. Expected: ImportError.

- [ ] **Step 3: Implement** `views.py` (`View`, `make_view`, truth definitions, the asof helpers) and `Run.view`.

- [ ] **Step 4: Run the tests and see them pass.** Run `pytest tests/test_views.py -v`, then `pytest -q`. Expected: all pass.

- [ ] **Step 5: Commit.** Message: `feat: views over the run's files, and the truth view`.

---

### Task 5: Bank view: customers, accounts, payments, statement lines, balances

**Files:**
- Modify: `src/arthasim/views.py`
- Create: `tests/test_bank_view.py`

**Interfaces:**
- Consumes: `View`, `asof_us`, `month_end` (Task 4); `instruments` kinds and `bank_customers` (Task 2); `balances_monthly` (Task 3).
- Produces:
  - `run.view("bank", bank=code)` with tables `customers`, `accounts`, `instruments`, `payments`, `statement_lines`, `balances_monthly`. Columns are per spec §5, plus a `date` column (IST calendar date) on `payments` and `statement_lines`.
  - Internal, reused by Tasks 6, 7 and 10:
    - `handles_sql(files) -> str`: one row per account, with `account_id`, `bank_code`, `vpa`, `account_no`, `terminal`, `branch`, `card_token`, `device_token`.
    - `counterparty_handle_sql(rail_col, other_alias, own_alias) -> str`: a SQL CASE expression implementing spec §4's table.
    - `narration_sql(...) -> str`.
    - `MCC: dict[str, int]`.
    - `REMARKS: dict[str, set[str]]`.
    - `lines_sql(files, account_filter: str, asof_us: int | None) -> str`: statement lines for any set of deposit accounts. The inspector reuses it for cash accounts with `narration` null.
- Rules:
  - An unknown bank code, or `SYNX00`, raises `ValueError` listing the bank codes.
  - A bank with no customers returns empty tables with the right columns.

- [ ] **Step 1: Write the failing tests** (all on `small_run()`):

```python
def test_statement_lines_close_on_monthly_balances(small_run):
    for code in BANKS:                                 # the 12 SYNBnn codes
        v = small_run().view("bank", bank=code)
        last = v.sql("""select account_id, arg_max(balance_after_paise, ts * 1000000 + line_key) b from statement_lines
                        where date < date '2025-05-01' group by 1""")
        # every account with lines in April closes on balances_monthly's April value
        ...

def test_statement_lines_partition_deposit_postings(small_run):
    run = small_run()
    total = sum(run.view("bank", bank=c).table("statement_lines").select(pl.len()).collect().item() for c in BANKS)
    expect = run.sql("""select count(*) n from postings p join accounts a using (account_id) join banks b
                        on a.issuer_entity_id = b.entity_id where a.type = 'DEPOSIT' and b.kind = 'BANK'""")["n"][0]
    assert total == expect

def test_bank_view_hides_other_banks_and_truth(small_run):
    run = small_run()
    v = run.view("bank", bank="SYNB03")
    own = set(v.table("accounts").collect()["account_id"])
    for t in v.tables():
        cols = v.table(t).collect_schema().names()
        assert "purpose" not in cols and "journal_id" not in cols
        if "account_id" in cols:
            assert set(v.table(t).collect()["account_id"]) <= own
    cust = v.table("customers").collect()
    assert "uid_token" not in cust.columns and "education" not in cust.columns and "birth_year" in cust.columns
    narr = v.table("statement_lines").collect()["narration"]
    assert not narr.str.contains("GROCERY|FOOD|ALLOWANCE|REMITTANCE|EARNINGS").any()
    assert narr.str.contains("/SALARY$").any()

def test_cross_bank_payments_seen_from_both_sides(small_run):
    run = small_run()
    rows = pl.concat([run.view("bank", bank=c).table("payments").collect().with_columns(pl.lit(c).alias("seen_by"))
                      for c in BANKS])
    ok = rows.filter(pl.col("status") == "SUCCESS")
    pairs = ok.group_by("ref").agg(pl.col("direction").sort(), pl.col("amount_paise").n_unique().alias("amounts"))
    # each successful deposit-to-deposit payment between two non-boundary banks: exactly ["CR", "DR"], one amount
    ...
    declined = rows.filter(pl.col("status") != "SUCCESS")
    assert (declined["direction"] == "DR").all()                     # only the payer's bank sees declines

def test_counterparty_handles_follow_rail(small_run):
    pay = small_run().view("bank", bank="SYNB01").table("payments").collect()
    assert pay.filter(pl.col("rail") == "ATM")["counterparty_handle"].str.starts_with("ATM").all()
    assert pay.filter(pl.col("rail") == "AEPS")["counterparty_handle"].str.starts_with("MATM").all()
    upi = pay.filter(pl.col("rail").str.starts_with("UPI"))["counterparty_handle"]
    assert upi.str.contains("@syn|^SYN").all()
    assert pay.filter(pl.col("rail") == "CASH").height == 0
    assert pay.filter(pl.col("rail") == "UPI_P2M", pl.col("direction") == "DR")["mcc"].is_in(list(MCC.values())).all()

def test_bank_with_no_customers_returns_empty_tables(tmp_path):
    run = World.build(Config.tier("S", persons=40, out_dir=str(tmp_path)), seed=3).run(until="2025-04-03")
    empty = [c for c in BANKS if run.sql(f"select count(*) n from bank_customers where bank_code = '{c}'")["n"][0] == 0]
    assert empty                                        # if seed 3 gives none, the builder picks a seed that does
    v = run.view("bank", bank=empty[0])
    assert all(v.table(t).collect().height == 0 for t in v.tables())

def test_unknown_or_boundary_bank_raises(small_run):
    for code in ("SYNB99", "SYNX00"):
        with pytest.raises(ValueError, match="SYNB01"):
            small_run().view("bank", bank=code)
```

  The statement-line order key is `(ts, journal_id, line_no)`. Expose it as `line_key` or sort by it. Either is the builder's choice; the test uses whichever exists.

- [ ] **Step 2: Run the tests and see them fail.** Run `pytest tests/test_bank_view.py -v`. Expected: FAIL.

- [ ] **Step 3: Implement** the definitions.

  Bank `payments`: union two selects over `payments` joined to `accounts`:
  - **The payer's side:** the payer account is a deposit issued by the bank, and `rail <> 'CASH'`. `direction = 'DR'`, and the counterparty is the payee.
  - **The payee's side:** the payee account is a deposit issued by the bank, and `status = 'SUCCESS'`. `direction = 'CR'`, and the counterparty is the payer.

  Rules for the other columns:
  - For withdrawals (ATM, AEPS) and branch deposits, the counterparty handle is built from the own account's branch (spec §4).
  - `mcc` is the payee organisation's category, mapped through `MCC`, on the payer's side of P2M and card payments, and on the payee side too.
  - `device_token` is set where the payer is the bank's customer and the rail is UPI.

  `statement_lines` is `lines_sql` over postings on the bank's deposit accounts, joined through `journal.payment_id` to `payments` for the rail and the other side.

- [ ] **Step 4: Run the tests and see them pass.** Run `pytest tests/test_bank_view.py -v`, then `pytest -q`. Expected: all pass.

- [ ] **Step 5: Commit.** Message: `feat: bank view with statement lines, narrations and handles`.

---

### Task 6: Switch and bureau views

**Files:**
- Modify: `src/arthasim/views.py`
- Create: `tests/test_switch_bureau.py`

**Interfaces:**
- Consumes: `handles_sql`, `counterparty_handle_sql`, `MCC` (Task 5).
- Produces:
  - `run.view("switch", network="upi")`. `network` ∈ {upi, imps, nach, card, atm, aeps} (spec §5), and the table is `payments`.
  - `run.view("bureau")`, with tables `consumers`, `tradelines`, `enquiries` and `scores`. All are empty, with typed columns per spec §5.

- [ ] **Step 1: Write the failing tests:**

```python
NETWORK_RAILS = {"upi": ["UPI_P2M", "UPI_P2P"], "imps": ["IMPS"], "nach": ["NACH_CR"], "card": ["DEBIT_CARD"],
                 "atm": ["ATM"], "aeps": ["AEPS"]}

def test_switch_sees_every_attempt_on_its_network_once(small_run):
    run = small_run()
    for net, rails in NETWORK_RAILS.items():
        sw = run.view("switch", network=net).table("payments").collect()
        truth = run.table("payments").filter(pl.col("rail").is_in(rails)).collect()
        assert sorted(sw["payment_id"]) == sorted(truth["payment_id"])
        assert not {"payer_account_id", "payee_account_id", "purpose", "balance_after_paise"} & set(sw.columns)

def test_switch_handles(small_run):
    upi = small_run().view("switch").table("payments").collect()
    assert upi["payer_handle"].null_count() == 0 and upi["payee_handle"].null_count() == 0
    p2m = upi.filter(pl.col("rail") == "UPI_P2M")
    assert p2m["mcc"].null_count() == 0 and p2m["payer_device_token"].null_count() == 0

def test_bureau_is_empty_with_columns(small_run):
    b = small_run().view("bureau")
    assert b.tables() == ["consumers", "enquiries", "scores", "tradelines"]
    assert all(b.table(t).collect().height == 0 for t in b.tables())
    assert b.table("consumers").collect_schema().names() == ["pan_like", "birth_year", "birth_month", "sex",
                                                             "district", "mobile_token"]

def test_unknown_network_raises(small_run):
    with pytest.raises(ValueError, match="upi"):
        small_run().view("switch", network="neft")
```

- [ ] **Step 2: Run the tests and see them fail.** Run `pytest tests/test_switch_bureau.py -v`. Expected: FAIL.

- [ ] **Step 3: Implement** both views. Empty bureau tables are `select ... where false`, with casts that type each column.

- [ ] **Step 4: Run the tests and see them pass.** Run the same command, then `pytest -q`. Expected: all pass.

- [ ] **Step 5: Commit.** Message: `feat: switch and bureau views`.

---

### Task 7: Inspector

**Files:**
- Create: `src/arthasim/inspector.py`, `tests/test_inspector.py`
- Modify: `src/arthasim/world.py` (`Run.inspect`)

**Interfaces:**
- Consumes: `lines_sql`, `handles_sql` (Task 5); `balances_monthly` (Task 3); `opening_balance_paise` (Task 2).
- Produces:
  - `EntityTrace(run, entity_id)`, with these methods (columns per spec §6):
    - `profile(asof=None) -> dict`
    - `timeline() -> pl.DataFrame`
    - `passbook(account_id=None) -> pl.DataFrame`
    - `net_worth() -> pl.DataFrame`
    - `loans() -> pl.DataFrame` (empty: `loan_id`, `product`, `lender_code`, `sanctioned_paise`, `outstanding_paise`, `dpd`)
    - `ego_network(hops=1) -> pl.DataFrame`
  - `Run.inspect(entity_id)`. It raises `KeyError` if the ID isn't in persons or orgs.
- Rules:
  - `profile` keys: `entity_id`, `kind`, `static` (the persons or orgs row as a dict), `state` (the `entity_state_monthly` row for the asof month, or the last month; `None` for organisations), `household` (a list of member entity IDs; persons only), and `accounts` (a list of dicts: `account_id`, `type`, `subtype`, `bank_code`, `opened_on`, `handles` {kind: value}, `balance_paise` at the end of `asof`, or now).
  - The balance at a moment is the last posting at or before it, ordered by (ts, journal_id, line_no), else `opening_balance_paise`. Accounts opened after `asof` are left out.

- [ ] **Step 1: Write the failing tests:**

```python
def test_passbook_balances_chain_and_cover_all_postings(small_run):
    run = small_run()
    eid = <a banked, salaried person with a second account if any>
    pb = run.inspect(eid).passbook()
    for acc, g in pb.group_by("account_id"):
        bal = g["balance_after_paise"].to_numpy(); amt = g["amount_paise"].to_numpy() * np.where(g["direction"] == "DR", -1, 1)
        assert (bal[1:] == bal[:-1] + amt[1:]).all()
    n = run.sql(f"select count(*) n from postings p join accounts a using (account_id) where a.holder_entity_id = {eid}")
    assert pb.height == n["n"][0]

def test_timeline_has_every_payment_and_event(small_run):
    ...   # count of payments touching the entity's accounts (payer or payee), plus life_events rows for the entity

def test_profile_asof_in_open_month_uses_postings(small_run):
    run = small_run(); t = run.inspect(eid)
    p = t.profile(asof="2025-05-10")
    assert p["state"]["month"] == "2025-05"
    # each account's balance equals the last balance_after with ts < asof_us("2025-05-10"), else the opening balance

def test_net_worth_matches_monthly_balances(small_run):
    nw = small_run().inspect(eid).net_worth()
    assert nw["month"].to_list() == ["2025-04"] and (nw["total_paise"] == nw["deposits_paise"] + nw["cash_paise"]).all()

def test_unbanked_person_and_merchant(small_run):
    run = small_run()
    u = <a person with has_account false in the first month>
    assert set(run.inspect(u).passbook()["account_type"]) <= {"CASH"}
    assert all(a["type"] == "CASH" for a in run.inspect(u).profile()["accounts"])
    m = <a merchant entity_id>
    assert run.inspect(m).profile()["state"] is None and run.inspect(m).passbook().height > 0

def test_ego_network_and_errors(small_run):
    run = small_run()
    e1 = run.inspect(eid).ego_network(); e2 = run.inspect(eid).ego_network(hops=2)
    assert set(e1["hop"]) == {1} and e2.height >= e1.height and run.inspect(eid).loans().height == 0
    with pytest.raises(KeyError):
        run.inspect(10**12)
```

- [ ] **Step 2: Run the tests and see them fail.** Run `pytest tests/test_inspector.py -v`. Expected: ImportError.

- [ ] **Step 3: Implement** with DuckDB queries filtered to the entity's accounts, which come from `accounts` with `holder_entity_id`. `passbook` is `lines_sql` over all of them, with `purpose` and `payment_id` added from `payments`, and `account_type` from `accounts`.

- [ ] **Step 4: Run the tests and see them pass.** Run the same command, then `pytest -q`. Expected: all pass.

- [ ] **Step 5: Commit.** Message: `feat: inspector for one person or organisation`.

---

### Task 8: Watch

**Files:**
- Modify: `src/arthasim/world.py` (`World.watch`, `World.unwatch`, `_day`)
- Create: `tests/test_watch.py`

**Interfaces:**
- Produces:
  - `World.watch(entity_id: int, callback: Callable[[dict], None]) -> None`
  - `World.unwatch(entity_id: int) -> None`
  - The dict keys are `date`, `entity_id`, `payments` (a list of dicts: the payments row plus `direction` "DR"/"CR"), `events` (a list of life-events dicts), `balances` ({account_id: paise}) and `state` (a dict, or `None`).
- Rules:
  - A call happens only on days with at least one payment attempt or life event for the entity.
  - When nothing is watched, `_day` does no extra work.
  - Accounts are `np.flatnonzero(book.holder == entity_id)`, worked out each day.
  - Callback exceptions propagate.

- [ ] **Step 1: Write the failing tests:**

```python
def test_watch_matches_stored_rows_and_changes_nothing(tmp_path):
    cfg = lambda d: Config.tier("S", persons=2_000, start="2025-04-28", out_dir=str(tmp_path / d))
    calls = []
    w = World.build(cfg("w"), seed=7); eid = <a banked person with an employer>
    w.watch(eid, calls.append)
    run = w.run(until="2025-05-06")
    plain = World.build(cfg("p"), seed=7).run(until="2025-05-06")
    assert run.manifest["content_hash"] == plain.manifest["content_hash"]
    accounts = run.sql(f"select account_id from accounts where holder_entity_id = {eid}")["account_id"].to_list()
    stored = run.table("payments").filter(pl.col("payer_account_id").is_in(accounts)
                                          | pl.col("payee_account_id").is_in(accounts)).collect()
    assert sum(len(c["payments"]) for c in calls) == stored.height
    may1 = [c for c in calls if c["date"] == date(2025, 5, 1)]
    assert not may1 or may1[0]["state"]["month"] == "2025-05"
    last = calls[-1]
    assert set(last["balances"]) == set(accounts)

def test_unwatch_and_unbanked(tmp_path):
    ...  # an unbanked person's cash payments trigger calls; after unwatch no further calls

def test_callback_errors_stop_the_run(tmp_path):
    w = World.build(...); w.watch(eid, lambda d: (_ for _ in ()).throw(RuntimeError("stop")))
    with pytest.raises(RuntimeError, match="stop"):
        w.run(until="2025-05-06")
```

- [ ] **Step 2: Run the tests and see them fail.** Run `pytest tests/test_watch.py -v`. Expected: AttributeError (no `watch`).

- [ ] **Step 3: Implement.** In `_day`, collect the module frames in a local dict (they are already added to the store). After `run_day` returns (the invariants have passed), call `self._notify(day, payments, frames, monthly_ran)` only if `self._watchers`.

- [ ] **Step 4: Run the tests and see them pass.** Run the same command, then `pytest -q`. Expected: all pass.

- [ ] **Step 5: Commit.** Message: `feat: watch one entity during a run`.

---

### Task 9: Metrics

**Files:**
- Create: `src/arthasim/metrics.py`, `tests/test_metrics.py`
- Modify: `src/arthasim/world.py` (`Run.metric`), `src/arthasim/__init__.py` (export `register`)

**Interfaces:**
- Produces:
  - `METRICS: dict[str, Callable]`
  - `class register` with `metric(fn) -> fn` as a staticmethod. A duplicate name raises `ValueError`.
  - `Run.metric(name_or_fn, **kwargs) -> pl.DataFrame`. An unknown name raises `KeyError`, listing the names.
  - Built-ins (spec §8):
    - `txn_volume(run, by=None, status="SUCCESS")`
    - `decline_rate(run, by=None)`
    - `consumption(run, by=None)`
    - `cash_withdrawal(run, by=None)`
    - `deposit_balance(run, by=None)`
  - Groupings: `month`, `rail`, `bank`, `district` and `life_stage` (`deposit_balance` takes no `rail`). `by` is a str or a list. The output columns are the groupings in the order given, then `value`, sorted by the groupings.
- Rules:
  - Spending purposes are GROCERY, FOOD, FUEL, PHARMACY, APPAREL, ELECTRONICS, TRANSPORT, SERVICES, OTHER, UTILITIES, TELECOM and MEDICAL. Withdrawals are purpose CASH_WITHDRAWAL.
  - Work in DuckDB over the truth tables. Metrics also work on spike runs, for tables that exist. Groupings needing tables a spike run lacks raise `ValueError`.

- [ ] **Step 1: Write the failing tests:**

```python
def test_builtins_agree_with_sql(small_run):
    run = small_run()
    assert run.metric("txn_volume")["value"][0] == run.sql("select count(*) n from payments where status='SUCCESS'")["n"][0]
    assert run.metric("txn_volume", status=None)["value"][0] == run.table("payments").collect().height
    dr = run.metric("decline_rate")["value"][0]
    assert abs(dr - run.sql("select avg((status <> 'SUCCESS')::int) r from payments")["r"][0]) < 1e-12
    ...   # consumption, cash_withdrawal, deposit_balance against hand-written SQL

@pytest.mark.parametrize("name", ["txn_volume", "consumption", "cash_withdrawal"])
@pytest.mark.parametrize("by", ["month", "rail", "bank", "district", "life_stage", ["month", "rail"]])
def test_grouped_values_sum_to_total(small_run, name, by):
    run = small_run()
    assert run.metric(name, by=by)["value"].sum() == run.metric(name)["value"][0]

def test_deposit_balance_by_month(small_run):
    db = small_run().metric("deposit_balance", by="bank")
    assert db.columns == ["month", "bank", "value"] and db["month"].unique().to_list() == ["2025-04"]

def test_register_and_errors(small_run):
    @register.metric
    def upi_share(run, by=None):
        return run.sql("select avg((rail like 'UPI%')::double) as value from payments where status='SUCCESS'")
    assert 0 < small_run().metric("upi_share")["value"][0] < 1
    with pytest.raises(ValueError):
        register.metric(upi_share)
    with pytest.raises(ValueError, match="rail"):
        small_run().metric("deposit_balance", by="rail")
    with pytest.raises(KeyError):
        small_run().metric("nope")
    METRICS.pop("upi_share")
```

- [ ] **Step 2: Run the tests and see them fail.** Run `pytest tests/test_metrics.py -v`. Expected: ImportError.

- [ ] **Step 3: Implement.** The groupings, as SQL:
  - `month`: `strftime(make_timestamp(settle_ts) + interval 330 minute, '%Y-%m')`.
  - `bank`: `payer_bank`. For `deposit_balance`, the bank through `accounts.issuer_entity_id` → `banks`.
  - `district`: through the payer account's holder, `coalesce(persons.district, orgs.district)`.
  - `life_stage`: `entity_state_monthly` on (holder, payment month). Payers who aren't persons get null.

- [ ] **Step 4: Run the tests and see them pass.** Run the same command, then `pytest -q`. Expected: all pass.

- [ ] **Step 5: Commit.** Message: `feat: run metrics with a shared contract and registration`.

---

### Task 10: Export

**Files:**
- Create: `src/arthasim/export.py`, `tests/test_export.py`
- Modify: `src/arthasim/views.py` (a `DESCRIPTIONS: dict[str, dict[str, str]]` for every view table and column), `src/arthasim/world.py` (`Run.export`)

**Interfaces:**
- Consumes: `make_view`, `View._definitions`, `View.fact_tables` (Task 4); `hashing.content_hash(path, name, fact=...)` (Task 1).
- Produces:
  - `export_view(run, dest, view="bank", asof=None, **scope) -> Path`
  - `Run.export(dest, view="bank", asof=None, **scope)`
- Rules:
  - **Simulator IDs.** For bank, switch and bureau, the columns dropped are `entity_id`, `account_id`, `payment_id`, `journal_id`, `household_id` and any ending in `_entity_id` or `_account_id`.
  - **Fact tables** are written one COPY per month, as `dest/<table>/month=YYYY-MM/part-0.parquet`, from `select * exclude (<ids>, month) from (<definition>) where month = ? order by <same order>`. The month comes from `date`, or from the `month` column. Dimension tables go to `dest/<table>.parquet`.
  - **`manifest.json`** holds `source_run_id`, `source_content_hash`, `view`, `scope`, `asof` (ISO or null), and `tables`: {name: {`rows`, `columns`: [[name, type]], `content_hash`}}. Keys are sorted, with no times.
  - **`README.md`** has one section per table, and one line per column from `DESCRIPTIONS`.
  - **`dest`:** if it exists and isn't an empty directory, raise `FileExistsError`. If it doesn't exist, create it.
  - **Truth export** copies every run table unchanged, under the same layout.

- [ ] **Step 1: Write the failing tests:**

```python
def test_bank_export_round_trip(small_run, tmp_path):
    run = small_run(); dest = tmp_path / "b3"
    run.export(dest, view="bank", bank="SYNB03")
    v = run.view("bank", bank="SYNB03")
    for t in v.tables():
        got = pl.read_parquet(dest / t) if t in v.fact_tables else pl.read_parquet(dest / f"{t}.parquet")
        assert not {c for c in got.columns if c in ID_COLUMNS or c.endswith(("_entity_id", "_account_id"))}
        want = v.table(t).collect().drop([c for c in v.table(t).collect_schema().names()
                                          if c in ID_COLUMNS or c.endswith(("_entity_id", "_account_id"))])
        assert got.height == want.height
    m = json.loads((dest / "manifest.json").read_text())
    assert m["view"] == "bank" and m["scope"] == {"bank": "SYNB03"} and set(m["tables"]) == set(v.tables())
    readme = (dest / "README.md").read_text()
    assert all(f"## {t}" in readme for t in v.tables())

def test_export_is_deterministic(small_run, tmp_path):
    a = json.loads((small_run().export(tmp_path / "a", view="switch") / "manifest.json").read_text())
    b = json.loads((small_run().export(tmp_path / "b", view="switch") / "manifest.json").read_text())
    assert a == b

def test_export_refuses_non_empty_dest_and_allows_empty(small_run, tmp_path):
    (tmp_path / "full").mkdir(); (tmp_path / "full" / "x").write_text("x")
    with pytest.raises(FileExistsError):
        small_run().export(tmp_path / "full", view="bureau")
    (tmp_path / "empty").mkdir()
    small_run().export(tmp_path / "empty", view="bureau")

def test_truth_export_keeps_ids(small_run, tmp_path):
    small_run().export(tmp_path / "t", view="truth")
    assert "entity_id" in pl.read_parquet(tmp_path / "t" / "persons.parquet").columns

def test_every_view_column_is_described(small_run):
    for kind, scope in [("bank", {"bank": "SYNB01"}), ("switch", {}), ("bureau", {})]:
        v = small_run().view(kind, **scope)
        for t in v.tables():
            assert set(v.table(t).collect_schema().names()) <= set(DESCRIPTIONS[t])
```

  `ID_COLUMNS` is exported from `export.py`. Bank and switch tables are both called `payments`, so `DESCRIPTIONS` is keyed by table name, and its `payments` entry covers both views' columns.

- [ ] **Step 2: Run the tests and see them fail.** Run `pytest tests/test_export.py -v`. Expected: ImportError.

- [ ] **Step 3: Implement.**

- [ ] **Step 4: Run the tests and see them pass.** Run the same command, then `pytest -q`. Expected: all pass.

- [ ] **Step 5: Commit.** Message: `feat: export a view with a manifest and data dictionary`.

---

### Task 11: Slow gate and demo script

**Files:**
- Create: `tests/test_gate_1c.py` (marked `slow`), `scripts/data_products_demo.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `scripts/data_products_demo.py RUN_PATH [--bank SYNB03] [--entity N] [--out DIR]`. It prints JSON with the seconds taken and the rows returned by each call:
  - `Run.open`, `table`, `sql`;
  - `view` bank `payments` / `statement_lines`, switch `payments`, bureau;
  - `inspect` (profile, timeline, passbook, net_worth);
  - each built-in metric by month;
  - `export` bank.

  It also prints the export folder size.

- [ ] **Step 1: Write the slow gate.** On a tier S, 90-day, seed 7 run:
  - every table's live hash equals `content_hash` from disk;
  - for SYNB03, every account's last April statement line equals `balances_monthly`;
  - every UPI attempt appears once in the switch view;
  - a bank export round-trips with no ID columns;
  - `watch` on one person over the last 5 days matches the stored rows.

- [ ] **Step 2: Run the gate.** Run `pytest -m slow tests/test_gate_1c.py -q`. Expected: PASS. Also run the earlier gates: `pytest -m slow -q`. Expected: all pass.

- [ ] **Step 3: Write the demo script** and run it on the gate's run directory. Expected: JSON with every call listed.

- [ ] **Step 4: Commit.** Message: `test: plan 1c slow gate and data products demo script`.

---

### After Task 11: final review, fixes, then Task 12

One fresh Opus reviewer reads the whole branch against the spec and this plan. Fix Critical and Important findings test-first, and record rulings in the ledger.

### Task 12: Results doc and merge

**Files:**
- Create: `docs/phase1c_results.md`
- Modify: `docs/superpowers/ledger.md`

- [ ] **Step 1: Bench before and after.** Run `scripts/bench.py --tier S --days 90 --seed 7` on `main` (or the `main` tip, if it moved) and on the branch, then `--days 365` on the branch. Record:
  - build, simulation and total seconds;
  - payments per second;
  - peak memory;
  - disk per table.
- [ ] **Step 2: Hash comparison.** For every table, compare the branch's 90-day manifest hash with `main`'s. Expect equality for all but `persons`, `accounts` and `instruments`. For those three, show that dropping the new columns (or rows of the new kinds) gives `main`'s content.
- [ ] **Step 3: Run the demo script** on the 365-day branch run, and put each call's timing and a small sample output into the doc.
- [ ] **Step 4: Re-query everything.** Re-query every figure in the doc from the runs. Then commit: `docs: plan 1c results`.
- [ ] **Step 5: Merge.** Rebase onto the local `main` and run the fast suite and all slow gates. If `main` moved, re-run Step 2 against its tip. Then run `git -C /Users/rbih/uc/projects/ArthaSim merge --ff-only claude/gallant-roentgen-ebc4d9`. Never push.
