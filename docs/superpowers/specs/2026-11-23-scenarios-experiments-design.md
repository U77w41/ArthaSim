# Plan 1d-2, scenarios and experiments: design

23 November 2026.

**Status.**
- The project owner chose to record macro paths only (approach A below).
- The owner handed the rest of the how to this session, with a standing instruction: decide the way the real system works, from public evidence, and record each decision with its source.
- Decisions taken under that instruction are marked **Decided**, each with its source or reason and its cost if wrong. Source notes with URLs are in `docs/sources/macro.md`, which this plan adds.

## Intent

Phase 1 ends when "a paired experiment returns an effect with an interval" and "every phase 1 call in section 14.1 works" (architecture section 18). Plan 1e (calibration and validation) builds on this plan.

Plan 1d-2 adds the following:
- **Checkpoints.** `world.save`, `World.load`, `world.fork` and `run.fork_at`. A run can pause, resume, or branch at any month end.
- **Scenarios.** Dated interventions applied to a world.
- **Experiments.** A shared prefix runs up to the intervention date. One fork per arm runs to the end, and this repeats for each seed. The result reports the mean paired difference per metric, with an interval.
- **Sweeps.** The same comparison across values of one parameter.

Paired arms share keyed randomness. Every draw is a pure function of (seed, stream, entity, day, index), so two arms of one seed make the same draws wherever their states agree. Differences come only from the intervention and what follows from it.

## Goals

- `world.save(path)` writes a checkpoint at a month end. `World.load(path)` continues it in a new run folder. The continued run's data files are byte-identical to an uninterrupted run's.
- `world.fork()` copies a world in memory at a month end. Every run keeps a checkpoint at each month end, so `run.fork_at(date)` can start a new world from any month.
- `Scenario.baseline().add(...)` builds a list of interventions, and `world.apply(iv)` and `world.run(until, scenario)` apply them. Eight intervention types work:
  - `MacroPath`;
  - `SetPolicyRate`;
  - `IncomeShock`;
  - `ExpenseShock`;
  - `DBTTransfer`;
  - `ChangeRailRule`;
  - `ParamOverride`;
  - `SetHook`.
- `Experiment(config, baseline, treatments, seeds, intervene_at, end).run(workers)` returns an `ExperimentResult`. Its `effect(metric, by=...)` gives the mean paired difference with a Student-t interval across seeds.
- `exp.sweep(param_id, values)` reruns the experiment at each value of one parameter.
- `ExperimentResult.report(path)` writes the effects and the interventions. It also lists the `assumption`-status parameters the runs read.
- Each run records:
  - the macro paths it ran under, in a new table `macro_paths`;
  - the interventions it applied, in a new table `interventions_log`.
- A run with no scenario produces the same content hash as on `main` for every table `main` writes.

## Non-goals

- Anything reading the macro paths. Nothing in the phase 1 world earns or pays interest, and there is no price level. `MacroPath` and `SetPolicyRate` change the recorded paths and nothing else, so their effect on every outcome is zero until a later plan wires a consumer (loans in phase 3). Savings interest that follows the repo rate is a candidate follow-up. In the real world it would: SBI cut its savings rate from 2.70% to 2.50% from 15 June 2025, nine days after the 50 bp repo cut.
- Section 11's hooks (`fraud_control`, `credit_policy`, `card_policy`, `recommender`). Their call sites arrive in phases 2 to 4. In phase 1, `SetHook` swaps a behaviour module (see `SetHook`).
- Rail rules the model does not enforce, such as fees, cooling periods and cut-offs. `ChangeRailRule` supports the one rail rule the model enforces: the UPI per-transaction limit.
- Interventions of phases 2 to 4 (`BankRule`, `FraudCampaign`, `AwarenessCampaign`, `ProductLaunch`, `MarketShock`).
- Saving or resuming mid-month, which section 16 does not ask for.
- Loading checkpoints made by another code version, or from anyone else. A checkpoint is a pickle, and loading one runs code, so only load checkpoints from your own runs.
- `calibrate` and `validate` (plan 1e).
- New built-in metrics. The five from plan 1c are enough for the results. `effect` passes keyword arguments through to the metric.

Anti-goals, outcomes that would be failures even if the code ran:
- A resumed or forked run that differs from an uninterrupted one in any data file.
- Arms that differ before the intervention date.
- A checkpoint that holds the release secret or any key derived from it.
- A run that rewrites a file shared, by hard link, with another run.
- An intervention that silently does nothing:
  - An override of a parameter that is only read at build is reported as having no effect.
  - A layoff that alignment quietly undoes counts as silently doing nothing.
- Experiment results that depend on the number of workers.

