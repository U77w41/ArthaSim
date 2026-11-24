# Plan 1e (calibration and validation) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pin the registry to primary sources, add `calibrate` and `run.validate`, fit the free parameters on 10,000-person worlds, and gate a calibrated tier S run on the core suite.

**Architecture:** Target values are registry rows; the core suite (`params/validation/core.yaml`) names each check's target row, statistic and tolerance; `arthasim/statistics.py` computes every statistic from a finished run's tables for both fitting and checking. `calibrate` drives Optuna's TPE sampler over sequential trials whose seeds run in parallel; the fitted set is a committed overrides file. `run.validate` adds hard checks re-derived from stored tables and writes `validation_report.parquet` into the run.

**Tech Stack:** Python 3.12, NumPy, Polars, DuckDB, Optuna 5.1 (new), pytest, Hypothesis.

**Spec:** `docs/superpowers/specs/2026-11-24-calibration-validation-design.md`. Sources: `docs/sources/calibration.md`.

## Global Constraints

- `scripts/bench.py --tier S --days 90 --seed 7` keeps all 20 content hashes of `main` at `29dd4a6` (recorded in the ledger before any code change).
- No registry value of an existing row changes without a ruling; adding rows is allowed.
- Every tolerance is in `params/validation/core.yaml` with a `why:` before the gate's first run, and is not changed after.
- `calibrate` results do not depend on `workers`.
- Money stays integer paise inside the simulator; statistics return floats in rupees or shares as the target row's `unit` says.
- Fast suite: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -p no:cacheprovider -q`. Slow gates: add `-m slow`.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

- **A run whose last month is incomplete** (the bench stops on 29 June): the ledger re-check must skip that month's month-end comparison but still check its postings; statistics must leave it out of the window. Pinned in Tasks 4 and 3.
- **A run shorter than two months:** the window is empty. Every statistic returns no value and its check is `skipped` with the reason, not an error. Pinned in Task 5.
- **A district kind with no persons in a group** (a 1,000-person world with no rural graduates aged 18–29): the component is `skipped`, not NaN passed as a pass. Pinned in Task 3.
- **Validating a run made with a release secret, or forked, or with a scenario:** determinism is `skipped` with its reason; the other checks run. Pinned in Task 4.
- **`calibrate` with `workers` greater than the seeds:** extra workers idle; the result is unchanged. Pinned in Task 6.

---

## File structure

| File | Responsibility |
| :--- | :--- |
| `params/registry.yaml` | New target and holdout rows; appendix A rows; sources and statuses of existing rows |
| `docs/sources/calibration.md` | Every figure's document, table, page and URL; every derivation |
| `src/arthasim/statistics.py` | `Context`, the window, area weights, one function per statistic |
| `src/arthasim/checks.py` | Hard checks: ledger re-check, determinism, identifier formats |
| `src/arthasim/validation.py` | Suite loading, `ValidationReport`, `validate(run, suite)` |
| `src/arthasim/calibration.py` | `Free`, overrides, the trial runner, `calibrate`, `CalibrationResult` |
| `params/validation/core.yaml` | The core suite |
| `params/calibration/space.yaml` | Default free parameters and fitted checks |
| `params/calibration/fitted.yaml` (+ `fitted_trials.parquet`, `fitted_report.md`) | The committed calibration |
| `scripts/calibrate.py`, `scripts/phase1e_results.py` | Running the calibration; measuring the results |
| `src/arthasim/world.py` | Manifest `config`; `Run.validate`; `Run.tables` lists `validation_report` |
| `src/arthasim/store/parquet.py` | `REPORT_TABLES` |
| `src/arthasim/build/identifiers.py` | Extra real formats |
| `tests/test_registry_sources.py`, `test_statistics.py`, `test_checks.py`, `test_validation.py`, `test_calibration.py`, `test_gate_1e.py` | Tests |

---

### Task 1: Registry rows and source notes

**Files:** Modify `params/registry.yaml`, `docs/sources/calibration.md`, `tests/test_life_sources.py:38`, `tests/test_macro.py:17`, `tests/test_dbt_schemes.py:30`, `tests/test_build_1b.py:25`. Create `tests/test_registry_sources.py`.

**Interfaces:** Produces registry rows read by Tasks 3 and 5 (ids and value shapes in the spec's core suite tables). Value shapes: area rows are `{rural: x, urban: y}`; monthly rows are `{"YYYY-MM": x}`; shares are fractions, rupees are rupees.

- [ ] **Step 1: Write the failing tests** in `tests/test_registry_sources.py`:
  - `test_target_and_holdout_rows_cite_a_document`: every row with role `target` or `holdout` has `http` or `docs/sources/` in its source.
  - `test_verified_rows_name_where`: every `verified` row's source names a table, statement, section, paragraph, item, clause or page (regex over those words).
  - `test_core_target_values`: spot values, `P.get("pay.regular_monthly") == {"rural": 17841, "urban": 26247}`, `P.get("consumption.mpce") == {"rural": 4122, "urban": 6996}`, `P.get("upi.p2m.share_under_500") == 0.86`, `P.get("dbt.cashout_lag") == {"d0_5": 0.179, "d6_15": 0.234, "d16_30": 0.173}`.
  - `test_no_input_value_changed`: every row present at `29dd4a6` keeps its value (the test holds the 134 old ids' values as a JSON digest computed from `main`).
- [ ] **Step 2: Run** `pytest tests/test_registry_sources.py -v`. Expected: FAIL (rows missing).
- [ ] **Step 3: Add the rows** in a new section at the end of `params/registry.yaml`, and update sources and statuses of the existing rows named in the source notes. Move the four row-count pins to the new count.
- [ ] **Step 4: Run** the fast suite. Expected: all pass.
- [ ] **Step 5: Commit** `feat: registry targets, holdouts and appendix A rows pinned to primary sources`.

### Task 2: Run metadata for validation

**Files:** Modify `src/arthasim/world.py`, `src/arthasim/store/parquet.py`. Test: `tests/test_validation.py` (first tests).

**Interfaces:** Produces `REPORT_TABLES = ["validation_report"]` (in `store/parquet.py`, handled by `table_files` like a dimension table); manifest key `config` (the config's `model_dump(mode="json", exclude={"release_secret"})`); `run_config(run) -> Config` and `run_params(run) -> ParamRegistry` in `statistics.py` (Task 3 uses them).

- [ ] **Step 1: Failing tests:** `test_manifest_records_the_config` (a small run's `Config(**manifest["config"]).hash() == config.hash()`, and a secret run's manifest has no secret); `test_report_table_is_listed_but_not_hashed` (writing `validation_report.parquet` into a run makes `run.tables()` list it and leaves `manifest["content_hash"]` keys unchanged after another flush).
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.** `_flush` adds `manifest["config"]`; `Run.tables` lists `REPORT_TABLES` present; `_content_hashes` does not include them.
- [ ] **Step 4: Run** the new tests and `tests/test_checkpoint.py`, `tests/test_run.py`. Expected: PASS.
- [ ] **Step 5: Commit** `feat: manifest records the config; validation_report is a run table outside the content hash`.

### Task 3: Statistics

**Files:** Create `src/arthasim/statistics.py`, `tests/test_statistics.py`.

**Interfaces:**
- `Context(run: Run, months: tuple[str, str] | None, params: ParamRegistry)`; `context(run, months=None) -> Context` builds it with `run_params(run)` and the default window.
- `window(run) -> tuple[str, str] | None`: second month to last complete month (a month is complete when `balances_monthly` has it); None when empty.
- `STATISTICS: dict[str, Callable[[Context], dict[str, float]]]`, one per spec check, keyed by check id. Components `rural`/`urban`, `all`, or named (`d0_5` etc.). A component with no data is absent from the dict.
- `national(ctx, per_area: dict[str, float]) -> float` weights with `population.urban_share`.
- `gini(values, weights) -> float`.

- [ ] **Step 1: Failing tests** on `small_run`-style fixtures (a 2,000-person run from 1 April to 30 June 2025, cached in the test module) and hand-made frames:
  - `test_window_skips_the_first_and_the_incomplete_month`;
  - `test_gini_matches_a_hand_computation` (weights [1, 1, 2], values [1, 2, 4]);
  - one test per statistic group recomputing its value with an independent DuckDB query on the same run (pay, MPCE, shares, per-adult counts, tickets, month-start spike, balances, zero balance, inoperative, festival ratio, cash-out lag);
  - `test_missing_group_is_absent_not_nan`.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement** each statistic as the spec's tables define it.
- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** `feat: statistics shared by calibration and validation`.

### Task 4: Hard checks

**Files:** Create `src/arthasim/checks.py`, `tests/test_checks.py`. Modify `src/arthasim/build/identifiers.py`.

**Interfaces:** `ledger(run) -> list[CheckRow]`, `determinism(run, release_secret=None) -> list[CheckRow]`, `identifiers(run) -> list[CheckRow]`, where `CheckRow` is a dict with the report's columns (`component`, `status`, `detail`, ...). `REAL_FORMATS` gains `account_digits` (`^[0-9]{9,18}$`) and `card16` (16 digits) plus `luhn(s) -> bool`.

- [ ] **Step 1: Failing tests:** each check passes on a clean small run (copied to `tmp_path`); each fails on a copy damaged one way (posting delta +1; a `balances_monthly` value +1; a vault's month-end balance −100; a `persons` row changed; a `pan_like` set to `ABCPE1234F`; a VPA handle set to `@okaxis`); determinism is `skipped` for a forked run and for a secret run without the secret, and passes with it.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement** as in the spec's "Hard checks" (ledger month by month: shapes via `_check_shapes` with a book built from `accounts`; continuity by sorting postings by account; month-end, bank and cash checks from `balances_monthly`).
- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** `feat: hard checks re-derived from a stored run`.

### Task 5: The suite and `run.validate`

**Files:** Create `src/arthasim/validation.py`, `params/validation/core.yaml`. Modify `src/arthasim/world.py`, `src/arthasim/__init__.py`. Test: `tests/test_validation.py`.

**Interfaces:** `load_suite(name_or_path) -> list[Check]`; `Check(id, kind, target, statistic, compare, tolerance, why, gap=None, uprate=None, months=None)`; `validate(run, suite="core", release_secret=None) -> ValidationReport`; `ValidationReport(frame)` with `passed`, `table()`, `failures()`, `report(path)`, `ValidationReport.open(run)`. `Run.validate(suite="core", release_secret=None)`.

- [ ] **Step 1: Failing tests:** the report's columns and dtypes; `passed` is false when one check fails and true when only skips remain; a `gap` check that fails keeps `status == "fail"` and its `gap` text; `run.validate` writes the table and `run.table("validation_report")` reads it; a windowed run raises; an unknown target id in a suite raises at load; a run of one month gives `skipped` target rows.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement**, with the suite file holding every spec check and tolerance.
- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** `feat: run.validate and the core suite`.

### Task 6: `calibrate`

**Files:** Create `src/arthasim/calibration.py`, `params/calibration/space.yaml`, `tests/test_calibration.py`. Modify `pyproject.toml` (add `optuna>=5.1` to dependencies), `src/arthasim/__init__.py`.

**Interfaces:** `Free(id, low, high, log=False, key=None, scale=False)`; `overrides(params, frees, values) -> dict[str, Any]`; `calibrate(config, params=None, targets=None, trials=200, seeds=(1, 2, 3), months=8, workers=1, sampler_seed=0, path=None) -> CalibrationResult`; `CalibrationResult` with `best`, `free`, `loss`, `scores`, `trials`, `registry_version`, `apply`, `save`, `load`, `report`.

- [ ] **Step 1: Failing tests:** `test_overrides_compose_key_and_scale`; `test_score_and_loss` (relative and absolute tolerances); `test_two_trials_same_with_one_or_two_workers` (1,000 persons, `months=2`, one seed, two trials: equal `best`, `loss`, `trials`); `test_save_load_roundtrip`; `test_apply_sets_overrides`; `test_unknown_or_unbounded_parameter_raises`.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement** with Optuna's ask/tell (`TPESampler(seed=sampler_seed, multivariate=True, n_startup_trials=min(20, trials))`), a spawned `ProcessPoolExecutor` reused across trials, one task per seed.
- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** `feat: calibrate with Optuna's TPE sampler over seeded three-month runs`.

