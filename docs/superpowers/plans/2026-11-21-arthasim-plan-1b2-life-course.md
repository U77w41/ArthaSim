# arthasim Plan 1b-2 (Life Course) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Person state changes month by month during a run: life-stage counts in every (district, sex, five-year age group) cell equal PLFS-based targets that follow the seasons, people are hired, laid off and switch jobs, pay rises once a year, and unbanked people open accounts, with every change recorded in `life_events` and `entity_state_monthly`.

**Architecture:** A new package `arthasim.life` holds the pure parts: PLFS sources, targets, alignment, transition rates, helper rule, jobs, accounts and events. A new module `LifeCourse` runs first in the population module list and updates, in place, the arrays the other modules already read. The build fits the start month's targets exactly, so the first month needs no moves; the account book can grow after the build.

**Tech Stack:** Python 3.12, NumPy, Numba, Polars, PyArrow, DuckDB, Pydantic 2, PyYAML, pytest, Hypothesis.

**Spec:** `docs/superpowers/specs/2026-11-21-life-course-design.md` (approved 21 November 2026). Source extracts: `docs/sources/plfs_2025_annual.md`, `docs/sources/plfs_bulletins_2025_26.md`, `docs/sources/labour_transitions.md`. Repo path of this plan: `docs/superpowers/plans/2026-11-21-arthasim-plan-1b2-life-course.md`.

**Commands** run from the repo root in the Python 3.12 virtual environment the ledger describes, with `PYTHONPATH=src`: fast suite `PYTHONPATH=src pytest -q`, slow gates `PYTHONPATH=src pytest -m slow -q`.

## Global Constraints

- Everything in the earlier plans' Global Constraints still holds: integer paise, keyed randomness only (`engine.rng`), no `np.random` or `random` under `src/`, a failed invariant stops the run, category orders from `build/categories.py`.
- The whole existing suite stays green, with only the test edits this plan names. Tier XS keeps the spike builder and its two modules, with no life course.
- Stage order (from `categories.py`): studying 0, seeking 1, salaried 2, self_employed 3, gig 4, farm 5, casual 6, homemaker 7, retired 8.
- Stream names for the life course start with `life.`; the build's new draws start with `pop.` or `life.`.
- Monthly draws are keyed on the first day of the calendar month (`month.replace(day=1).toordinal()`), as `Budget` does.
- Every new number is a registry row (prefix `life.`) or a source value in `params/lifecourse/plfs_2025.yaml`. Transcribed source values have status `unverified`; values with no Indian source have status `assumption`.
- Modules read state and emit intents. The life course changes person state only in its monthly hook; only settlement changes balances. Opening an account moves no money.
- For salaried people `monthly_income_paise == person_salary` and `person_employer >= 0`; for everyone else `person_salary == 0` and `person_employer == -1`. Helpers have `monthly_income_paise == 0`.

## Review Focus

1. A cell whose target needs people in a stage that no allowed move reaches with positive probability (for example seeking in a 65+ cell with no seekers): the raking floor makes it reachable and the cell still lands exactly on target. Test in Task 3.
2. A run that starts mid-month (2025-04-20) runs no transitions until 1 May, and a split run equals a single run. Test in Task 9.
3. A person hired without an account opens one that month and their first salary lands in it on the employer's payday. Test in Task 9.
4. The last own-account member of a household leaves farm or self_employed: the household's helpers in that stage become own-account and start earning. Tests in Tasks 6 and 9.
5. A run past March 2026 (2026-03-20 to 2026-05-05) maps months to the same calendar month inside the window, and people ageing past 85 keep using the 65+ shares. Tests in Tasks 2 and 9.

## File Structure

| File | Responsibility |
| :--- | :--- |
| `params/lifecourse/plfs_2025.yaml` | Transcribed PLFS tables, bulletins, panel flows and effects, with URLs, tables and pages |
| `params/registry.yaml` (modify) | 23 new `life.` rows; `inclusion.account_ownership` becomes 0.89 |
| `params/population/*.yaml` (modify) | Comment only: `life_stage` rows are used only without PLFS targets |
| `src/arthasim/build/categories.py` (modify) | Age groups, stage groups, `PUBLIC_ADMIN` |
| `src/arthasim/life/sources.py` | `Plfs2025`, `load_plfs` |
| `src/arthasim/life/targets.py` | Stage mapping, interpolation by age, seasonal path, `Targets`, `cell_counts` |
| `src/arthasim/life/align.py` | `rake`, `round_flows`, `choose_movers`, `align` |
| `src/arthasim/life/rates.py` | Panel flows, study exits, `RateInputs`, `person_probs` |
| `src/arthasim/life/helpers.py` | The family-business rule for unpaid helpers |
| `src/arthasim/life/state.py` | `LifeState` and its initial values |
| `src/arthasim/life/jobs.py` | Employer choice, entry pay, switches, raises, payroll |
| `src/arthasim/life/accounts.py` | `open_accounts` |
| `src/arthasim/life/events.py` | Event names, the stage-change table, `EventLog`, `state_frame` |
| `src/arthasim/modules/lifecourse.py` | `LifeCourse` module |
| `src/arthasim/ledger/instruments.py` (modify) | `InstrumentBook.extend` after freeze |
| `src/arthasim/build/earnings.py`, `attributes.py`, `banking.py` (modify) | `income_for`, `draw_sector`, `pick_banks` extracted for reuse |
| `src/arthasim/build/population.py`, `pipeline.py`, `world.py` (modify) | Synthesis from targets, helpers, `LifeState`, `account_opened_on`, persons and account frames |
| `src/arthasim/modules/base.py`, `src/arthasim/world.py`, `src/arthasim/store/parquet.py` (modify) | `tables()` hook, module list, new fact tables, account tables rewritten at flush |
| `scripts/bench.py` (modify) | Life stage from `entity_state_monthly`; life summary |
| `docs/phase1b2_results.md`, `docs/superpowers/ledger.md` | Results and ledger |

---

### Task 1: Source data, registry rows and loader

**Files:**
- Create: `params/lifecourse/plfs_2025.yaml`, `src/arthasim/life/__init__.py`, `src/arthasim/life/sources.py`
- Modify: `params/registry.yaml`, `params/population/metro_archetype.yaml`, `params/population/rural_archetype.yaml`, `src/arthasim/build/categories.py`, `tests/test_build_1b.py` (registry count 91 → 114)
- Test: `tests/test_life_sources.py`

**Interfaces:**
- Produces:
  - `categories.py`: `AGE_GROUPS = ["18-19", "20-24", "25-29", "30-34", "35-39", "40-44", "45-49", "50-54", "55-59", "60-64", "65+"]`, `AGE_GROUP_EDGES = [18, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65]`, `N_AGE_GROUPS = 11`, `WORK = (SELF_EMPLOYED, GIG, FARM, CASUAL)`, `NON_EARNING = (STUDYING, SEEKING, HOMEMAKER, RETIRED)`, `PUBLIC_ADMIN = 7`, `def age_group(age) -> np.ndarray` (index into `AGE_GROUPS`).
  - `sources.py`: `GROUPS = ("rural_male", "rural_female", "urban_male", "urban_female")`; `def group_name(kind: str, sex: int) -> str` (`"metro"` → urban, `"rural"` → rural); `PLFS_COLUMNS = ["15-19", "20-24", ..., "60-64", "65+", "15+"]` (12); `ANNUAL_ROWS` (the 18 row names below); `@dataclass(frozen=True) class FlowPairs: pairs: list[list[list[float | None]]]; row_totals: list[list[float]]`; `@dataclass(frozen=True) class Plfs2025: annual: dict[str, dict[str, list[float]]]; cws_2025: dict[str, dict[str, float]]; monthly: dict[str, dict[str, dict[str, float]]]; quarterly: dict[str, dict[str, dict[str, float]]]; flows: dict[str, FlowPairs]; effects: dict[str, dict[str, dict[str, float]]]`; `def load_plfs(path: str | Path = "params/lifecourse/plfs_2025.yaml") -> Plfs2025` (relative paths resolve against the repo root, like `marginals._resolve`; validated with Pydantic; cached per resolved path).

**Data file layout** (`params/lifecourse/plfs_2025.yaml`). Every block carries `source` (URL), `table`, `pages`, `status: unverified`:

