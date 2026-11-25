# Plan 1e, calibration and validation: design

24 November 2026.

**Status.**
- The project owner asked for plan 1e and handed every decision to this session, with a standing instruction: decide, ground decisions in open data, and record each one as a `Ruling:` in the ledger. The roadmap row (`docs/superpowers/plans/2026-11-15-arthasim-phase-0-spike.md`) reads: "Pin appendix A to primary sources, `calibrate`, `validate`, acceptance checks, tier S gate".
- Decisions taken under that instruction are marked **Decided**, each with its source or reason and its cost if wrong.
- Source notes with URLs, tables and pages are in `docs/sources/calibration.md`, which this plan adds.

## Intent

Phase 1 exits when "Phase 1 acceptance checks pass at tier S" (architecture section 18). Section 15 says how: every number is a registry entry with a source and a status; free parameters are fitted by simulation against target entries; holdouts are checked after the fit and never fitted; and section 15.3 lists the acceptance checks.

Until now the registry has 134 rows, all of them inputs. None is a target or a holdout, and most are placeholders from plans 1a and 1b. Earlier results already show where the model is off: plan 1d-1 found that "simulated incomes run high", and plan 1b-2 left "the calibration gaps" for this plan.

Plan 1e adds:
- **Pinned sources.** Every registry row that can have a primary Indian source names it: document, table, page, year and URL. Its `status` says whether the figure was read in that document (`verified`), taken from somewhere weaker (`unverified`), or chosen here (`assumption`). The appendix A rows enter the registry with the same treatment.
- **`calibrate(config, params, ...) -> CalibrationResult`.** It fits free parameters by simulation. An Optuna sampler proposes values; each proposal runs three-month worlds for seeds 1, 2 and 3 and is scored against target entries. It keeps the fitted set, the scores and the registry version.
- **`run.validate(suite="core") -> ValidationReport`.** It runs the phase 1 rows of section 15.3 against a finished run: hard checks, target checks and holdouts. It writes the result into the run as the data product `validation_report`.
- **A tier S gate.** A slow test runs the core suite on a calibrated tier S run.

## What exists today

Measured on `main` at `29dd4a6` (tier S, 90 days, seed 7, the bench run), May and June 2025:

| | Simulated | Published |
| :--- | ---: | ---: |
| Mean monthly pay, salaried, metro / rural | ₹58,359 / ₹32,628 | PLFS 2025 regular wage, urban / rural: ₹26,247 / ₹17,841 |
| Mean monthly income, self-employed, metro / rural | ₹48,677 / ₹26,805 | PLFS 2025, gross, last 30 days: ₹23,012 / ₹12,266 |
| MPCE, metro / rural | ₹14,203 to ₹14,717 / ₹5,642 to ₹5,726 | HCES 2023-24 urban / rural: see below |
| UPI payments per person per month, metro / rural | 14.9 / 3.8 | NPCI, see below |
| Zero-balance person deposit accounts | about 0.1% | PMJDY, see below |
| Salary credits by day of month | spread over days 1–28 (employer paydays are drawn uniformly) | — |

Other facts the design rests on:
- **Tier XS is the spike builder.** `Config.tier("XS")` has no population, life course or banking build, so it cannot be calibrated. Section 5.4 names XS as the size for "calibration trials".
- **A 10,000-person population world runs three months in about 3.5 s**, build included (two runs, seeds 1 and 2). The tier S bench takes 25 s for 90 days.
- **Every run already checks the section 7.3 invariants each day** and stops on a failure. A finished run is evidence that they held, but nothing re-checks a stored run.
- **The registry's `version()`** hashes ids and values, not sources or statuses. Pinning a source does not change it; adding rows or changing values does.
- **Content hashes cover tables, not the registry.** Adding registry rows changes the manifest's `registry_version` and nothing in the bench's 20 content hashes.

## Goals

1. Every registry row has a source with document, table or section, year and URL where a primary source exists, and an honest `status` and `role`. The appendix A rows are in the registry.
2. `calibrate(config, params, targets=None, trials=200, seeds=(1, 2, 3), ...)` fits free parameters on three-month runs and returns a `CalibrationResult` with `best`, `apply(config)`, `report(path)` and `save(path)`. Results do not depend on the number of worker processes.
3. `run.validate(suite="core")` returns a `ValidationReport` with `passed`, `table()` and `failures()`, and writes the table `validation_report` into the run folder.
4. A committed calibration (`params/calibration/fitted.yaml`) fitted on 10,000-person worlds, and a slow gate that validates a full tier S run with it.
5. `scripts/bench.py --tier S --days 90 --seed 7` keeps all 20 content hashes.

## Non-goals