## Approaches considered

### What macro paths do (chosen by the project owner)

| Approach | Trade-off | Verdict |
| :--- | :--- | :--- |
| **A. Record only.** Runs get a `macro_paths` table holding the real repo and CPI paths. `MacroPath` and `SetPolicyRate` change those series, and nothing reads them yet. | Baseline output is unchanged, and the plan stays on the experiment machinery. Macro interventions show zero effect until phase 3. | **Chosen by the project owner** |
| B. Add savings interest. Banks credit quarterly interest at a rate that follows the repo rate. | `SetPolicyRate` gets a real, small effect. It needs a new journal kind and new invariant rules, and every run's output changes. | Dropped |
| C. B plus an inflation index scaling the registry's fixed rupee amounts. | More behaviour change, which needs its own evidence. | Dropped |

### How checkpoints and forks work (this session's call)

| Approach | Trade-off | Verdict |
| :--- | :--- | :--- |
| **1. Pickle the whole world at month ends; fork in memory.** | A tier S world after a month pickles to about 75 MB in 0.06 s. A fork copies state and hash objects in memory, and the run folder hard-links the shared months. Any field a later phase adds is carried without extra work, and the byte-for-byte test catches anything missed. Loading a pickle runs code, so checkpoints are for your own runs only. | **Chosen** |
| 2. Replay instead of saving: a load re-runs from the start. | Nothing new to save, but every arm pays for the whole prefix, and a resume takes as long as the original run. | Dropped |
| 3. Structured checkpoints (`.npz` and Parquet per state field). | Safe to load from anywhere, but needs a hand-written serializer per state class kept in step with every new field. A missed field silently breaks resume. | Dropped |

## Checkpoints

### When a world can be saved or forked

At a month end, meaning `world.date` is the first of a month, or before the first simulated day. Otherwise `save` and `fork` raise `ValueError` naming the next month end.
- **Decided.** Architecture section 16: "State is checkpointed at each month end." At a month end every fact table's month is closed: its rows are on disk, its content-hash spool is folded in, and no file is open. So nothing from the open month has to be saved.
- Cost if wrong: a user who wants a mid-month save must step to the month end first.

### What a checkpoint holds

A checkpoint is a folder:

| File | Contents |
| :--- | :--- |
| `world.pkl` | The `World`, pickled with protocol 5. It holds the state, the modules (with any intervention state), the parameter registry, counters, the day count and the applied interventions. It leaves out the store, watch callbacks, the release secret and every key derived from it. |
| `checkpoint.json` | Run id, next date, seed, config without the secret, `config_hash`, `release_secret` (bool), `registry_version`, `code_version`, the Python, NumPy, Numba and Polars versions, the run's content hashes so far, and the interventions applied so far. |
| `run/` | Hard links to every file of the run so far: dimension tables, fact parts of the closed months, `run_manifest.json`, `macro_paths` and `interventions_log`. If the file system refuses a hard link, the file is copied. |

- **The release secret.**
  - The pickle stores the seed as the run seed only.
  - `World.load(path, release_secret=...)` needs the secret when `checkpoint.json` says the run had one. It derives the keys again and checks `config.hash()` against the recorded `config_hash`. A missing or wrong secret raises `ValueError`, and the message never shows the secret.
  - **Decided.** This follows plan 1c-2: the secret is "never shown or written".
  - Cost if wrong: none to correctness; a user must keep the secret to resume a release run.
- **Versions.** `World.load` refuses a checkpoint whose `code_version` or Polars version differs from the running one. A different Polars could change bytes and content hashes; plan 1b-1 found the row hash stable only within one Polars version.
- **Module caches.** A module keeps no cache in a checkpoint. A cache keyed by `id()` of an object, as `Consumption` keeps today, is dropped on pickling and rebuilt on first use.

### Save, load and fork

- **`world.save(path)`** first writes the run's manifest and dimension tables. It then writes `world.pkl` and `checkpoint.json`, and hard-links the run's files into `path/run/`. `path` must not exist.
- **`World.load(path, path_out=None, release_secret=None, checkpoints=True)`** loads the world into a new run folder:
  - The folder is `path_out`, or by default `<config.out_dir>/<run_id>-from-<YYYY-MM>`, with `-2`, `-3` and so on added if it exists.
  - It hard-links `path/run/*` into the new folder, unpickles, and opens a new store.
  - The running SHA-256 state of a content hash cannot be saved, so it rebuilds each fact table's running hash by streaming that table's closed months from disk, exactly as `content_hash` reads them. That costs about what hashing the prefix from disk costs: about 1.5 s per 90 days at tier S, measured in plan 1c.
