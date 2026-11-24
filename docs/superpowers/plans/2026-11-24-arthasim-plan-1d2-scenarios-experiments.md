# Plan 1d-2: Scenarios and Experiments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Worlds that save, load and fork at month ends; eight dated interventions; paired experiments over seeds that return an effect with a Student-t interval; sweeps over one parameter.

**Architecture:**
- **Checkpoints** pickle the `World` without its store, watchers, secret or keys (`src/arthasim/checkpoint.py`). Run folders share closed months by hard link. Every file a world rewrites is replaced atomically. Loading rebuilds the running content hashes from disk; forking copies them in memory.
- **Interventions** are frozen dataclasses (`src/arthasim/interventions.py`). `world.apply` hands them to a per-world runtime, `Active` (`src/arthasim/active.py`). `Active` changes parameters at the start of a day, swaps modules at a month start, and acts after named modules' monthly hooks: income shocks after `lifecourse`, expense shocks after `budget`. Scenario DBT schemes run inside the `dbt` module.
- **Experiments** (`src/arthasim/experiment.py`) run one task per seed: a prefix to the day before `intervene_at`, one in-memory fork per treatment arm, then the baseline. They measure windowed runs (`Run.window`) and aggregate paired differences with an in-house t quantile (`src/arthasim/stats.py`).

**Tech Stack:** Python 3.12, numpy 2.5, numba 0.68, polars 2.1, duckdb 2.0, pytest. No new dependency.
- Set `SP=/private/tmp/claude-501/-Users-rbih-uc-projects-ArthaSim--claude-worktrees-nostalgic-wescoff-b80231/fd4a09be-822a-4f0f-b6d3-a67a6e0f38d5/scratchpad`.
- Fast suite: `PYTHONPATH=src $SP/venv/bin/python -m pytest -q`.
- Slow gates: add `-m slow`.

**Spec:** `docs/superpowers/specs/2026-11-23-scenarios-experiments-design.md`. Sources: `docs/sources/macro.md`.

## Global Constraints

- A run with no scenario keeps the same content hash as `main` for every table `main` writes. The reference is `scripts/bench.py --tier S --days 90 --seed 7`, recorded in Task 1, Step 1.
- Every intervention draw goes through `arthasim.engine.rng` with a stream named `iv.<ClassName>.<12 hex>` (`Intervention.stream()`). Baseline streams are never used for intervention choices. There is no `np.random` under `src/`.
- Money is integer paise.
- The release secret and its derived keys (`k0`, `k1`, `id_key`) never reach disk (`world.pkl`, `checkpoint.json`, the manifest), and never appear in an error message.
- A file a world rewrites (dimension and metadata tables, `run_manifest.json`) is written to `<name>.tmp` and moved into place with `os.replace`.
- New values, exactly:
  - `Purpose.DBT_OTHER = 22`;
  - `EVENT_NAMES` gains `"PAY_CUT"` and `"PAY_RESTORED"`, appended at the end;
  - registry rows `macro.policy_rate` and `macro.cpi_inflation`, so 134 rows.
- Save and fork happen only at a month end: `world.date.day == 1`, or before the first simulated day.
- Every new behaviour is population-only unless stated. Spike (XS) worlds behave exactly as before, apart from the two new metadata tables.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Never push.
- Record each ruling you make during execution in a new section of `docs/superpowers/ledger.md`, `# Plan 1d-2 (scenarios and experiments) execution ledger`, as earlier plans did.

## Review Focus

1. **A run whose config starts mid-month** (as `small_run` does, on 20 April). It saves before its first day (label `start`) and at its first month end (label `2025-04`), and resumes byte-identically. Test in Task 3.
2. **The same scenario passed to `world.run` in segments**, or extended with `.add` between segments. Only what is new is applied; nothing is applied twice. Test in Task 6.
3. **A `where` that selects nobody.** The run completes, `affected` is 0, and no events or credits are written. Tests in Tasks 7 and 8.
4. **A layoff shift larger than the next month's salaried target in a cell** (rate 1, `months=0`). The shift is clamped to the target, so alignment stays feasible. Test in Task 7.
5. **Loading the same checkpoint twice, or into a folder that exists.** Default folders are numbered `-2`, `-3`; an explicit existing folder raises `FileExistsError`. Nothing is overwritten. Test in Task 3.

## Builder's calls (the spec leaves these open)