- New behaviour. Where a check fails because the model has no mechanism for it (a festival, accounts left unused), the check reports the failure and the results say so. Building the mechanism is later work.
- Phase 2 to 4 checks (fraud, credit, investments), the face-validity review of 50 traces and the transfer test. Their appendix A rows are pinned, but nothing checks them.
- Changing registry defaults to the fitted values. The fitted set is applied explicitly (see "Where the fitted set lives").
- Re-deriving inputs that are placeholders by design (attribute weights, trait shapes, bank archetypes). They stay `assumption`.

Anti-goals, outcomes that would be failures even if the code ran:
- A row marked `verified` whose figure was not read in the document it names.
- A number in the registry, the results or the spec that no source or derivation supports.
- Tolerances chosen after seeing the calibrated run, to make checks pass. Every tolerance is fixed in this spec and the suite file before the gate's first run.
- A gate that hides a failing check. A check that fails stays a failure in the report, whatever the gate does with it.
- A calibration whose result depends on the worker count.
- A default run (no overrides) whose output changes.

## Approaches considered

### Where targets and checks live

| Approach | Trade-off | Verdict |
| :--- | :--- | :--- |
| **A. Target values in the registry; the suite in a YAML file; statistics in one Python module that both `calibrate` and `validate` use.** | Section 15.1 already says targets are registry rows. The suite file (`params/validation/core.yaml`) names each check, the target row it compares with, the statistic, the comparison and the tolerance, with a reason for each tolerance, where a reviewer can read them in one place. A statistic is computed one way for fitting and for checking. | **Decided** |
| B. Checks as Python classes, tolerances as constants. | Fewer files, but tolerances hide in code, and the fitted loss and the checks could drift apart. | Dropped |
| C. Targets in their own file, apart from the registry. | Splits "every number the model uses" across two places, against section 15.1. | Dropped |

### The optimiser

| Approach | Trade-off | Verdict |
| :--- | :--- | :--- |
| **1. Optuna's TPE sampler, seeded, trials one after another; each trial's seeds run in parallel.** | Section 16 names Optuna. A seeded TPE study asked one trial at a time is deterministic, so with the seeds of a trial spread over workers the result does not depend on the worker count. It adds a dependency (Optuna 5.1 and its own: SQLAlchemy, alembic, colorlog, tqdm). A different Optuna version may propose different values, so the fitted file records the version. | **Decided** |
| 2. An in-house sampler (the project wrote its own t interval rather than add SciPy). | No dependency, but a TPE or Gaussian-process sampler is a few hundred lines to get right and test, for no gain in the result. | Dropped |
| 3. Optuna with trials in parallel. | Faster with many workers, but the proposals then depend on which trials finished first, so the result would depend on the worker count (an anti-goal). | Dropped |

### Where the fitted set lives

| Approach | Trade-off | Verdict |
| :--- | :--- | :--- |
| **I. A committed file, `params/calibration/fitted.yaml`, applied as parameter overrides (`CalibrationResult.load(path).apply(config)`).** | Default runs, the bench hashes and every earlier result stay as they are. The calibration's effect is visible as a diff between two runs. A user must apply it on purpose. | **Decided** |
| II. Write the fitted values into the registry's defaults. | Every default run becomes the calibrated one, which is where the project should end up. But it changes all 20 bench hashes and every result measured so far, in the same change that introduces the checks that judge it. | Dropped for this plan; listed as a follow-up for the owner |

## The registry

### Rows

Each row keeps the fields it has today: `id`, `value`, `unit`, `as_of`, `source`, `status`, `role`. The source field of a pinned row names the document, the table or section, the page, and the URL, or points to the row's section in `docs/sources/calibration.md` when that would not fit.

- `verified`: the figure was read in the primary document named, by this plan or an earlier one (with its date of reading in the source notes).
- `unverified`: the figure comes from a weaker source (a news report, a summary) or could not be opened; the notes say which.
- `assumption`: chosen or derived here, with the reasoning in the source notes.

A ratio of two counts read in the same table keeps `verified`, with the arithmetic in the notes. A figure that needs a modelling choice (uprating by CPI, interpolating a population, mapping one definition onto another) is `assumption` even when every input is `verified`, and the derivation is written out.

### What changes

- **Existing rows.** Rows with a source label are checked and their status set. A row whose value disagrees with its primary source is reported in the source notes; its value changes only by a ruling, since inputs change default runs.
- **New target and holdout rows,** one for each figure a core check compares with (section "The core suite").
- **Appendix A rows.** Each enters with its pinned source, or `unverified` with a note when the cited figure could not be found. Rows for phases 2 to 4 enter with role `target` and nothing checks them in phase 1.
- **Row-count pins.** Four tests pin the row count at 134 (`test_life_sources`, `test_macro`, `test_dbt_schemes`, `test_build_1b`). They move to the new count.
- **A test of the registry itself** (`tests/test_registry_sources.py`): every `target` or `holdout` row has a URL in its source or a pointer to the source notes; every `verified` row names a document and a table or section; every row referenced by `params/validation/core.yaml` and `params/calibration/space.yaml` exists and has the role the file needs.

