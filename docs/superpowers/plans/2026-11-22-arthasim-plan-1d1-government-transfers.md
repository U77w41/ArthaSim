# Plan 1d-1: Government Transfers (DBT) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a government with a balance at the central bank, and pay three DBT schemes (PM-Kisan, a social old-age pension, a state cash transfer to women) by APBS into eligible people's accounts, on real dates and in real amounts.

**Architecture:**
- A new journal kind, `GOVERNMENT_TRANSFER`, posts three lines: government balance down, deposit up, the deposit bank's reserves up. The kernel, the reference journal and the invariants all know it.
- Scheme rules are pure functions in `src/arthasim/dbt/schemes.py`, called by the build (to bank every enrolee and draw the BPL list) and by a monthly module, `GovernmentTransfers` (`src/arthasim/modules/dbt.py`). The module enrols people, opens accounts, emits credits and sets transfer income.
- `Budget` and `Allowance` count that transfer income.

**Tech Stack:** Python 3.12, numpy, numba, polars, duckdb, pytest, hypothesis. Run everything as `PYTHONPATH=src <venv>/bin/python -m pytest ...`; the venv is in the session scratchpad.

**Spec:** `docs/superpowers/specs/2026-11-22-government-transfers-design.md`. Sources: `docs/sources/dbt.md`.

## Global Constraints

- New enum values, exactly as listed:
  - `Kind.GOVERNMENT_TRANSFER = 6`;
  - `FlowType.SOCIAL_BENEFIT = 10`;
  - `InstrumentType.GOVERNMENT = 4`;
  - `Rail.APBS = 11`;
  - `Purpose.DBT_PM_KISAN = 7`, `Purpose.DBT_OLD_AGE_PENSION = 8`, `Purpose.DBT_WOMEN = 9`;
  - `EntityKind.GOVERNMENT = 9`, `Sector.GOVERNMENT = 6`.
- Money is integer paise. No `np.random` under `src/`; every draw goes through `arthasim.engine.rng` with a stream starting `dbt.`.
- A government transfer never declines: no funds check, no technical decline.
- `monthly_income_paise` stays earned income only. Transfers live in `BehaviourState.person_transfer` and `transfer_income` and are never paid by `Income`.
- "Households with no income" means `truth_household_monthly.income_paise = 0` (earned).
- Account ownership at build is unchanged by DBT: the swap holds each district's count of account holders.
- Population builds only. The spike world (tier XS) behaves exactly as before.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Never push.

## Review Focus