- `annual.<group>.<row>`: 12 percentages, columns `PLFS_COLUMNS`, from Table 15 in `docs/sources/plfs_2025_annual.md` §1b. Rows (code, NIC): `own_agri` (11,12; 01-03), `own_secondary` (11,12; 05-43), `own_tertiary` (11,12; 45-96), `helper_agri`, `helper_secondary`, `helper_tertiary` (21), `regular` (31; 01-99), `regular_agri` (31; 01-03), `casual_public` (41), `casual_other` (51; 01-99), `casual_other_agri` (51; 01-03), `unemployed` (81), `student` (91), `domestic` (92), `domestic_collect` (93), `pensioner` (94), `disabled` (95), `others` (97). The partition rows are all except `regular_agri` and `casual_other_agri`, which are sub-rows.
- `cws_2025.<group>`: `{lfpr, wpr}` from Tables 30 and 31, ages 15+ (§Item 4): rural male 78.9 / 75.0, rural female 38.3 / 36.8, urban male 75.3 / 70.7, urban female 25.9 / 23.6.
- `monthly."YYYY-MM".<group>`: `{lfpr, wpr}` for 2025-04 to 2026-03, from `docs/sources/plfs_bulletins_2025_26.md` Part 1.
- `quarterly."YYYY-MM".<group>`: `{regular, casual, agriculture}` (% of CWS workers), keyed by the quarter's middle month (2025-05, 2025-08, 2025-11, 2026-02), from Part 2 tables (a) and (b).
- `flows.M`, `flows.F`: the four quarter pairs of QB October–December 2024 Table (5) (`docs/sources/labour_transitions.md` §1.4). `pairs[k][row][col]` with rows and columns in the order own, helper, regular, casual, unemployed, nlf (the "self employed" row and the "all self-employed#" column are left out; `*` is `null`); `row_totals[k][row]` is the row's "all" value.
- `effects.F`, `effects.M`: Bhattacharya Table 7 (§1.2), `{lost: {...}, gained: {...}}` with keys `very_young, young, graduate, has_child, married, e_ratio, streak2, streak3`, values as published (quarterly marginal effects).

**Registry rows** (`params/registry.yaml`, `as_of: 2026-11`, role `input`; status `unverified` where a source is named, else `assumption`):

| id | value | source |
| :--- | :--- | :--- |
| `life.gig.nonfarm_share` | `{2020: 0.026, 2029: 0.067}` (fiscal-year starts) | NITI Aayog 2022 |
| `life.return.weight` | 5 | assumption |
| `life.return.window_months` | 12 | assumption |
| `life.retire.superannuation_age` | `{private: 58, public_admin: 60}` | Standing Orders; FR 56(a) |
| `life.retire.superannuation_prob` | 0.5 | assumption (PLFS 55–59 to 60–64 salaried) |
| `life.study.max_age` | 35 | PLFS 2025 Table 15 |
| `life.within.farm_nonfarm` | 0.005 | ICRISAT VDSA |
| `life.within.self_gig` | 0.01 | assumption |
| `life.within.helper_to_own` | 0.005 | assumption |
| `life.within.own_to_helper` | 0.001 | assumption |
| `life.within.homemaker_retired` | 0.001 | assumption |
| `life.flows.negligible_pct` | 0.025 | assumption (half the 0.05 rounding) |
| `life.prob_bounds` | `[0.0003, 0.95]` | assumption |
| `life.switch.monthly_prob` | 0.011 | Aon 2025 (16.2% less 3.4% involuntary) |
| `life.switch.young` | `{age: 30, multiplier: 1.5}` | assumption (EPFO age mix) |
| `life.switch.same_sector_prob` | 0.7 | assumption |
| `life.switch.pay_factor` | `{median: 1.15, sigma: 0.15}` | assumption |
| `life.layoff.employer_shock_sigma` | 0.5 | assumption |
| `life.raise.mean` | 0.089 | Aon 2025 actual |
| `life.raise.sd` | 0.04 | assumption |
| `life.raise.april_share` | 0.56 | Naukri survey 2023 |
| `life.account.open_monthly_prob` | 0.015 | assumption (Findex trend) |
| `life.rake.floor` | 1.0e-6 | assumption |

`inclusion.account_ownership` becomes `{metro: 0.89, rural: 0.89}`, status `unverified`, source "Global Findex 2025 (PIB factsheet 150832)".

- [ ] **Step 1: Write the failing test** (`tests/test_life_sources.py`)

```python
import numpy as np
from arthasim.build import categories as c
from arthasim.life.sources import ANNUAL_ROWS, GROUPS, load_plfs
from helpers import P

S = load_plfs()
PARTITION = [r for r in ANNUAL_ROWS if r not in ("regular_agri", "casual_other_agri")]


def test_table_15_spot_values_and_column_sums():
    assert S.annual["urban_female"]["domestic"][11] == 47.7
    assert S.annual["rural_female"]["helper_agri"][11] == 13.6
    assert S.annual["rural_male"]["student"][0] == 68.6
    assert S.annual["urban_male"]["regular"][9] == 14.5
    for g in GROUPS:
        for j in range(12):
            assert abs(sum(S.annual[g][r][j] for r in PARTITION) - 100) < 0.7, (g, j)


def test_bulletins():
    assert len(S.monthly) == 12 and min(S.monthly) == "2025-04" and max(S.monthly) == "2026-03"
    assert S.monthly["2025-06"]["rural_female"]["wpr"] == 33.6 and S.monthly["2025-12"]["rural_female"]["wpr"] == 38.6
    assert S.cws_2025["rural_female"] == {"lfpr": 38.3, "wpr": 36.8}
    assert sorted(S.quarterly) == ["2025-05", "2025-08", "2025-11", "2026-02"]
    assert S.quarterly["2025-11"]["rural_female"]["agriculture"] == 75.5


def test_flows_and_effects():
    m = S.flows["M"]
    assert len(m.pairs) == 4 and m.pairs[0][2] == [0.3, None, 32.1, 0.2, 0.4, 0.1] and m.row_totals[0][2] == 33.1
    assert S.effects["F"]["lost"]["streak3"] == -0.099 and S.effects["M"]["gained"]["very_young"] == -0.054


def test_categories_and_registry():
    assert c.age_group(np.array([18, 19, 20, 34, 35, 64, 65, 90])).tolist() == [0, 0, 1, 3, 4, 9, 10, 10]
    assert c.SECTORS[c.PUBLIC_ADMIN] == "public_admin"
    assert P.get("life.raise.mean") == 0.089 and P.get("inclusion.account_ownership") == {"metro": 0.89, "rural": 0.89}
    assert P.table().height == 114
```

- [ ] **Step 2: Run it and see it fail**

Run: `PYTHONPATH=src pytest -q tests/test_life_sources.py`
Expected: collection error, `arthasim.life` does not exist.

- [ ] **Step 3: Add the categories, write the data file and registry rows, and implement `load_plfs`**

Transcribe the YAML from the three `docs/sources/` files with a throwaway script (not committed); the tests pin spot values and every column sum. Add a comment above the `life_stage` rows of both district files: "Used only when the build runs without PLFS targets (tests of the old path)."

- [ ] **Step 4: Run the tests and the whole suite**