## Statistics

`arthasim/statistics.py` holds one function per simulated statistic, `fn(run) -> dict[str, float]`, keyed by component: `rural` and `urban`, or `all`. Both `calibrate` and `validate` call them, on the same window of the run.

- **Area.** The metro archetype stands for urban India and the rural archetype for rural India, in every comparison.
  - **Decided.** The life course already aligns the metro district to PLFS urban rates and the rural district to PLFS rural rates (plan 1b-2).
  - Cost if wrong: a metro district is richer than urban India's average, so calibration pulls the metro archetype toward an average town. That is what the targets ask for.
- **Window.** Statistics read the complete months from the run's second month to its last complete month: May to November 2025 in a calibration trial and in the gate.
  - **Decided.** The first month is the build settling. Over April to June in the bench run, the median household spends 63% of income in April and 71% to 73% after.
  - Cost if wrong: one month of a three-month trial is not scored.
- **National figures.** A target published for all of India (UPI volume, card and ATM counts) is compared with the simulated rate per adult, as the mean of the urban and rural rates weighted by India's urban and rural shares of adults (see the source notes).
  - **Decided.** The archetypes' 60:40 metro split is a tier S setting, not India's.
  - Cost if wrong: a national rate weighted the wrong way.
- **Per adult.** Persons are adults aged 18 and over (section 5.1). National counts are divided by India's population aged 18 and over (source notes).

## Calibration

### Call

```python
calibrate(config, params=None, targets=None, trials=200, seeds=(1, 2, 3), months=8,
          workers=1, sampler_seed=0, path=None) -> CalibrationResult
```

- `config`: the config each trial builds, with its overrides applied on top. The committed calibration uses `Config.tier("S", persons=10_000)`.
  - **Decided.** Section 15.2 says "tier XS or S", and section 5.4 names XS for calibration trials, but `Config.tier("XS")` is the spike builder, which has none of the behaviour being fitted. A tier S config at 10,000 persons is the XS size with the population builder.
  - Cost if wrong: fitted values that do not carry from 10,000 to 100,000 persons. The gate checks them at 100,000.
- `params`: the free parameters. `None` takes the default set in `params/calibration/space.yaml`. A list of ids takes their bounds from that file; a `Free(...)` gives its own.
- `targets`: check ids from the core suite to fit. `None` takes the default list in `space.yaml`.
- `trials`, `seeds`: section 14.2's defaults.
- `months`: the length of each trial run from `config.start`; the default 8 runs April to November 2025, the gate's own span, and scores May to November.
  - **Decided**, against section 15.2's "three-month runs". The model is not stationary over months. In a 10,000-person world (seed 1, base pay halved), basic accounts' mean month-end balance rose from ₹5,975 in May to ₹9,145 in August, and monthly spending rose 20% from May to November: households open with 0.8 months of income in the bank against a buffer target of 3 months, so they save and their budgets rise as buffers fill. A fit to May and June would be scored on levels the gate's May–November window does not have.
  - Cost if wrong: trials take about 2.5 times as long (about 9 s a seed at 10,000 persons). The drift itself remains a property of the model, reported month by month in the results.
- `workers`: processes, spawned. Each trial runs its seeds in parallel; trials run one after another, so the result does not depend on `workers`.
- `sampler_seed`: the TPE sampler's seed.
- `path`: a folder for the trial runs, removed run by run after scoring. Default: a temporary folder under `config.out_dir`.

### A free parameter

`Free(id, low, high, log=False, key=None, scale=False)`:
- a scalar row takes the proposed value;
- `key="casual"` sets one entry of a mapping row, such as `earn.stage_multiplier`;
- `scale=True` multiplies every number in a list or mapping row by the proposed value, such as `consumption.purchases_per_month`.

The override passed to the trial's config is the row's whole new value. Two free parameters on one row compose.

### A trial

For each seed, build the world (`checkpoints=False`), run `months` months from `config.start`, compute the target statistics on the window, and delete the run folder. The trial's statistic is the mean over seeds.

The score of one target component is its error in units of its tolerance:
- relative tolerance `t`: `(simulated / target - 1) / t`;
- absolute tolerance `t`: `(simulated - target) / t`.

The trial's loss is the mean of the squared scores over every component of every target. A component exactly at its tolerance scores 1.

**Decided.** Scaling by the check's own tolerance makes a percentage point of food share and a rupee of MPCE comparable, and ties the fit to the same yardstick the check uses. Cost if wrong: targets with tight tolerances pull harder, which is the intent.