- **`world.fork(path_out=None)`** makes a new `World` in the same process:
  - It deep-copies everything `world.pkl` would hold, copies each running hash object (`hashlib`'s `copy()`), and hard-links the run's files into the new folder.
  - The default folder is `<run path>-fork-<YYYY-MM>`, numbered like `load`'s.
  - Nothing is re-hashed.
- **`run.fork_at(date)`** loads the run's own month-end checkpoint for the month before `date`. `date` must be the first of a month after the run's first month end, with a checkpoint present. Otherwise it raises `ValueError`.
- **Monthly checkpoints.** `World.build(config, seed, path=None, checkpoints=True)` and `World.load` keep a checkpoint at every month end, in `<run>/checkpoints/<YYYY-MM>/`, with the layout above.
  - **Decided.** Section 16 asks for it.
  - The cost at tier S is about 75–90 MB and under 0.2 s a month, uncompressed. A month of tier S output is about 250 MB. zlib level 1 shrinks a checkpoint to 19 MB but takes 0.55 s, about 14% of a month's simulation time, so checkpoints stay uncompressed.
  - Cost if wrong: about 36% more disk per run; `checkpoints=False` turns them off.
  - Experiment arms run with checkpoints off, because their fork points are held in memory.
- **`World.build` gains an optional `path`.** Without it, the folder name is unchanged: `<out_dir>/<tier>-seed<seed>-<config hash[:8]>`.

### Shared files are never modified

Fork and load share the prefix files by hard link. Every file a world rewrites is written to a temporary name and renamed over the old one, never opened for writing in place. That covers dimension tables (`accounts`, `instruments` and `bank_customers` are rewritten at each flush), `run_manifest.json`, `macro_paths` and `interventions_log`. Fact parts are already written this way, and are never rewritten once their month closes.

A loaded or forked world rewrites `accounts`, `instruments` and `bank_customers` from its own state when it opens. The parent may have opened accounts after the checkpoint, and its later files must not show through.

### What the manifest adds

- `forked_from`: `{"run_id", "month", "how": "load" | "fork"}`, or null.
- `checkpoints`: true or false.
- `scenario`: the interventions applied, in order, as JSON (see `interventions_log`).
- `params_read`: the sorted ids of every registry parameter read on a simulated day.

The fields `days`, `payments` and `wall_seconds` count the whole run, prefix included.

## Scenarios and interventions

### Scenario

`Scenario` is immutable:
- `Scenario.baseline()` has no interventions;
- `s.add(*ivs)` returns a new scenario with the interventions appended;
- `s.interventions` is the tuple.

Two scenarios are equal when their interventions are equal, in order.

Interventions are frozen dataclasses in `arthasim.interventions`, with the signatures of architecture section 14.2. There is one addition: `ExpenseShock` gains `months: int = 0`, matching `IncomeShock`.
- **Decided.** Without a duration, a cost shock could only last for ever.
- Cost if wrong: one optional field.

Dates are ISO strings or `datetime.date`.

### Applying

- `world.apply(iv)` registers an intervention. Each type has an effective date (table below). `apply` raises `ValueError` when that date is before `world.date`.
- `world.run(until, scenario=None)` applies each of the scenario's interventions, then runs.
- `world.set_hook(kind, impl, bank=None)` is `apply(SetHook(kind, impl, bank, date=world.date))`. Before the first day it passes `date=None`, so a world that starts mid-month can swap a module from its first day.

The type checks below happen at `apply`, so a mistake fails before any day runs.

| Intervention | Takes effect | Date rule |
| :--- | :--- | :--- |
| `ParamOverride(param_id, value, date)` | At the start of `date`; `None` means the run's first day | Any day |
| `ChangeRailRule(date, rail, rule, value)` | At the start of `date` | Any day |
| `MacroPath(name, series)` | From its earliest date | Any day |
| `SetPolicyRate(date, change_bp)` | From `date` | Any day |
| `IncomeShock(date, where, kind, rate, months)` | At the month start `date` | Must be the 1st |
| `ExpenseShock(date, where, kind, rate, months)` | At the month start `date` | Must be the 1st |
| `DBTTransfer(scheme, amount, where, dates)` | Enrolment from the 1st of its earliest date's month; credits on each date | Must be applied by that 1st |
| `SetHook(kind, impl, bank, date)` | At the month start `date`; `None` means the run's first day | Must be the 1st |

**Decided.** The behaviour that shocks and module swaps touch is set once a month: life stages, incomes, budgets and medical costs. A shock dated mid-month would have to either wait or redo the month. Requiring the 1st makes the timing explicit. Cost if wrong: a user rounds a date to a month start.

### Order within a day

1. Parameter, rail and macro interventions effective today are applied.
2. On a month start, or the first simulated day, module swaps effective today are made.
3. The modules' monthly hooks run in their order, with intervention effects at fixed points:
   1. `lifecourse`;
   2. income shocks (layoffs, pay cuts, and restoring cuts that end this month);
   3. `income`, `remittances`;
   4. `dbt`, with scenario schemes among its schemes;
   5. `budget`;
   6. expense shocks;
   7. `allowance`, `consumption`, `cash`.
4. The day's intents, settlement and end-of-day jobs run, as today.

### Who `where` selects

`where` is a SQL boolean expression over one row per person, evaluated on the month's state after the life course has run. It accepts `==` as well as `=`, `and`, `or`, `not`, `in (...)` and comparisons.

The columns use the names of `persons` and `entity_state_monthly`:

| Column | Meaning |
| :--- | :--- |
| `entity_id`, `household_id` | Ids |
| `age`, `sex` (`'F'`/`'M'`), `education` | Demographics |
| `district` (name), `district_kind` (`'metro'`/`'rural'`) | Place |
| `life_stage` (`'farm'`, `'salaried'`, ...), `helper`, `sector` | Work |
| `monthly_income_paise` | Earned income |
| `household_income_paise` | Members' earned income |
| `transfer_income_paise` | DBT monthly value |
| `has_account`, `has_upi`, `has_card`, `primary_bank` | Banking |
| `bpl` | Household on the BPL list |

An unknown column or a syntax error raises `ValueError` at `apply`, checked against the world's current state. The architecture's example `occupation == 'farmer'` is written `life_stage == 'farm'` here.

### Randomness

An intervention's draws use streams named `iv.<type>.<digest>`. The digest is a hash of the intervention's fields, so two arms with the same intervention make the same draws and different interventions make different ones. Draws are keyed on the entity and the first day of the month.

The baseline's streams are untouched. That is what keeps arms paired.

### `ParamOverride`

- From its date, `world.params` is the registry with the one value changed. Every module reads it from that day on.
- No module may keep a parameter value across days. Two places do today:
  - `Consumption` caches its category shares, so its cache is keyed on the registry object as well.
  - The life course's `Targets` (`life/targets.py`) keeps the build-time registry and caches by fiscal year. It feeds `life.layoff.employer_shock_sigma` to `firm_shock` and the gig share. It reads the live registry instead, and the world clears its cache when a parameter changes.
  - A run with no scenario gives the same output as before.
- The world records which parameters are read on each simulated day. `interventions_log.read_after` is true when the parameter was read on or after the override's date. A false value means the override had no effect, typically because the parameter is read only at build, and `ExperimentResult.report` says so.
- An unknown id raises `KeyError` at `apply`.

### `ChangeRailRule`

A named alias for a registry parameter.

| `rail` | `rule` | Parameter | `value` |
| :--- | :--- | :--- | :--- |
| `"UPI"` | `"per_txn_limit"` | `rail.upi.limit_paise` | Paise per transaction; applies to UPI P2P and P2M |

Any other pair raises `ValueError`, listing the supported pairs.

**Decided.** This is the one rail rule the model enforces: the settlement kernel's limit decline, and the rail choices of spending, allowances and remittances. Fees, cooling periods and cut-offs do not exist yet, and later phases add rows to this table.

### Macro paths, `MacroPath` and `SetPolicyRate`

There are two series. Each is a registry row whose value maps an effective date to a value, holding until the next date and carried forward past the last.

| Series | Registry id | Unit | Default path | Status |
| :--- | :--- | :--- | :--- | :--- |
| `policy_rate` | `macro.policy_rate` | % a year, RBI repo rate | See below | verified (statements pinned in `docs/sources/macro.md`) |
| `cpi_inflation` | `macro.cpi_inflation` | %, all-India CPI (Combined), year on year | See below | verified |

The repo rate steps are:
- 6.25% from 7 February 2025;
- 6.00% from 9 April 2025;
- 5.50% from 6 June 2025;
- 5.25% from 5 December 2025.

The rate was held at 5.25% in February and April 2026.

CPI inflation, dated at the 1st of each month:

| Month | 2025-04 | 05 | 06 | 07 | 08 | 09 | 10 | 11 | 12 | 2026-01 | 02 | 03 |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| % | 3.16 | 2.82 | 2.10 | 1.61 | 2.07 | 1.44 | 0.25 | 0.71 | 1.33 | 2.75 | 3.21 | 3.40 |

- April to December 2025 are on base 2012=100, from the time series in MoSPI's December 2025 release; December is provisional there.
- January to March 2026 are on the new base 2024=100: January (provisional) from MoSPI's January 2026 release, February (final) and March (provisional) from its March 2026 release.
- MoSPI publishes no linked series across the change of base. The values are as published.

Two more tables follow the series:
- **`macro_paths`**, a run-metadata table with columns `series`, `date` and `value`, holds the paths in force: the defaults, with every `MacroPath` and `SetPolicyRate` that has taken effect.
- **`world.macro(series, day)`** returns the value in force on a day. Nothing calls it in phase 1 except tests.

The two interventions act on the series as follows:
- **`MacroPath(name, series)`** replaces the named series from its earliest date on; the history before that date is kept. An unknown name raises `ValueError`.
- **`SetPolicyRate(date, change_bp)`** adds `change_bp / 100` percentage points to every `policy_rate` value in force from `date` on. A step at `date` is created if none exists. A rate must be in force on `date`, in the series as the interventions before it will leave it; `apply` and `Experiment` construction refuse one dated before the series' first step.

Both set `read_after` like a parameter override. In phase 1 it is always false, and the report says that nothing reads the series yet.

### `IncomeShock`

There are two kinds of income shock. Any other kind raises `ValueError`.

**`kind="layoff"`.** In the month starting `date`, after the life course has run:
- each selected person who is salaried is laid off with probability `rate`, drawn per person;
- selected people who are not salaried are left alone, and the log counts them;
- a laid-off person moves to `seeking` exactly as the life course moves a salaried leaver: `LAID_OFF` event, employer cleared, income 0, and `last_stage`, `last_income` and `last_sector` kept, so the life course's return rules apply to them;
- payrolls are recomputed.

**Alignment must not undo it.** Every month the life course aligns each (district, sex, age group) cell exactly to its PLFS targets. Unchanged, the next month's alignment would re-hire people to refill the cell's salaried target.
- So, from the month after the shock, for `months − 1` further months (for the rest of the run when `months` is 0), each cell's salaried target falls, and its seeking target rises, by the number of people laid off from that cell.
- When the shock ends, the shift goes and alignment re-hires as usual.
- **Decided.**
  - PLFS counts a job loser who looks for work as unemployed, so the shift goes to `seeking`.
  - The life course's own transitions then move some on, for example to casual work. During COVID many salaried job losers fell back on informal work (Azim Premji University, State of Working India 2021).
  - Cost if wrong: unemployment rises in the shocked cells, and informal work rises somewhat less than it would.

**`kind="pay_cut"`.** In the month starting `date`, after the life course has run:
- each selected person whose life stage is salaried, self-employed, gig, farm or casual, and who is not a helper, has their earned income multiplied by `1 − rate`, rounded to the paisa;
- for salaried people, salary is cut too, since the model keeps the two equal;
- a `PAY_CUT` event is written.

At the start of the month `months` later, after the life course:
- the cut is reversed (income divided by `1 − rate`, rounded) for each person still in the same life stage whose pay has not been reset since, by a job switch, a hire, or an own-account or helper flip;
- raises in between are kept, because a raise multiplies the pay;
- a `PAY_RESTORED` event is written;
- with `months = 0` the cut lasts for the rest of the run.

**Decided**: the pay cut is a level cut that is reversed at the end. Cost if wrong: small rounding differences.

`rate` must be in (0, 1).
- A 100% cut cannot be reversed by dividing.
- It would also leave salaried people with a zero salary credit, which the intents check rejects.
- An unpaid furlough is the layoff kind's job.

For layoffs, `rate` must be in (0, 1]. `PAY_CUT` and `PAY_RESTORED` join the event names. Events from interventions continue the life course's event-id counter.

### `ExpenseShock`

`kind="medical"` is the only kind in phase 1. Any other kind raises `ValueError`, because the model has no other cost category to pay.

- **Who.** A household is selected when any member matches `where`.
- **What happens.** In each month from `date`, for `months` months (for the rest of the run when 0), each selected household has an extra medical shock with probability `rate`, drawn per household and month.
  - The extra shock uses the same cost distribution (`shock.medical_median_paise`, `shock.medical_sigma`) and stress bonus as the baseline shock.
  - It adds to `medical_due`. It applies after `budget`, so the month's baseline shock is drawn as before.
  - `rate` must be in [0, 1].
- **Decided**: the shock is extra, not a replacement. The baseline draws stay paired between arms, and a household can have both shocks in one month, as it could have two illnesses. Cost if wrong: a slightly higher total incidence than a replacement rule would give.

### `DBTTransfer`

A scheme that the `dbt` module holds alongside its three built-in schemes.

- **`scheme`.** A name, written to `truth_dbt_monthly.scheme` as given. It must not equal a built-in scheme or another scenario scheme in the world.
- **`amount`.** Rupees per credit, in whole paise.
- **`where`.** Evaluated each month, like the built-in rules.
- **Enrolment.** Everyone selected is enrolled (coverage 1), in each month from the month of the earliest date to the month of the latest. Narrowing who is paid is what `where` is for.
- **Accounts.** An enrolled payee without a bank account opens one that month, as for the built-in schemes.
- **Credits.** Every enrolled payee is credited on each date, by APBS, with slots 24 to 39 as for the other schemes, and a new purpose `DBT_OTHER = 22`. The slot and second are drawn from the intervention's own streams (`<stream>.slot`, `<stream>.offset`), so a person also paid by a built-in scheme that day gets a different time.
  - In the views, APBS narrations name `DBT_OTHER`.
  - The scheme's name is in the truth layer only.
- **Transfer income.** The scheme counts as transfer income in the month it pays, at the amount paid that month. It counts nothing in other months.
  - **Decided.** A one-off tranche has no monthly value to smooth over a year.
  - Recipients of the 2020 PMGKY transfers to women's Jan Dhan accounts mostly withdrew the money soon after it arrived. Vidhi Legal Policy's survey found 94% of recipients withdrew it; RCRC's April 2020 rapid survey found 76% had already withdrawn.
  - Cost if wrong: the spending response is concentrated in the pay month rather than spread out.
- **Spike worlds.** A spike world (tier XS) has no government, so `DBTTransfer`, `IncomeShock` and `ExpenseShock` raise `ValueError` there.

### `SetHook`

- **`kind="module"`.** `impl` is a `BehaviourModule` whose `name` matches an existing module. From the month start `date`, it replaces that module in the same position.
  - `bank` must be `None`.
  - The replaced module's pending tables are written first.
  - `impl` must pickle, for checkpoints and workers.
  - **Decided.** Section 11's hook kinds have no call site in phase 1. Swapping a behaviour module is the phase 1 way to "change behaviour from a date" in one arm, for example a different consumption rule.
- **Section 11's kinds** (`fraud_control`, `credit_policy`, `card_policy`, `recommender`) raise `NotImplementedError`, naming the phase that brings each one.

### `interventions_log`

A run-metadata table, rewritten at each flush, with one row per applied intervention:

| Column | Type | Meaning |
| :--- | :--- | :--- |
| `seq` | Int64 | Order applied |
| `kind` | String | Class name |
| `effective` | Date | When it took or takes effect |
| `ends` | Date, nullable | When it stops, for shocks with `months` |
| `details` | String | JSON of the fields. A `SetHook` impl is shown by its class's qualified name. |
| `affected` | Int64, nullable | People laid off or cut, households selected, or payees in the first pay month; null until the intervention has taken effect |
| `read_after` | Boolean, nullable | For parameter, rail and macro interventions, see `ParamOverride` |

`macro_paths` and `interventions_log` join the run-metadata tables. They are written for every population and spike run, and `interventions_log` is empty when nothing was applied. Content hashes cover both.

## Experiments

```python
exp = Experiment(config, baseline, {"dbt_2000": treat}, seeds=range(1, 11),
                 intervene_at="2025-11-01", end="2025-12-31", path=None)
res = exp.run(workers=4)
res.effect("cash_withdrawal", by="month", fill=0)
sweep = exp.sweep("consumption.buffer_target_months", [2, 3, 4, 6], workers=4)
```

### Rules checked at construction

- `intervene_at` is `config.start` or the first of a month after it, and before `end`.
- Arm names are unique, not `"baseline"`, and contain only letters, digits, `_` and `-`.
- Every arm's interventions effective before `intervene_at` equal the baseline's, in order. Otherwise the shared prefix would be wrong.
- Every intervention must pass its date rule as if applied on `intervene_at`.

### One seed

1. Build the world for (`config`, seed) with checkpoints off, into `<exp>/baseline-seed<s>/`.
2. Apply the baseline's interventions effective before `intervene_at`, and run to the day before `intervene_at`.
3. For each treatment, in the order given:
   1. fork the world into `<exp>/<arm>-seed<s>/`;
   2. apply the arm's interventions effective on or after `intervene_at`;
   3. run the fork to `end`;
   4. drop the fork from memory.
4. Apply the baseline's own interventions effective on or after `intervene_at` to the prefix world, and run it on to `end`. It is the baseline arm.

At most two worlds are in memory at once.

### Workers

`run(workers=n)` runs seeds in a process pool with the `spawn` start method, one task per seed.
- Results do not depend on `n`, because each seed's runs depend only on the seed.
- A task's memory is about two worlds, about 1.5 GB at tier S.
- Interventions and metrics must pickle.

### Folders and reopening

- `path` defaults to `<config.out_dir>/experiment-<digest>`. The digest is 12 hex characters of a SHA-256 over the config hash, the scenarios' JSON (with the SHA-256 of each swapped module's pickle), the seeds, `intervene_at` and `end`. An existing folder raises `FileExistsError`.
- `experiment.json` records the arms, their interventions, the seeds, the dates, the config without the secret, and each run's folder.
- `ExperimentResult.open(path)` reopens a finished experiment.