1. **A government transfer to a deposit with no reserve lookup (−1).** `settle_day` must raise `ValueError` before the kernel runs, not post to account −1 (the last account). Test in Task 2.
2. **A run that starts mid-month after a pay day.** It pays no arrears for that month. A run whose first day is a pay day pays that day. Test in Task 5.
3. **A tiny world where a district has fewer swap donors than unbanked enrolees.** The build must not fail; the extra accounts stay. Test in Task 4.
4. **A person enrolled one month who becomes ineligible the next** (for example, turns 61 in the women's scheme). They are not paid, and their transfer income drops to 0. Test in Task 5.
5. **Coverage overridden to 0 or 1 with `--set`.** At 0 there are no DBT intents and the run is unchanged apart from tables. At 1 every eligible payee is enrolled. Tests in Tasks 3 and 5.

---

### Task 1: Ledger shape for the government transfer

**Files:**
- Modify: `src/arthasim/ledger/instruments.py` (add `GOVERNMENT = 4`)
- Modify: `src/arthasim/ledger/journal.py` (`Kind.GOVERNMENT_TRANSFER = 6`, `FlowType.SOCIAL_BENEFIT = 10`, shape rule in `check_shape`)
- Modify: `src/arthasim/ledger/invariants.py` (`_check_shapes`, `flow_matrix`)
- Modify: `src/arthasim/engine/intents.py` (`Rail.APBS = 11`; the three purposes)
- Modify: `src/arthasim/build/world.py` (`EntityKind.GOVERNMENT = 9`, `Sector.GOVERNMENT = 6`)
- Test: `tests/test_ledger_dbt.py` (new)

**Interfaces:**
- Produces: the enum values above.
- Produces: the shape rule. A `GOVERNMENT_TRANSFER` is valid iff:
  - there are three lines;
  - the types are `[GOVERNMENT, DEPOSIT, RESERVE]`;
  - `d0 < 0` and `d1 == d2 == -d0`;
  - `holder[a2] == issuer[a1]`.
- Produces: `flow_matrix` covers `PAYMENT`, `CASH_PAYMENT`, and lines whose account type is not `RESERVE` in `GOVERNMENT_TRANSFER` entries.

- [ ] **Step 1: Write the failing tests** in `tests/test_ledger_dbt.py`. The world helper: book with a government balance (holder `GOV=10`, issuer `CB=9`, opening 0), a household deposit at `BANK1=7` (opening 0), reserves for `BANK1` and `BANK2=8`, and a vault for each bank. Sectors: household 1, bank 3, central bank 4, government 6.

```python
def test_enums():
    assert (Kind.GOVERNMENT_TRANSFER, FlowType.SOCIAL_BENEFIT, T.GOVERNMENT, Rail.APBS) == (6, 10, 4, 11)
    assert (Purpose.DBT_PM_KISAN, Purpose.DBT_OLD_AGE_PENSION, Purpose.DBT_WOMEN) == (7, 8, 9)
    assert (EntityKind.GOVERNMENT, Sector.GOVERNMENT) == (9, 6)

def test_reference_journal_posts_and_lets_the_government_go_negative():
    # j.post(0, GOVERNMENT_TRANSFER, SOCIAL_BENEFIT, 1, [(gov, -1500), (dep, 1500), (res1, 1500)])
    # balances: gov -1500, dep +1500, res1 +1500

@pytest.mark.parametrize("bad", ["two_lines", "wrong_reserve_bank", "unequal", "positive_first", "cash_line"])
def test_reference_journal_rejects_malformed(bad):  # each raises LedgerError

def test_day_with_a_transfer_passes_every_invariant_and_balances_by_sector():
    # post the transfer, then check_day(...) with equity unchanged; sector_balance: GOV -1500, HOUSEHOLD +1500, BANK 0, CB 0
    # flow_matrix rows: (SOCIAL_BENEFIT, GOVERNMENT, -1500), (SOCIAL_BENEFIT, HOUSEHOLD, 1500)

def test_vectorised_shapes_catch_a_reserve_at_the_wrong_bank():
    # hand-built journal/postings frames with line 2 = res2 → InvariantError("shapes")
```

- [ ] **Step 2: Run them and confirm they fail.** Run `pytest tests/test_ledger_dbt.py -q`. Expected: ImportError or AttributeError on the new enum names.
- [ ] **Step 3: Implement.**
  - Add the enum values.
  - In `check_shape`, add a `GOVERNMENT_TRANSFER` branch with the rule above.
  - In `_check_shapes`, add the vectorised condition, using the existing `line()` helpers and `book.holder[a2] == book.issuer[a1]`.
  - In `flow_matrix`, extend the mask to `m |= (kind == Kind.GOVERNMENT_TRANSFER) & (book.type[acct] != T.RESERVE)`.
  - `Journal.post`'s negative-balance check already skips non-DEPOSIT, non-CASH accounts. Leave it.
- [ ] **Step 4: Run** `pytest tests/test_ledger_dbt.py tests/test_ledger.py tests/test_ledger_1b.py tests/test_invariants.py tests/test_flow_columns.py -q`. Expected: all pass.
- [ ] **Step 5: Commit** with `feat: government balance and the government-transfer journal shape`.

### Task 2: Kernel and scheduler post government transfers

**Files:**
- Modify: `src/arthasim/engine/settlement.py` (`_settle`, `settle_day`)
- Modify: `src/arthasim/engine/scheduler.py` (pass `reserve_for_deposit`)
- Modify: `src/arthasim/build/world.py` (`WorldState.reserve_for_deposit: Any = None`, after `account_opened_on`)
- Test: `tests/test_ledger_dbt.py`

**Interfaces:**
- Produces: `settle_day(..., withdraw_rail=None, withdrawal_note=1, reserve_for_deposit: np.ndarray | None = None) -> Settled`.
  - When `reserve_for_deposit` is `None`, the kernel gets an all −1 array.
  - Before calling the kernel, `settle_day` raises `ValueError("government transfer to an account with no reserve")` if any `GOVERNMENT_TRANSFER` intent's payee has `reserve_for_deposit[payee] < 0`.
- Produces: `run_day` passes `reserve_for_deposit=getattr(state, "reserve_for_deposit", None)`.

- [ ] **Step 1: Write the failing tests.** Use the test module's `TYPE`/`DEP_FOR_CASH`/`VAULT_FOR_DEP` style, adding a GOVERNMENT account and a RESERVE account.

```python
def test_kernel_posts_three_lines_and_never_declines():
    # gov balance 0, deposit 0: one GOVERNMENT_TRANSFER of 2000 by Rail.APBS, Purpose.DBT_WOMEN, tech u=0.0, rate=1.0
    assert s.payments["status"].tolist() == [Status.SUCCESS]
    assert s.postings["account_id"].tolist() == [gov, dep, res] and s.postings["delta"].tolist() == [-2000, 2000, 2000]
    assert bal[gov] == -2000 and s.journal["kind"].tolist() == [Kind.GOVERNMENT_TRANSFER]

def test_missing_reserve_lookup_raises():
    with pytest.raises(ValueError, match="no reserve"):
        settle_day(..., reserve_for_deposit=None)   # GOVERNMENT_TRANSFER present, lookup all -1

def test_netting_leaves_government_transfers_alone(tmp_path):
    # small population world (persons=300), one day: inject a GOVERNMENT_TRANSFER via a stub module
    # appended to world.modules. After the day the bank's reserve rose by exactly the transfer and
    # check_day passed (the day returned without InvariantError).
```

- [ ] **Step 2: Run them and confirm they fail.** Run `pytest tests/test_ledger_dbt.py -q`. Expected: the new tests fail on the unknown keyword and wrong postings.
- [ ] **Step 3: Implement.**
  - Kernel constant `_GOVT = 6`.
  - In `_settle`, skip the funds check for `_GOVT`. The UPI limit and technical-decline checks apply to UPI rails only, so `APBS` never declines.
  - After posting lines 0 and 1, post line 2 to `reserve_for_deposit[dst]` with `+a`.
  - Add `reserve_for_deposit` as the last positional argument of `_settle`.
- [ ] **Step 4: Run** `pytest tests/test_ledger_dbt.py tests/test_settlement.py tests/test_ledger_1b.py -q`. Expected: pass.
- [ ] **Step 5: Commit** with `feat: the kernel posts government transfers to deposit and reserve`.

### Task 3: Registry rows and scheme rules

**Files:**
- Modify: `params/registry.yaml` (17 rows, listed below)
- Modify: `tests/test_build_1b.py` (row count 115 → 132)
- Create: `src/arthasim/dbt/__init__.py` (empty), `src/arthasim/dbt/schemes.py`
- Test: `tests/test_dbt_schemes.py` (new)

**Registry rows.** All have `as_of: 2026-11` and `role: input`. The `source` cites `docs/sources/dbt.md` plus the named publication. Status `unverified` (U) or `assumption` (A):

| Id | Value | Status |
| :--- | :--- | :--- |
| `dbt.pm_kisan.amount_paise` | `200000` | U |
| `dbt.pm_kisan.dates` | `["2025-08-02", "2025-11-19", "2026-03-13", "2026-06-20"]` | U |
| `dbt.pm_kisan.coverage` | `0.66` | A |
| `dbt.pm_kisan.pension_exclusion_paise` | `1000000` | U |
| `dbt.taxpayer_income_paise` | `70000000` (per year) | A |
| `dbt.old_age.min_age` | `60` | U |
| `dbt.old_age.central_paise` | `[[60, 20000], [80, 50000]]` (from that age) | U |
| `dbt.old_age.state_topup_paise` | `80000` | A |
| `dbt.bpl.headcount` | `{metro: 0.264, rural: 0.309}` | U |
| `dbt.old_age.coverage` | `0.5` | A |
| `dbt.old_age.day` | `5` | A |
| `dbt.women.ages` | `[21, 60]` | U |
| `dbt.women.amount_tiers` | `[[100000, 363.2], [125000, 157.8], [150000, 200.8], [200000, 119.2], [210000, 19.8], [250000, 61.6]]` | A |
| `dbt.women.income_cap_paise` | `25000000` (per year) | U |
| `dbt.women.coverage` | `0.4` | A |
| `dbt.women.day` | `10` | A |
| `dbt.slots` | `[24, 39]` | A |

**Interfaces** (`src/arthasim/dbt/schemes.py`):
- Produces:

```python
PM_KISAN, OLD_AGE_PENSION, WOMEN = "PM_KISAN", "OLD_AGE_PENSION", "WOMEN"

@dataclass(frozen=True)
class DbtInputs:            # one entry per person unless noted
    stage: np.ndarray       # life stage index
    helper: np.ndarray      # bool
    age: np.ndarray
    sex: np.ndarray
    sector: np.ndarray      # attributes.sector (int)
    income: np.ndarray      # monthly_income_paise (earned)
    household: np.ndarray   # household index per person
    is_metro: np.ndarray    # bool per person
    hh_members: np.ndarray  # per household: adults + dependants
    bpl: np.ndarray         # per household, bool

@dataclass(frozen=True)
class SchemeResult:
    scheme: str
    payee: np.ndarray          # person indices of eligible payees, ascending
    enrolled: np.ndarray       # bool, aligned with payee
    amount: np.ndarray         # paise per credit; 0 where not enrolled
    monthly_value: np.ndarray  # paise per month; 0 where not enrolled

@dataclass(frozen=True)
class Scheme:
    name: str
    purpose: int
    evaluate: Callable[[DbtInputs, ParamRegistry, int], SchemeResult]
    pays_on: Callable[[dt.date, ParamRegistry], bool]

def bpl_households(per_member_income: np.ndarray, members: np.ndarray, is_metro: np.ndarray,
                   headcount: Mapping[str, float]) -> np.ndarray: ...   # per household, bool
def pm_kisan(inp: DbtInputs, params: ParamRegistry, seed: int) -> SchemeResult: ...
def old_age_pension(inp: DbtInputs, params: ParamRegistry, seed: int) -> SchemeResult: ...
def women(inp: DbtInputs, params: ParamRegistry, seed: int) -> SchemeResult: ...
def default_schemes() -> list[Scheme]: ...   # in order PM_KISAN, OLD_AGE_PENSION, WOMEN
def enrolled_payees(inp: DbtInputs, params: ParamRegistry, seed: int,
                    schemes: list[Scheme] | None = None) -> np.ndarray: ...  # bool per person
```

- **Rules**, exact:
  - **PM-Kisan.**
    - A household is eligible if it has a member with `stage == FARM & ~helper`.
    - It is excluded if any member has `stage == SALARIED & sector == PUBLIC_ADMIN`, or `income * 12 > dbt.taxpayer_income_paise`, or `stage == RETIRED & income >= dbt.pm_kisan.pension_exclusion_paise`.
    - The payee is the eldest own-account farmer, with the lowest index on ties.
    - Covered if `uniform(seed, S("dbt.pm_kisan.cover"), household_index, 0) < coverage`.
    - The amount is `dbt.pm_kisan.amount_paise`; the monthly value is `amount * 3 // 12`.
    - It pays when `day.isoformat()` is in `dbt.pm_kisan.dates`.
  - **Old-age pension.**
    - Eligible if `age >= min_age & stage != RETIRED & bpl[household]`.
    - Covered by stream `"dbt.old_age.cover"` on the person index.
    - The amount is the central amount for the highest listed age ≤ age, plus the top-up. The monthly value equals the amount.
    - It pays when `day.day == dbt.old_age.day`.
  - **Women.**
    - Eligible if `sex == F & lo <= age <= hi`, household earned income `* 12 < dbt.women.income_cap_paise`, and no household member is salaried in `PUBLIC_ADMIN`.
    - Covered by stream `"dbt.women.cover"`.
    - The tier is the first tier whose cumulative normalised weight exceeds `uniform(seed, S("dbt.women.tier"), person, 0)`. The amount is that tier's; the monthly value equals the amount.
    - It pays when `day.day == dbt.women.day`.
  - **BPL.**
    - Within each district kind, sort households by per-member income (ties by household index).
    - A household is BPL if the members of strictly earlier households number fewer than `headcount × total members` of that kind.

- [ ] **Step 1: Write the failing tests** in `tests/test_dbt_schemes.py`, with hand-built `DbtInputs` for 3 to 6 households:

```python
def test_registry_rows_and_count():
    assert P.table().height == 132 and P.get("dbt.pm_kisan.amount_paise") == 200_000
    assert P.get("dbt.bpl.headcount") == {"metro": 0.264, "rural": 0.309}

def test_bpl_takes_the_poorest_persons_up_to_the_headcount():
    # per-member incomes [0, 100, 200, 300] with members [1, 1, 1, 1], all rural, headcount 0.309
    assert bpl_households(...).tolist() == [True, True, False, False]   # 0 < 1.236 and 1 < 1.236 members before
    # straddling household is included; metro and rural are ranked separately

def test_pm_kisan_one_payee_per_household_and_exclusions():
    # household 0: farmer 50y + farmer 60y → payee is the 60-year-old
    # household 1: farmer + public_admin salaried member → excluded
    # household 2: farmer + member earning 60,000/month (7.2 lakh/yr) → excluded; 58,000 → eligible
    # household 3: farmer + retired with pension 10,000 → excluded; 9,999 → eligible
    # household 4: helper only → not eligible
    # with coverage 1.0: amount 200000 and monthly_value 50000 for each payee

def test_old_age_pension_amounts_and_rules():
    # 79y BPL homemaker → 100000; 80y → 130000; 65y retired → not eligible; 65y non-BPL → not eligible

def test_women_rules_and_tiers():
    # F 21 and 60 eligible, 20 and 61 not; male not; household income 2,083,333 paise/month (= cap/12 rounded down) → 24,999,996 < cap eligible;
    # 2,083,334 → 25,000,008 ≥ cap not eligible; public_admin member → not eligible
    # with coverage 1.0 over 20,000 synthetic women: tier shares within 0.01 of 363.2/922.4 etc.

def test_coverage_is_fixed_per_entity_and_respects_0_and_1():
    # same inputs, two calls → identical enrolled; coverage 0 → none enrolled; 1 → all

def test_enrolled_payees_marks_every_enrolled_person():
    # the union over schemes of payee[enrolled]
```

- [ ] **Step 2: Run them and confirm they fail.** Run `pytest tests/test_dbt_schemes.py tests/test_build_1b.py -q`. Expected: ImportError, and the row count is 115.
- [ ] **Step 3: Implement.** Add the registry rows and write `schemes.py`. Pass parameter overrides through the `ParamRegistry` as given, so `with_params` overrides reach the rules.
- [ ] **Step 4: Run** `pytest tests/test_dbt_schemes.py tests/test_build_1b.py tests/test_params.py -q`. Expected: pass.
- [ ] **Step 5: Commit** with `feat: DBT scheme rules and registry rows from published sources`.

### Task 4: The government and banked enrolees at build

**Files:**
- Modify: `src/arthasim/build/world.py` (`GovernmentState`; `WorldState.government: Any = None`)
- Modify: `src/arthasim/build/banking.py` (`assign_banking(..., must_bank=None)` swap)
- Modify: `src/arthasim/build/pipeline.py` (entity, balance, BPL, enrolment, `reserve_for_deposit`, frames)
- Modify: `src/arthasim/life/accounts.py` (grow `reserve_for_deposit`)
- Test: `tests/test_dbt_build.py` (new)

**Interfaces:**
- Produces:

```python
@dataclass
class GovernmentState:
    entity_id: int
    balance_account: int
    bpl: np.ndarray            # per household, bool, fixed for the run

def dbt_inputs(state: WorldState) -> DbtInputs        # in pipeline.py; live arrays of a population state
```

- Produces: `assign_banking(persons, attributes, orgs, districts, config, params, seed, must_bank: np.ndarray | None = None) -> Banking`. The swap works per district:
  - `need = must_bank & ~has_account`;
  - donors are `has_account & ~salaried & ~must_bank`, ranked by `u("bank.dbt_swap")`;
  - the first `min(need, donors)` donors lose their account, and every needer gains one.
- Produces:
  - `state.government`;
  - `state.reserve_for_deposit` (per account, the issuing bank's reserve account, −1 elsewhere);
  - the government id is `boundary_id + 1`, and `kind`/`sector` arrays are one longer;
  - the government balance is `book.add(T.GOVERNMENT, government_id, central_bank_id, 0)`, added after the boundary's accounts.
- Produces:
  - an `orgs` row `kind="GOVERNMENT"`;
  - `accounts.type == "GOVERNMENT"`, with `subtype == "treasury"` for the balance.
- Build order in `build_population_state`:
  1. After `edges`, compute household members, earned income per member and `bpl`.
  2. Compute `must_bank = enrolled_payees(...)` from build state.
  3. Then call `assign_banking`.

  Banking moves after the BPL and enrolment step. Orgs are already built.

- [ ] **Step 1: Write the failing tests:**

```python
def test_government_entity_balance_and_frames():
    s = small_world().state
    g = s.government
    assert s.kind[g.entity_id] == EntityKind.GOVERNMENT and s.sector[g.entity_id] == Sector.GOVERNMENT
    assert s.book.type[g.balance_account] == T.GOVERNMENT and s.book.holder[g.balance_account] == g.entity_id
    assert s.book.issuer[g.balance_account] == s.central_bank_id and s.book.opening[g.balance_account] == 0
    # reserve_for_deposit: for every person deposit, holder of that reserve == issuer of the deposit

def test_bpl_shares_by_district_kind():
    # persons in BPL households / all persons (adults + dependants) is >= headcount and < headcount + largest household share

def test_every_enrolee_is_banked_and_ownership_is_unchanged():
    # build twice at persons=5_000: with dbt coverage overridden to 0 (no enrolees) and default
    # per-district count of account holders identical; every enrolled payee has person_deposit >= 0
    # salaried keep accounts in both

def test_tiny_world_with_too_few_donors_still_builds(tmp_path):
    # persons=300, women coverage 1.0 and account_ownership {metro: 0.3, rural: 0.3}: builds; every enrolee banked

def test_open_accounts_grows_the_reserve_lookup():
    # open one account; reserve_for_deposit[new] == bank_reserve[bank]
```

- [ ] **Step 2: Run them and confirm they fail.** Run `pytest tests/test_dbt_build.py -q`. Expected: `AttributeError: government`.
- [ ] **Step 3: Implement** as above.
  - `dbt_inputs` reads `pop.persons`, `s.life.helper`, `pop.attributes`, `pop.households` and `s.government.bpl`.
  - At build, before `WorldState` exists, construct `DbtInputs` directly from the build arrays.
- [ ] **Step 4: Run** `pytest -q` (the fast suite). Expected: all pass. Seeded figures elsewhere may shift because banking now depends on DBT. If a test pins an exact count that the swap legitimately moves, update it and say why in the commit message.
- [ ] **Step 5: Commit** with `feat: the government and its balance; DBT payees banked at build`.

### Task 5: The GovernmentTransfers module

**Files:**
- Create: `src/arthasim/modules/dbt.py`
- Modify: `src/arthasim/behaviour.py` (`person_transfer` per person, `transfer_income` per household)
- Modify: `src/arthasim/modules/lifecourse.py` (`entity_state_monthly` built in `tables()`)
- Modify: `src/arthasim/world.py` (module list; `_household_monthly` gains `transfer_income_paise`)
- Modify: `src/arthasim/store/parquet.py` (`truth_dbt_monthly` joins `FACT_TABLES`)
- Modify: `tests/test_money_flows.py` (module list)
- Test: `tests/test_dbt_module.py` (new)

**Interfaces:**
- Consumes: `default_schemes`, `SchemeResult`, `dbt_inputs`, `open_accounts`, `pick_banks`, `EventLog`.
- Produces: `class GovernmentTransfers(BehaviourModule)` with `name = "dbt"`, `schemes: list[Scheme]`.
  - **`monthly`:**
    1. Evaluate each scheme.
    2. Open accounts for unbanked enrolled payees. Banks come from `pick_banks(uniform(seed, S("dbt.bank"), persons, first_of_month_ordinal), is_metro, params, banks)`. Log `ACCOUNT_OPENED` with ids from `s.life.next_event_id`, then advance it.
    3. Set `beh.person_transfer` to the sum of enrolled monthly values.
    4. Buffer a `truth_dbt_monthly` frame.
  - **`intents`:** for each scheme whose `pays_on(day)` holds, emit one intent per enrolled payee:
    - kind `GOVERNMENT_TRANSFER`, flow `SOCIAL_BENEFIT`;
    - payer `government.balance_account`, payee `person_deposit[payee]`;
    - rail `APBS`, the scheme's purpose and the payee's amount;
    - slot `lo + min(floor(u * (hi - lo + 1)), hi - lo)` on stream `"dbt.slot"` keyed on (payee, day ordinal);
    - offset on `"dbt.offset"`.
  - **`tables`:** `{"truth_dbt_monthly": frame, "life_events": events}` once per month.
- Produces: `truth_dbt_monthly` with columns `entity_id` Int64, `month` String, `scheme` String, `enrolled` Boolean, `monthly_value_paise` Int64, `opened_account` Boolean.
- Produces: the module order `["lifecourse", "income", "remittances", "dbt", "budget", "allowance", "consumption", "cash"]`.

- [ ] **Step 1: Write the failing tests.** Use `World.build(Config.tier("S", persons=5_000, out_dir=...), seed=7)` worlds:

```python
def test_module_order_and_tables(tmp_path): ...       # names list; truth_dbt_monthly in run.tables() after 31 days

def test_women_and_pensions_paid_on_their_days_to_enrolled_payees(tmp_path):
    # run April 2025: DBT_WOMEN credits all on 2025-04-10, DBT_OLD_AGE_PENSION on 2025-04-05,
    # each credit's payee holder == an enrolled row of truth_dbt_monthly for 2025-04 and that scheme,
    # every enrolled row paid exactly once, amounts == monthly_value_paise, rail APBS, status SUCCESS,
    # slots within 24..39, payer account == government balance
    # government balance == -sum(amounts)

def test_pm_kisan_pays_on_its_date_only(tmp_path):
    # Config start 2025-08-01, run to 2025-08-03: DBT_PM_KISAN credits only on 2025-08-02, one per enrolled household, 200000 each

def test_mid_month_start_pays_no_arrears_and_a_start_on_the_pay_day_pays(tmp_path):
    # start 2025-04-11 → no DBT_WOMEN in April; start 2025-04-10 → DBT_WOMEN paid on 2025-04-10

def test_people_enrolled_during_the_run_open_accounts_and_are_paid(tmp_path):
    # force: after build, set an enrolled-to-be woman unbanked is impossible (build banks them);
    # instead run 3 months and assert: every truth_dbt_monthly row with opened_account has an ACCOUNT_OPENED
    # life_event that month and the person's entity_state_monthly row that month has has_account true

def test_ineligible_next_month_stops_payment_and_transfer_income(tmp_path):
    # pick a woman aged 60 with birth_month == 5 who is enrolled in April; run to May 31:
    # paid on 2025-04-10, not on 2025-05-10; person_transfer for her == 0 at end (unless pension)

def test_coverage_zero_means_no_dbt_intents(tmp_path):
    # all three coverages 0 → no DBT purposes in payments; truth rows all enrolled false

def test_split_run_equals_single_run_and_determinism(tmp_path):
    # as tests/test_money_flows.py does, including truth_dbt_monthly hashes

def test_entity_state_shows_dbt_accounts(tmp_path): ...  # covered with the opened-account test
```

- [ ] **Step 2: Run them and confirm they fail.** Run `pytest tests/test_dbt_module.py -q`. Expected: ImportError.
- [ ] **Step 3: Implement.**
  - Write the module.
  - Add the behaviour fields (`zeros` makes them).
  - In `LifeCourse`, keep `self._state_month`, and build `entity_state_monthly` in `tables()` from `state_frame(s, month)`.
  - In `World`, add the module after `Remittances`.
  - Add the store table.
- [ ] **Step 4: Run** `pytest -q`. Expected: all pass, including `tests/test_lifecourse.py` with the moved state frame.
- [ ] **Step 5: Commit** with `feat: GovernmentTransfers pays PM-Kisan, old-age pensions and women's transfers by APBS`.

### Task 6: Budgets and allowances count transfers

**Files:**
- Modify: `src/arthasim/modules/budget.py`, `src/arthasim/modules/allowance.py`, `src/arthasim/world.py` (`_household_monthly`)
- Modify: `scripts/bench.py` (`_mixed_households` uses earned + transfer income)
- Test: `tests/test_dbt_module.py`, `tests/test_budget.py`, `tests/test_allowance.py`

**Interfaces:**
- Produces: `Budget.monthly` sets `beh.income` (earned, unchanged) and `beh.transfer_income` (sum of `person_transfer` per household). It calls `household_budget(beh.income + beh.transfer_income, ...)`.
- Produces: `Allowance.monthly` passes `monthly_income_paise + beh.person_transfer` to `allowance_pairs`.
- Produces: `truth_household_monthly.transfer_income_paise`.

- [ ] **Step 1: Write the failing tests:**

```python
def test_budget_counts_transfer_income():
    # small_world-like fresh world: set person_transfer[x] = 150000 for a member of household h with earned income I
    # after Budget.monthly: beh.income[h] == I and beh.transfer_income[h] == 150000, budget[h] equals
    # household_budget(I + 150000, ...)[0][h]

def test_allowance_shortfall_falls_by_the_transfer():
    # household with one earner and one homemaker: homemaker's allowance with person_transfer 150000
    # == allowance without minus 150000 (when the shortfall exceeds 150000)

def test_household_monthly_table_has_transfer_column(tmp_path):
    # run April: truth_household_monthly.transfer_income_paise sum == sum of enrolled monthly_value_paise in April;
    # income_paise unchanged against monthly_income_paise sums
```

- [ ] **Step 2: Run them and confirm they fail.** Run `pytest tests/test_dbt_module.py tests/test_budget.py tests/test_allowance.py -q`. Expected: fail.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** with `feat: budgets and allowances count DBT income`.

### Task 7: Bench figures and the slow gate

**Files:**
- Modify: `scripts/bench.py`
- Create: `tests/test_gate_1d1.py`
- Test: `tests/test_bench.py`

**Interfaces:**
- Produces: the bench JSON gains these keys:
  - `"dbt"`: `{scheme: {"credits", "rupees", "beneficiaries"}}`, `"government_balance_rupees"`, `"dbt_accounts_opened"`, `"dbt_enrolled_share"` (`women_21_60`, `aged_60_plus`, `farm_households`; last month);
  - `"declined_funds_rate_no_income_households"`;
  - `"no_income_households_by_month"`;
  - `purpose_group_share["government"]`.

- [ ] **Step 1: Write the failing tests.**
  - In `tests/test_bench.py`, a tiny tier S run (persons 2,000, 40 days, so 10 April falls inside) asserts the new keys are present and `dbt["WOMEN"]["credits"] > 0`.
  - `tests/test_gate_1d1.py` (`@pytest.mark.slow`): tier S, seed 7, until `2026-03-31`. Assert that:
    - PM-Kisan credit dates (IST) are exactly `{2025-08-02, 2025-11-19, 2026-03-13}`;
    - for every month and scheme, the set of payees paid equals the set of enrolled rows in `truth_dbt_monthly` (PM-Kisan in its three months only);
    - every DBT payment is `SUCCESS` by `APBS`;
    - the government balance equals −(sum of DBT amounts).
- [ ] **Step 2: Run them and confirm they fail.** Run `pytest tests/test_bench.py -q`. Expected: KeyError on `dbt`.
- [ ] **Step 3: Implement** the bench queries.
  - DBT figures come from `payments` with the three purposes.
  - Enrolment shares come from `truth_dbt_monthly` joined with `entity_state_monthly` and `persons` for the last month.
  - The decline rate comes from attempts whose payer's household has `income_paise = 0` that month.
- [ ] **Step 4: Run** `pytest tests/test_bench.py -q`, then `pytest -m slow -q tests/test_gate_1d1.py`. Expected: pass.
- [ ] **Step 5: Commit** with `feat: bench reports DBT money and no-income declines; plan 1d-1 gate`.

### Task 8: Results and ledger notes

**Files:**
- Create: `docs/phase1d1_results.md`
- Modify: `docs/superpowers/ledger.md`

- [ ] **Step 1: Run the benches.**
  - `scripts/bench.py --tier S --days 90 --seed 7` on `main` (before) and on the branch (after).
  - Then `--days 365` on both.
- [ ] **Step 2: Run the whole fast suite and every slow gate** (`pytest -m slow -q`). Record the times.
- [ ] **Step 3: Write `docs/phase1d1_results.md`.** It covers:
  - funds declines overall;
  - funds declines for households with no earned income, as a share of declines and as their own rate, with the household count;
  - money moved by scheme;
  - the government balance;
  - accounts opened;
  - enrolment shares against the real figures in `docs/sources/dbt.md` (women 0.32; IGNOAPS about 15% of people aged 60+; PM-Kisan 0.66 of farm households);
  - cost.

  Re-query every figure from the run directories, and state the commands and the machine.
- [ ] **Step 4: Add the ledger notes.** In `docs/superpowers/ledger.md`, record what was built, the overnight decisions and the findings.
- [ ] **Step 5: Commit** with `docs: plan 1d-1 results`.