- **File layout:** as in the Architecture above, plus `src/arthasim/macro.py`, `src/arthasim/scenario.py` and `src/arthasim/where.py`.
- **Checkpoint labels.** A checkpoint is labelled by the month that just ended (`2025-05` holds the world at the start of 1 June), or `start` before the first simulated day. Monthly folders, the default load and fork folders (`<run>-from-<label>`, `<run>-fork-<label>`) and `forked_from.month` all use the label.
- **`checkpoint.json` content hashes** are copied from the live store. `World.load` compares the rebuilt fact hashes with them and raises `ValueError` naming the table on a mismatch.
- **`world.run(until, scenario)`** applies each of the scenario's interventions in order, except those matched one for one by an equal intervention already applied.
- **`details`** is the JSON of the fields (dates ISO, `SetHook.impl` as its class's qualified name, `MacroPath.series` as `{date: value}`). Once a shock or transfer takes effect, `details` gains:
  - `"selected"`;
  - for layoffs, `"not_salaried"`;
  - for pay cuts, `"not_earning"`.
- **The `where` engine** is DuckDB over a per-person Polars frame. It is checked at `apply` and at `Experiment` construction against an empty frame with the same schema, so no world is needed for the check.
- **`transfer_income_paise` in `where`** is the person's DBT monthly value as the previous `dbt` step set it. At every evaluation point that is last month's value; it is 0 before the first.
- **Event order.** Income-shock events take ids after the life course's and before `dbt`'s, and their rows are stored between the two, so `life_events` stays in id order.
- **A swapped-out module's pending tables.** `_day` drains every module's tables each day, so at a month start they are empty. A month that has closed cannot take rows anyway. So a swap checks that they are empty and raises `RuntimeError` if not, rather than writing them.
- **`Experiment.run(workers=1)`** runs in-process. Above 1, it uses a spawn-context `ProcessPoolExecutor`.
- **`sweep`** returns a `SweepResult` that has `effect`, `report` and `results`, one `ExperimentResult` per value.

---

### Task 1: Macro series, run-metadata tables and atomic rewrites

**Files:**
- Modify: `params/registry.yaml` (two rows, at the end)
- Create: `src/arthasim/macro.py`
- Modify: `src/arthasim/store/parquet.py` (`META_TABLES`, `LOG_SCHEMA`, `write_atomic`, atomic `write_dimension`, `table_files`)
- Modify: `src/arthasim/world.py` (`_flush`, `_content_hashes`, `Run.tables`, `World.macro`)
- Test: `tests/test_macro.py` (new); pins in `tests/test_run.py:14`, `tests/test_pipeline.py:27`, `tests/test_build_1b.py:25`, `tests/test_life_sources.py:38`, `tests/test_dbt_schemes.py:30`

**Interfaces:**
- Produces, in `arthasim.macro`:
  - `SERIES = {"policy_rate": "macro.policy_rate", "cpi_inflation": "macro.cpi_inflation"}`;
  - `MACRO_SCHEMA = {"series": pl.String, "date": pl.Date, "value": pl.Float64}`;
  - `steps(params: ParamRegistry, series: str) -> list[tuple[dt.date, float]]`, ascending; an unknown series raises `ValueError` listing the names;
  - `value_on(steps, day: dt.date) -> float | None`, the last step on or before `day`, or `None` before the first;
  - `replace_from(steps, new: Sequence[tuple[dt.date, float]]) -> dict[str, float]`, which keeps steps before `new`'s earliest date and takes `new` from there;
  - `add_from(steps, date: dt.date, change_pp: float) -> dict[str, float]`, which adds `change_pp` to every step on or after `date` and inserts a step at `date` (the value in force plus `change_pp`) if none is there. Values are rounded to 6 decimals;
  - `frame(params) -> pl.DataFrame`, both series under `MACRO_SCHEMA`, sorted by series then date.
- The two dict-returning functions give the registry's value form: ISO-date keys in ascending order.
- Produces, in `arthasim.store.parquet`:
  - `META_TABLES = ["macro_paths", "interventions_log"]`, stored as `<name>.parquet` like dimension tables;
  - `LOG_SCHEMA = {"seq": pl.Int64, "kind": pl.String, "effective": pl.Date, "ends": pl.Date, "details": pl.String, "affected": pl.Int64, "read_after": pl.Boolean}`;
  - `write_atomic(path: Path, data: bytes | str) -> None`.
- Produces: `World.macro(series: str, day: Date) -> float | None`.

- [ ] **Step 1: Record `main`'s reference hashes before any code change** (background, about 2 minutes):

```bash
PYTHONPATH=src $SP/venv/bin/python scripts/bench.py --tier S --days 90 --seed 7 --out $SP/bench-main > $SP/bench-main.json
$SP/venv/bin/python -c "import json; r=json.load(open('$SP/bench-main.json')); m=json.load(open(r['run_path']+'/run_manifest.json')); json.dump(m['content_hash'], open('$SP/hashes-main.json','w'), indent=1, sort_keys=True)"
```

Expected: `$SP/hashes-main.json` lists 18 tables.

- [ ] **Step 2: Add the registry rows**, values from the spec:

```yaml
- id: macro.policy_rate
  value: {'2025-02-07': 6.25, '2025-04-09': 6.0, '2025-06-06': 5.5, '2025-12-05': 5.25}
  unit: percent a year, RBI repo rate, by effective date
  as_of: 2026-11
  source: RBI MPC statements of April, June and December 2025 and February 2026; Annual Report 2024-25 for the February 2025 step (docs/sources/macro.md)
  status: verified
  role: input
- id: macro.cpi_inflation
  value: {'2025-04-01': 3.16, '2025-05-01': 2.82, '2025-06-01': 2.1, '2025-07-01': 1.61, '2025-08-01': 2.07, '2025-09-01': 1.44, '2025-10-01': 0.25, '2025-11-01': 0.71, '2025-12-01': 1.33, '2026-01-01': 2.75, '2026-02-01': 3.21, '2026-03-01': 3.4}
  unit: percent year on year, all-India CPI (Combined), by month
  as_of: 2026-11
  source: MoSPI CPI releases for December 2025, January 2026 and March 2026; base 2012=100 to December 2025 and 2024=100 from January 2026, as published (docs/sources/macro.md)
  status: verified
  role: input
```

- [ ] **Step 3: Write the failing tests** in `tests/test_macro.py`, and move the five pins. The three `132`s become `134`. The two `run.tables()` sets gain `"macro_paths", "interventions_log"`.

```python
from datetime import date
import os, pytest
from arthasim import Config, World, macro
from arthasim.store.parquet import LOG_SCHEMA, Store, content_hash
from helpers import P

def xs(tmp_path): return Config.tier("XS", persons=500, employers=10, merchants=30, out_dir=str(tmp_path))

def test_registry_rows():
    assert P.table().height == 134
    assert macro.steps(P, "policy_rate") == [(date(2025, 2, 7), 6.25), (date(2025, 4, 9), 6.0),
                                             (date(2025, 6, 6), 5.5), (date(2025, 12, 5), 5.25)]
    cpi = macro.steps(P, "cpi_inflation")
    assert len(cpi) == 12 and cpi[0] == (date(2025, 4, 1), 3.16) and cpi[6] == (date(2025, 10, 1), 0.25)
    assert cpi[-1] == (date(2026, 3, 1), 3.4)

def test_value_on_holds_and_carries_forward():
    s = macro.steps(P, "policy_rate")
    assert macro.value_on(s, date(2025, 2, 6)) is None
    assert macro.value_on(s, date(2025, 6, 5)) == 6.0 and macro.value_on(s, date(2025, 6, 6)) == 5.5
    assert macro.value_on(s, date(2027, 1, 1)) == 5.25

def test_replace_from_keeps_history():
    out = macro.replace_from(macro.steps(P, "policy_rate"), [(date(2025, 6, 6), 5.75), (date(2025, 9, 1), 6.0)])
    assert out == {"2025-02-07": 6.25, "2025-04-09": 6.0, "2025-06-06": 5.75, "2025-09-01": 6.0}

def test_add_from_shifts_later_steps_and_inserts_one():
    s = macro.steps(P, "policy_rate")
    assert macro.add_from(s, date(2025, 8, 1), -0.25) == {
        "2025-02-07": 6.25, "2025-04-09": 6.0, "2025-06-06": 5.5, "2025-08-01": 5.25, "2025-12-05": 5.0}
    assert macro.add_from(s, date(2025, 6, 6), 0.1)["2025-06-06"] == 5.6

def test_unknown_series():
    with pytest.raises(ValueError, match="policy_rate"):
        macro.steps(P, "repo")

def test_runs_write_the_metadata_tables(tmp_path):
    world = World.build(xs(tmp_path), seed=7)
    run = world.run(until="2025-04-03")
    paths = run.table("macro_paths").collect()
    assert paths.schema == macro.MACRO_SCHEMA and paths.height == 16
    log = run.table("interventions_log").collect()
    assert log.height == 0 and dict(log.schema) == LOG_SCHEMA
    for t in ("macro_paths", "interventions_log"):
        assert run.manifest["content_hash"][t] == content_hash(run.path, t)
    assert world.macro("policy_rate", "2025-04-08") == 6.25 and world.macro("cpi_inflation", "2025-04-30") == 3.16

def test_rewrites_never_touch_a_hard_linked_copy(tmp_path):
    world = World.build(xs(tmp_path / "w"), seed=7)
    world.run(until="2025-04-02")
    for name in ("persons.parquet", "run_manifest.json"):
        os.link(world.path / name, tmp_path / name)
    before = {n: (tmp_path / n).read_bytes() for n in ("persons.parquet", "run_manifest.json")}
    world._store.write_dimension("persons", Run.open(world.path).table("persons").head(3).collect())
    world.run(until="2025-04-04")                               # rewrites the manifest
    assert {n: (tmp_path / n).read_bytes() for n in before} == before
```

- [ ] **Step 4: Run them to make sure they fail.** Run `PYTHONPATH=src $SP/venv/bin/python -m pytest -q tests/test_macro.py`. Expected: import error for `arthasim.macro`, and the pins fail.

- [ ] **Step 5: Implement.**
  - `macro.py` as in the Interfaces. Registry keys are ISO strings; `steps` parses them.
  - `write_dimension` writes `<name>.parquet.tmp` and `os.replace`s it.
  - `table_files` treats `META_TABLES` like `DIM_TABLES`. `content_hash(..., fact=None)` already reads non-fact tables from `<name>.parquet`.
  - `World._flush` writes `macro_paths` (`macro.frame(self.params)`) and `interventions_log` (`pl.DataFrame(schema=LOG_SCHEMA)` until Task 6) with `write_dimension`, for every builder, before the manifest. It writes the manifest with `write_atomic`.
  - `_content_hashes` and `Run.tables` iterate `FACT_TABLES + DIM_TABLES + META_TABLES`.
  - `World.macro` is `macro.value_on(macro.steps(self.params, series), _as_date(day))`.

- [ ] **Step 6: Run the new tests and the full fast suite.** Expected: all pass.

- [ ] **Step 7: Commit.**

```bash
git add params/registry.yaml src/arthasim/macro.py src/arthasim/store/parquet.py src/arthasim/world.py tests
git commit -m "feat: macro paths in the registry and a macro_paths table; interventions_log; atomic rewrites of dimension tables and the manifest"
```

---

### Task 2: Live parameters

**Files:**
- Modify: `src/arthasim/params.py` (read tracking, `__contains__`)
- Modify: `src/arthasim/life/targets.py` (`Targets.set_params`)
- Modify: `src/arthasim/world.py` (`World.set_params`, read tracking in `_day`, manifest `params_read`)
- Modify: `src/arthasim/modules/spending.py` (`Consumption` cache)
- Modify: `src/arthasim/dbt/schemes.py` (`_OnDay` replaces the lambda)
- Test: `tests/test_live_params.py` (new)

**Interfaces:**
- Produces:
  - `ParamRegistry._reads: set[str] | None`, a class attribute defaulting to `None`. While set, `get` adds each id it serves;
  - `ParamRegistry.__contains__(param_id) -> bool`, which records no read;
  - `World.set_params(params: ParamRegistry) -> None`, which replaces `world.params` and, when `state.life` exists, calls `state.life.targets.set_params(params)`;
  - `Targets.set_params(params) -> None`, which replaces `self.params`, recomputes `study_max_age` and clears `_annual` and `_shares`. `firm_shock` keeps reading `state.life.targets.params`, which is now live;
  - `World._params_read: set[str]`; the manifest's `params_read` is its sorted list.
- In `_day`, a fresh `reads` set is installed on `self.params` before `run_day` and removed after it (`try`/`finally`), then merged into `_params_read`. Build-time reads are never recorded. Task 6 passes `reads` to `Active.end_of_day`.
- `Consumption` keeps one cache, `self._cache: tuple[state, params, _Static] | None`, reused only while both objects are the same (`is`). `__getstate__` drops the cache.
- `dbt.schemes._OnDay(param: str)` is a frozen dataclass with `__call__(day, params) -> bool`. The default schemes pickle.

- [ ] **Step 1: Write the failing tests** in `tests/test_live_params.py`. Each test builds its own 2,000-person tier S world under `tmp_path`, because these tests mutate it.

```python
def test_reads_are_recorded_only_on_simulated_days(tmp_path):
    world = World.build(Config.tier("S", persons=2_000, out_dir=str(tmp_path)), seed=7)
    assert world._params_read == set()
    read = world.run(until="2025-04-02").manifest["params_read"]
    assert read == sorted(read) and {"rail.upi.limit_paise", "consumption.buffer_target_months"} <= set(read)
    assert "attr.noise_sd" not in read                       # read only at build

def test_targets_follow_set_params(tmp_path):
    world = ...; T = world.state.life.targets
    month = date(2025, 5, 1); before = T.shares(month, 0, c.F).copy()
    world.set_params(world.params.override("life.gig.nonfarm_share", {2020: 0.9, 2029: 0.9}))
    assert T.params is world.params and not np.allclose(T.shares(month, 0, c.F), before)
    world.set_params(world.params.override("life.layoff.employer_shock_sigma", 0.0))
    assert np.allclose(firm_shock(world.state, 7, month.toordinal()), 1.0)

def test_consumption_cache_follows_the_registry(tmp_path):
    world = ...; m = Consumption(); a = m._setup(world)
    assert m._setup(world) is a
    shares = list(world.params.get("consumption.category_shares.metro")); shares[0], shares[1] = shares[1], shares[0]
    world.set_params(world.params.override("consumption.category_shares.metro", shares))
    assert m._setup(world) is not a
    assert pickle.loads(pickle.dumps(m))._cache is None

def test_default_schemes_pickle():
    again = pickle.loads(pickle.dumps(default_schemes()))
    assert again[1].pays_on(date(2025, 5, 5), P) and not again[1].pays_on(date(2025, 5, 6), P)
```

- [ ] **Step 2: Run them to make sure they fail.** Expected: `params_read` is missing, `set_params` is missing, the cache attribute is missing, and pickling fails on the lambda.

- [ ] **Step 3: Implement** as in the Interfaces. `Targets.set_params` reads `life.study.max_age` through `params.get`; it runs outside a simulated day, so the read is not recorded.

- [ ] **Step 4: Run the new tests and the full fast suite.** Expected: all pass. The content-hash tests still pass, so no output changed.

- [ ] **Step 5: Commit.**

```bash
git commit -am "feat: the world tracks parameter reads; Targets and Consumption follow the live registry; DBT schemes pickle"
```

---

### Task 3: Save and load

**Files:**
- Create: `src/arthasim/checkpoint.py`
- Modify: `src/arthasim/store/hashing.py` (`RunningHash.from_disk`, `_feed_month`, shared with `content_hash`)
- Modify: `src/arthasim/store/parquet.py` (`Store.restore`)
- Modify: `src/arthasim/world.py` (`__getstate__`/`__setstate__`, `save`, `load`, `build(path=, checkpoints=)`, `label`, manifest `forked_from` and `checkpoints`)
- Modify: `tests/helpers.py` (`run_files`)
- Test: `tests/test_checkpoint.py` (new)

**Interfaces:**
- Produces, on `World`:
  - `World.build(config, seed, path: str | Path | None = None, checkpoints: bool = True)`. Without `path`, the folder name is unchanged;
  - `world.save(path) -> None`;
  - `World.load(path, path_out=None, release_secret: str | None = None, checkpoints: bool = True) -> World`;
  - `world.label -> str`: `"start"` before the first day, else `f"{world.date - 1 day:%Y-%m}"`;
  - `world._checkpoints: bool`;
  - `world._forked_from: dict | None`.
- Produces, in `arthasim.checkpoint`:
  - `require_month_end(world) -> None`: `ValueError("save and fork need a month end; the next is YYYY-MM-01")`;
  - `link_tree(src: Path, dst: Path) -> None`: hard-links every file under `src` into `dst`, keeping relative paths. It skips the top-level `checkpoints` folder and `*.tmp` files, and copies a file when `os.link` raises `OSError`;
  - `next_free(base: Path) -> Path`: `base`, else `base-2`, `base-3` and so on;
  - `write(world, path: Path) -> None`;
  - `read(path: Path, release_secret: str | None) -> tuple[World, dict]`, the world with its config and seed restored, plus the metadata.
- Produces:
  - `RunningHash.from_disk(spool_dir, name, run_path) -> RunningHash`, closed, `month` set to the last month folder's `YYYY-MM`;
  - `Store.restore(hashes: dict[str, RunningHash]) -> None`, which sets `_hash`, and `_month` from each hash's `month`.
- `checkpoint.json` keys:
  - `run_id`, `label`, `next_date`, `seed` (the run seed);
  - `config`: `model_dump(mode="json", exclude={"release_secret"})`;
  - `config_hash`, `release_secret` (bool), `registry_version`;
  - `code_version`, `python`, `numpy`, `numba`, `polars`;
  - `content_hash` (from `world._content_hashes()`);
  - `interventions` (`[]` until Task 6).
- Manifest gains `forked_from`, `{"run_id", "month", "how"}` or null, and `checkpoints`, a bool. Monthly checkpoints are written in Task 4.

- [ ] **Step 1: Add two helpers to `tests/helpers.py`:**
  - `run_files(path) -> dict[str, str]`: the SHA-256 of every `*.parquet` under `path` except `checkpoints/`, keyed by relative path;
  - `data_files(path)`: the same without `interventions_log.parquet`, for comparing a run that applied interventions with one that did not.

  Then write the failing tests in `tests/test_checkpoint.py`:

```python
S = lambda out, **kw: Config.tier("S", persons=3_000, out_dir=str(out), **kw)

def test_save_load_continue_is_byte_identical(tmp_path):
    plain = World.build(S(tmp_path), 7, path=tmp_path / "plain", checkpoints=False).run("2025-06-02")
    w = World.build(S(tmp_path), 7, path=tmp_path / "b", checkpoints=False); w.run("2025-04-30"); w.save(tmp_path / "ck")
    resumed = World.load(tmp_path / "ck", path_out=tmp_path / "c", checkpoints=False).run("2025-06-02")
    assert run_files(resumed.path) == run_files(plain.path)
    assert resumed.manifest["content_hash"] == plain.manifest["content_hash"]
    assert resumed.manifest["forked_from"] == {"run_id": "b", "month": "2025-04", "how": "load"}
    assert plain.manifest["forked_from"] is None and plain.manifest["checkpoints"] is False

def test_spike_save_load(tmp_path):   # XS, persons=500, employers=10, merchants=30: save at 2025-04-30, run to 2025-05-03
    ...same assertions on run_files and content_hash...

def test_save_needs_a_month_end(tmp_path):
    w = World.build(S(tmp_path), 7, checkpoints=False); w.run("2025-04-10")
    with pytest.raises(ValueError, match="2025-05-01"):
        w.save(tmp_path / "ck")

def test_mid_month_start_saves_before_the_first_day_and_at_the_first_month_end(tmp_path):   # Review Focus 1
    cfg = S(tmp_path, start="2025-04-20")
    plain = World.build(cfg, 7, path=tmp_path / "plain", checkpoints=False).run("2025-05-03")
    w = World.build(cfg, 7, path=tmp_path / "w", checkpoints=False)
    assert w.label == "start"; w.save(tmp_path / "ck0")
    a = World.load(tmp_path / "ck0", path_out=tmp_path / "a", checkpoints=False).run("2025-05-03")
    w.run("2025-04-30"); assert w.label == "2025-04"; w.save(tmp_path / "ck1")
    b = World.load(tmp_path / "ck1", path_out=tmp_path / "b", checkpoints=False).run("2025-05-03")
    assert run_files(a.path) == run_files(b.path) == run_files(plain.path)

def test_checkpoint_never_holds_the_secret(tmp_path):
    cfg = S(tmp_path, release_secret=RELEASE_SECRET)
    plain = World.build(cfg, 7, path=tmp_path / "plain", checkpoints=False).run("2025-05-02")
    w = World.build(cfg, 7, path=tmp_path / "w", checkpoints=False); w.run("2025-04-30"); w.save(tmp_path / "ck")
    blob = b"".join(f.read_bytes() for f in (tmp_path / "ck").rglob("*") if f.is_file() and f.suffix in (".pkl", ".json"))
    keys = KeyedSeed.derive(7, bytes.fromhex(RELEASE_SECRET))
    for needle in (bytes.fromhex(RELEASE_SECRET), RELEASE_SECRET.encode(), keys.id_key, keys.id_key.hex().encode(),
                   keys.k0.to_bytes(8, "little"), keys.k1.to_bytes(8, "little"), str(keys.k0).encode(), str(keys.k1).encode()):
        assert needle not in blob
    for wrong in (None, "6b" * 32):
        with pytest.raises(ValueError) as e:
            World.load(tmp_path / "ck", release_secret=wrong)
        assert RELEASE_SECRET not in str(e.value) and "6b" * 32 not in str(e.value)
    again = World.load(tmp_path / "ck", path_out=tmp_path / "c", release_secret=RELEASE_SECRET, checkpoints=False)
    assert run_files(again.run("2025-05-02").path) == run_files(plain.path)

def test_load_refuses_other_versions(tmp_path):   # edit checkpoint.json: code_version -> "9.9.9", then polars -> "0.0.0"
    with pytest.raises(ValueError, match="code version"): ...
    with pytest.raises(ValueError, match="Polars"): ...

def test_load_never_overwrites(tmp_path):         # Review Focus 5
    w = World.build(S(tmp_path), 7, path=tmp_path / "r", checkpoints=False); w.run("2025-04-30"); w.save(tmp_path / "ck")
    first, second = World.load(tmp_path / "ck"), World.load(tmp_path / "ck")
    assert (first.path.name, second.path.name) == ("r-from-2025-04", "r-from-2025-04-2")
    with pytest.raises(FileExistsError): World.load(tmp_path / "ck", path_out=first.path)
    with pytest.raises(FileExistsError): w.save(tmp_path / "ck")

def test_load_detects_a_changed_file(tmp_path):
    # In ck/run/payments/month=2025-04/, unlink part-0.parquet and write a 10-row slice of it in its place
    with pytest.raises(ValueError, match="payments"): World.load(tmp_path / "ck")
```

- [ ] **Step 2: Run them to make sure they fail.** Expected: `build()` rejects `path`, and `save` and `load` are missing.

- [ ] **Step 3: Implement.**
  - **`World.__getstate__`** returns `__dict__` without `_store` and `_watchers`. It replaces `seed` with `run_seed` and `config` with `config.model_copy(update={"release_secret": None})`. `__setstate__` sets `_store = None` and `_watchers = {}`.
  - **`save`:**
    1. `require_month_end`; `path` must not exist (`FileExistsError`).
    2. `self._flush()`.
    3. `world.pkl` (`pickle.dump(self, f, protocol=5)`).
    4. `checkpoint.json`.
    5. `link_tree(self.path, path / "run")`.
  - **`load`:**
    1. Read the metadata. Refuse another `code_version` (`ValueError` naming both) or another Polars version (`ValueError` naming "Polars" and both).
    2. The metadata says a secret was used and none is passed: `ValueError("this checkpoint was made with a release secret; pass release_secret")`.
    3. `Config(**meta["config"], release_secret=release_secret)`. Its `hash()` must equal `config_hash`, else `ValueError("the release secret or config does not match this checkpoint")`.
    4. Unpickle. Set `config`, and `seed` (`KeyedSeed.derive(run_seed, secret)` or `run_seed`).
    5. The folder is `path_out`, which must not exist (`FileExistsError`), or by default `next_free(Path(config.out_dir) / f"{run_id}-from-{label}")`.
    6. `link_tree(path / "run", folder)`.
    7. A new `Store`, then `restore` with `from_disk` for every fact table that has files. Compare each with `meta["content_hash"]` (`ValueError` naming the table).
    8. Set `_checkpoints`, and `_forked_from` with `how="load"`.
    9. `self._flush()`, which rewrites `accounts`, `instruments`, `bank_customers` and the manifest.

- [ ] **Step 4: Run the tests and the full fast suite.** Expected: all pass.

- [ ] **Step 5: Commit.**

```bash
git add src/arthasim/checkpoint.py src/arthasim/store src/arthasim/world.py tests/helpers.py tests/test_checkpoint.py
git commit -m "feat: world.save and World.load at month ends; checkpoints hold no secret; loads rebuild content hashes from disk"
```

---

### Task 4: Fork, monthly checkpoints and `run.fork_at`

**Files:**
- Modify: `src/arthasim/store/hashing.py` (`RunningHash.clone`)
- Modify: `src/arthasim/world.py` (`fork`, monthly checkpoints in `_day`, `checkpoint_seconds`, `Run.fork_at`)
- Test: `tests/test_checkpoint.py`

**Interfaces:**
- Consumes: Task 3's `checkpoint.write`, `link_tree`, `next_free`, `require_month_end` and `label`.
- Produces:
  - `World.fork(path_out=None, checkpoints: bool | None = None) -> World`. `None` keeps the parent's setting. The default folder is `next_free(Path(f"{self.path}-fork-{self.label}"))`. It sets `forked_from` with `how="fork"`;
  - `RunningHash.clone(spool_dir) -> RunningHash`: needs a closed month, else `ValueError`; copies `_h` with `.copy()`;
  - `World.checkpoint_seconds: float`, the total time spent writing monthly checkpoints. It is not in the manifest; `bench.py` reads it in Task 11;
  - `Run.fork_at(date: Date, path_out=None, release_secret=None, checkpoints: bool = True) -> World`.
- `fork`:
  1. `require_month_end`.
  2. `self._flush()`.
  3. `clone = pickle.loads(pickle.dumps(self, protocol=5))`, with `config` and `seed` copied from `self` in memory.
  4. `link_tree(self.path, folder)`.
  5. A new `Store`, restored with clones of `self._store._hash`.
  6. `clone._flush()`.
- **Monthly checkpoints.** In `_day`, after `end_month` and after `_wall` is updated, when `self._checkpoints` is set: `checkpoint.write(self, self.path / "checkpoints" / self.label)`, timed into `checkpoint_seconds`.
- **`fork_at(date)`:** `date` must be the 1st of a month. The checkpoint `checkpoints/<the month before date>` must exist; otherwise raise `ValueError` listing the labels present. It calls `World.load` on that folder.

- [ ] **Step 1: Write the failing tests:**

```python
def test_fork_is_byte_identical_and_isolated(tmp_path):
    plain = World.build(S(tmp_path), 7, path=tmp_path / "plain", checkpoints=False).run("2025-06-02")
    w = World.build(S(tmp_path), 7, path=tmp_path / "b", checkpoints=False); w.run("2025-04-30")
    child = w.fork(path_out=tmp_path / "c")
    snap = run_files(child.path)
    parent = w.run("2025-06-02")                                   # the parent continues first
    assert run_files(child.path) == snap
    snap_parent = run_files(parent.path)
    done = child.run("2025-06-02")
    assert run_files(parent.path) == snap_parent                   # and the child never touches the parent
    assert run_files(done.path) == run_files(plain.path) == snap_parent
    assert done.manifest["forked_from"] == {"run_id": "b", "month": "2025-04", "how": "fork"}

def test_fork_mid_month_raises(tmp_path): ...  # w.run("2025-04-10"); pytest.raises(ValueError, match="2025-05-01")

def test_monthly_checkpoints_and_fork_at(tmp_path):
    run = World.build(S(tmp_path), 7, path=tmp_path / "m").run("2025-06-02")
    assert sorted(p.name for p in (Path(run.path) / "checkpoints").iterdir()) == ["2025-04", "2025-05"]
    assert run.manifest["checkpoints"] is True
    w = run.fork_at("2025-05-01", path_out=tmp_path / "f", checkpoints=False)
    assert w.date == date(2025, 5, 1)
    assert run_files(w.run("2025-06-02").path) == run_files(run.path)
    for bad in ("2025-05-02", "2025-04-01", "2025-08-01"):
        with pytest.raises(ValueError):
            run.fork_at(bad)

def test_spike_fork(tmp_path): ...  # XS world forked at 2025-05-01 and run to 2025-05-03 matches a plain run
```

- [ ] **Step 2: Run them to make sure they fail.**

- [ ] **Step 3: Implement** as in the Interfaces.

- [ ] **Step 4: Run the tests and the full fast suite.** Expected: all pass. Existing runs now write checkpoints at month ends, and no content hash changes.

- [ ] **Step 5: Commit.**

```bash
git commit -am "feat: world.fork in memory, a checkpoint at every month end, and run.fork_at"
```

---

### Task 5: Interventions, `Scenario` and `where`

**Files:**
- Create: `src/arthasim/interventions.py`, `src/arthasim/scenario.py`, `src/arthasim/where.py`
- Test: `tests/test_interventions.py` (new)

**Interfaces:**
- Produces: `class Intervention` with:
  - `effective(start: dt.date) -> dt.date`;
  - `ends() -> dt.date | None`: for shocks with `months > 0`, the 1st of the month `months` after `date`, otherwise `None`;
  - `details() -> dict`, JSON-safe;
  - `stream() -> str`: `f"iv.{type(self).__name__}.{sha256(json.dumps(self.details(), sort_keys=True))[:12]}"`.
- Produces: the eight frozen dataclasses, with 14.2's field orders, all subclassing `Intervention`:
  - `ParamOverride(param_id, value, date=None)`;
  - `ChangeRailRule(date, rail, rule, value)`;
  - `MacroPath(name, series)`;
  - `SetPolicyRate(date, change_bp)`;
  - `IncomeShock(date, where, kind, rate, months=0)`;
  - `ExpenseShock(date, where, kind, rate, months=0)`;
  - `DBTTransfer(scheme, amount, where, dates)`;
  - `SetHook(kind, impl, bank=None, date=None)`.
- `__post_init__` normalises fields with `object.__setattr__`:
  - dates become `dt.date`;
  - `MacroPath.series` becomes a sorted tuple of `(dt.date, float)`;
  - `DBTTransfer.dates` becomes a sorted tuple of unique dates.
- `__post_init__` raises the static errors:

| Check | Error |
| :--- | :--- |
| `IncomeShock.kind` not `layoff` or `pay_cut` | `ValueError` |
| Layoff `rate` not in (0, 1]; pay-cut `rate` not in (0, 1) | `ValueError` |
| `months` negative or not an int | `ValueError` |
| `ExpenseShock.kind` not `medical`; `rate` not in [0, 1] | `ValueError` |
| A shock's `date` not the 1st; a `SetHook` `date` given and not the 1st | `ValueError` |
| `ChangeRailRule` pair not in `RAIL_RULES` | `ValueError` listing the pairs |
| `MacroPath.name` not in `macro.SERIES`; empty `series` | `ValueError` |
| `DBTTransfer`: `amount * 100` not a whole number (tolerance 1e-9), `amount <= 0`, or no dates | `ValueError` |
| `SetHook` kind `fraud_control` (phase 2), `credit_policy` or `card_policy` (phase 3), `recommender` (phase 4) | `NotImplementedError` naming the phase |
| Any other `SetHook` kind | `ValueError` |
| `SetHook("module", ...)` with a `bank` | `ValueError` |

- Produces: `RAIL_RULES = {("UPI", "per_txn_limit"): "rail.upi.limit_paise"}`, `ChangeRailRule.param_id`, `DBTTransfer.amount_paise: int`.
- Effective dates:
  - `ParamOverride` and `SetHook`: `date or start`;
  - `MacroPath`: the earliest series date;
  - `DBTTransfer`: the 1st of the earliest date's month;
  - the others: `date`.
- Produces: `Scenario`, a frozen dataclass with `interventions: tuple[Intervention, ...] = ()`. It has `baseline()`, `add(*ivs)` (`TypeError` for a non-intervention) and `details() -> list[dict]` (`{"kind": ..., **iv.details()}`).
- Produces, in `arthasim.where`:
  - `COLUMNS`, the spec's 18 names in its order;
  - `WHERE_SCHEMA`, their dtypes: ids, ages and paise `Int64`; names `String`; flags `Boolean`;
  - `person_frame(world) -> pl.DataFrame`. A spike world raises `ValueError("... needs a population world (tier S and above)")`;
  - `check(expr: str) -> None`. A `;`, an unknown column or a syntax error raises `ValueError(f"where {expr!r}: {first line of the DuckDB error}")`. It runs on an empty `WHERE_SCHEMA` frame;
  - `select(world, expr) -> np.ndarray`: person indices, ascending, `int64`.
- The query is `select _i from persons_now where ({expr}) order by _i` over the frame with a row index `_i`.
- `person_frame` columns:
  - `entity_id`, `household_id`;
  - `age`, `sex` (`c.SEX`), `education` (`c.EDUCATION`);
  - `district` (`d.id`), `district_kind` (`d.kind`);
  - `life_stage` (`c.LIFE_STAGE`), `helper` (`life.helper`), `sector` (`c.SECTORS`, null for −1);
  - `monthly_income_paise`; `household_income_paise` (the members' sum);
  - `transfer_income_paise` (`behaviour.person_transfer`);
  - `has_account`, `has_upi`, `has_card`, `primary_bank` (as `state_frame` builds them);
  - `bpl` (`government.bpl[household]`).

- [ ] **Step 1: Write the failing tests:**

```python
def test_dates_normalise_and_compare():
    a = IncomeShock("2025-06-01", "life_stage == 'salaried'", "layoff", 0.1)
    assert a == IncomeShock(date(2025, 6, 1), "life_stage == 'salaried'", "layoff", 0.1) and a.date == date(2025, 6, 1)
    assert MacroPath("policy_rate", {"2025-06-06": 5.75}).series == ((date(2025, 6, 6), 5.75),)
    assert DBTTransfer("X", 2000, "true", ["2025-05-15", "2025-05-01"]).dates == (date(2025, 5, 1), date(2025, 5, 15))

@pytest.mark.parametrize("make", [
    lambda: IncomeShock("2025-06-01", "true", "pay_cut", 1.0), lambda: IncomeShock("2025-06-01", "true", "layoff", 0.0),
    lambda: IncomeShock("2025-06-02", "true", "layoff", 0.1), lambda: IncomeShock("2025-06-01", "true", "strike", 0.1),
    lambda: ExpenseShock("2025-06-01", "true", "fuel", 0.1), lambda: ExpenseShock("2025-06-01", "true", "medical", 1.5),
    lambda: ChangeRailRule("2025-06-01", "UPI", "fee", 1), lambda: MacroPath("repo", {"2025-06-01": 5.0}),
    lambda: DBTTransfer("X", 2000.555, "true", ["2025-05-15"]), lambda: SetHook("module", object(), bank="SYNB01")])
def test_static_rules(make):
    with pytest.raises(ValueError):
        make()

def test_layoff_rate_one_and_section_11_hooks():
    IncomeShock("2025-06-01", "true", "layoff", 1.0)
    with pytest.raises(NotImplementedError, match="phase 2"):
        SetHook("fraud_control", object())
    assert DBTTransfer("X", 2000, "true", ["2025-05-15"]).amount_paise == 200_000

def test_streams_effective_and_ends():
    a, b = (IncomeShock("2025-06-01", "true", "layoff", r, months=3) for r in (0.1, 0.2))
    assert a.stream().startswith("iv.IncomeShock.") and a.stream() != b.stream()
    assert a.stream() == IncomeShock("2025-06-01", "true", "layoff", 0.1, months=3).stream()
    assert a.ends() == date(2025, 9, 1) and IncomeShock("2025-06-01", "true", "layoff", 0.1).ends() is None
    assert DBTTransfer("X", 1, "true", ["2025-05-15"]).effective(date(2025, 4, 1)) == date(2025, 5, 1)
    assert ParamOverride("rail.upi.limit_paise", 1).effective(date(2025, 4, 1)) == date(2025, 4, 1)
    json.dumps(SetHook("module", Consumption(), date="2025-05-01").details())

def test_scenario_is_immutable():
    a, b = ParamOverride("x", 1), ParamOverride("y", 2)
    s = Scenario.baseline(); t = s.add(a).add(b)
    assert s.interventions == () and t.interventions == (a, b) and t == Scenario.baseline().add(a, b)

def test_where_selects_and_checks():
    world = small_world()                      # read-only
    p, life = world.state.population.persons, world.state.life
    got = where.select(world, "life_stage == 'farm' and not helper")
    assert np.array_equal(got, np.flatnonzero((p.life_stage == c.FARM) & ~life.helper))
    assert where.person_frame(world).columns == list(where.COLUMNS)
    assert where.select(world, "age > 500").size == 0
    for bad in ("occupation == 'farmer'", "age >", "true; select 1"):
        with pytest.raises(ValueError):
            where.check(bad)
```

- [ ] **Step 2: Run them to make sure they fail.**

- [ ] **Step 3: Implement** as in the Interfaces.

- [ ] **Step 4: Run the tests and the full fast suite.** Expected: all pass.

- [ ] **Step 5: Commit.**

```bash
git add src/arthasim/interventions.py src/arthasim/scenario.py src/arthasim/where.py tests/test_interventions.py
git commit -m "feat: the eight phase 1 interventions, Scenario, and the where evaluator"
```

---

### Task 6: Applying interventions: parameters, rails, macro paths and module swaps

**Files:**
- Create: `src/arthasim/active.py`
- Modify: `src/arthasim/world.py` (`self.active`, `apply`, `set_hook`, `module`, `run(until, scenario=None)`, `_day` hooks, `_flush` writes the log, manifest `scenario`)
- Modify: `src/arthasim/engine/scheduler.py` (`world.active.after_module` after each monthly hook)
- Modify: `src/arthasim/checkpoint.py` (`interventions` in `checkpoint.json`)
- Test: `tests/test_apply.py` (new)

**Interfaces:**
- Consumes:
  - Task 5's interventions and `where.check`;
  - Task 2's `World.set_params` and the day's `reads`;
  - Task 1's `macro.replace_from`, `macro.add_from` and `LOG_SCHEMA`.
- Produces: `class Active`, pickled with the world, with these methods:

| Method | What it does |
| :--- | :--- |
| `apply(world, iv) -> int` | Checks the intervention, logs it and returns its `seq` |
| `start_of_day(world, day)` | Applies parameter changes due on or before `day`, in `seq` order. On a month start or the first simulated day, makes module swaps due on or before `day` |
| `after_module(world, name, day)` | No-op here; Tasks 7 and 8 fill it |
| `end_of_day(world, day, reads)` | Sets `read_after` |
| `tables() -> dict[str, pl.DataFrame]` | Empty here; Task 7 adds events |
| `log_frame() -> pl.DataFrame` | The log under `LOG_SCHEMA`, rows in `seq` order |
| `details() -> list[dict]` | For the manifest's `scenario` and `checkpoint.json`'s `interventions` |
| `applied` | `list[Intervention]` |

- `apply` checks, in order:
  1. `iv.effective(world.config.start) < world.date` raises `ValueError` naming both dates.
  2. `ParamOverride` with an unknown id raises `KeyError`. Use `in`, so no read is recorded.
  3. Shocks and `DBTTransfer` on a spike world raise `ValueError`. Their `where` must pass `where.check`.
  4. `SetHook("module")`: `impl` is not a `BehaviourModule` (`TypeError`); no module has `impl.name` (`ValueError` listing names); `pickle.dumps(impl)` fails (`ValueError`).
- The new value of a macro or rail intervention is computed when it takes effect, from the series in force then, so they stack:
  - `ChangeRailRule` overrides `iv.param_id`;
  - `MacroPath` overrides `macro.SERIES[name]` with `replace_from`;
  - `SetPolicyRate` overrides `macro.policy_rate` with `add_from(..., change_bp / 100)`.
- A swap drains the old module's `tables()`. Any non-empty frame raises `RuntimeError`.
- Log rows:
  - `read_after` starts `False` for the four parameter kinds and is null for the others. It turns true on the first simulated day, on or after `effective`, whose `reads` contain the parameter;
  - `affected` stays null for these kinds.
- Produces on `World`:
  - `apply(iv) -> None`;
  - `set_hook(kind, impl, bank=None)`, which is `apply(SetHook(kind, impl, bank, date=self.date))`;
  - `module(name) -> BehaviourModule`, `KeyError` if absent;
  - `run(until, scenario=None)`, which applies each scenario intervention in order except those matched one for one by an equal one in `active.applied`.
- `_day` runs in this order:
  1. `active.start_of_day`;
  2. read tracking on;
  3. `run_day`;
  4. read tracking off;
  5. `active.end_of_day`.
- It stores `active.tables()` right after the module named `lifecourse`, or after all modules when there is none.
- The scheduler calls `world.active.after_module(world, module.name, day)` after each `monthly`.
- `_flush` writes `interventions_log` from `active.log_frame()`. The manifest gains `scenario: active.details()`.

- [ ] **Step 1: Write the failing tests** in `tests/test_apply.py`.
  - `build(path)` builds a fresh 3,000-person tier S world, starting 2025-04-01, with `checkpoints=False`; `build_xs(path)` builds the 500-person XS world of Task 1.
  - Two module-level classes, so they pickle: `Recorder(Consumption)`, whose `intents` appends `day` to `self.days` and calls `super()`; and `Unnamed(BehaviourModule)` with `name = "nothing"`.

```python
UPI_LIMIT = "select max(amount_paise) as m from payments where rail like 'UPI%' and status = 'SUCCESS' and {day}"

def test_param_override_from_its_date(tmp_path):
    world = build(tmp_path)
    world.apply(ParamOverride("rail.upi.limit_paise", 100_000, "2025-04-15"))
    run = world.run("2025-04-20")
    assert run.sql(UPI_LIMIT.format(day=f"{IST_DAY} >= '2025-04-15'"))["m"][0] <= 100_000
    assert run.sql(UPI_LIMIT.format(day=f"{IST_DAY} < '2025-04-15'"))["m"][0] > 100_000
    log = run.table("interventions_log").collect()
    assert log["kind"].to_list() == ["ParamOverride"] and log["read_after"].to_list() == [True]
    assert log["effective"].to_list() == [date(2025, 4, 15)] and log["affected"].to_list() == [None]

def test_override_of_a_build_only_parameter_has_no_effect(tmp_path):
    plain = build(tmp_path / "p").run("2025-04-05")
    world = build(tmp_path / "o"); world.apply(ParamOverride("attr.noise_sd", 0.5, "2025-04-02"))
    run = world.run("2025-04-05")
    assert run.table("interventions_log").collect()["read_after"].to_list() == [False]
    assert data_files(run.path) == data_files(plain.path)

def test_change_rail_rule(tmp_path): ...  # ChangeRailRule("2025-04-15", "UPI", "per_txn_limit", 100_000): as the override

def test_macro_interventions(tmp_path):   # XS world
    world = build_xs(tmp_path)
    world.apply(MacroPath("cpi_inflation", {"2025-06-01": 5.0, "2025-07-01": 6.0}))
    world.apply(SetPolicyRate("2025-05-15", -25))
    world.run("2025-05-10")
    assert world.macro("policy_rate", "2025-05-20") == 6.0                     # not yet in force
    run = world.run("2025-06-02")
    assert world.macro("policy_rate", "2025-05-20") == 5.75 and world.macro("policy_rate", "2026-01-01") == 5.0
    cpi = run.sql("select date, value from macro_paths where series = 'cpi_inflation' order by date")
    assert cpi["value"].to_list() == [3.16, 2.82, 5.0, 6.0]
    assert run.table("interventions_log").collect()["read_after"].to_list() == [False, False]

def test_module_swap_from_its_month_start(tmp_path):
    plain = build(tmp_path / "p").run("2025-05-03")
    world = build(tmp_path / "s"); rec = Recorder()                 # module-level: class Recorder(Consumption) logging days in intents
    world.apply(SetHook("module", rec, date="2025-05-01"))
    world.run("2025-04-30"); assert world.module("consumption") is not rec
    run = world.run("2025-05-03")
    assert world.modules.index(world.module("consumption")) == 6 and world.module("consumption") is rec
    assert rec.days == [date(2025, 5, 1), date(2025, 5, 2), date(2025, 5, 3)]
    assert data_files(run.path) == data_files(plain.path)            # Recorder behaves as Consumption does

def test_apply_errors(tmp_path):
    world = build(tmp_path); world.run("2025-04-10")
    with pytest.raises(ValueError, match="2025-04-11"): world.apply(ParamOverride("rail.upi.limit_paise", 1, "2025-04-05"))
    with pytest.raises(KeyError): world.apply(ParamOverride("no.such", 1, "2025-04-20"))
    with pytest.raises(ValueError): world.set_hook("module", Recorder())               # 2025-04-11 is not the 1st
    with pytest.raises(ValueError): world.apply(SetHook("module", Unnamed(), date="2025-05-01"))   # name matches no module
    with pytest.raises(ValueError): build_xs(tmp_path / "x").apply(IncomeShock("2025-05-01", "true", "layoff", 0.1))

def test_run_applies_a_scenario_once_across_segments(tmp_path):     # Review Focus 2
    a, b = ParamOverride("rail.upi.limit_paise", 100_000, "2025-04-03"), ParamOverride("consumption.spend_share", 0.7, "2025-04-09")
    world = build(tmp_path); s = Scenario.baseline().add(a)
    world.run("2025-04-05", s); world.run("2025-04-08", s); run = world.run("2025-04-10", s.add(b))
    log = run.table("interventions_log").collect()
    assert log["seq"].to_list() == [0, 1] and [json.loads(d)["param_id"] for d in log["details"]] == [
        "rail.upi.limit_paise", "consumption.spend_share"]
    assert run.manifest["scenario"][0]["kind"] == "ParamOverride"

def test_interventions_survive_a_checkpoint(tmp_path):
    # Apply ParamOverride("rail.upi.limit_paise", 100_000, "2025-05-10") at build.
    # Run to 2025-04-30, save, load, run to 2025-05-12.
    # Files equal an uninterrupted run with the same intervention; checkpoint.json lists it.
    ...
```

- [ ] **Step 2: Run them to make sure they fail.**

- [ ] **Step 3: Implement** as in the Interfaces.

- [ ] **Step 4: Run the tests and the full fast suite.** Expected: all pass. With nothing applied, every content hash is unchanged.

- [ ] **Step 5: Commit.**

```bash
git add src/arthasim/active.py src/arthasim/world.py src/arthasim/engine/scheduler.py src/arthasim/checkpoint.py tests/test_apply.py
git commit -m "feat: world.apply and run(scenario): parameter, rail and macro interventions, module swaps, and the interventions log"
```

---

### Task 7: Income shocks

**Files:**
- Modify: `src/arthasim/active.py` (income shocks after `lifecourse`, pay-cut restores, layoff shifts)
- Modify: `src/arthasim/modules/lifecourse.py` (`lay_off`, `cell_of`, shift in `_Cycle.run` step 2)
- Modify: `src/arthasim/life/events.py` (`PAY_CUT`, `PAY_RESTORED`)
- Test: `tests/test_income_shock.py` (new)

**Interfaces:**
- Produces, in `arthasim.modules.lifecourse`:
  - `cell_of(state) -> np.ndarray`: each person's target cell, `(district * 2 + sex) * c.N_AGE_GROUPS + c.age_group(age)`, the formula `Targets.counts` uses;
  - `lay_off(world, who: np.ndarray, first: dt.date, log: EventLog) -> None`. It moves people as `movers` moves a salaried leaver to `seeking`:
    - `last_stage = SALARIED`, `months_since_left = 0`;
    - `last_income` and `last_sector` set from their current values;
    - `person_employer = -1`, `life_stage = SEEKING`, `sector = -1`;
    - income and salary 0, `months_in_stage = 1`;
    - a `LAID_OFF` event with from and to stages, `employer_from` and incomes;
    - then `recompute_payroll`.
- Produces: `Active.target_shift(month: dt.date, n_cells: int) -> np.ndarray` (int64), the sum of the layoff shifts active in that month.
- `_Cycle.run` step 2, after the targets are summed:

```python
k = np.minimum(self.world.active.target_shift(self.month, T.n_cells), targets[:, c.SALARIED])
targets[:, c.SALARIED] -= k
targets[:, c.SEEKING] += k
```

- **Layoff, after `lifecourse` in the month of `date`:**
  1. `sel = where.select(...)`.
  2. Salaried among `sel`: `u = rng.uniform(seed, stream_id(iv.stream()), person_ids[sal], first.toordinal()) < rate`.
  3. `lay_off` those people.
  4. Record a shift: the laid-off counts per `cell_of` cell, active for month indices `m + 1` to `m + months − 1`, or with no end when `months` is 0.
  5. `affected` is the number laid off. `details` gains `selected` and `not_salaried`.
- **Pay cut, after `lifecourse`:**
  1. The eligible are the selected whose stage is in `c.EARNING` and who are not helpers.
  2. `new = where(income > 0, max(1, rint(income * (1 − rate))), 0)`. Salary is set to `new` for the salaried and 0 for the rest, as `_Cycle.set_income` does. Then `recompute_payroll`.
  3. Write a `PAY_CUT` event (`income_before`, `income_after`).
  4. Keep a record `(seq, rate, who, stage, entry = m − months_in_stage, pay_set, restore = m + months or None)`.
  5. `affected` is the number cut. `details` gains `selected` and `not_earning`.
- **Restore, after `lifecourse` in month `restore`:**
  1. A person is restored when all hold: the same `life_stage`, not a helper, `life.pay_set` unchanged, and `m − months_in_stage == entry`.
  2. Income becomes `rint(income / (1 − rate))`, salary as above, then `recompute_payroll`.
  3. Write a `PAY_RESTORED` event.
- **Events.** They go to `EventLog().frame(first, s.life.next_event_id)`, and the counter is advanced. `Active.tables()` returns them as `life_events`.
- Shocks act in `seq` order. Restores come before new shocks in the same month.

- [ ] **Step 1: Write the failing tests.** Use 5,000-person tier S worlds, starting 2025-04-01, with `checkpoints=False`. Each test also runs a plain world of the same config to compare against.

```python
METRO = "district == 'metro_archetype'"

def salaried_by_cell(run, month):   # {cell: count} from entity_state_monthly joined to persons, cell as cell_of computes it
    ...

def test_layoff_and_alignment(tmp_path):
    plain = build(tmp_path / "p").run("2025-07-01")
    world = build(tmp_path / "t"); world.apply(IncomeShock("2025-05-01", METRO, "layoff", 0.5, months=2))
    run = world.run("2025-07-01")
    ev = run.sql("select entity_id from life_events where event = 'LAID_OFF' and date = '2025-05-01'"
                 " and entity_id not in (select entity_id from {plain May LAID_OFF})")      # the shock's own
    may_sal = plain metro salaried in May (entity_state_monthly)
    assert set(ev) <= may_sal and 0.4 < len(ev) / len(may_sal) < 0.6
    assert their May state in run: life_stage 'seeking', monthly_income_paise 0, employer_entity_id null
    shift = per-cell counts of ev (cells from May ages)
    for cell, n in salaried_by_cell(plain, "2025-06").items():
        assert salaried_by_cell(run, "2025-06").get(cell, 0) == n - min(shift.get(cell, 0), n)
    assert salaried_by_cell(run, "2025-07") == salaried_by_cell(plain, "2025-07")
    assert run.table("interventions_log").collect()["affected"].to_list() == [len(ev)]

def test_layoff_shift_is_clamped(tmp_path):                 # Review Focus 4: rate 1, months 0
    # Same comparison for June and July with IncomeShock("2025-05-01", METRO, "layoff", 1.0): in every cell,
    # run's salaried == max(0, plain's - shift); the run completes.
    ...

def test_pay_cut_and_restore(tmp_path):
    plain = build(tmp_path / "p").run("2025-07-01")
    world = build(tmp_path / "t")
    world.apply(IncomeShock("2025-05-01", "life_stage in ('salaried', 'farm')", "pay_cut", 0.2, months=2))
    world.run("2025-05-01")
    cut = PAY_CUT events; for each: income_after == round(income_before * 0.8), income_before == plain's May income
    i, j = two salaried cut people (person indices)
    a, s = world.state.population.attributes, world.state
    raise_i = int(round(a.monthly_income_paise[i] * 1.1))                     # a raise in between
    a.monthly_income_paise[i] = s.person_salary[i] = raise_i
    s.life.pay_set[j] = month_index(date(2025, 6, 1))                         # j's pay was reset by a switch
    run = world.run("2025-07-01")
    restored = PAY_RESTORED events on 2025-07-01
    assert i in restored with income_after == round(raise_i / 0.8) and j not in restored
    assert every restored income_after == round(income_before / 0.8)

def test_permanent_cut_is_never_restored(tmp_path): ...   # months=0: no PAY_RESTORED by 2025-07-01

def test_shocks_that_select_nobody(tmp_path):            # Review Focus 3
    world = build(tmp_path); world.apply(IncomeShock("2025-05-01", "age > 500", "layoff", 0.5))
    run = world.run("2025-05-02")
    assert run.table("interventions_log").collect()["affected"].to_list() == [0]

def test_event_ids_stay_in_order(tmp_path):
    # In the layoff run, life_events' event_id is 0..n-1 and ascending in file order, month by month.
    ...
```

- [ ] **Step 2: Run them to make sure they fail.**

- [ ] **Step 3: Implement** as in the Interfaces.

- [ ] **Step 4: Run the tests and the full fast suite.** Expected: all pass.

- [ ] **Step 5: Commit.**

```bash
git commit -am "feat: income shocks: layoffs held against alignment for their duration, and pay cuts restored after it"
```

---

### Task 8: Expense shocks and scenario DBT transfers

**Files:**
- Modify: `src/arthasim/active.py` (expense shocks after `budget`; DBT `affected` after `dbt`; `dbt_schemes`)
- Modify: `src/arthasim/dbt/schemes.py` (`ScenarioScheme`)
- Modify: `src/arthasim/modules/dbt.py` (scenario schemes in `monthly`)
- Modify: `src/arthasim/engine/intents.py` (`Purpose.DBT_OTHER = 22`)
- Modify: `src/arthasim/views.py` (`REMARKS["APBS"]` adds `"DBT_OTHER"`)
- Test: `tests/test_expense_dbt.py` (new)

**Interfaces:**
- Produces: `ScenarioScheme`, a frozen dataclass in `dbt/schemes.py`, with fields `name`, `amount_paise: int`, `where: str`, `dates: tuple[dt.date, ...]`, `seq: int` and `purpose: int = int(Purpose.DBT_OTHER)`, and these methods:
  - `active(first: dt.date) -> bool`: the month lies from the earliest date's month to the latest's;
  - `pays_on(day, params) -> bool`: `day in dates`;
  - `per_month(first) -> int`: `amount_paise × the dates in that month`.
- Produces: `Active.dbt_schemes(first) -> list[ScenarioScheme]`, the active ones in `seq` order.
- `apply` rejects a `DBTTransfer` whose name is `PM_KISAN`, `OLD_AGE_PENSION`, `WOMEN` or another scenario scheme's name (`ValueError`).
- `GovernmentTransfers.monthly` appends `(sch, SchemeResult(...))` for each scheme from `world.active.dbt_schemes(first)`, after the built-ins and before account opening:
  - `payee = where.select(world, sch.where)`;
  - every payee enrolled;
  - `amount = amount_paise`;
  - `monthly_value = per_month(first)`.
- Opening, credits (slots from `dbt.slots`) and transfer income then follow the existing code unchanged.
- **Expense shock, after `budget` in each month from `date` up to `ends()`, or every month when `months` is 0:**
  1. `hh = unique(household_of_person[where.select(...)])`.
  2. `hit = rng.uniform(seed, stream_id(iv.stream()), hh, first.toordinal()) < rate`.
  3. `cost = rng.lognormal(seed, stream_id(iv.stream() + ".cost"), hh, first.toordinal(), shock.medical_median_paise, shock.medical_sigma)`.
  4. `medical_due[hh[hit]] += max(100, rint(cost))`.
  5. `stress = min(1, stress + shock.stress_bonus)` for the hit.
  6. `affected` is the households selected in the first month.
- **DBT `affected`:** after `dbt` in the earliest date's month, the number of enrolled payees of that scheme. `details` gains `selected`.

- [ ] **Step 1: Write the failing tests.** Use 5,000-person tier S worlds, starting 2025-04-01, with `checkpoints=False`.

```python
FARMERS = "life_stage == 'farm' and not helper"

def test_dbt_transfer(tmp_path):
    plain = build(tmp_path / "p").run("2025-06-01")
    world = build(tmp_path / "t"); world.apply(DBTTransfer("TEST_TRANCHE", 2000, FARMERS, ["2025-05-15"]))
    run = world.run("2025-06-01")
    farmers = set(run.sql("select entity_id from entity_state_monthly where month = '2025-05' "
                          "and life_stage = 'farm' and not helper")["entity_id"])
    dbt = run.sql("select * from truth_dbt_monthly where scheme = 'TEST_TRANCHE'")
    assert set(dbt["entity_id"]) == farmers and dbt["enrolled"].all() and set(dbt["monthly_value_paise"]) == {200_000}
    assert set(dbt["month"]) == {"2025-05"}
    pay = run.sql(f"select * from payments y where purpose = 'DBT_OTHER'")
    assert pay.height == len(farmers) and set(pay["amount_paise"]) == {200_000} and set(pay["rail"]) == {"APBS"}
    assert set(pay["status"]) == {"SUCCESS"} and all IST days are 2025-05-15 and IST hours in 6..9
    unbanked = farmers with has_account false in plain's May entity_state_monthly
    assert unbanked and unbanked <= set(ACCOUNT_OPENED entity_ids on 2025-05-01 in run)
    assert dbt.filter(entity_id in unbanked)["opened_account"].all()
    # Transfer income: May households gain 200_000 per payee; June equals plain.
    assert May transfer_income_paise (run - plain), per household, == 200_000 * that household's payees
    assert June transfer_income_paise run == plain for every household
    assert run.table("interventions_log").collect()["affected"].to_list() == [len(farmers)]
    lines = pl.concat(run.view("bank", bank=b).table("statement_lines").filter(pl.col("rail") == "APBS").collect() for b in BANKS)
    assert lines.filter(pl.col("narration").str.ends_with("/DBT_OTHER")).height == len(farmers)

def test_dbt_errors(tmp_path):
    world = build(tmp_path)
    with pytest.raises(ValueError): world.apply(DBTTransfer("PM_KISAN", 1, "true", ["2025-05-15"]))
    world.apply(DBTTransfer("A", 1, "true", ["2025-05-15"]))
    with pytest.raises(ValueError): world.apply(DBTTransfer("A", 2, "true", ["2025-06-15"]))
    world.run("2025-05-02")
    with pytest.raises(ValueError): world.apply(DBTTransfer("B", 1, "true", ["2025-05-20"]))   # its month began

def test_dbt_and_expense_that_select_nobody(tmp_path):     # Review Focus 3
    world = build(tmp_path)
    world.apply(DBTTransfer("NOBODY", 2000, "age > 500", ["2025-05-15"]))
    world.apply(ExpenseShock("2025-05-01", "age > 500", "medical", 1.0, months=1))
    run = world.run("2025-05-20")
    assert run.sql("select count(*) as n from payments where purpose = 'DBT_OTHER'")["n"][0] == 0
    assert run.table("interventions_log").collect()["affected"].to_list() == [0, 0]

def test_expense_shock(tmp_path):
    plain = build(tmp_path / "p").run("2025-06-01")
    world = build(tmp_path / "t")
    world.apply(ExpenseShock("2025-05-01", "district == 'rural_archetype'", "medical", 1.0, months=1))
    run = world.run("2025-06-01")
    may = medical_due_paise of run vs plain in truth_household_monthly for 2025-05, joined to households.district
    assert all rural: run >= plain + 100; all metro: run == plain
    assert June medical_due_paise run == plain for every household

def test_expense_shock_at_rate_zero_changes_nothing(tmp_path):
    # ExpenseShock("2025-05-01", "true", "medical", 0.0): data_files equal the plain run's to 2025-06-01
    ...
```

- [ ] **Step 2: Run them to make sure they fail.**

- [ ] **Step 3: Implement** as in the Interfaces.

- [ ] **Step 4: Run the tests and the full fast suite.** Expected: all pass. With no scenario, `test_dbt_*` and the view tests are unchanged.

- [ ] **Step 5: Commit.**

```bash
git commit -am "feat: expense shocks and scenario DBT transfers (APBS, purpose DBT_OTHER), with transfer income in the pay month"
```

---

### Task 9: Windowed runs and the t interval

**Files:**
- Modify: `src/arthasim/store/parquet.py` (`table_files(path, name, months=None)`)
- Modify: `src/arthasim/world.py` (`Run(path, manifest, months=None)`, `Run.window`; `tables`, `table` and `sql` honour `months`)
- Create: `src/arthasim/stats.py`
- Test: `tests/test_window_stats.py` (new)

**Interfaces:**
- Produces:
  - `table_files(path, name, months: tuple[str, str] | None = None)`: fact files whose folder month `YYYY-MM` lies within `months`, inclusive. Other tables are unchanged;
  - `Run.window(start: Date, end: Date) -> Run`, with `months = (f"{start:%Y-%m}", f"{end:%Y-%m}")`;
  - `Run.months: tuple[str, str] | None`;
  - `stats.t_quantile(p: float, df: int) -> float`;
  - `stats.interval(d: Sequence[float], level: float) -> tuple[float, float | None, float | None, int]`, giving `(mean, lo, hi, n)`; `lo` and `hi` are `None` when n < 2.
- `t_quantile` is in-house: the Student-t CDF via the regularised incomplete beta function (Lentz continued fraction), inverted by bisection to 1e-10.

- [ ] **Step 1: Write the failing tests:**

```python
@pytest.mark.parametrize("p, df, t", [(0.975, 1, 12.7062), (0.975, 2, 4.3027), (0.975, 9, 2.2622), (0.95, 5, 2.0150),
                                      (0.995, 9, 3.2498), (0.975, 30, 2.0423), (0.975, 1000, 1.9623)])
def test_t_quantile(p, df, t):
    assert abs(stats.t_quantile(p, df) - t) < 1e-4

def test_interval():
    m, lo, hi, n = stats.interval([1, 2, 3, 4], 0.95)
    assert (m, n) == (2.5, 4) and abs(lo - 0.44574) < 1e-4 and abs(hi - 4.55426) < 1e-4
    assert stats.interval([3, 3, 3], 0.95) == (3.0, 3.0, 3.0, 3) and stats.interval([5], 0.95) == (5.0, None, None, 1)

def test_window_sees_only_its_months():
    run = small_run()                                          # 2025-04-20 to 2025-05-25, read-only
    w = run.window("2025-05-01", "2025-05-31")
    assert w.table("payments").select(pl.col("settle_ts")).collect().height == run.sql(
        f"select count(*) as n from payments y where {metrics._MONTH} = '2025-05'")["n"][0]
    assert w.metric("txn_volume", by="month")["month"].to_list() == ["2025-05"]
    assert w.table("persons").collect().height == run.table("persons").collect().height
    assert "balances_monthly" not in w.tables() and w.metric("deposit_balance").height == 0
```

- [ ] **Step 2: Run them to make sure they fail.**

- [ ] **Step 3: Implement** as in the Interfaces.

- [ ] **Step 4: Run the tests and the full fast suite.** Expected: all pass.

- [ ] **Step 5: Commit.**

```bash
git add src/arthasim/stats.py src/arthasim/store/parquet.py src/arthasim/world.py tests/test_window_stats.py
git commit -m "feat: run.window over month partitions and an in-house Student-t interval"
```

---

### Task 10: Experiments, sweeps and reports

**Files:**
- Create: `src/arthasim/experiment.py`
- Modify: `src/arthasim/__init__.py` (export `Scenario`, `Experiment`, `ExperimentResult`, `interventions`, `macro`)
- Test: `tests/test_experiment.py` (new)

**Interfaces:**
- Consumes:
  - `World.build(path=, checkpoints=False)`, `fork(path_out, checkpoints=False)`, `apply`, `run`;
  - `Run.window`;
  - `stats.interval`;
  - `Intervention.effective`, `Scenario.details`, `where.check`.
- Produces:

```python
class Experiment:
    def __init__(self, config: Config, baseline: Scenario, treatments: Mapping[str, Scenario], seeds: Iterable[int],
                 intervene_at: Date, end: Date, path: str | Path | None = None) -> None
    path: Path
    def run(self, workers: int = 1) -> "ExperimentResult"
    def sweep(self, param_id: str, values: Sequence[Any], workers: int = 1) -> "SweepResult"

class ExperimentResult:
    path: Path; arms: list[str]; seeds: list[int]; intervene_at: dt.date; end: dt.date; config: Config
    @classmethod
    def open(cls, path: str | Path) -> "ExperimentResult"
    def runs(self, arm: str) -> list[Run]
    def effect(self, metric, by=None, fill=None, level=0.95, window="arms", **kwargs) -> pl.DataFrame
    def report(self, path: str | Path, metrics=None, window="arms") -> None

class SweepResult:
    param_id: str; values: list[Any]; results: list[ExperimentResult]
    def effect(self, metric, by=None, fill=None, level=0.95, window="arms", **kwargs) -> pl.DataFrame
    def report(self, path, metrics=None, window="arms") -> None

def _run_seed(exp: Experiment, seed: int) -> dict[str, str]     # module level, for spawn
```

- **Construction checks** (`ValueError`), each naming what failed:
  - `intervene_at` equals `config.start`, or is the 1st of a month after it, and is before `end`;
  - arm names match `[A-Za-z0-9_-]+` and are not `baseline`;
  - each arm's interventions with `effective(start) < intervene_at` equal the baseline's, in order;
  - every intervention's `effective(start) >= config.start`;
  - every `where` passes `where.check`;
  - seeds are unique, and there is at least one.
- **Folder.** The default is `Path(config.out_dir) / f"experiment-{digest}"`, where `digest = sha256(json.dumps({"config": config.hash(), "baseline": baseline.details(), "arms": {n: s.details()}, "seeds": seeds, "intervene_at": iso, "end": iso}, sort_keys=True, default=str))[:12]`. `run` raises `FileExistsError` when the folder exists.
- **`_run_seed`** follows the spec's "One seed":
  1. Build into `<path>/baseline-seed<s>` with checkpoints off.
  2. Apply the baseline's prefix interventions, and run to `intervene_at − 1 day` when `intervene_at > config.start`.
  3. For each arm, in order: fork into `<path>/<arm>-seed<s>`, apply the arm's interventions effective on or after `intervene_at`, run to `end`, and drop the fork.
  4. Apply the baseline's own later interventions and run it to `end`.
  5. Return `{arm: folder name}`.
- **`run`.** `workers == 1` loops in-process; above 1, `ProcessPoolExecutor(workers, mp_context=multiprocessing.get_context("spawn"))`. Results are in seed order. It writes `experiment.json`:
  - `arms` (each arm's interventions), `seeds`, `intervene_at`, `end`;
  - `config` without the secret, `config_hash`, `release_secret`;
  - `runs` (`{arm: {seed: folder}}`).
- **`effect`** follows the spec's four steps:
  - group columns are every column but `value`; with none, the frames join by `how="cross"`;
  - the outer join coalesces keys;
  - `fill` fills the value columns, and without it rows with a null value are dropped;
  - columns `arm`, the groups, `baseline`, `treatment`, `effect`, `lo`, `hi`, `n`, `relative`;
  - rows in arm order, then by groups.
- **`SweepResult.effect`** puts `param_value` first: `Int64` when every value is an int, `Float64` when every value is numeric, otherwise `String` (`str` for strings, `json.dumps` otherwise). `sweep` checks `param_id` against the registry first (`KeyError`) and runs each value as `Experiment(config.with_params(**{param_id: v}), ..., path=self.path / f"sweep-{param_id}" / str(i))`.
- **`report` Markdown** has five parts:
  1. A header: config tier, persons, seeds, dates, and the window measured.
  2. Each arm's interventions, as `details`.
  3. One table per metric. The default is the five built-ins, ungrouped, with `fill=0` for all but `decline_rate`.
  4. "Interventions": `affected` and `read_after` per arm from seed 1's log. Each `read_after` false gets a line saying it had no effect (for `macro.` series: "nothing reads macro paths in phase 1"), and so does each `affected` of 0.
  5. "Assumptions read": each `assumption`-status parameter in the union of the runs' `params_read`, with its source from the registry at `config.params_path`.

- [ ] **Step 1: Write the failing tests.** A module-level `functools.lru_cache` fixture `dbt_experiment()` runs one shared experiment:
  - tier S, 2,000 persons, start 2025-04-01;
  - one arm, `dbt`, with `DBTTransfer("TEST_TRANCHE", 2000, FARMERS, ["2025-05-05"])`;
  - a second arm, `same`, with `ParamOverride("rail.upi.limit_paise", P.get("rail.upi.limit_paise"), "2025-05-01")`;
  - seeds `[1, 2]`, `intervene_at="2025-05-01"`, `end="2025-05-06"`, `workers=1`.

```python
def test_baseline_arm_equals_a_plain_run(tmp_path):
    res = dbt_experiment()
    plain = World.build(CONFIG, 1, path=tmp_path / "p", checkpoints=False).run("2025-05-06")
    assert res.runs("baseline")[0].manifest["content_hash"] == plain.manifest["content_hash"]

def test_arms_match_before_intervene_at():
    res = dbt_experiment()
    for b, t in zip(res.runs("baseline"), res.runs("dbt")):
        april = lambda r: {k: v for k, v in run_files(r.path).items() if "month=2025-04" in k}
        assert april(b) == april(t) and april(b)

def test_effect_on_apbs_credits_is_the_payees():
    res = dbt_experiment()
    eff = res.effect("txn_volume", by="rail", fill=0).filter((pl.col("arm") == "dbt") & (pl.col("rail") == "APBS"))
    payees = [r.sql("select count(*) as n from truth_dbt_monthly where scheme = 'TEST_TRANCHE'")["n"][0] for r in res.runs("dbt")]
    assert eff["effect"][0] == sum(payees) / 2 and eff["n"][0] == 2 and eff["lo"][0] <= eff["effect"][0] <= eff["hi"][0]
    assert eff.columns == ["arm", "rail", "baseline", "treatment", "effect", "lo", "hi", "n", "relative"]

def test_an_intervention_that_changes_nothing_has_zero_effect():
    row = dbt_experiment().effect("txn_volume").filter(pl.col("arm") == "same")
    assert (row["effect"][0], row["lo"][0], row["hi"][0], row["relative"][0]) == (0, 0, 0, 0)

def test_fill_decides_groups_missing_from_one_side():
    def other(run, by=None):
        return run.sql("select purpose as g, count(*) as value from payments where purpose = 'DBT_OTHER' group by 1")
    res = dbt_experiment()
    assert res.effect(other).filter(pl.col("arm") == "dbt").height == 0
    assert res.effect(other, fill=0).filter(pl.col("arm") == "dbt")["n"].to_list() == [2]

def test_window_run_measures_whole_runs():
    res = dbt_experiment()
    arms = res.effect("txn_volume", fill=0).filter(pl.col("arm") == "dbt")
    whole = res.effect("txn_volume", fill=0, window="run").filter(pl.col("arm") == "dbt")
    assert arms["effect"][0] == whole["effect"][0] and arms["baseline"][0] < whole["baseline"][0]

def test_open_reads_back():
    res = dbt_experiment()
    assert ExperimentResult.open(res.path).effect("cash_withdrawal", fill=0).equals(res.effect("cash_withdrawal", fill=0))

def test_report(tmp_path):
    res = dbt_experiment(); res.report(tmp_path / "r.md"); text = (tmp_path / "r.md").read_text()
    assert "TEST_TRANCHE" in text and "cash_withdrawal" in text and "2025-05-01" in text
    read = set().union(*(set(r.manifest["params_read"]) for a in res.arms for r in res.runs(a)))
    rows = {r["id"]: r for r in P.table().iter_rows(named=True)}
    for pid in read:
        if rows[pid]["status"] == "assumption":
            assert pid in text

def test_workers_do_not_change_results(tmp_path):
    one = Experiment(CONFIG, base, {"dbt": dbt}, [1, 2], "2025-05-01", "2025-05-03", path=tmp_path / "a").run(workers=1)
    two = Experiment(CONFIG, base, {"dbt": dbt}, [1, 2], "2025-05-01", "2025-05-03", path=tmp_path / "b").run(workers=2)
    assert one.effect("txn_volume", by="rail", fill=0).equals(two.effect("txn_volume", by="rail", fill=0))
    for arm in one.arms:
        assert [r.manifest["content_hash"] for r in one.runs(arm)] == [r.manifest["content_hash"] for r in two.runs(arm)]

def test_sweep(tmp_path):
    exp = Experiment(CONFIG, base, {"dbt": dbt}, [1], "2025-05-01", "2025-05-03", path=tmp_path / "s")
    sw = exp.sweep("consumption.buffer_target_months", [2, 3])
    eff = sw.effect("consumption", fill=0)
    assert eff.columns[0] == "param_value" and eff["param_value"].to_list() == [2, 3] and eff["param_value"].dtype == pl.Int64
    assert (tmp_path / "s" / "sweep-consumption.buffer_target_months" / "1" / "experiment.json").exists()

@pytest.mark.parametrize("kw", [dict(intervene_at="2025-05-02"), dict(intervene_at="2025-05-03", end="2025-05-03"),
                                dict(treatments={"baseline": Scenario.baseline()}), dict(treatments={"a b": Scenario.baseline()}),
                                dict(treatments={"x": Scenario.baseline().add(ParamOverride("rail.upi.limit_paise", 1, "2025-04-10"))}),
                                dict(seeds=[])])
def test_construction_errors(kw): ...   # each raises ValueError

def test_existing_folder(tmp_path): ...  # run() into an existing path raises FileExistsError
```

- [ ] **Step 2: Run them to make sure they fail.**

- [ ] **Step 3: Implement** as in the Interfaces.

- [ ] **Step 4: Run the tests and the full fast suite.** Expected: all pass.

- [ ] **Step 5: Commit.**

```bash
git add src/arthasim/experiment.py src/arthasim/__init__.py tests/test_experiment.py
git commit -m "feat: Experiment, ExperimentResult and SweepResult: paired arms over seeds with a t interval, reports, and worker pools"
```

---

### Task 11: Bench, slow gate, results and ledger

**Files:**
- Modify: `scripts/bench.py` (`checkpoint_seconds`, `checkpoint_mb`, `content_hash` in the output)
- Create: `scripts/phase1d2_results.py`
- Create: `tests/test_gate_1d2.py`
- Create: `docs/phase1d2_results.md`
- Modify: `docs/superpowers/ledger.md`

**Interfaces:**
- `bench.py` adds three keys to its JSON:
  - `checkpoint_seconds` (`world.checkpoint_seconds`);
  - `checkpoint_mb` (the size of `<run>/checkpoints`, counting each inode once);
  - `content_hash` (the manifest's).
- `scripts/phase1d2_results.py --part {experiment,checkpoint} --workers N --seeds 1-10 --out DIR` prints JSON:
  - `experiment`:
    - the spec's experiment: ₹2,000 to `life_stage == 'farm' and not helper` on 2025-11-15, `intervene_at` 2025-11-01, `end` 2025-12-31;
    - its effects on `cash_withdrawal` (total, `by="month"` and `by="district"`, `fill=0`), `consumption` (`fill=0`) and `txn_volume` with `status="DECLINED_FUNDS"` (`fill=0`);
    - wall seconds;
    - peak RSS of the parent and of the children (`RUSAGE_CHILDREN`);
  - `checkpoint`:
    - tier S, seed 7, an uninterrupted run to 2025-07-31 against a save at 2025-05-31, a load and a run on to 2025-07-31;
    - the hash of every data file on both sides, and whether they all match;
    - the manifest fields that differ;
    - checkpoint size and save seconds, load seconds (re-hashing included), and fork seconds.

- [ ] **Step 1: Write the slow gate** `tests/test_gate_1d2.py` (`@pytest.mark.slow`), as the spec's success measure:
  - tier S, seed 7, from 2025-04-01;
  - uninterrupted to 2025-07-31, against a run to 2025-05-31, `save`, `load` and a run on to 2025-07-31: `run_files` and `content_hash` are equal;
  - an `Experiment` with seeds `[1, 2]`, `intervene_at="2025-06-01"`, `end="2025-07-31"` and arm `dbt` = `DBTTransfer("GATE_TRANCHE", 2000, "life_stage == 'farm' and not helper", ["2025-06-15"])`:
    - in every seed, the `txn_volume` APBS difference equals that seed's `GATE_TRANCHE` payees in `truth_dbt_monthly`;
    - `effect("cash_withdrawal", fill=0)` has non-null `lo` and `hi` for `dbt`.

- [ ] **Step 2: Run it.** Command: `PYTHONPATH=src $SP/venv/bin/python -m pytest -q -m slow tests/test_gate_1d2.py` (background). Expected: pass.

- [ ] **Step 3: Bench after.** Run `scripts/bench.py --tier S --days 90 --seed 7 --out $SP/bench-branch`. Compare its `content_hash` with `$SP/hashes-main.json`. Expected: every table in `main`'s file is equal, and the only new keys are `macro_paths` and `interventions_log`.

- [ ] **Step 4: Run the results script** in the background:
  - `--part experiment` with `--workers 1` and with `--workers 4`;
  - `--part checkpoint`.

  Save the JSON outputs in `$SP/results/`.

- [ ] **Step 5: Write `docs/phase1d2_results.md`.** Re-query every figure from the saved runs. It covers:
  - the experiment's effect tables, with intervals and n;
  - the checkpoint demonstration: the per-file hash table, whether all match, and the differing manifest fields (run id, source label, wall time, `forked_from`);
  - costs: checkpoint size and time, load time, fork time, and the experiment's wall time and peak memory with 1 and 4 workers;
  - the bench before and after, with the new tables listed;
  - what the numbers do not show: macro paths have zero effect by design, and n = 10.

- [ ] **Step 6: Write the ledger section:** tasks with commits and test counts, rulings, findings.

- [ ] **Step 7: Run the full fast suite and every slow gate.** Expected: all pass.

- [ ] **Step 8: Commit.**

```bash
git add scripts tests/test_gate_1d2.py docs/phase1d2_results.md docs/superpowers/ledger.md
git commit -m "docs: plan 1d-2 results, slow gate and execution ledger"
```

---

## After the tasks

1. **Review.** One fresh reviewer on Opus reads the whole branch against the spec and this plan (superpowers:requesting-code-review). Fix each finding test-first and record the rulings in the ledger.
2. **Merge.**
   1. Rebase onto `main`.
   2. Rerun the fast suite and every slow gate.
   3. Run `git checkout main && git merge --ff-only claude/nostalgic-wescoff-b80231`, from the main checkout.
   4. Do not push.