### The window an effect measures

By default `effect` and `report` measure the arms' window, from `intervene_at` to `end`. Pass `window="run"` to measure whole runs instead.
- **Decided.** The prefix is identical in every arm. It adds nothing to a difference in a sum, but it dilutes rates such as `decline_rate`, and it dilutes the `baseline`, `treatment` and `relative` columns. In the results-doc experiment, the prefix is 7 of 9 months.
- Cost if wrong: none; both windows are available.

**`run.window(start, end)`** returns a `Run` whose `tables`, `table` and `sql` see fact tables only for the months from `start` to `end`. Dimension tables are unchanged.
- `intervene_at` is always a month start, so filtering by month partition is exact.
- Every metric that reads through `run.table` or `run.sql` is windowed without change. That covers the five built-ins and registered user metrics.

### `effect(metric, by=None, fill=None, level=0.95, window="arms", **kwargs)`

1. For each run, compute `run.metric(metric, by=by, **kwargs)`, on the windowed run unless `window="run"`. When `by` is None, `by` is not passed. The result's grouping columns are every column but `value`.
2. Within each seed, join each treatment's frame to the baseline's on the grouping columns, outer join. A group missing from one side takes `fill`. With `fill=None`, that seed gives no difference for the group.
3. Across seeds, for each arm and group:
   - `baseline` and `treatment`: the means over seeds;
   - `effect`: the mean paired difference d̄;
   - `lo`, `hi`: d̄ ∓ t(1 − (1 − level)/2, n − 1) · s_d / √n, null when n < 2;
   - `n`: the seeds that contributed;
   - `relative`: d̄ / mean baseline, null when that is 0.