### The result

`CalibrationResult` holds:
- `best`: the override values of the best trial (`{registry id: value}`);
- `free`: the proposed value of each free parameter in that trial;
- `loss` and `scores` (per target component, best trial);
- `trials`: a frame with every trial's proposals, statistics and loss;
- `registry_version` (of the registry before overrides), `config` (without the secret), `seeds`, `months`, `sampler_seed`, `optuna_version`, `arthasim_version`.

Methods:
- `apply(config)` returns `config.with_params(**best)`;
- `save(path)` writes YAML (the trials frame beside it as Parquet), and `CalibrationResult.load(path)` reads it back;
- `report(path)` writes Markdown: the free parameters with bounds and fitted values, each target with its published value, simulated value and score, and the loss path.

A calibrated run's manifest records its config, overrides included (a new `config` field, without the secret), so the fitted set travels with every run made from it.

`scripts/calibrate.py` runs the default calibration and writes `params/calibration/fitted.yaml` and its report.

### The default free parameters and targets (`params/calibration/space.yaml`)

Sixteen parameters, each a placeholder (`assumption`) that moves a fitted target. The first search used the first fourteen, with `earn.sigma` from 0.2 and `open.deposit_months_of_income` from 0.1; see "Two stages" below.

| Parameter | Bounds | Scale | Moves |
| :--- | :--- | :--- | :--- |
| `earn.base_paise` | ₹3,000 to ₹15,000 | log | every earnings level, MPCE |
| `earn.premium.metro` | 0 to 0.8 | linear | the urban–rural gap |
| `earn.sigma` | 0.05 to 0.9 | linear | dispersion, the Gini |
| `earn.stage_multiplier`, key `self_employed` | 0.3 to 1.5 | linear | self-employment earnings |
| `earn.stage_multiplier`, key `farm` | 0.2 to 1.2 | linear | self-employment earnings (rural) |
| `earn.stage_multiplier`, key `casual` | 0.2 to 1.2 | linear | casual wages |
| `consumption.spend_share` | 0.5 to 1.0 | linear | MPCE |
| `consumption.purchases_per_month`, every entry scaled | ×0.5 to ×3 | log | payments per person |
| `rail.choice.upi_preference` | 0.3 to 1.0 | linear | UPI's share of purchases |
| `attr.digital.upi_threshold` | 0.1 to 0.8 | linear | who uses UPI |
| `rail.choice.card_preference` | 0.005 to 0.6 | log | debit card use |
| `spike.cash_withdrawal_paise` | ₹1,000 to ₹15,000 | log | ATM withdrawal size and count |
| `open.deposit_months_of_income` | 0.02 to 3 | log | balances |
| `consumption.ticket_sigma` | 0.3 to 1.3 | linear | ticket sizes |
| `earn.return_by_education`, every entry scaled | ×0.3 to ×1.5 | linear | pay dispersion, the Gini |
| `consumption.buffer_target_months` | 0.5 to 6 | log | saving, balances |

Fitted checks: `pay.regular_monthly`, `pay.casual_daily`, `pay.self_employed_monthly`, `consumption.mpce`, `consumption.gini`, `payments.upi_p2m_per_adult`, `payments.debit_card_per_adult`, `payments.atm_per_adult`, `payments.atm_ticket`, `payments.p2m_under_500`, `balances.basic_mean`. Every other target check is validation only; holdouts are never fitted.

**Two stages (decided during the build).** The first search (400 trials, 14 parameters) ended with `earn.sigma` and `open.deposit_months_of_income` within 7% and 3% of their lower bounds, and with the consumption Gini (+2.4 and +3.0 tolerances) and the basic-account balance (+1.3) still above their bands. As the known-gaps rule allows, the search was widened rather than the checks excused: both floors were lowered, the returns to education (as a scale) and the buffer target were added, and a second search of 200 trials ran inside bounds narrowed around the first fit (`calibration.refine`, width 0.25), starting from it, so it cannot end worse. The first search's files are kept as `params/calibration/stage1.*`.

**Decided.** The committed calibration runs 400 trials, not the signature's default of 200: TPE needs more trials as dimensions grow. At about 10 s a trial with three workers (8-month runs), 400 trials take a little over an hour. The first 20 trials are random (`n_startup_trials=20`), and the sampler is multivariate. Cost if wrong: a fit that a longer search would improve; the trials table shows whether the loss was still falling.

## Validation

### Call

`run.validate(suite="core", release_secret=None) -> ValidationReport`. `suite` is a name (`params/validation/<name>.yaml`) or a path. The report is also written into the run folder as `validation_report.parquet`, replacing any earlier one, and `run.table("validation_report")` reads it.
- `validation_report` is run metadata (architecture section 13.2 lists it). It is not part of the manifest's content hashes, since it describes the run rather than being part of it. `Run.tables()` lists it when present, so the truth view and a truth export carry it. It holds no identifier.