### Task 7: The committed calibration

**Files:** Create `scripts/calibrate.py`, `params/calibration/fitted.yaml`, `params/calibration/fitted_trials.parquet`, `params/calibration/fitted_report.md`.

- [ ] **Step 1:** `scripts/calibrate.py --trials 400 --workers 3 --out params/calibration/fitted.yaml` (run in the background; about 70 minutes).
- [ ] **Step 2:** Read the report: the loss path, any fitted value at a bound (a bound that binds is recorded as a finding).
- [ ] **Step 3: Commit** `feat: committed calibration (400 trials, seeds 1-3, 10,000 persons)`.

### Task 8: The tier S gate

**Files:** Create `tests/test_gate_1e.py`. Modify `params/validation/core.yaml` (`gap:` entries, each with a ruling in the ledger).

- [ ] **Step 1:** Write the gate as the spec says. Run it once with no `gap:` entries; it fails, listing failing checks.
- [ ] **Step 2:** For each failing check, decide from the report whether the model lacks the mechanism (a gap, ruled and listed) or the calibration or code is wrong (fix it). Tolerances are not changed.
- [ ] **Step 3: Run** `pytest -m slow tests/test_gate_1e.py`. Expected: PASS.
- [ ] **Step 4: Commit** `feat: tier S acceptance gate on the calibrated run`.

### Task 9: Bench, results, ledger

**Files:** Create `scripts/phase1e_results.py`, `docs/phase1e_results.md`. Modify `docs/superpowers/ledger.md`.

- [ ] **Step 1:** Bench on the branch; compare all 20 content hashes with the reference.
- [ ] **Step 2:** `scripts/phase1e_results.py` on the gate's run and on the same run uncalibrated; write the results doc from its output only.
- [ ] **Step 3:** Fast suite and all slow gates.
- [ ] **Step 4: Commit** `docs: plan 1e results and execution ledger`.
- [ ] **Step 5:** One fresh Opus reviewer on the whole branch; fix, rule or defer each finding; commit.