4. Return one row per arm and group: `arm`, the grouping columns, then the columns above.

- **Decided**: a Student-t interval on per-seed paired differences.
  - The seeds are independent draws of the whole world: population, behaviour, everything.
  - Pairing within a seed removes the noise the arms share.
  - Section 12 asks for the "mean paired difference per metric with an interval".
  - Cost if wrong: with few seeds and skewed differences, the interval's coverage is off. The report states n.
- The t quantile is computed in-house, so the plan adds no dependency. It is tested against tabulated values to 1e-4.
- `fill=0` is right for counts and sums (`txn_volume`, `consumption`, `cash_withdrawal`, `deposit_balance`). It is wrong for rates, hence no default.

### `sweep(param_id, values, workers=1)`

For each value:
- the experiment is rerun with `config.with_params(param_id=value)`, into `<exp>/sweep-<param_id>/<value index>/`;
- the prefix is rebuilt for each value, because the parameter applies from the build.

`effect` on a sweep result has a `param_value` column first. It is numeric when every value is numeric, otherwise text.

### Other result calls

- **`runs(arm)`** returns the arm's `Run`s, in seed order.
- **`report(path, metrics=None, window="arms")`** writes Markdown:
  - the config, seeds, dates, the window measured, and each arm's interventions;
  - for each metric (default: the five built-ins, ungrouped, `fill=0` for the four sums), the effect table;
  - each intervention's `affected` and `read_after`, with a line for every one that had no effect;
  - the `assumption`-status registry parameters in the runs' `params_read`, with their sources.