Run: `PYTHONPATH=src pytest -q tests/test_life_sources.py tests/test_build_1b.py && PYTHONPATH=src pytest -q`
Expected: all pass (the suite's other tests do not yet use the new rows; `test_banking` reads ownership from the registry).

- [ ] **Step 5: Commit**

```bash
git add params/lifecourse params/registry.yaml params/population src/arthasim/build/categories.py src/arthasim/life tests/test_life_sources.py tests/test_build_1b.py docs/sources
git commit -m "feat: PLFS 2025 sources, life-course registry rows and loader"
```

---

### Task 2: Targets

**Files:**
- Create: `src/arthasim/life/targets.py`
- Test: `tests/test_life_targets.py`

**Interfaces:**
- Consumes: `load_plfs`, `Plfs2025`, `group_name`, `PLFS_COLUMNS`, `age_group`, `N_AGE_GROUPS` (Task 1).
- Produces:
  - `AGE_MIN, AGE_MAX = 18, 85`; `N_AGES = 68`; `def age_index(age) -> np.ndarray` (`min(age, 85) - 18`).
  - `MIDPOINTS = [17, 22, 27, 32, 37, 42, 47, 52, 57, 62, 70]` (one per PLFS five-year column).
  - `def gig_share(params, month: dt.date) -> float`: linear in the fiscal-year start (`month.year` if `month.month >= 4` else `month.year - 1`) between the two `life.gig.nonfarm_share` points, clamped outside them. 2025-04 gives `0.026 + 0.041 * 5 / 9`.
  - `def stage_column(src, group: str, column: int, gig: float) -> np.ndarray` (9,): one PLFS column mapped to stages and normalised to sum 1.
  - `def window_month(month: dt.date) -> str`: `"YYYY-MM"` of the same calendar month inside 2025-04 to 2026-03.
  - `def seasonal_rows(src, group: str, month: dt.date, rows: np.ndarray, base15: np.ndarray) -> np.ndarray` (k, 9).
  - `def cell_counts(rows: np.ndarray, cell: np.ndarray, n_cells: int) -> np.ndarray` (n_cells, 9) int64: per cell, the column sums of `rows` integerised (`build.ipf.integerise`) to the cell's size.
  - `class Targets(src: Plfs2025, params: ParamRegistry, kinds: Sequence[str])` with methods `columns(district, sex, month) -> (11, 9)` annual group columns (the month sets the gig share); `annual(district, sex, month) -> (N_AGES, 9)`; `shares(month, district, sex) -> (N_AGES, 9)` (cached by `window_month` and fiscal year); `for_persons(month, district, sex, age) -> (n, 9)`; `start_array(month) -> (n_districts, 2, N_AGES, 9)`; `helper_share(district, sex, age, stage) -> (n,)`; `counts(month, district, sex, age) -> tuple[cell (n,), targets (n_districts * 2 * 11, 9)]` with `cell = (district * 2 + sex) * 11 + age_group(age)`.

**Rules** (from the spec's Targets section):
- `stage_column`: farm = `own_agri + helper_agri`; salaried = `regular`; casual = `casual_public + casual_other`; non-farm self-employment = `own_secondary + own_tertiary + helper_secondary + helper_tertiary`; workers = farm + salaried + casual + non-farm self-employment; non-farm workers = workers − (`own_agri + helper_agri + regular_agri + casual_other_agri`); gig = `min(gig * nonfarm_workers, own_secondary + own_tertiary)`; self_employed = non-farm self-employment − gig; seeking = `unemployed`; studying = `student`; homemaker = `domestic + domestic_collect + disabled + others`; retired = `pensioner`.
- `annual`: at age a, linear interpolation between the two `MIDPOINTS` columns that bracket a (ages ≥ 70 use the 65+ column); studying is 0 from `life.study.max_age`; rows renormalised to 1.
- `seasonal_rows`: with `W15`, `U15` the working and seeking shares of `base15` (the mapped 15+ column) and `c_s = base15[s] / W15` for working stages: `fW = (W15 + (wpr_m − wpr_2025) / 100) / W15`, `fU = (U15 + ((lfpr_m − wpr_m) − (lfpr_2025 − wpr_2025)) / 100) / U15`. Quarterly deviations δ (agriculture, casual, regular: quarter value minus the four-quarter mean, in shares) sit at each quarter's middle month and are interpolated linearly month by month (flat before 2025-05 and after 2026-02). Composition: `c'_farm = c_farm + δ_agri`, `c'_casual = c_casual + δ_casual`, `c'_salaried = c_salaried + δ_regular`; self_employed and gig share `1 − (c'_farm + c'_casual + c'_salaried)` in proportion to `c_self_employed : c_gig`. Each working stage's share is multiplied by `fW * c'_s / c_s` (1 where `c_s == 0`), seeking by `fU`, retired unchanged; studying and homemaker share what is left in proportion to their row values (all to homemaker if both are 0); negatives clipped to 0 and rows renormalised.
- `shares(month)` = `seasonal_rows(src, group, month, annual(...), stage_column(src, group, 11, gig))`.
- `helper_share`: farm `helper_agri / (own_agri + helper_agri)`, self_employed `(helper_secondary + helper_tertiary) / (own_secondary + own_tertiary + helper_secondary + helper_tertiary)`, interpolated by age like `annual`; 0 for other stages.

- [ ] **Step 1: Write the failing test** (`tests/test_life_targets.py`)

```python
import datetime as dt
import numpy as np
from arthasim.build import categories as c
from arthasim.life.sources import load_plfs
from arthasim.life.targets import (Targets, cell_counts, gig_share, seasonal_rows, stage_column, window_month,
                                   age_index)
from helpers import P

S = load_plfs()
T = Targets(S, P, ["metro", "rural"])
APR, JUN = dt.date(2025, 4, 1), dt.date(2025, 6, 1)
WORKING = [c.SALARIED, c.SELF_EMPLOYED, c.GIG, c.FARM, c.CASUAL]


def test_stage_column_rural_female_40_44():
    gig = 0.026 + 0.041 * 5 / 9
    assert abs(gig_share(P, APR) - gig) < 1e-12
    g = gig * 17.7          # non-farm workers: 67.7 workers less 50.0 in agriculture
    want = np.array([0.0, 0.1, 6.1, 8.2 - g, g, 40.4, 13.0, 31.4, 1.0]) / 100.2
    assert np.allclose(stage_column(S, "rural_female", 5, gig), want, atol=1e-12)


def test_interpolation_and_study_cut():
    a = T.annual(1, c.F, APR)
    assert np.allclose(a[age_index(42)], stage_column(S, "rural_female", 5, gig_share(P, APR)))
    assert np.allclose(a[age_index(44)], 0.6 * a[age_index(42)] + 0.4 * a[age_index(47)])
    assert (a[age_index(np.arange(35, 86)), c.STUDYING] == 0).all()
    assert age_index(np.array([18, 85, 90])).tolist() == [0, 67, 67]


def test_seasonal_moves_work_and_seeking_by_the_bulletin():
    base = stage_column(S, "rural_female", 11, gig_share(P, JUN))
    out = seasonal_rows(S, "rural_female", JUN, base[None], base)[0]
    assert abs(out[WORKING].sum() - (base[WORKING].sum() + (33.6 - 36.8) / 100)) < 1e-9
    assert abs(out[c.SEEKING] - (base[c.SEEKING] + ((35.2 - 33.6) - (38.3 - 36.8)) / 100)) < 1e-9
    assert out[c.RETIRED] == base[c.RETIRED] and abs(out.sum() - 1) < 1e-12


def test_every_month_is_valid_and_outside_months_repeat_the_window():
    for m in [dt.date(2025, k, 1) for k in range(4, 13)] + [dt.date(2026, k, 1) for k in range(1, 7)]:
        for d in (0, 1):
            for sex in (c.F, c.M):
                s = T.shares(m, d, sex)
                assert (s >= 0).all() and np.allclose(s.sum(axis=1), 1)
    assert window_month(dt.date(2026, 6, 1)) == "2025-06"
    assert np.array_equal(T.shares(dt.date(2026, 6, 1), 1, c.F), T.shares(dt.date(2025, 6, 1), 1, c.F))


def test_counts_and_helper_share():
    rows = np.array([[0.5, 0.5] + [0.0] * 7] * 3 + [[0.0] * 8 + [1.0]])
    assert cell_counts(rows, np.array([0, 0, 0, 1]), 2).tolist() == [[2, 1] + [0] * 7, [0] * 8 + [1]]
    age = np.array([42, 42, 70])
    cell, tgt = T.counts(APR, 1, c.F, age)
    assert cell.tolist() == [(1 * 2 + c.F) * 11 + 5] * 2 + [(1 * 2 + c.F) * 11 + 10]
    assert tgt.shape == (44, 9) and tgt.sum() == 3
    assert abs(T.helper_share(1, c.F, np.array([42]), c.FARM)[0] - 18.5 / 40.4) < 1e-12
```

- [ ] **Step 2: Run it and see it fail**

Run: `PYTHONPATH=src pytest -q tests/test_life_targets.py`
Expected: import error.

- [ ] **Step 3: Implement `targets.py`** with the signatures and rules above.

- [ ] **Step 4: Run the tests**

Run: `PYTHONPATH=src pytest -q tests/test_life_targets.py`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/arthasim/life/targets.py tests/test_life_targets.py
git commit -m "feat: life-stage targets from PLFS 2025 with the seasonal path"
```

---

### Task 3: Alignment

**Files:**
- Create: `src/arthasim/life/align.py`
- Test: `tests/test_life_align.py`

**Interfaces:**
- Consumes: `build.ipf.ipf`.
- Produces:
  - `def rake(expected: np.ndarray, rows: np.ndarray, cols: np.ndarray, allowed: np.ndarray, floor: float) -> np.ndarray` (9, 9) float: cells where `allowed` get `max(expected, floor * rows[i])` for rows with people (other rows zero), then `ipf` with margins rows (axis 0) and cols (axis 1). Raises `ValueError` if `rows.sum() != cols.sum()`.
  - `def round_flows(flows: np.ndarray, rows: np.ndarray, cols: np.ndarray, allowed: np.ndarray) -> np.ndarray` (9, 9) int64: row sums equal `rows` and column sums equal `cols` exactly; algorithm below.
  - `def choose_movers(prob: np.ndarray, quota: np.ndarray, u: np.ndarray, own: int) -> np.ndarray` (n,) int: destination stage for each of the n people now in stage `own`; `quota[d]` people go to each `d != own`, the rest stay.
  - `def align(stage: np.ndarray, prob: np.ndarray, cell: np.ndarray, targets: np.ndarray, allowed: np.ndarray, u: np.ndarray, floor: float) -> np.ndarray` (n,): new stages; `targets` is (n_cells, 9), `allowed` is (n_cells, 9, 9) bool, `u` is (n, 9) uniform draws.

`round_flows`: start from `floor(flows)`; take the remaining row and column deficits; in order of falling fractional part (ties by flat index), add 1 to an allowed cell whose row and column both still have a deficit; if deficits remain, repeat over allowed cells by falling `flows` value, then over any cell.

`choose_movers`: destinations in index order, skipping `own`; for destination d with quota q, among people not yet assigned, key `log(u[:, d]) / prob[:, d]` (−inf where `prob[:, d] == 0`), take the q largest keys (ties by `u[:, d]`, then position).

`align`: per cell and per current stage, the expected flow matrix is the sum of `prob` rows of the cell's people grouped by current stage; `rake`, `round_flows`, then `choose_movers` per row.

- [ ] **Step 1: Write the failing test** (`tests/test_life_align.py`)

```python
import numpy as np
from hypothesis import given, settings, strategies as st
from arthasim.life.align import align, choose_movers, rake, round_flows

ALL = np.ones((9, 9), dtype=bool)


@st.composite
def cells(draw):
    n = draw(st.integers(5, 60))
    rng = np.random.default_rng(draw(st.integers(0, 10_000)))       # test data only, not under src/
    stage = rng.integers(0, 9, n)
    prob = rng.random((n, 9)) ** 3
    prob /= prob.sum(axis=1, keepdims=True)
    target = np.bincount(rng.integers(0, 9, n), minlength=9)
    return stage, prob, target, rng.random((n, 9))


@settings(max_examples=60, deadline=None)
@given(cells())
def test_align_lands_exactly_on_target(case):
    stage, prob, target, u = case
    new = align(stage, prob, np.zeros(stage.size, dtype=np.int64), target[None], ALL[None], u, 1e-6)
    assert np.bincount(new, minlength=9).tolist() == target.tolist()
    assert np.array_equal(new, align(stage, prob, np.zeros(stage.size, dtype=np.int64), target[None], ALL[None], u, 1e-6))


@settings(max_examples=60, deadline=None)
@given(cells())
def test_round_flows_keeps_both_margins(case):
    stage, prob, target, _ = case
    rows = np.bincount(stage, minlength=9)
    expected = np.zeros((9, 9))
    np.add.at(expected, stage, prob)
    f = rake(expected, rows, target, ALL, 1e-6)
    n = round_flows(f, rows, target, ALL)
    assert n.sum(axis=1).tolist() == rows.tolist() and n.sum(axis=0).tolist() == target.tolist()
    assert (np.abs(n - f) < 2).all()


def test_floor_reaches_a_stage_no_one_would_choose():
    stage = np.zeros(10, dtype=np.int64)
    prob = np.zeros((10, 9)); prob[:, 0] = 1.0
    target = np.zeros(9, dtype=np.int64); target[0], target[1] = 7, 3
    new = align(stage, prob, np.zeros(10, dtype=np.int64), target[None], ALL[None], np.linspace(0.05, 0.95, 90).reshape(10, 9), 1e-6)
    assert np.bincount(new, minlength=9)[:2].tolist() == [7, 3]


def test_choose_movers_prefers_likely_movers():
    prob = np.zeros((1000, 9)); prob[:, 0] = 0.9; prob[:500, 1] = 0.1; prob[500:, 1] = 0.001
    u = (np.arange(1000) * 0.618034) % 1.0
    u = np.repeat(u[:, None], 9, axis=1)
    dest = choose_movers(prob, np.array([0, 100] + [0] * 7), u, own=0)
    assert (dest == 1).sum() == 100 and (dest[:500] == 1).sum() > 90
```

- [ ] **Step 2: Run it and see it fail**

Run: `PYTHONPATH=src pytest -q tests/test_life_align.py`
Expected: import error.

- [ ] **Step 3: Implement `align.py`** with the signatures and algorithms above.

- [ ] **Step 4: Run the tests**

Run: `PYTHONPATH=src pytest -q tests/test_life_align.py`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/arthasim/life/align.py tests/test_life_align.py
git commit -m "feat: exact alignment by raking, rounding and weighted choice"
```

---

### Task 4: Synthesis from the start month's targets

**Files:**
- Modify: `src/arthasim/build/population.py`, `src/arthasim/build/pipeline.py` (`fit_report` only)
- Test: `tests/test_population_targets.py`

**Interfaces:**
- Consumes: `Targets` (Task 2), `align`, `cell_counts` (Tasks 2–3).
- Produces:
  - `synthesise_persons(districts, priors, n, seed, stage_shares: np.ndarray | None = None) -> Persons`. With `stage_shares` (shape `(n_districts, 2, N_AGES, 9)`, from `Targets.start_array`): the IPF seed is `age_education` broadcast over stage (no age-by-stage prior); the stage margin is `((0, 1, 3), age_band[b] * sex[x] * band_share[d, x, b, s])`, where `band_share` is the mean of `stage_shares` over the band's single ages, renormalised; ages within a band are drawn conditional on stage, `P(age) ∝ stage_shares[d, sex, age, stage]`, with keyed stream `pop.age_given_stage`; then each (district, sex, age group) cell is aligned exactly to `cell_counts` of the people's share rows, with `prob = share rows`, all moves allowed, floor `life.rake.floor` (passed as 1e-6), and draws from stream `pop.align`. `age_band` is recomputed from the final ages. Without `stage_shares`, behaviour is unchanged.
  - `fit_report(districts, persons, stage_target: np.ndarray | None = None) -> dict`: with `stage_target` (shape `(n_districts, 2, 9)`, the mean share rows of each district's women and men), the `life_stage_F` and `life_stage_M` errors compare with it instead of the YAML rows.

- [ ] **Step 1: Write the failing test** (`tests/test_population_targets.py`)

```python
import datetime as dt
import numpy as np
from arthasim.build import categories as c
from arthasim.build.population import synthesise_persons
from arthasim.life.sources import load_plfs
from arthasim.life.targets import Targets
from helpers import D, PR, P, l1

T = Targets(load_plfs(), P, [d.kind for d in D])
APR = dt.date(2025, 4, 1)
p = synthesise_persons(D, PR, 20_000, seed=7, stage_shares=T.start_array(APR))


def test_every_cell_lands_on_the_start_targets():
    for d in (0, 1):
        for sex in (c.F, c.M):
            m = (p.district == d) & (p.sex == sex)
            cell, want = T.counts(APR, d, sex, p.age[m])
            got = np.zeros_like(want)
            np.add.at(got, (cell, p.life_stage[m]), 1)
            assert np.array_equal(got, want)


def test_other_margins_and_age_profile():
    for d, m in enumerate(D):
        s = p.district == d
        assert l1(np.bincount(p.age_band[s], minlength=5), m.age_band) < 0.02
        assert l1(np.bincount(p.education[s], minlength=5), m.education) < 0.02
    young, older = p.age <= 20, (p.age >= 24) & (p.age <= 26)
    assert (p.life_stage[young] == c.STUDYING).mean() > 3 * (p.life_stage[older] == c.STUDYING).mean()
    assert not ((p.life_stage == c.STUDYING) & (p.age >= 35)).any()
    assert np.array_equal(p.age_band, np.searchsorted([25, 35, 45, 60], p.age, side="right"))


def test_deterministic():
    again = synthesise_persons(D, PR, 20_000, seed=7, stage_shares=T.start_array(APR))
    assert np.array_equal(again.life_stage, p.life_stage) and np.array_equal(again.age, p.age)
```

- [ ] **Step 2: Run it and see it fail**

Run: `PYTHONPATH=src pytest -q tests/test_population_targets.py`
Expected: `TypeError` (no `stage_shares` parameter).

- [ ] **Step 3: Implement the targets path in `synthesise_persons` and the `stage_target` option in `fit_report`.**

- [ ] **Step 4: Run the new tests and the old population tests**

Run: `PYTHONPATH=src pytest -q tests/test_population_targets.py tests/test_population.py`
Expected: all pass (the old path is untouched).

- [ ] **Step 5: Commit**

```bash
git add src/arthasim/build/population.py src/arthasim/build/pipeline.py tests/test_population_targets.py
git commit -m "feat: synthesise persons on the start month's PLFS targets"
```

---

### Task 5: Transition probabilities

**Files:**
- Create: `src/arthasim/life/rates.py`
- Test: `tests/test_life_rates.py`

**Interfaces:**
- Consumes: `Plfs2025` (Task 1), `Targets.columns` (Task 2).
- Produces:
  - `FLOW_STATES = ("own", "helper", "regular", "casual", "unemployed", "nlf")`.
  - `def quarterly_flows(src, sex: int, negligible_pct: float) -> np.ndarray` (6, 6): cells summed over the four pairs, `null` counted as `negligible_pct`, divided by the summed row totals; each row's residual (row total less its six cells) added to the diagonal.
  - `def monthly_flows(q: np.ndarray) -> np.ndarray` (6, 6): exit `e = 1 − q[i, i]` becomes `1 − (1 − e) ** (1/3)`, split across destinations in the quarterly proportions.
  - `def study_exit(columns: np.ndarray, age: np.ndarray) -> tuple[np.ndarray, np.ndarray]`: monthly hazard (n,) and destination weights (n, 9). For age a between midpoints `MIDPOINTS[g]` and `MIDPOINTS[g + 1]`: `Δ = columns[g + 1] − columns[g]`; hazard `max(0, −Δ[studying]) / ((MIDPOINTS[g + 1] − MIDPOINTS[g]) * 12) / share_at_a[studying]` (0 when that share is 0; at most 0.95); destinations ∝ `max(0, Δ[s])` for s ≠ studying (all to seeking if none rise); hazard 0 from age 70.
  - `@dataclass class RateInputs`: `stage, helper, sex, age, education, has_child, months_in_stage, last_stage, months_since_left` (n,); `shares` (n, 9), this month's targets at each person's age; `study_hazard` (n,), `study_dest` (n, 9); `firm_shock` (n,), 1 for non-salaried; `superannuation` (n,) bool.
  - `def effect_features(age, education, has_child, months_in_stage) -> np.ndarray` (n, 6): `very_young` (age < 21), `young` (21–30), `graduate` (education ≥ 3), `has_child`, `streak2` (months 4–6), `streak3` (months ≥ 7).
  - `def person_probs(x: RateInputs, src, params) -> np.ndarray` (n, 9), rows sum to 1.

**`person_probs` rules**, in this order (spec, Transition probabilities):
1. Flow row: salaried → regular, casual → casual, farm, self_employed and gig → helper if `helper` else own, seeking → unemployed, studying, homemaker and retired → nlf. Monthly flows by sex.
2. Effects: for employed rows, `L = M[row, unemployed] + M[row, nlf]`; `L' = L + (features @ lost[sex]) / 3 − mean of that over the people with the same (sex, row)`, clipped to `life.prob_bounds`; both columns scaled by `L'/L`. For unemployed and nlf rows the same with `G = M[row, own..casual]` and `gained[sex]`. Only `very_young, young, graduate, has_child, streak2, streak3` are used.
3. Expand columns to stages: own and helper → farm, self_employed and gig in proportion to the person's `shares` of those three; regular → salaried; casual → casual; unemployed → seeking; nlf → studying, homemaker and retired in proportion to `shares`. A destination in the person's own block (own or helper for workers in self-employment, nlf for studying, homemaker and retired) adds to staying.
4. Studying rows are replaced: exit `study_hazard`, destinations `study_dest`.
5. Moves inside blocks, taken from staying: farm → self_employed and gig `life.within.farm_nonfarm` in total (split by `shares`); self_employed and gig → farm `life.within.farm_nonfarm`; self_employed ↔ gig `life.within.self_gig`; homemaker ↔ retired `life.within.homemaker_retired`.
6. Coming back: if `0 <= last_stage != stage` and `months_since_left <= life.return.window_months`, the probability of `last_stage` × `life.return.weight`.
7. Salaried rows: every move out × `firm_shock`.
8. Superannuation: where `superannuation`, the probability of retired is at least `life.retire.superannuation_prob`.
9. Studying is 0 as a destination from `life.study.max_age`.
10. If the moves out sum to more than 0.95, scale them to 0.95; staying is 1 minus the moves out.

- [ ] **Step 1: Write the failing test** (`tests/test_life_rates.py`)

```python
import numpy as np
from arthasim.build import categories as c
from arthasim.life.rates import (RateInputs, effect_features, monthly_flows, person_probs, quarterly_flows,
                                 study_exit)
from arthasim.life.sources import load_plfs
from arthasim.life.targets import Targets, age_index
from helpers import P
import datetime as dt

S = load_plfs()
T = Targets(S, P, ["metro", "rural"])


def test_flows():
    q = quarterly_flows(S, c.M, 0.025)
    assert np.allclose(q.sum(axis=1), 1) and abs(q[2, 4] - (0.4 + 0.3 + 0.3 + 0.3) / (33.1 + 32.9 + 33.8 + 34.0)) < 1e-12
    m = monthly_flows(q)
    assert np.allclose(m.sum(axis=1), 1) and abs((1 - m[2, 2]) - (1 - (q[2, 2]) ** (1 / 3))) < 1e-12


def test_study_exit_urban_women_mostly_to_homemaker():
    hazard, dest = study_exit(T.columns(0, c.F, dt.date(2025, 4, 1)), np.array([23]))
    assert hazard[0] > 0
    assert dest[0, c.HOMEMAKER] / dest[0].sum() > 0.55


def inputs(n, stage, **kw):
    base = dict(stage=np.full(n, stage), helper=np.zeros(n, bool), sex=np.full(n, c.F), age=np.full(n, 40),
                education=np.full(n, 2), has_child=np.zeros(n, bool), months_in_stage=np.full(n, 24),
                last_stage=np.full(n, -1), months_since_left=np.full(n, 9999),
                shares=np.repeat(T.shares(dt.date(2025, 4, 1), 0, c.F)[age_index(40)][None], n, axis=0),
                study_hazard=np.zeros(n), study_dest=np.zeros((n, 9)), firm_shock=np.ones(n),
                superannuation=np.zeros(n, bool))
    base.update(kw)
    return RateInputs(**base)


def test_rows_sum_to_one_and_centring_keeps_the_published_mean():
    n = 400
    months = np.where(np.arange(n) < 40, 2, 30)
    p = person_probs(inputs(n, c.SALARIED, months_in_stage=months), S, P)
    assert np.allclose(p.sum(axis=1), 1) and (p >= 0).all()
    q = monthly_flows(quarterly_flows(S, c.F, 0.025))
    lost = p[:, c.SEEKING] + p[:, c.HOMEMAKER] + p[:, c.STUDYING] + p[:, c.RETIRED]
    assert abs(lost.mean() - (q[2, 4] + q[2, 5])) < 2e-3
    assert lost[:40].mean() > lost[40:].mean()


def test_return_weight_superannuation_and_study_cut():
    base = person_probs(inputs(2, c.HOMEMAKER), S, P)
    back = person_probs(inputs(2, c.HOMEMAKER, last_stage=np.full(2, c.FARM), months_since_left=np.full(2, 3)), S, P)
    assert abs(back[0, c.FARM] - 5 * base[0, c.FARM]) < 1e-12
    old = person_probs(inputs(1, c.SALARIED, age=np.array([58]), superannuation=np.array([True])), S, P)
    assert old[0, c.RETIRED] >= 0.5
    assert person_probs(inputs(1, c.SEEKING, age=np.array([36])), S, P)[0, c.STUDYING] == 0


def test_effect_features():
    f = effect_features(np.array([19, 25, 40]), np.array([3, 1, 4]), np.array([True, False, False]), np.array([1, 5, 9]))
    assert f.tolist() == [[1, 0, 1, 1, 0, 0], [0, 1, 0, 0, 1, 0], [0, 0, 1, 0, 0, 1]]
```

- [ ] **Step 2: Run it and see it fail**

Run: `PYTHONPATH=src pytest -q tests/test_life_rates.py`
Expected: import error.

- [ ] **Step 3: Implement `rates.py`.**

- [ ] **Step 4: Run the tests**

Run: `PYTHONPATH=src pytest -q tests/test_life_rates.py`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/arthasim/life/rates.py tests/test_life_rates.py
git commit -m "feat: monthly transition probabilities from the PLFS urban panel"
```

---

### Task 6: Helpers, life state and the population build

**Files:**
- Create: `src/arthasim/life/helpers.py`, `src/arthasim/life/state.py`
- Modify: `src/arthasim/build/earnings.py`, `src/arthasim/build/attributes.py`, `src/arthasim/build/banking.py`, `src/arthasim/build/pipeline.py`, `src/arthasim/build/world.py`, `tests/test_pipeline.py` (`PERSON_COLUMNS`)
- Test: `tests/test_life_build.py`

**Interfaces:**
- Consumes: Tasks 1–5.
- Produces:
  - `earnings.py`: `def income_for(stage, education, age, is_metro, sector, z, params) -> np.ndarray` int64: earning stages `max(100, rint(starting_pay(...) * stage_multiplier))`, retired `max(100, rint(pension_ratio * starting_pay(edu, exp, metro, OTHER_SERVICES, 0)))`, others 0; experience `max(0, age - start_age_by_education[edu])`. `attach_attributes` uses it; its output stays bit-identical (`tests/test_attributes.py` unchanged).
  - `attributes.py`: `def draw_sector(stage, is_metro, u, params) -> np.ndarray` int64 (farm 0, other earning stages from `org.sector_shares.<kind>[1:]`, else −1), used by `attach_attributes` (bit-identical).
  - `banking.py`: `def pick_banks(u, is_metro, params, n_banks) -> np.ndarray` int64, used by `assign_banking` (bit-identical).
  - `helpers.py`: `def assign_helpers(stage, household, candidate) -> np.ndarray` bool: helper iff `candidate`, stage in (farm, self_employed), and the household has at least one member in the same stage who is not a candidate. `def orphaned(stage, household, helper) -> np.ndarray` bool: helpers whose household has no non-helper member in their stage.
  - `state.py`: `@dataclass class LifeState: birth_month (int8, 1–12); months_in_stage (int32); last_stage (int8, −1 none); months_since_left (int32, 9999 none); last_income (int64); last_sector (int8, −1 none); helper (bool); raise_month (int8 per employer, 1–12); targets: Targets; next_event_id: int = 0`. `def initial_life_state(persons, households, attributes, orgs, targets, params, seed, start) -> LifeState`: birth month `1 + floor(12u)` (stream `life.birth_month`); raise month 4 if `u < life.raise.april_share` else one of the other eleven, equally likely (stream `life.raise_month`); months in stage geometric with the monthly base exit rate of the person's flow row and sex (`1 − monthly_flows(quarterly_flows(...))[row, row]`, Task 5; stream `life.months_in_stage`), capped at `(age − 15) * 12` for studying and `(age − 18) * 12 + 1` otherwise, at least 1.
  - `WorldState` gains `life: Any = None` and `account_opened_on: Any = None` (per account, `datetime64[D]`).
  - `pipeline.py`: the population build uses `Targets`, passes `stage_shares=targets.start_array(config.start)` and `stage_target` to `fit_report`, assigns helpers right after households (candidate if keyed `u < targets.helper_share(...)`, stream `life.helper`), zeroes helpers' income right after `attach_attributes`, and fills `life` and `account_opened_on`. `def account_frames(state, config) -> dict[str, pl.DataFrame]` builds `accounts` (with `opened_on` from `account_opened_on`) and `instruments` from live state; `population_frames` uses it. The `persons` frame drops `age, life_stage, sector, employer_entity_id, monthly_income_paise, has_account, primary_bank` and gains `birth_month` after `sex`.

- [ ] **Step 1: Write the failing test** (`tests/test_life_build.py`) and update `PERSON_COLUMNS` in `tests/test_pipeline.py` to `["entity_id", "household_id", "district", "locality", "sex", "birth_month", "education", "has_pan", "pan_like", "uid_token", "mobile_token"]`.

```python
import numpy as np
from arthasim.build import categories as c
from arthasim.life.helpers import assign_helpers, orphaned
from world_fixture import small_world


def test_helper_rule():
    stage = np.array([c.FARM, c.FARM, c.FARM, c.SELF_EMPLOYED, c.FARM, c.FARM])
    hh = np.array([0, 0, 1, 1, 2, 2])
    cand = np.array([True, False, True, False, True, True])
    assert assign_helpers(stage, hh, cand).tolist() == [True, False, False, False, False, False]
    assert orphaned(stage, hh, np.array([True, False, True, False, True, False])).tolist() == [False, False, True, False, False, False]


def test_build_state():
    s = small_world().state
    b, life = s.population, s.life
    stage, inc = b.persons.life_stage, b.attributes.monthly_income_paise
    assert life.helper.shape == stage.shape and (inc[life.helper] == 0).all()
    assert np.isin(stage[life.helper], [c.FARM, c.SELF_EMPLOYED]).all()
    assert not orphaned(stage, b.households.household_of_person, life.helper).any()
    own = np.isin(stage, [c.FARM, c.SELF_EMPLOYED]) & ~life.helper
    assert (inc[own] > 0).all() and life.helper.any()
    assert life.birth_month.min() >= 1 and life.birth_month.max() <= 12
    assert 0.45 < (life.raise_month == 4).mean() < 0.67 and life.raise_month.size == len(s.employer_ids)
    assert (life.months_in_stage >= 1).all() and (life.last_stage == -1).all()
    assert s.account_opened_on.shape == (len(s.book),)
    assert abs(b.banking.person_has_account[stage != c.SALARIED].mean() - 0.89) < 0.03
    assert all(v["life_stage_F"] < 0.01 and v["life_stage_M"] < 0.01 for v in b.report["l1"].values())
```

- [ ] **Step 2: Run it and see it fail**

Run: `PYTHONPATH=src pytest -q tests/test_life_build.py tests/test_pipeline.py`
Expected: import error for `arthasim.life.helpers`, and the persons columns differ.

- [ ] **Step 3: Implement the extractions (`income_for`, `draw_sector`, `pick_banks`), `helpers.py`, `state.py`, and the pipeline and `WorldState` changes.**

- [ ] **Step 4: Run the whole suite**

Run: `PYTHONPATH=src pytest -q`
Expected: all pass. Tests that counted people by life stage or income in `small_world` may need their expected values re-derived; any such edit goes in the ledger with its reason.

- [ ] **Step 5: Commit**

```bash
git add src/arthasim tests
git commit -m "feat: population build on PLFS targets with unpaid family helpers and life state"
```

---

### Task 7: Opening accounts during a run

**Files:**
- Create: `src/arthasim/life/accounts.py`
- Modify: `src/arthasim/ledger/instruments.py`
- Test: `tests/test_life_accounts.py`

**Interfaces:**
- Consumes: `pick_banks` (Task 6), `WorldState.account_opened_on` (Task 6).
- Produces:
  - `InstrumentBook.extend(type: int, holders, issuers, openings) -> np.ndarray`: after `freeze`, appends to `type`, `holder`, `issuer`, `opening` and `balance` (balance starts at the opening) and returns the new ids; before `freeze` it raises `RuntimeError`.
  - `def open_accounts(state, params, persons: np.ndarray, banks: np.ndarray, day: dt.date, seed: int) -> np.ndarray`: one zero-balance deposit each at `bank_ids[banks]`. Extends `posted_total` (0), `deposit_for_cash` (−1), `vault_for_deposit` (the bank's vault), `bank_of_account` (the bank), `withdraw_rail` (ATM), `account_opened_on` (`day`); then links `deposit_for_cash[person_cash] = new id`, sets `person_deposit`, `banking.person_has_account`, `banking.person_primary_bank` (the same array as `state.person_bank`), `person_has_card` (keyed `u < inclusion.debit_card_share`, stream `life.card`), `person_upi` (the same array as `state.person_digital`: has mobile and `digital_literacy > attr.digital.upi_threshold`), `person_basic_account` (income below `inclusion.basic_account_income_paise`), and `withdraw_rail[person_cash]` (ATM with a card, else AePS). Raises `ValueError` if any person already has an account.

- [ ] **Step 1: Write the failing test** (`tests/test_life_accounts.py`)

```python
import datetime as dt
import numpy as np
import polars as pl
import pytest
from arthasim import Config, World
from arthasim.engine.intents import Rail
from arthasim.ledger.instruments import InstrumentBook, InstrumentType as T
from arthasim.ledger.invariants import check_day
from arthasim.life.accounts import open_accounts


def test_extend_after_freeze_only():
    b = InstrumentBook()
    b.add(T.CASH, 1, 9, 50)
    with pytest.raises(RuntimeError):
        b.extend(T.DEPOSIT, [1], [2], [0])
    b.freeze()
    ids = b.extend(T.DEPOSIT, [1, 3], [2, 2], [0, 0])
    assert ids.tolist() == [1, 2] and b.type.tolist() == [2, 1, 1] and b.balance.tolist() == [50, 0, 0]


def test_open_accounts_keeps_the_ledger_whole(tmp_path):
    w = World.build(Config.tier("S", persons=3_000, out_dir=str(tmp_path)), seed=7)
    s = w.state
    who = np.flatnonzero(s.person_deposit < 0)[:20]
    n0 = len(s.book)
    ids = open_accounts(s, w.params, who, np.zeros(who.size, dtype=np.int64), dt.date(2025, 5, 1), w.seed)
    assert ids.tolist() == list(range(n0, n0 + who.size)) and (s.book.balance[ids] == 0).all()
    assert (s.person_deposit[who] == ids).all() and (s.deposit_for_cash[s.person_cash[who]] == ids).all()
    assert s.population.banking.person_has_account[who].all() and (s.person_bank[who] == 0).all()
    card = s.population.banking.person_has_card[who]
    assert (s.withdraw_rail[s.person_cash[who]] == np.where(card, Rail.ATM, Rail.AEPS)).all()
    assert all(len(a) == len(s.book) for a in (s.posted_total, s.bank_of_account, s.vault_for_deposit,
                                                s.withdraw_rail, s.account_opened_on))
    empty_j = pl.DataFrame(schema={"journal_id": pl.Int64, "ts": pl.Int64, "kind": pl.Int64, "flow_type": pl.Int64,
                                   "payment_id": pl.Int64})
    empty_p = pl.DataFrame(schema={"journal_id": pl.Int64, "line_no": pl.Int64, "account_id": pl.Int64,
                                   "delta_paise": pl.Int64, "balance_after_paise": pl.Int64})
    check_day(s.book, empty_j, empty_p, s.posted_total, s.bank_ids.tolist(), s.equity, s.currency_issued, s.sector)
    with pytest.raises(ValueError):
        open_accounts(s, w.params, who[:1], np.zeros(1, dtype=np.int64), dt.date(2025, 5, 1), w.seed)
```

- [ ] **Step 2: Run it and see it fail**

Run: `PYTHONPATH=src pytest -q tests/test_life_accounts.py`
Expected: `AttributeError: 'InstrumentBook' object has no attribute 'extend'`.

- [ ] **Step 3: Implement `InstrumentBook.extend` and `open_accounts`.**

- [ ] **Step 4: Run the tests and the ledger tests**

Run: `PYTHONPATH=src pytest -q tests/test_life_accounts.py tests/test_ledger.py tests/test_invariants.py`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/arthasim/ledger/instruments.py src/arthasim/life/accounts.py tests/test_life_accounts.py
git commit -m "feat: grow the account book and open accounts mid-run"
```

---

### Task 8: Jobs and pay

**Files:**
- Create: `src/arthasim/life/jobs.py`
- Test: `tests/test_life_jobs.py`

**Interfaces:**
- Consumes: `income_for`, `draw_sector` (Task 6).
- Produces:
  - `def choose_employers(state, persons, sector, u) -> np.ndarray` int64: among employers in the person's (district, sector), weighted by `max(0, capacity − staff) + 1`; if the group has none, among all employers in the district weighted the same way; `ValueError` if the district has none.
  - `def entry_income(state, params, persons, stage, sector, z) -> np.ndarray` int64: `income_for` at each person's current age (metro from their district kind).
  - `def switch_pay(old, z, params) -> np.ndarray` int64: `max(100, rint(old * exp(log(median) + sigma * z)))` from `life.switch.pay_factor`.
  - `def raise_due(state, month: dt.date) -> np.ndarray`: salaried persons whose employer's `raise_month == month.month`.
  - `def raised_pay(old, z, params) -> np.ndarray` int64: `rint(old * (1 + max(0, mean + sd * z)))` from `life.raise.mean`, `life.raise.sd`.
  - `def recompute_payroll(state) -> None`: `employer_payroll` = sum of `person_salary` by employer.
  - `def firm_shock(state, seed, key_day) -> np.ndarray` (per employer): `lognormal(median=exp(−σ²/2), sigma=σ)` with `σ = life.layoff.employer_shock_sigma`, stream `life.firm_shock`.

- [ ] **Step 1: Write the failing test** (`tests/test_life_jobs.py`)

```python
import datetime as dt
import numpy as np
from arthasim.build import categories as c
from arthasim.life.jobs import (choose_employers, entry_income, firm_shock, raise_due, raised_pay,
                                recompute_payroll, switch_pay)
from helpers import P
from world_fixture import small_world


def test_choose_employers_stays_in_district_and_sector():
    s = small_world().state
    o = s.population.orgs
    who = np.flatnonzero(s.population.persons.life_stage == c.SEEKING)[:200]
    sector = np.full(who.size, 3)
    e = choose_employers(s, who, sector, np.linspace(0, 0.999, who.size))
    assert (o.employer_district[e] == s.population.persons.district[who]).all()
    has_group = [((o.employer_district == d) & (o.employer_sector == 3)).any() for d in s.population.persons.district[who]]
    assert (o.employer_sector[e][has_group] == 3).all()


def test_pay_rules():
    assert switch_pay(np.array([1_000_000]), np.array([0.0]), P).tolist() == [1_150_000]
    assert raised_pay(np.array([1_000_000]), np.array([0.0]), P).tolist() == [1_089_000]
    assert raised_pay(np.array([1_000_000]), np.array([-5.0]), P).tolist() == [1_000_000]
    s = small_world().state
    who = np.flatnonzero(s.population.persons.life_stage == c.SEEKING)[:5]
    pay = entry_income(s, P, who, np.full(5, c.SALARIED), np.full(5, 3), np.zeros(5))
    assert (pay > 0).all()


def test_raise_due_and_payroll():
    s = small_world().state
    due = raise_due(s, dt.date(2025, 4, 1))
    assert (s.life.raise_month[s.person_employer[due]] == 4).all() and (s.person_salary[due] > 0).all()
    before = s.employer_payroll.copy()
    recompute_payroll(s)
    assert np.array_equal(before, s.employer_payroll)
    shock = firm_shock(s, 7, dt.date(2025, 5, 1).toordinal())
    assert shock.shape == (len(s.employer_ids),) and 0.8 < shock.mean() < 1.2
```

- [ ] **Step 2: Run it and see it fail**

Run: `PYTHONPATH=src pytest -q tests/test_life_jobs.py`
Expected: import error.

- [ ] **Step 3: Implement `jobs.py`.**

- [ ] **Step 4: Run the tests**

Run: `PYTHONPATH=src pytest -q tests/test_life_jobs.py`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/arthasim/life/jobs.py tests/test_life_jobs.py
git commit -m "feat: employer choice, entry pay, switches and raises"
```

---

### Task 9: The LifeCourse module, events and world integration

**Files:**
- Create: `src/arthasim/life/events.py`, `src/arthasim/modules/lifecourse.py`
- Modify: `src/arthasim/modules/base.py`, `src/arthasim/world.py`, `src/arthasim/store/parquet.py`, `tests/test_money_flows.py` (module list), `tests/test_pipeline.py` (table set)
- Test: `tests/test_lifecourse.py`

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `events.py`: `EVENT_NAMES = ("HIRED", "LAID_OFF", "LEFT_JOB", "RETIRED", "JOB_SWITCH", "STARTED_WORK", "STOPPED_WORK", "CHANGED_WORK", "STARTED_STUDY", "LEFT_STUDY", "STARTED_SEEKING", "STOPPED_SEEKING", "LEFT_RETIREMENT", "RAISE", "ACCOUNT_OPENED", "BECAME_OWN_ACCOUNT", "BECAME_HELPER")`; `STAGE_EVENT` (9, 9) of event names, `None` on the diagonal, from the table below; `class EventLog` with `add(entity, event, *, from_stage=None, to_stage=None, employer_from=None, employer_to=None, income_before, income_after, account_id=None)` (arrays) and `frame(date: dt.date, first_id: int) -> pl.DataFrame`; `def state_frame(state, month: str) -> pl.DataFrame`. Column schemas as in the spec's Tables section, stages and banks as names, `month` as `"YYYY-MM"`, `date` as `pl.Date`.
  - `BehaviourModule.tables(self) -> dict[str, pl.DataFrame]` (default `{}`): frames produced since the last call; `World._day` stores them under the day's month after `run_day`.
  - `class LifeCourse(BehaviourModule)`, `name = "lifecourse"`, monthly hook only.
  - `FACT_TABLES` gains `"life_events"` and `"entity_state_monthly"`; `World._flush` rewrites `accounts` and `instruments` from `account_frames` before hashing (population builds only); the population module list starts with `LifeCourse()`.

Stage-change events (row: from, column: to; W = self_employed, gig, farm, casual):

| from \ to | studying | seeking | salaried | W | homemaker | retired |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| studying | — | LEFT_STUDY | HIRED | STARTED_WORK | LEFT_STUDY | RETIRED |
| seeking | STARTED_STUDY | — | HIRED | STARTED_WORK | STOPPED_SEEKING | RETIRED |
| salaried | LEFT_JOB | LAID_OFF | — | CHANGED_WORK | LEFT_JOB | RETIRED |
| W | STOPPED_WORK | STOPPED_WORK | HIRED | CHANGED_WORK (another W) | STOPPED_WORK | RETIRED |
| homemaker | STARTED_STUDY | STARTED_SEEKING | HIRED | STARTED_WORK | — | RETIRED |
| retired | STARTED_STUDY | STARTED_SEEKING | HIRED | STARTED_WORK | LEFT_RETIREMENT | — |

**`LifeCourse.monthly(world, month)`**, with `key = month.replace(day=1).toordinal()`:
- On the world's first simulated day: raises due (`raise_due`, `raised_pay` with stream `life.raise`), events, `state_frame` rows. Nothing else.
- From the second month on, at the start of each month, in this order:
  1. Ageing: `birth_month == month.month` → age + 1; `age_band` recomputed.
  2. Targets: `Targets.counts` per (district, sex); share rows by person.
  3. `RateInputs` (`shares` from `Targets.for_persons`; `study_hazard` and `study_dest` from `study_exit(targets.columns(district, sex, month), age)`; `has_child` = household dependants > 0; `firm_shock` from `firm_shock` at each salaried person's employer; `superannuation` = salaried, birthday this month, new age equals the superannuation age for the employer's sector), `person_probs`.
  4. `align` with `allowed` all True except the studying column in cells whose age group starts at or above `life.study.max_age`; draws `u` from stream `life.align` (entity person, day `key`, index = destination).
  5. Movers: `last_stage`, `months_since_left = 0`, `last_income`, `last_sector` (if they leave salaried). Leaving salaried: employer −1, salary 0. Entering: sector (farm 0; salaried and other work: `last_sector` if within the return window, else `draw_sector`, stream `life.sector`), employer (`choose_employers`, stream `life.employer`), income (`last_income` when returning within the window to `last_stage`, else `entry_income`, stream `life.pay`), helper (`assign_helpers` with candidates from `helper_share`, stream `life.helper`; helpers get income 0), pension for retired, 0 for non-earning stages. Unbanked people entering salaried open an account (`open_accounts`; bank: employer's bank if `u < inclusion.salary_account_at_employer_bank`, else `pick_banks`, stream `life.bank`).
  6. Helpers whose household has lost its last own-account member in their stage (`orphaned`) become own-account (`BECAME_OWN_ACCOUNT`, `entry_income`); then helper ↔ own-account flips for stayers at `life.within.helper_to_own` and `life.within.own_to_helper` (an own-account person becomes a helper only if the household keeps another own-account member in the stage), stream `life.flip`.
  7. Job switches for salaried stayers: probability `life.switch.monthly_prob`, times `life.switch.young.multiplier` under `life.switch.young.age`; new employer in the same sector with probability `life.switch.same_sector_prob`, else `draw_sector`; `switch_pay` (streams `life.switch`, `life.switch_sector`, `life.switch_employer`, `life.switch_pay`).
  8. Voluntary account opening for the unbanked at `life.account.open_monthly_prob` (stream `life.open`), bank by `pick_banks`.
  9. `recompute_payroll`; raises due; `months_in_stage` = 1 for movers, + 1 for stayers; `months_since_left` + 1 for everyone else with a `last_stage`.
  10. Events (one per stage change from `STAGE_EVENT`; plus `JOB_SWITCH`, `RAISE`, `ACCOUNT_OPENED`, `BECAME_OWN_ACCOUNT`, `BECAME_HELPER`), dated the first of the month, ids from `life.next_event_id`; `state_frame`.

- [ ] **Step 1: Write the failing test** (`tests/test_lifecourse.py`)

```python
import datetime as dt
import numpy as np
import polars as pl
from arthasim import Config, World
from arthasim.build import categories as c
from arthasim.life.helpers import orphaned


def cfg(tmp_path, **kw):
    return Config.tier("S", **{"persons": 5_000, "out_dir": str(tmp_path), **kw})


def test_three_months_on_target_with_consistent_events(tmp_path):
    world = World.build(cfg(tmp_path), seed=7)
    assert [m.name for m in world.modules][0] == "lifecourse"
    run = world.run(until="2025-06-30")
    esm = run.table("entity_state_monthly").collect()
    assert esm["month"].unique().sort().to_list() == ["2025-04", "2025-05", "2025-06"]
    s, t = world.state, world.state.life.targets
    p = s.population.persons
    for month in ("2025-05", "2025-06"):
        m = esm.filter(pl.col("month") == month).sort("entity_id")
        stage = np.array([c.LIFE_STAGE.index(x) for x in m["life_stage"].to_list()])
        age = m["age"].to_numpy()
        for d in (0, 1):
            for sex in (c.F, c.M):
                sel = (p.district == d) & (p.sex == sex)
                cell, want = t.counts(dt.date.fromisoformat(month + "-01"), d, sex, age[sel])
                got = np.zeros_like(want)
                np.add.at(got, (cell, stage[sel]), 1)
                assert np.array_equal(got, want), (month, d, sex)
    ev = run.table("life_events").collect()
    changes = (esm.sort(["entity_id", "month"])
               .with_columns(pl.col("life_stage").shift(1).over("entity_id").alias("prev"))
               .filter(pl.col("prev").is_not_null() & (pl.col("prev") != pl.col("life_stage"))))
    stage_events = ev.filter(pl.col("from_stage").is_not_null())
    assert stage_events.height == changes.height > 0
    assert {"HIRED", "LAID_OFF", "RAISE"} <= set(ev["event"].unique())
    sal = esm.filter((pl.col("month") == "2025-06") & (pl.col("life_stage") == "salaried"))
    assert sal["employer_entity_id"].null_count() == 0 and sal["has_account"].all()
    payroll = np.zeros(len(s.employer_ids), dtype=np.int64)
    np.add.at(payroll, s.person_employer[s.person_employer >= 0], s.person_salary[s.person_employer >= 0])
    assert np.array_equal(payroll, s.employer_payroll)
    live, inc, helper = p.life_stage, s.population.attributes.monthly_income_paise, s.life.helper
    assert not orphaned(live, s.population.households.household_of_person, helper).any()
    assert (inc[helper] == 0).all() and (inc[np.isin(live, [c.FARM, c.SELF_EMPLOYED]) & ~helper] > 0).all()
    assert ((s.person_employer >= 0) == (live == c.SALARIED)).all()


def test_hire_without_account_gets_paid_into_the_new_account(tmp_path):
    run = World.build(cfg(tmp_path), seed=7).run(until="2025-06-30")
    ev = run.table("life_events").collect()
    opened = ev.filter(pl.col("event") == "ACCOUNT_OPENED").select("entity_id", "account_id", "date")
    hired = ev.filter(pl.col("event") == "HIRED").select("entity_id", "date")
    both = opened.join(hired, on=["entity_id", "date"])
    assert both.height > 0
    pay = run.table("payments").collect().filter(pl.col("purpose") == "SALARY")
    paid = both.join(pay, left_on="account_id", right_on="payee_account_id")
    assert paid.select("entity_id").n_unique() == both.height


def test_mid_month_start_split_run_and_outside_window(tmp_path):
    one = World.build(cfg(tmp_path / "a", start="2025-04-20"), seed=7).run(until="2025-05-05")
    assert one.table("life_events").filter(pl.col("from_stage").is_not_null()).collect()["date"].min() == dt.date(2025, 5, 1)
    w = World.build(cfg(tmp_path / "b", start="2025-04-20"), seed=7)
    w.step(5)
    two = w.run(until="2025-05-05")
    assert one.manifest["content_hash"] == two.manifest["content_hash"]
    late = World.build(cfg(tmp_path / "c", start="2026-03-20"), seed=7).run(until="2026-05-05")
    assert late.table("entity_state_monthly").collect()["month"].unique().sort().to_list() == ["2026-03", "2026-04", "2026-05"]
```

Update `tests/test_money_flows.py` to expect `["lifecourse", "income", "remittances", "budget", "allowance", "consumption", "cash"]`, and the table set in `tests/test_pipeline.py` to include `"life_events"` and `"entity_state_monthly"`.

- [ ] **Step 2: Run it and see it fail**

Run: `PYTHONPATH=src pytest -q tests/test_lifecourse.py`
Expected: the module list does not start with `lifecourse`.

- [ ] **Step 3: Implement `events.py`, `LifeCourse`, the `tables()` hook, the new fact tables, the account-table rewrite and the module list.**

- [ ] **Step 4: Run the whole fast suite**

Run: `PYTHONPATH=src pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/arthasim tests
git commit -m "feat: life-course module with events, monthly state and world integration"
```

---

### Task 10: Bench, gate, results and ledger

**Files:**
- Modify: `scripts/bench.py`, `docs/superpowers/ledger.md`
- Create: `tests/test_gate_1b2.py`, `docs/phase1b2_results.md`

**Interfaces:**
- Consumes: all tables above.
- Produces:
  - `bench.py`: the life stage of a payer is read from `entity_state_monthly` for the payment's month, replacing every `join persons p` used for `life_stage`:
    ```sql
    join entity_state_monthly e on e.entity_id = a.holder_entity_id
     and e.month = strftime(make_timestamp(y.intent_ts) + interval 330 minute, '%Y-%m')
    ```
    `unbanked_share` comes from `entity_state_monthly` in the last month. A new key `life` holds: events by type and month; account ownership by month; working share of rural women by month (the bulletin comparison); simulated quarterly urban gross flows by sex in the panel's six states; funds declines by month and in the month after a `LAID_OFF` event.
  - `tests/test_gate_1b2.py`, marked slow: one tier S run, seed 7, 2025-04-01 to 2026-03-31; for every month, every cell's counts equal `Targets.counts`; `manifest["days"] == 365`.

- [ ] **Step 1: Write the gate test** (`tests/test_gate_1b2.py`), using the per-cell check from `tests/test_lifecourse.py::test_three_months_on_target_with_consistent_events` over all twelve months.

- [ ] **Step 2: Run the slow gates**

Run: `PYTHONPATH=src pytest -m slow -q`
Expected: 4 passed (phase 0, 1a, 1b-1, 1b-2).

- [ ] **Step 3: Update `bench.py` and run it before and after**

Run: `python scripts/bench.py --tier S --days 90 --seed 7 --out runs` on `main` (before) and on the branch (after), then `python scripts/bench.py --tier S --days 365 --seed 7 --out runs` on the branch.
Expected: both complete; record status shares, timing and memory, and the `life` block.

- [ ] **Step 4: Write `docs/phase1b2_results.md` and the ledger entry**

Results: rural women's working share by month against the bulletin path; urban gross flows against the published matrix; events per month; switches against Aon's attrition; account ownership over the year; funds declines by month and after layoffs; cost against plan 1b-1. Every figure re-queried before it is written. Ledger: one line per task (red, green, counts), every ruling with its cost if wrong, and deviations from the spec.

- [ ] **Step 5: Commit**

```bash
git add scripts/bench.py tests/test_gate_1b2.py docs/phase1b2_results.md docs/superpowers/ledger.md
git commit -m "docs: plan 1b-2 gate, bench and results"
```

## What follows this plan

Plan 1c (views and inspector) and plan 1d (government transfers). The life-course follow-ups named in the spec: births, deaths and new adults; seasonal paid days; arrears; households formed by occupation, which would let helper shares match PLFS; calibration of the assumption rows (plan 1e).