### The report

One row per check component:

| Column | Meaning |
| :--- | :--- |
| `suite`, `check`, `kind` | Suite name; check id; `hard`, `target` or `holdout` |
| `component` | `rural`, `urban`, `all`, or a named part (for a hard check, the invariant) |
| `target_id` | The registry row compared with (null for hard checks) |
| `target_status` | That row's status: `verified`, `unverified` or `assumption` |
| `simulated`, `target` | The simulated statistic and the published value it is compared with (after any uprating) |
| `lower`, `upper` | The accepted band |
| `status` | `pass`, `fail` or `skipped` |
| `detail` | What was measured, over which months; why a check was skipped; what failed |
| `gap` | For a check listed as a known gap in the suite file, the ruling's text; else null |

`ValidationReport` has:
- `passed`: true when no check failed (a skipped check does not fail; it is listed);
- `table()`: the frame;
- `failures()`: the failed rows;
- `report(path)`: Markdown with every row, grouped by kind.

### Hard checks

**Ledger invariants (section 7.3), re-checked from the stored tables.** The run checked them every day; this re-checks a stored run from its files, month by month, so a damaged or hand-edited run fails.
1. **Shapes.** Every journal entry matches its kind's shape: `ledger.invariants._check_shapes` on each month's journal and postings, with account types, holders and issuers from the `accounts` table.
2. **Stock and flow.** For every account and month end, opening balance plus postings equals the month-end balance in `balances_monthly`. Within each account, every posting's `balance_after_paise` is the one before plus its delta.
3. **No negative money.** No deposit or cash balance is below zero after any posting.
4. **Bank balance sheets.** For each bank, reserves plus vault cash minus the deposits it issued is the same at every month end as at opening (its equity).
5. **Cash conservation.** Cash held by everyone is the same at every month end as at opening.

The daily flow-matrix checks (invariants 6) need each holder's sector, which no table records; the run's own daily check covers them, and the report says so. Invariant 7 (illicit funds) has nothing to check until phase 2.

**Same seed, same output.** The run's config (from the manifest, with `release_secret` if the run had one) and seed build a fresh world in a temporary folder, which runs to the end of the run's first month. Every fact table's month must hash the same as the run's own month, and every dimension table that does not change during a run (`persons`, `households`, `orgs`, `banks`, `edges`, `geo`, `truth_person_latent`) must hash the same as the run's.
- Skipped, with the reason, for a run that was forked or loaded, has a scenario with an intervention effective in its first month, or had a release secret that was not given.
- **Decided.** One month covers the build and a full monthly cycle (life course, budgets, a pay cycle, bills) at a tenth of the cost of a full rerun. The account tables change during a run and are left out.
- Cost if wrong: a divergence that starts after the first month is not caught here (the split-run tests and the 1d-2 resume test cover later months).

**No synthetic identifier matches a real format** (section 5.3). Every value in these columns is checked:
- `persons.pan_like` against the PAN format (`REAL_FORMATS["pan"]`);
- `persons.uid_token` against the Aadhaar format, and `persons.mobile_token` and `MOBILE` instruments against Indian mobile numbers;
- `BRANCH` instruments against the IFSC format;
- `ACCOUNT_NO` instruments and `bank_customers.customer_no` must not be all digits (real account numbers are 9 to 18 digits);
- `DEBIT_CARD` instruments must not be 16 digits passing the Luhn check;
- `VPA` instruments must end in a handle of the synthetic form `@synNN`.
The patterns are the ones in `build/identifiers.py`, extended by the last three.

### Known gaps

A target or holdout check that the model cannot pass is listed in the suite file with `gap:` and a ruling. It still runs and still fails in the report; `gap` only says why. The gate (below) checks that the list is exact: every failing check is listed, and every listed check fails.