## Parameters

There are two new registry rows, `macro.policy_rate` and `macro.cpi_inflation`. The row-count pins in `tests/test_build_1b.py` and `tests/test_life_sources.py` move from 132 to 134. Sources go in `docs/sources/macro.md`.

## What other parts see

| Part | Change |
| :--- | :--- |
| `world.py` | `save`, `load`, `fork`, `apply`, `set_hook`, `macro`, and `run(scenario=)`. Monthly checkpoints, intervention activation, the manifest's new fields, `Run.fork_at` and `Run.window`. Atomic rewrites of the manifest. |
| `life/targets.py`, `life/jobs.py` | `Targets` reads the live registry; its cache clears when a parameter changes |
| `store/parquet.py`, `store/hashing.py` | Atomic `write_dimension`; a running hash rebuilt from disk; two new run-metadata tables |
| `params.py` | Read tracking; date-stepped series values |
| `modules/lifecourse.py` | Alignment targets plus active layoff shifts; intervention events continue the counter |
| `modules/dbt.py`, `dbt/schemes.py` | Schemes that pickle (no lambdas); scenario schemes; transfer income by pay month for scenario schemes |
| `modules/budget.py`, `modules/spending.py` | An expense-shock point after `budget`; `Consumption`'s cache keyed on the registry and not pickled |
| `engine/intents.py`, `views.py` | `Purpose.DBT_OTHER = 22`; APBS narration names it |
| `life/events.py` | `PAY_CUT` and `PAY_RESTORED` |
| New: `interventions.py`, `scenario.py`, `experiment.py`, `where.py` (or as the builder lays them out) | Interventions, `Scenario`, `Experiment`, `ExperimentResult`, the `where` evaluator, the t quantile |
| `arthasim/__init__.py` | Exports `Scenario`, `Experiment`, `ExperimentResult`, `interventions` |
| `scripts/bench.py` | Reports checkpoint seconds and MB; otherwise unchanged |
| Tests | Row-count pins; new tests below |

## Success measure

**Fast tests:**
- Save at a month end, load, and run on: every Parquet file is byte-identical to an uninterrupted run's, and the manifests' `content_hash` are equal. The same holds for `fork` and for `run.fork_at`. This covers a population world (crossing two month ends) and a spike world.
- `save` or `fork` mid-month raises an error.
- A checkpoint made with a release secret contains neither the secret nor the derived keys, as bytes or as hex. Loading it without the secret, or with a wrong one, raises an error.
- After a fork, the parent continuing does not change any file the child sees, and the reverse.
- Each intervention's semantics, at a small population world:
  - Override: a parameter changes on its date, and `read_after` is false for a build-only parameter.
  - Rail rule: the UPI limit changes on its date.
  - Macro: `MacroPath` and `SetPolicyRate` change `macro_paths` and `world.macro`.
  - Layoff: the right people are laid off, and alignment keeps the cell's salaried count down for `months` and then recovers.
  - Pay cut: the cut is applied and then restored, keeping a raise in between.
  - Expense shock: medical costs rise only for selected households.
  - DBT: payees are paid on the dates, accounts are opened, and transfer income counts in the pay month.
  - Module swap: the replacement runs from its month start.
  - Errors: each date rule and type check raises.
- A `where` with an unknown column raises an error.
- Experiments:
  - The baseline arm's content hashes equal a plain run's.
  - A treatment arm's months before `intervene_at` are identical to the baseline's.
  - An intervention that changes nothing (an override to the same value) gives effect 0, with interval [0, 0].
  - `workers=1` and `workers=2` give identical results.
  - `sweep` gives one block per value.
  - `ExperimentResult.open` reads back what `run` returned.