What may be a gap, and what may not:
- **A gap** is a failure whose cause no free parameter reaches: a missing mechanism, or a placeholder input this plan does not change (Goal 5 keeps every input value). Its ruling names the mechanism or the input and the follow-up that would close it.
- **Not a gap:** a fitted check that misses. The calibration may be rerun with a wider search, other bounds or more trials, and each rerun is recorded. If it still misses after that, the miss is recorded as a calibration finding with its own ruling, and only then listed.
- **Predicted before the gate's first run** (from the code, before any calibrated run), so the list is not fitted to the result:
  - `payments.month_start_spike`: employer paydays are drawn uniformly over days 1–28 (`build/pipeline.py`), so no month-start spike can form.
  - `accounts.zero_balance`: every account opens with a deposit (at least `open.deposit_floor_paise`) or, when opened for DBT, receives its credit at once, and automatic withdrawals leave the part of the balance below a whole note; nothing leaves an account at exactly zero for long. (0.09% of basic accounts at the May month end of the uncalibrated bench run, against 9.15%.)
  - `accounts.inoperative` is **not** predicted: on the uncalibrated bench run 28% of basic accounts had no transaction their holder made in May alone, so over seven months the share could fall either side of the band.
  - `labour.ur.educated` and `labour.ur.graduate_15_29`: life stages carry no education gradient beyond the build's priors.
  - `payments.upi_p2p_per_adult`: the model's P2P flows are allowances, remittances and some earnings, not the informal transfers that make up most real P2P.
  - `holdout.festival_uplift`: the model has no festival behaviour.
  - `payments.debit_card_ticket`: the rail choice (`modules/spending.py`, `choose_rail`) does not depend on the amount, so cards carry ordinary tickets (₹316 on the uncalibrated bench run, against about ₹3,300).
  - `payments.p2p_under_500`: the same P2P flows are mostly allowances and earnings, which are large (7% under ₹500 on the bench run, against 59%).
  The gate's first run is compared with this list in the results. The list comes from the code and from the uncalibrated bench run, before any calibrated run.
- **The gate must end green.** A red gate is not an end state. The phase 1 exit criterion ("acceptance checks pass at tier S") is met only for the checks that pass; the results doc states plainly that each listed gap leaves it unmet.

**Decided.** A gate that ignored failures would hide them; a gate that required them to pass would require new behaviour this plan does not build. Listing them in the suite, where the report shows them, keeps the failure visible and the gate honest. Cost if wrong: none to the record; the list must be updated when a gap closes, which the gate enforces.