- The t quantile matches tabulated values, and the interval formula is checked on fixed differences.

**A slow gate (`tests/test_gate_1d2.py`):**
- tier S, seed 7, from 1 April 2025;
- run to 31 July 2025 uninterrupted; and run to 31 May 2025, save, load and run on to 31 July 2025: every data file is identical;
- a two-seed experiment with a `DBTTransfer` to own-account farmers on 15 June 2025, intervening on 1 June and ending on 31 July: the effect on APBS credit count equals the payees credited, and the effect on cash withdrawals is reported with an interval.

**Results doc (`docs/phase1d2_results.md`):** every figure re-queried.
- A paired experiment at tier S:
  - ₹2,000 to every own-account farmer (`life_stage == 'farm' and not helper`) on 15 November 2025;
  - intervening on 1 November 2025 and ending on 31 December 2025;
  - seeds 1 to 10.
  - It reports the effect on cash withdrawals (total, and by month and district), on consumption and on funds declines, each with its interval.
- The checkpoint demonstration at tier S:
  - a run saved at a month end and resumed, against an uninterrupted run;
  - the hashes of every data file, which must all match;
  - the manifest fields that differ (run id, source label, wall time, `forked_from`).
- Costs:
  - checkpoint size and time;
  - load time, including re-hashing the prefix;
  - fork time;
  - the experiment's wall time with 1 and 4 workers, and peak memory.
- The bench at 90 days, before and after: every content hash of a table `main` writes is unchanged, with the new tables listed.

## Left to the builder

- File layout, and the exact internal protocol interventions use to act at their points in the day.
- The format of `details` JSON and of the report's Markdown.
- How layoffs reuse the life course's leaver code, and how pay-cut records are kept on state.
- The `where` evaluator (DuckDB or Polars SQL over a per-person frame), provided it accepts the operators listed.
- Whether `checkpoint.json` content hashes are recomputed or copied from the live store.