**Decided.** Target values and the bands derived from them (the festival band is half the measured uplift; the month-start band spans the five months' range) are taken from the source notes as written. If a later re-reading changes a value, its band is re-derived by the same rule, with a ruling.

## The core suite

`params/validation/core.yaml` lists every check below with its kind, target row, statistic, comparison, tolerance and a `why:` for the tolerance. Statistics read the run's complete months from its second month on ("the window": May to November 2025 in the gate), unless a check says otherwise. Rupee figures are per month unless stated. "National" means the rate per adult with urban and rural weighted 0.36 and 0.64 (section "Statistics").

**Decided.** Each tolerance is set from what the comparison can honestly resolve: the published figure's own precision, the gap between its definition and the simulated statistic, and the transfer from the archetype districts to India. None was set from a simulated value. Cost if wrong: a check too loose to catch a real gap, or too tight to pass a sound model; each `why:` says which risk was taken.

### Target checks (labour stocks)

| Check | Target row (source) | Simulated statistic | Band | Why that band |
| :--- | :--- | :--- | :--- | :--- |
| `labour.stages` | the life course's PLFS targets (`params/lifecourse/plfs_2025.yaml`: Table 15 with the CWS bulletins) | For each month, district kind and sex: the largest gap between the simulated share of persons in a life stage and the mean target share of the same persons | ≤ 0.02 | Alignment rounds to whole persons and floors probabilities; 2 points is the size of a month's CWS sampling movement in the bulletins |
| `labour.ur` | `labour.ur.by_area` (PLFS 2025 Highlights Table 3: rural 2.4%, urban 4.8%, ps+ss, 15+) | Seeking ÷ (working + seeking), persons 18+ | ± 1 point | The model's stages follow usual status; persons are 18+ against PLFS's 15+, and 15–17s are mostly students |
| `labour.ur.educated` | `labour.ur.educated` (Statement 17: rural 6.0%, urban 7.2%) | The same among persons with secondary education or more | ± 2 points | Smaller groups than the overall rate |
| `labour.ur.graduate_15_29` | `labour.ur.graduate_15_29` (Table 21: rural 21.5%, urban 23.2%) | The same among graduates aged 18–29 | ± 3 points | Small group; 18–29 against 15–29 |
| `labour.share.regular_salaried` | `labour.share.regular_salaried` (Statement 7: rural 14.1%, urban 47.6% of workers) | Salaried ÷ persons in an earning stage | ± 3 points | All ages against 18+; the model's helper flag |
| `labour.share.self_employed` | `labour.share.self_employed` (Statement 7: rural 62.4%, urban 40.4%) | Self-employed, gig and farm stages ÷ persons in an earning stage | ± 3 points | As above |

### Target checks (pay and consumption)

| Check | Target row | Simulated statistic | Band | Why |
| :--- | :--- | :--- | :--- | :--- |
| `pay.regular_monthly` | PLFS Statement 11: rural ₹17,841, urban ₹26,247 | Mean monthly income of persons in the salaried stage | ± 10% | Large PLFS samples (44,000 and 80,000 employees); fitted |
| `pay.casual_daily` | PLFS Statement 12: rural ₹433, urban ₹549 | Mean monthly income of casual workers ÷ their pay events a month (`income.pay_events_per_month`, 22) | ± 10% | Fitted; the days-worked conversion is the model's own |
| `pay.self_employed_monthly` | PLFS Statement 13: rural ₹12,266, urban ₹23,012 (zero earners left out) | Mean monthly income of persons in the self-employed, gig and farm stages with income above zero | ± 15% | The model's three stages against PLFS's one self-employed group |
| `consumption.mpce` | HCES 2023-24 Statement 1: rural ₹4,122, urban ₹6,996, times `consumption.hces_uprate` (rural 1.0467, urban 1.0501: mean CPI April–December 2025 over August 2023 – July 2024), so ₹4,314 and ₹7,347 | Successful spending payments by a household's members ÷ (adults + dependants), averaged over persons | ± 10% | Fitted. HCES counts home-grown produce, which the model does not pay for |
| `consumption.gini` | HCES Statement 8: rural 0.237, urban 0.284 | Gini of household MPCE over the window, each household weighted by its size | ± 0.03 | Fitted; one survey year against a few simulated months |
| `consumption.food_share` | HCES Statement 1: rural 47.04%, urban 39.68% | Grocery and food payments ÷ all spending payments | ± 3 points | Not fitted; the category shares are inputs |

### Target checks (payments)

| Check | Target row (source) | Simulated statistic | Band | Why |
| :--- | :--- | :--- | :--- | :--- |
| `payments.upi_p2m_per_adult` | `upi.volume.monthly` (RBI PSI) × `upi.p2m.share` 0.63 (Ministry of Finance, PIB 2257087) ÷ `population.adults_18plus` | Successful UPI P2M payments per person per month, national | ± 25% | Two archetype districts against India; a derived adult population; P2M also includes businesses paying merchants |
| `payments.upi_p2p_per_adult` | the same with 0.37 | Successful UPI P2P payments per person per month, national | ± 25% | As above |
| `payments.debit_card_per_adult` | `cards.debit.volume_monthly` (RBI PSI item 4.2) ÷ adults | Successful debit card payments per person per month, national | ± 25% | As above |
| `payments.atm_per_adult` | `atm.withdrawal.volume_monthly` (RBI PSI item 3.2) ÷ adults | Successful ATM withdrawals per person per month, national | ± 25% | As above |
| `payments.atm_ticket` | `atm.withdrawal.value_monthly` ÷ volume (RBI PSI): about ₹5,300 | Mean amount of a successful ATM withdrawal | ± 20% | Fitted |
| `payments.debit_card_ticket` | `cards.debit.value_monthly` ÷ volume: about ₹3,300 | Mean amount of a successful debit card payment | ± 25% | Not fitted |
| `payments.p2m_under_500` | `upi.p2m.share_under_500` 0.86 (PIB 2257087, FY 2025-26) | Share of successful UPI P2M payments below ₹500 | ± 5 points | Fitted through ticket dispersion |
| `payments.p2p_under_500` | `upi.p2p.share_under_500` 0.59 (same) | Share of successful UPI P2P payments below ₹500 | ± 5 points | Not fitted |
| `payments.month_start_spike` | `upi.month_start_spike` 1.29 (NPCI daily statistics, May–September 2025) | UPI value on the 1st to 3rd of a month ÷ UPI value on the 10th to 25th, per day, averaged over the window's months | ± 0.10 | The five months range from 1.26 to 1.36 |

Months: a target with monthly values uses the months of the window, and the simulated statistic is compared with their mean.

`payments.month_start_spike` stands for section 15.3's "salary-day inflow spike". Salary credits are not published by day; UPI value by day is, and its rise at the turn of the month is the spending and transfers that follow them.

### Target checks (balances and accounts)

| Check | Target row (source) | Simulated statistic | Band | Why |
| :--- | :--- | :--- | :--- | :--- |
| `balances.basic_mean` | `inclusion.pmjdy.average_balance` ₹4,808 (Lok Sabha unstarred question 20, 1 December 2025) | Mean month-end balance of basic (BSBD) accounts held by persons | ± 25% | Fitted. PMJDY accounts are the model's basic accounts |
| `accounts.zero_balance` | `inclusion.pmjdy.zero_balance_share` 9.15% (same answer) | Share of basic accounts with a zero balance at a month end | ± 3 points | Counts are exact; the model's accounts are newer |
| `accounts.inoperative` | `inclusion.pmjdy.operative_share` 73.6% operative (same answer) | Share of basic accounts with no debit or credit initiated by the holder over the window | ± 5 points | The real rule needs two years without a transaction; the window is months, so the simulated share is an upper bound on the two-year share |

### Holdouts

| Check | Holdout row (source) | Simulated statistic | Band | Why |
| :--- | :--- | :--- | :--- | :--- |
| `holdout.festival_uplift` | `festival.diwali.upi_uplift` 1.031: UPI value per day in October 2025 ÷ the mean of September and November (RBI PSI; Diwali was 20 October) | The same ratio from the run's UPI payments | ± 0.015 | Half the measured uplift, so a model with no festival effect fails and one with the right effect passes. The centred ratio removes UPI's month-on-month growth, which the model does not have |
| `holdout.dbt_cashout` | `dbt.cashout_lag` (Field, Rigol, Troyer Moore, Pande and Schaner 2022, Table A.5 Panel A): the next withdrawal falls 0–5 days after a DBT credit 17.9% of the time, 6–15 days 23.4%, 16–30 days 17.3% | For each APBS credit with 30 days of the run after it: the days to the holder's next cash withdrawal, in the same three windows | ± 8 points each | One study of poor women in two Madhya Pradesh districts in 2018–19, with kiosk accounts an hour away; the only measured lag found |

The gate's run covers April to November 2025, so both holdouts have their months.

### Rows pinned but not checked

`labour.lfpr.15plus`, `labour.wpr.15plus` and `labour.ur.15plus` (all-India, 15+) are pinned; the core suite checks the same report by area through `labour.stages` and `labour.ur`. `imps.volume.fy26`, `aeps.volume.monthly` and the phase 2 to 4 rows are pinned and not checked (reasons in the source notes).

**Not checked, no source.** A savings-balance check against RBI's BSR-2 (savings accounts and balances by population group) was planned; the table is published only on RBI's DBIE portal, which the research could not read. The month-end balance check is the PMJDY average alone.

## The tier S gate

`tests/test_gate_1e.py` (slow):
1. loads `params/calibration/fitted.yaml` and checks that its registry version is the current registry's (a calibration fitted to other inputs is stale);
2. builds `Config.tier("S")` with the fitted overrides, seed 7, and runs from 1 April to 30 November 2025, so that the festival holdout has September to November and the DBT holdout has the August PM-Kisan instalment;
3. runs `run.validate("core")`;
4. asserts that every hard check passes, that every target and holdout check either passes or is a listed gap, and that every listed gap fails.

Seed 7 is not one of the calibration seeds, so the gate is also out of sample in its randomness. Runtime about two minutes.

## Testing

Test first throughout. The fast tests use worlds of 500 to 2,000 persons over one to three months.
- **Registry:** `tests/test_registry_sources.py` (above); the moved row-count pins.
- **Statistics:** each statistic against a hand computation on a small run's tables, or on a hand-made frame where the run cannot produce the case (for example a known Gini).
- **Hard checks:** each passes on a real small run, and fails on a copy of that run damaged in the one way it guards: a posting's delta changed, a month-end balance changed, a vault drained, a dimension table rewritten with a changed row, a `pan_like` replaced by a real-format PAN, a VPA given a real handle.
- **Validation:** the report's schema and statuses; a known gap that fails; a check skipped for a forked run; the report written into the run and read back with `run.table`; `run.validate` on a window raises.
- **Calibration:** a two-trial calibration on a 1,000-person world returns the same `best`, `trials` and `loss` with one worker and with two; `Free` with `key` and `scale` builds the right overrides; `save` then `load` gives an equal result; `apply` gives the overrides.
- **Slow gate:** `tests/test_gate_1e.py` (above).
- **Bench:** `scripts/bench.py --tier S --days 90 --seed 7`, before and after, all 20 content hashes equal.

## Bench, results and ledger

- **Bench.** `scripts/bench.py --tier S --days 90 --seed 7` on `main` at `29dd4a6` before any change (recorded in the ledger), and on the branch at the end: all 20 content hashes equal. The branch changes no input value, so any difference is a defect.
- **Results.** `scripts/phase1e_results.py` produces every figure in `docs/phase1e_results.md` from the committed calibration and the gate's run: the fitted values against their bounds, the loss path, each check's simulated and published values, and the default (uncalibrated) run validated beside the calibrated one, so the calibration's effect is visible check by check. Every statement in the results doc is re-queried before it is written.
- **Ledger.** Every **Decided** above is recorded as a `Ruling:` in `docs/superpowers/ledger.md`, with any made during the build.

## What is left to the builder

- Names of private helpers, the layout of `statistics.py`, and how SQL is split between DuckDB and Polars.
- The Markdown layout of `CalibrationResult.report` and `ValidationReport.report`.
- Test fixtures and world sizes, within the fast suite's time.
