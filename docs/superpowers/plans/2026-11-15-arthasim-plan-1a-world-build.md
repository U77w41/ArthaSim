# arthasim Plan 1a (World Build) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A tier S world (100,000 adults in two districts) synthesised from district marginals, with households, attributes, employers, merchants, 12 banks and 2 NBFCs, accounts, identifiers and a social graph, on which the phase 0 day loop runs with every invariant passing.

**Architecture:** A pipeline of pure functions. Each takes arrays and returns a dataclass of arrays: marginals, IPF, persons, households, attributes, organisations, banking, edges. `build_state` dispatches on `Config.builder`. The population builder fills the same `WorldState` fields the phase 0 loop reads and attaches the richer tables as `state.population`.

**Tech Stack:** Python 3.11+, NumPy, Numba, Polars, PyArrow, DuckDB, Pydantic 2, PyYAML, pytest, Hypothesis.

**Spec:** `docs/simulation_architecture_v2.md`, sections 5.1 to 5.4, 8.1, 8.3 (starting pay) and 13.2. Repo path of this plan: `docs/superpowers/plans/2026-11-15-arthasim-plan-1a-world-build.md`.

## Global Constraints

- Everything in the phase 0 plan's Global Constraints still holds (integer paise, keyed randomness only, no `np.random` or `random` under `src/`, Asia/Kolkata, a failed invariant stops the run).
- The phase 0 suite stays green. Tier XS keeps the spike builder.
- Persons are adults aged 18 to 84. Children are a count on the household.
- Category orders are fixed lists defined once in `src/arthasim/build/categories.py`. Arrays store the index.
- District numbers come only from `params/population/*.yaml`. Every other number comes from `params/registry.yaml`.
- No generated identifier may match a real format: PAN `^[A-Z]{5}[0-9]{4}[A-Z]$`, IFSC `^[A-Z]{4}0[A-Z0-9]{6}$`, Aadhaar `^[2-9][0-9]{11}$`, mobile `^[6-9][0-9]{9}$`.
- Stream names carry the module prefix: `pop.`, `hh.`, `attr.`, `org.`, `bank.`, `graph.`. Build draws use `day = 0`.
- Traits, literacy and skill are truth-only. They never appear in the `persons` table.

## Scope

- **In:** the parametric population from published-style marginals (the fallback named in spec 8.1), behind an interface a microdata source can replace.
- **Out, with reason:** real district marginals and microdata (plan 1e pins sources; the two district files here are archetypes with status `assumption`). Generational household structure and merchant ownership (need microdata). NBFC products (phase 3). Income for the self-employed, gig, farm and casual groups inside the day loop (plan 1b), so those persons spend down their opening balances in this plan's smoke run.

## Review Focus

1. A single-district config builds, and has zero remittance edges (Tasks 9 and 10).
2. A marginal share of exactly zero (metro women in `farm`) yields no such person and no division by zero (Tasks 3 and 4).
3. Infeasible marginals, where a target has mass but the prior is zero, raise `ValueError` naming the margin (Task 3).
4. Unbanked persons (`person_deposit == -1`) survive the day loop: they pay in cash and never trigger an ATM withdrawal (Task 10).
5. A tiny population (200 persons) still gives every locality a grocery merchant, every salaried person an employer, and no empty household (Tasks 5 and 7).

## File Structure

| File | Responsibility |
| :--- | :--- |
| `src/arthasim/config.py` (modify) | Tier S, `builder`, `districts`, `nbfcs`, `localities_per_district` |
| `params/registry.yaml` (modify) | 44 new parameters |
| `params/population/metro_archetype.yaml`, `rural_archetype.yaml`, `priors.yaml` | District marginals and association priors |
| `src/arthasim/build/categories.py` | Category lists and index constants |
| `src/arthasim/build/marginals.py` | `DistrictMarginals`, `Priors`, loaders |
| `src/arthasim/build/ipf.py` | `ipf`, `integerise` |
| `src/arthasim/build/population.py` | `Persons`, `synthesise_persons` |
| `src/arthasim/build/households.py` | `Households`, `form_households` |
| `src/arthasim/build/earnings.py`, `attributes.py` | `starting_pay`, `Attributes`, `attach_attributes` |
| `src/arthasim/build/orgs.py` | `Orgs`, `build_orgs` |
| `src/arthasim/build/identifiers.py`, `banking.py` | Synthetic identifiers; `Banking`, `assign_banking` |
| `src/arthasim/build/graph.py` | `build_edges` |
| `src/arthasim/build/pipeline.py` | `PopulationBundle`, `build_population_state` |
| `src/arthasim/build/world.py`, `world.py`, `store/parquet.py` (modify) | Dispatch, new tables, manifest fields |
| `tests/helpers.py` | Shared test inputs |
| `docs/phase1a_results.md` | Gate result |

---

### Task 1: Tier S config and registry additions

**Files:**
- Modify: `src/arthasim/config.py`, `params/registry.yaml`, `tests/test_params.py` (the row-count assertion becomes `t.height >= 17`)
- Test: `tests/test_config_s.py`

**Interfaces:**
- Produces: `Config` fields `builder: Literal["spike", "population"] = "spike"`, `districts: list[str] = []`, `nbfcs: int = 0`, `localities_per_district: int = 20`; `employers` and `merchants` become `int | None`.
- Rules: the spike builder needs `employers` and `merchants` set. The population builder needs `districts` non-empty and both of those `None`. `nbfcs >= 0`, `localities_per_district >= 1`.
- Tier `S`: `persons=100_000, banks=12, nbfcs=2, builder="population", districts=["metro_archetype", "rural_archetype"], employers=None, merchants=None`.

New registry entries, all `role: input`, `status: assumption`:

| id | value |
| :--- | :--- |
| `attr.digital.base_by_education` | [0.15, 0.30, 0.50, 0.75, 0.85] |
| `attr.digital.metro_bonus` | 0.10 |
| `attr.digital.age_penalty` | 0.40 |
| `attr.digital.upi_threshold` | 0.45 |
| `attr.financial.base_by_education` | [0.10, 0.20, 0.40, 0.65, 0.80] |
| `attr.skill.base` | 0.20 |
| `attr.skill.per_education_level` | 0.12 |
| `attr.skill.per_year_experience` | 0.004 |
| `attr.noise_sd` | 0.10 |
| `attr.trait_shapes` | {risk_appetite: [2, 3], habit_strength: [3, 2], price_sensitivity: [2, 2], trust_in_offers: [2, 3]} |
| `earn.base_paise` | 1200000 |
| `earn.return_by_education` | [0.0, 0.15, 0.45, 0.95, 1.30] |
| `earn.experience.linear` | 0.035 |
| `earn.experience.quadratic` | 0.0006 |
| `earn.premium.metro` | 0.25 |
| `earn.premium.by_sector` | [-0.20, 0.05, 0.0, 0.0, 0.0, 0.45, 0.40, 0.25, 0.10, -0.05] |
| `earn.sigma` | 0.45 |
| `earn.stage_multiplier` | {salaried: 1.0, self_employed: 0.9, gig: 0.6, farm: 0.5, casual: 0.4} |
| `earn.pension_ratio` | 0.35 |
| `earn.start_age_by_education` | [18, 18, 18, 22, 24] |
| `org.sector_shares.metro` | [0.01, 0.14, 0.08, 0.18, 0.08, 0.14, 0.07, 0.08, 0.10, 0.12] |
| `org.sector_shares.rural` | [0.30, 0.10, 0.14, 0.14, 0.07, 0.01, 0.02, 0.07, 0.08, 0.07] |
| `org.employer_size_classes` | [[1, 9, 0.70], [10, 49, 0.22], [50, 249, 0.07], [250, 2000, 0.01]] |
| `org.persons_per_merchant` | 40 |
| `org.merchant_category_shares` | [0.30, 0.15, 0.04, 0.06, 0.08, 0.04, 0.08, 0.15, 0.10] |
| `org.merchant_upi_acceptance` | {metro: 0.80, rural: 0.45} |
| `org.merchant_card_acceptance` | {metro: 0.25, rural: 0.05} |
| `bank.archetypes` | 12 rows of [archetype, metro share, rural share]: [public, 0.20, 0.28], [public, 0.12, 0.18], [public, 0.08, 0.12], [public, 0.05, 0.08], [private, 0.18, 0.06], [private, 0.12, 0.04], [private, 0.08, 0.03], [private, 0.05, 0.02], [small_finance, 0.03, 0.05], [small_finance, 0.02, 0.04], [payments, 0.04, 0.06], [cooperative, 0.03, 0.04] |
| `inclusion.account_ownership` | {metro: 0.90, rural: 0.80} |
| `inclusion.second_account_share` | {metro: 0.25, rural: 0.10} |
| `inclusion.salary_account_at_employer_bank` | 0.60 |
| `inclusion.basic_account_income_paise` | 1000000 |
| `inclusion.debit_card_share` | 0.70 |
| `inclusion.mobile_share` | 0.90 |
| `identity.pan_share` | {salaried: 0.95, other_earning: 0.45, non_earning: 0.30} |
| `open.deposit_months_of_income` | 0.8 |
| `open.deposit_floor_paise` | 200000 |
| `open.deposit_sigma` | 1.0 |
| `open.cash_median_paise` | 150000 |
| `open.cash_sigma` | 0.6 |
| `graph.coworker_degree` | 5 |
| `graph.neighbour_degree` | 4 |
| `graph.migrant_share` | 0.15 |
| `hh.dependant_ages` | [20, 49] |

- [ ] **Step 1: Write the failing test**

```python
import pathlib
import pytest
from arthasim import Config, ParamRegistry

PATH = pathlib.Path(__file__).parents[1] / "params" / "registry.yaml"


def test_tier_s():
    c = Config.tier("S")
    assert (c.persons, c.banks, c.nbfcs, c.builder) == (100_000, 12, 2, "population")
    assert c.districts == ["metro_archetype", "rural_archetype"]
    assert c.employers is None and c.merchants is None and c.localities_per_district == 20


def test_builder_rules():
    assert Config.tier("XS").builder == "spike"
    for bad in ({"districts": []}, {"employers": 5}, {"localities_per_district": 0}, {"nbfcs": -1}):
        with pytest.raises(ValueError):
            Config.tier("S", **bad)
    with pytest.raises(ValueError):
        Config.tier("XS", employers=None)


def test_registry_has_plan_1a_parameters():
    r = ParamRegistry.load(PATH)
    assert r.table().height == 61
    assert len(r.get("bank.archetypes")) == 12 and r.get("graph.migrant_share") == 0.15
    for key in ("org.sector_shares.metro", "org.sector_shares.rural", "org.merchant_category_shares"):
        assert abs(sum(r.get(key)) - 1.0) < 1e-9
    for col in (1, 2):
        assert abs(sum(row[col] for row in r.get("bank.archetypes")) - 1.0) < 1e-9
```

- [ ] **Step 2: Run** `pytest tests/test_config_s.py -v`. Expected: FAIL, unknown tier `S`.
- [ ] **Step 3: Implement** the fields, the validator and the 44 registry rows.
- [ ] **Step 4: Run** `pytest -q`. Expected: PASS, including the whole phase 0 suite.
- [ ] **Step 5: Commit** `git commit -am "feat: tier S config and plan 1a parameters"`.

### Task 2: Categories, district marginals and priors

**Files:**
- Create: `src/arthasim/build/categories.py`, `src/arthasim/build/marginals.py`, `params/population/metro_archetype.yaml`, `params/population/rural_archetype.yaml`, `params/population/priors.yaml`
- Test: `tests/test_marginals.py`

**Interfaces:**
- `categories.py`: `AGE_BANDS = ["18-24", "25-34", "35-44", "45-59", "60+"]`, `AGE_EDGES = [18, 25, 35, 45, 60, 85]`, `SEX = ["F", "M"]`, `EDUCATION = ["none", "primary", "secondary", "graduate", "postgraduate"]`, `LIFE_STAGE = ["studying", "seeking", "salaried", "self_employed", "gig", "farm", "casual", "homemaker", "retired"]`, `SECTORS = ["agriculture", "manufacturing", "construction", "trade", "transport", "it_services", "finance", "public_admin", "education_health", "other_services"]`, `MERCHANT_CATEGORIES = ["grocery", "food", "fuel", "pharmacy", "apparel", "electronics", "transport", "services", "other"]`; index constants `F, M = 0, 1`, `STUDYING, SEEKING, SALARIED, SELF_EMPLOYED, GIG, FARM, CASUAL, HOMEMAKER, RETIRED = range(9)`, `EARNING = (2, 3, 4, 5, 6)`, `GROCERY = 0`.
- `marginals.py`: `DistrictMarginals` (Pydantic) with `id, name, kind` (`"metro"` or `"rural"`), `state_code, district_code` (nullable), `status, adult_population, age_band` (5), `sex` (2), `education` (5), `life_stage` (2 rows of 9, F then M), `household_adults` (5, for 1 to 5 adults), `dependants_mean`; `load_district(name, root="params/population")`; `Priors` with `age_life_stage` (5 by 9) and `age_education` (5 by 5); `load_priors(root="params/population")`. Every share list must be non-negative and sum to 1 within 1e-6, else `ValueError`.

District files (lists follow the category order):

| Field | `metro_archetype` | `rural_archetype` |
| :--- | :--- | :--- |
| `kind`, `adult_population` | metro, 3000000 | rural, 2000000 |
| `age_band` | [0.17, 0.26, 0.22, 0.22, 0.13] | [0.18, 0.24, 0.20, 0.23, 0.15] |
| `sex` | [0.48, 0.52] | [0.50, 0.50] |
| `education` | [0.10, 0.15, 0.35, 0.30, 0.10] | [0.30, 0.25, 0.30, 0.12, 0.03] |
| `life_stage` F | [0.07, 0.03, 0.18, 0.08, 0.02, 0.00, 0.05, 0.47, 0.10] | [0.04, 0.02, 0.05, 0.10, 0.01, 0.22, 0.12, 0.36, 0.08] |
| `life_stage` M | [0.08, 0.05, 0.40, 0.20, 0.07, 0.01, 0.09, 0.00, 0.10] | [0.06, 0.04, 0.14, 0.18, 0.03, 0.30, 0.17, 0.00, 0.08] |
| `household_adults` | [0.12, 0.48, 0.22, 0.12, 0.06] | [0.08, 0.42, 0.25, 0.15, 0.10] |
| `dependants_mean` | 0.9 | 1.4 |

Both have `status: assumption`, `state_code: null`, `district_code: null`.

`priors.yaml`, rows are age bands:

| Age band | `age_life_stage` | `age_education` |
| :--- | :--- | :--- |
| 18-24 | [1.0, 1.0, 0.6, 0.4, 1.0, 0.7, 1.0, 0.6, 0.0] | [0.5, 0.7, 1.2, 1.0, 0.4] |
| 25-34 | [0.1, 0.8, 1.0, 0.9, 1.0, 1.0, 1.0, 1.0, 0.0] | [0.6, 0.8, 1.1, 1.2, 1.2] |
| 35-44 | [0.0, 0.4, 1.0, 1.0, 0.6, 1.0, 1.0, 1.0, 0.0] | [0.9, 1.0, 1.0, 1.0, 1.0] |
| 45-59 | [0.0, 0.3, 0.9, 1.0, 0.3, 1.0, 0.9, 1.0, 0.15] | [1.2, 1.2, 0.9, 0.8, 0.8] |
| 60+ | [0.0, 0.05, 0.1, 0.4, 0.05, 0.5, 0.2, 0.8, 1.0] | [1.6, 1.3, 0.8, 0.6, 0.6] |

- [ ] **Step 1: Write the failing test**

```python
import numpy as np
import pytest
from arthasim.build import categories as c
from arthasim.build.marginals import load_district, load_priors


def test_categories():
    assert len(c.AGE_BANDS) == 5 and len(c.LIFE_STAGE) == 9 and len(c.SECTORS) == 10
    assert c.LIFE_STAGE[c.SALARIED] == "salaried" and c.LIFE_STAGE[c.RETIRED] == "retired"
    assert [c.LIFE_STAGE[i] for i in c.EARNING] == ["salaried", "self_employed", "gig", "farm", "casual"]
    assert c.MERCHANT_CATEGORIES[c.GROCERY] == "grocery" and c.AGE_EDGES == [18, 25, 35, 45, 60, 85]


def test_district_files_load_and_sum_to_one():
    metro, rural = load_district("metro_archetype"), load_district("rural_archetype")
    assert (metro.kind, rural.kind) == ("metro", "rural") and metro.adult_population == 3_000_000
    for d in (metro, rural):
        assert d.status == "assumption" and d.district_code is None
        for shares in (d.age_band, d.sex, d.education, d.household_adults, *d.life_stage):
            assert abs(sum(shares) - 1.0) < 1e-6
    assert metro.life_stage[c.F][c.FARM] == 0.0 and metro.life_stage[c.M][c.HOMEMAKER] == 0.0


def test_priors_and_errors(tmp_path):
    pr = load_priors()
    assert np.asarray(pr.age_life_stage).shape == (5, 9) and np.asarray(pr.age_education).shape == (5, 5)
    assert pr.age_life_stage[2][c.STUDYING] == 0.0 and pr.age_life_stage[0][c.RETIRED] == 0.0
    with pytest.raises(FileNotFoundError):
        load_district("nowhere")
    text = open("params/population/metro_archetype.yaml").read().replace("[0.48, 0.52]", "[0.48, 0.62]")
    (tmp_path / "bad.yaml").write_text(text)
    with pytest.raises(ValueError):
        load_district("bad", root=tmp_path)
```

- [ ] **Step 2: Run** `pytest tests/test_marginals.py -v`. Expected: FAIL, modules not found.
- [ ] **Step 3: Implement.** Write `sex: [0.48, 0.52]` in the metro file exactly as shown, since the test edits that text. A relative `root` that does not exist under the working directory is resolved against the repo root.
- [ ] **Step 4: Run** `pytest tests/test_marginals.py -v`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "feat: categories, district marginals and priors"`.

### Task 3: IPF and integerisation

**Files:**
- Create: `src/arthasim/build/ipf.py`
- Test: `tests/test_ipf.py`

**Interfaces:**
- `ipf(seed, targets, tol=1e-9, max_iter=500) -> np.ndarray`. `targets` is a list of `(axes, array)`, where `axes` is the tuple of axes kept and `array` has their shape. Raises `ValueError` whose message contains `margin <i>` when target `i` has mass where the seed's margin is zero, when totals differ by more than 1e-6, or when the fit has not reached `tol` after `max_iter`.
- `integerise(weights, n) -> int64 array` of the same shape summing to `n`, by largest remainder with ties broken by flat index.

- [ ] **Step 1: Write the failing test**

```python
import numpy as np
import pytest
from arthasim.build.ipf import ipf, integerise


def test_ipf_matches_all_margins_and_keeps_zeros():
    seed = np.ones((3, 2, 4))
    seed[0, :, 3] = 0
    t0 = np.array([0.2, 0.5, 0.3])
    t12 = np.array([[0.1, 0.2, 0.1, 0.1], [0.2, 0.1, 0.1, 0.1]])
    w = ipf(seed, [((0,), t0), ((1, 2), t12)])
    assert np.allclose(w.sum(axis=(1, 2)), t0, atol=1e-8) and np.allclose(w.sum(axis=0), t12, atol=1e-8)
    assert (w[0, :, 3] == 0).all() and (w >= 0).all()


def test_ipf_handles_a_zero_target():
    w = ipf(np.ones((2, 3)), [((0,), np.array([0.4, 0.6])), ((1,), np.array([0.5, 0.0, 0.5]))])
    assert (w[:, 1] == 0).all() and np.isfinite(w).all() and abs(w.sum() - 1.0) < 1e-9


def test_ipf_rejects_infeasible_and_mismatched_targets():
    seed = np.ones((2, 2))
    seed[0, :] = 0
    with pytest.raises(ValueError, match="margin 0"):
        ipf(seed, [((0,), np.array([0.5, 0.5])), ((1,), np.array([0.5, 0.5]))])
    with pytest.raises(ValueError):
        ipf(np.ones((2, 2)), [((0,), np.array([0.5, 0.5])), ((1,), np.array([0.6, 0.6]))])


def test_integerise():
    w = np.array([[0.26, 0.24], [0.25, 0.25]])
    counts = integerise(w, 10)
    assert counts.dtype == np.int64 and counts.sum() == 10 and (np.abs(counts - w * 10) < 1).all()
    assert np.array_equal(counts, integerise(w, 10))
    assert integerise(np.array([0.0, 1.0]), 7).tolist() == [0, 7]
    assert integerise(np.array([1.0, 1.0, 1.0]), 2).tolist() == [1, 1, 0]
```

- [ ] **Step 2: Run** `pytest tests/test_ipf.py -v`. Expected: FAIL, module not found.
- [ ] **Step 3: Implement.** One IPF sweep rescales the table to each target in turn; a cell whose current margin is zero keeps weight zero. Convergence is the largest absolute gap between any fitted margin and its target.
- [ ] **Step 4: Run** `pytest tests/test_ipf.py -v`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "feat: IPF and integerisation"`.

### Task 4: Person synthesis

**Files:**
- Create: `src/arthasim/build/population.py`, `tests/helpers.py`
- Test: `tests/test_population.py`

**Interfaces:**
- Consumes: `DistrictMarginals`, `Priors`, `ipf`, `integerise`, `rng`.
- Produces: `Persons`, a dataclass of equal-length arrays `district, age, age_band, sex, education, life_stage`, ordered by district; `synthesise_persons(districts, priors, n, seed) -> Persons`.
- `tests/helpers.py` holds `D` (the two districts), `PR` (priors), `P` (registry) and `l1(counts, target)`, the sum of absolute differences between `counts / counts.sum()` and `target`.

Method: split `n` across districts in proportion to `adult_population` with `integerise`. Per district, the seed table over (age band, sex, education, life stage) is `age_life_stage[a, l] * age_education[a, e]`; fit it to four targets (age band, sex, education, and sex by life stage); `integerise` to the district's count; expand cells to persons. Exact age is uniform inside the band on stream `pop.age`. Persons are then put in keyed random order within the district on stream `pop.order`, so that id does not encode attributes.

- [ ] **Step 1: Write `tests/helpers.py` and the failing test**

```python
# tests/helpers.py
import pathlib
import numpy as np
from arthasim import ParamRegistry
from arthasim.build.marginals import load_district, load_priors

D = [load_district("metro_archetype"), load_district("rural_archetype")]
PR = load_priors()
P = ParamRegistry.load(pathlib.Path(__file__).parents[1] / "params" / "registry.yaml")


def l1(counts, target):
    counts = np.asarray(counts, dtype=float)
    return float(np.abs(counts / counts.sum() - np.asarray(target, dtype=float)).sum())
```

```python
# tests/test_population.py
import numpy as np
from arthasim.build import categories as c
from arthasim.build.population import synthesise_persons
from helpers import D, PR, l1

p = synthesise_persons(D, PR, 20_000, seed=7)


def test_margins_fit_in_each_district():
    assert np.bincount(p.district).tolist() == [12_000, 8_000]
    for d, m in enumerate(D):
        s = p.district == d
        assert l1(np.bincount(p.age_band[s], minlength=5), m.age_band) < 0.02
        assert l1(np.bincount(p.sex[s], minlength=2), m.sex) < 0.02
        assert l1(np.bincount(p.education[s], minlength=5), m.education) < 0.02
        for sex in (c.F, c.M):
            t = s & (p.sex == sex)
            assert l1(np.bincount(p.life_stage[t], minlength=9), m.life_stage[sex]) < 0.03


def test_structure_and_ranges():
    assert p.age.min() >= 18 and p.age.max() <= 84
    assert np.array_equal(p.age_band, np.searchsorted([25, 35, 45, 60], p.age, side="right"))
    assert not ((p.life_stage == c.STUDYING) & (p.age >= 35)).any()
    assert not ((p.life_stage == c.RETIRED) & (p.age < 45)).any()
    assert not ((p.district == 0) & (p.sex == c.F) & (p.life_stage == c.FARM)).any()
    assert not ((p.sex == c.M) & (p.life_stage == c.HOMEMAKER)).any()
    assert (np.diff(p.district) >= 0).all()


def test_deterministic_and_not_sorted_by_cell():
    a, b = (synthesise_persons(D, PR, 5_000, seed=7) for _ in range(2))
    other = synthesise_persons(D, PR, 5_000, seed=8)
    assert np.array_equal(a.age, b.age) and np.array_equal(a.life_stage, b.life_stage)
    assert not np.array_equal(a.age, other.age)
    assert 0.3 < a.sex[:200].mean() < 0.7
```

- [ ] **Step 2: Run** `pytest tests/test_population.py -v`. Expected: FAIL, module not found.
- [ ] **Step 3: Implement** as described under Method. Add `pythonpath = ["tests"]` to the pytest section of `pyproject.toml` so `helpers` imports.
- [ ] **Step 4: Run** `pytest tests/test_population.py -v`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "feat: person synthesis from marginals"`.

### Task 5: Households

**Files:**
- Create: `src/arthasim/build/households.py`
- Test: `tests/test_households.py`

**Interfaces:**
- Consumes: `Persons`, `DistrictMarginals`, `ParamRegistry`, `integerise`, `rng`.
- Produces: `Households` with `household_of_person` (one entry per person) and per-household arrays `district, locality, adults, dependants, head` (`head` is a person index); `form_households(persons, districts, n_localities, params, seed) -> Households`. Household ids are contiguous from 0, ordered by district.

Method, per district: the number of households is the district's persons divided by the mean of `household_adults`, rounded; `integerise` gives the count of households of each size; the size list is put in keyed order (`hh.size`) and cut where its running total reaches the district's persons, the last household taking the remainder. Women and men are each put in keyed order (`hh.member`), and each household is filled by alternating man, woman while both remain. The head is the oldest member, lowest index on ties. Locality is a keyed uniform draw (`hh.locality`). Dependants are Poisson with mean `dependants_mean` (`hh.dependants`) when the household has an adult aged within `hh.dependant_ages`, else zero.

- [ ] **Step 1: Write the failing test**

```python
import numpy as np
from arthasim.build.households import form_households
from arthasim.build.population import synthesise_persons
from helpers import D, PR, P, l1

p = synthesise_persons(D, PR, 20_000, seed=7)
h = form_households(p, D, 20, P, seed=7)
N = len(h.adults)


def test_partition_head_and_location():
    assert np.array_equal(np.bincount(h.household_of_person, minlength=N), h.adults)
    assert h.adults.min() >= 1 and h.adults.max() <= 5
    assert np.array_equal(h.district[h.household_of_person], p.district) and (np.diff(h.district) >= 0).all()
    assert ((h.locality >= 0) & (h.locality < 20)).all() and len(np.unique(h.locality)) == 20
    oldest = np.zeros(N, dtype=np.int64)
    np.maximum.at(oldest, h.household_of_person, p.age)
    assert np.array_equal(p.age[h.head], oldest)
    assert np.array_equal(h.household_of_person[h.head], np.arange(N))


def test_size_distribution_and_sex_mixing():
    for d, m in enumerate(D):
        assert l1(np.bincount(h.adults[h.district == d], minlength=6)[1:], m.household_adults) < 0.03
    men = np.zeros(N, dtype=np.int64)
    np.add.at(men, h.household_of_person, p.sex)
    assert (men[h.adults == 2] == 1).mean() > 0.8


def test_dependants_rule():
    in_range = (p.age >= 20) & (p.age <= 49)
    eligible = np.zeros(N, dtype=bool)
    eligible[h.household_of_person[in_range]] = True
    assert (h.dependants[~eligible] == 0).all() and h.dependants.min() >= 0
    for d, m in enumerate(D):
        s = eligible & (h.district == d)
        assert abs(h.dependants[s].mean() - m.dependants_mean) < 0.1


def test_tiny_population_and_determinism():
    small = synthesise_persons(D, PR, 200, seed=7)
    hs = form_households(small, D, 20, P, seed=7)
    assert np.bincount(hs.household_of_person, minlength=len(hs.adults)).min() >= 1
    again = form_households(p, D, 20, P, seed=7)
    assert np.array_equal(again.household_of_person, h.household_of_person)
    assert not np.array_equal(form_households(p, D, 20, P, seed=8).household_of_person, h.household_of_person)
```

- [ ] **Step 2: Run** `pytest tests/test_households.py -v`. Expected: FAIL, module not found.
- [ ] **Step 3: Implement** as described under Method.
- [ ] **Step 4: Run** `pytest tests/test_households.py -v`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "feat: household formation"`.

### Task 6: Attributes and starting pay

**Files:**
- Create: `src/arthasim/build/earnings.py`, `src/arthasim/build/attributes.py`
- Test: `tests/test_attributes.py`

**Interfaces:**
- `earnings.starting_pay(education, experience, is_metro, sector, z, params) -> float64 array` in paise: `base * exp(return[education] + linear * experience - quadratic * experience**2 + metro_premium * is_metro + sector_premium[sector] + sigma * z)`. Plan 1b's income module reuses it.
- `Attributes` with `float32` arrays in [0, 1]: `domain_skill, digital_literacy, financial_literacy, risk_appetite, habit_strength, price_sensitivity, trust_in_offers`; plus `sector` (`int8`, −1 when not earning) and `monthly_income_paise` (`int64`).
- `attach_attributes(persons, districts, params, seed) -> Attributes`.

Rules:
- Experience is `max(0, age - start_age_by_education)`.
- `digital_literacy = clip(base[education] + metro_bonus * is_metro - age_penalty * max(0, age - 35) / 50 + noise)`. `financial_literacy = clip(base[education] + noise)`. `domain_skill = clip(skill.base + per_education_level * education + per_year_experience * experience + noise)`. Noise is normal with `attr.noise_sd`.
- Each trait is Kumaraswamy(a, b) from one uniform `u`: `(1 - (1 - u) ** (1 / b)) ** (1 / a)`.
- Sector: `farm` is agriculture. Other earners draw from the district kind's sector shares with agriculture removed and the rest renormalised.
- Income: earners get `starting_pay` times `earn.stage_multiplier`. Retired persons get `earn.pension_ratio` times `starting_pay` with `sector = other_services` and `z = 0`. Everyone else gets 0. Positive incomes are at least 100 paise.

- [ ] **Step 1: Write the failing test**

```python
import numpy as np
from arthasim.build import categories as c
from arthasim.build.attributes import attach_attributes
from arthasim.build.earnings import starting_pay
from arthasim.build.population import synthesise_persons
from helpers import D, PR, P

p = synthesise_persons(D, PR, 20_000, seed=7)
a = attach_attributes(p, D, P, seed=7)
FIELDS = ("domain_skill", "digital_literacy", "financial_literacy", "risk_appetite",
          "habit_strength", "price_sensitivity", "trust_in_offers")


def test_ranges_and_gradients():
    for f in FIELDS:
        x = getattr(a, f)
        assert x.dtype == np.float32 and x.min() >= 0 and x.max() <= 1 and x.std() > 0.05
    for f in ("digital_literacy", "financial_literacy"):
        by_edu = [getattr(a, f)[p.education == e].mean() for e in range(5)]
        assert by_edu == sorted(by_edu)
    assert a.digital_literacy[p.age >= 60].mean() < a.digital_literacy[p.age < 35].mean()
    assert a.digital_literacy[p.district == 0].mean() > a.digital_literacy[p.district == 1].mean()


def test_income_and_sector_rules():
    inc = a.monthly_income_paise
    earning = np.isin(p.life_stage, c.EARNING)
    assert inc.dtype == np.int64 and (inc[earning] > 0).all() and (inc[p.life_stage == c.RETIRED] > 0).all()
    assert (inc[np.isin(p.life_stage, [c.STUDYING, c.SEEKING, c.HOMEMAKER])] == 0).all()
    sal = p.life_stage == c.SALARIED
    med = [np.median(inc[sal & (p.education == e)]) for e in (0, 2, 3)]
    assert med[0] < med[1] < med[2]
    same = sal & (p.education == 2)
    assert np.median(inc[same & (p.district == 0)]) > np.median(inc[same & (p.district == 1)])
    assert (a.sector[earning] >= 0).all() and (a.sector[~earning] == -1).all()
    assert (a.sector[p.life_stage == c.FARM] == 0).all()
    assert (a.sector[earning & (p.life_stage != c.FARM)] != 0).all()


def test_starting_pay_formula():
    w = starting_pay(np.array([3]), np.array([10.0]), np.array([True]), np.array([5]), np.array([0.0]), P)
    assert abs(w[0] / (1_200_000 * np.exp(0.95 + 0.35 - 0.06 + 0.25 + 0.45)) - 1) < 1e-9


def test_deterministic():
    b = attach_attributes(p, D, P, seed=7)
    assert np.array_equal(a.monthly_income_paise, b.monthly_income_paise)
    assert not np.array_equal(a.risk_appetite, attach_attributes(p, D, P, seed=8).risk_appetite)
```

- [ ] **Step 2: Run** `pytest tests/test_attributes.py -v`. Expected: FAIL, modules not found.
- [ ] **Step 3: Implement.** Each attribute has its own stream (`attr.digital`, `attr.financial`, `attr.skill`, `attr.<trait>`, `attr.sector`, `attr.pay`), keyed on the person's index.
- [ ] **Step 4: Run** `pytest tests/test_attributes.py -v`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "feat: attributes and starting pay"`.

### Task 7: Employers, merchants and billers

**Files:**
- Create: `src/arthasim/build/orgs.py`
- Test: `tests/test_orgs.py`

**Interfaces:**
- Consumes: `Persons`, `Attributes`, `DistrictMarginals`, `ParamRegistry`, `integerise`, `rng`.
- Produces: `Orgs` with employer arrays `employer_district, employer_sector, employer_capacity`; `person_employer` (employer index, −1 if none); merchant arrays `merchant_district, merchant_locality, merchant_category, merchant_accepts_upi, merchant_accepts_card`; `billers = ["telecom", "electricity", "ecommerce", "amc"]`. `build_orgs(persons, attributes, districts, n_localities, params, seed) -> Orgs`.

Method:
- **Employers.** For each (district, sector) with salaried persons, draw employer capacities from `org.employer_size_classes` (class by share, capacity uniform within the class, stream `org.size`) until total capacity covers the group. Put the group in keyed order (`org.assign`) and fill employers in turn up to capacity. Drop employers left with no staff.
- **Merchants.** Per district the count is `max(persons // org.persons_per_merchant, 1)`. `integerise` splits it by `org.merchant_category_shares`. Locality is keyed uniform (`org.locality`). Any locality without a grocery merchant gets one added. Acceptance flags are keyed Bernoulli draws at the district kind's rate (`org.upi`, `org.card`).

- [ ] **Step 1: Write the failing test**

```python
import numpy as np
from arthasim.build import categories as c
from arthasim.build.attributes import attach_attributes
from arthasim.build.orgs import build_orgs
from arthasim.build.population import synthesise_persons
from helpers import D, PR, P, l1

p = synthesise_persons(D, PR, 20_000, seed=7)
a = attach_attributes(p, D, P, seed=7)
o = build_orgs(p, a, D, 20, P, seed=7)


def test_every_salaried_person_has_a_matching_employer():
    sal = p.life_stage == c.SALARIED
    assert (o.person_employer[sal] >= 0).all() and (o.person_employer[~sal] == -1).all()
    e = o.person_employer[sal]
    assert np.array_equal(o.employer_district[e], p.district[sal])
    assert np.array_equal(o.employer_sector[e], a.sector[sal])
    staff = np.bincount(e, minlength=len(o.employer_capacity))
    assert (staff >= 1).all() and (staff <= o.employer_capacity).all()
    assert (o.employer_capacity <= 9).mean() > 0.5 and o.employer_capacity.max() <= 2000


def test_merchants_and_billers():
    persons_in = np.bincount(p.district)
    for d in range(2):
        m = o.merchant_district == d
        assert m.sum() >= persons_in[d] // 40
        assert set(o.merchant_locality[m & (o.merchant_category == c.GROCERY)].tolist()) == set(range(20))
        assert l1(np.bincount(o.merchant_category[m], minlength=9), P.get("org.merchant_category_shares")) < 0.08
    upi = [o.merchant_accepts_upi[o.merchant_district == d].mean() for d in range(2)]
    assert upi[0] > upi[1] and abs(upi[0] - 0.80) < 0.08
    assert o.billers == ["telecom", "electricity", "ecommerce", "amc"]


def test_tiny_population_and_determinism():
    ps = synthesise_persons(D, PR, 200, seed=7)
    at = attach_attributes(ps, D, P, seed=7)
    small = build_orgs(ps, at, D, 20, P, seed=7)
    for d in range(2):
        m = (small.merchant_district == d) & (small.merchant_category == c.GROCERY)
        assert set(small.merchant_locality[m].tolist()) == set(range(20))
    assert (small.person_employer[ps.life_stage == c.SALARIED] >= 0).all()
    again = build_orgs(p, a, D, 20, P, seed=7)
    assert np.array_equal(again.person_employer, o.person_employer)
    assert np.array_equal(again.merchant_locality, o.merchant_locality)
```

- [ ] **Step 2: Run** `pytest tests/test_orgs.py -v`. Expected: FAIL, module not found.
- [ ] **Step 3: Implement** as described under Method.
- [ ] **Step 4: Run** `pytest tests/test_orgs.py -v`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "feat: employers, merchants and billers"`.

### Task 8: Identifiers, banks and accounts

**Files:**
- Create: `src/arthasim/build/identifiers.py`, `src/arthasim/build/banking.py`
- Test: `tests/test_banking.py`

**Interfaces:**
- `identifiers.py`: `REAL_FORMATS` (dict of compiled patterns keyed `pan, ifsc, aadhaar, mobile`, as in Global Constraints); `pan_like(index, initial, type_letter="P")` giving `SY`, a digit, the type letter, a letter, four digits, a letter, unique per index; `token(prefix, seed, stream, ids)` giving `<prefix>_<16 hex digits>`; `branch_code(bank_index, district_index, locality)` giving `SY`, two-digit bank number, `0`, two-digit district, four-digit locality; `vpa(entity_id, bank_index)` giving `p<entity_id>@syn<two-digit bank number>`. All return object arrays of strings.
- `Banking` with `bank_codes` (`SYNB01` to `SYNB12`, then `SYNX00`), `bank_archetype`, `nbfc_codes` (`SYNN01`, `SYNN02`), and per-person arrays `person_has_account, person_primary_bank, person_second_bank` (−1 if none), `person_basic_account, person_has_pan, person_upi, person_has_card, person_has_mobile, opening_deposit, opening_second, opening_cash`; plus `employer_bank, merchant_bank`.
- `assign_banking(persons, attributes, orgs, districts, config, params, seed) -> Banking`.

Rules:
- Employers and merchants get a bank by the district kind's shares in `bank.archetypes`.
- Salaried persons always have an account. Others have one with probability `inclusion.account_ownership`.
- Primary bank: a salaried person banks with the employer's bank with probability `inclusion.salary_account_at_employer_bank`; every other draw follows the district kind's shares.
- A second account, at a different bank, exists with probability `inclusion.second_account_share`.
- The primary account is basic when monthly income is below `inclusion.basic_account_income_paise`.
- PAN: `identity.pan_share` by group (salaried, other earning, not earning).
- UPI needs an account, a mobile and `digital_literacy > attr.digital.upi_threshold`. A debit card needs an account and a `inclusion.debit_card_share` draw.
- Opening deposit is lognormal with median `max(open.deposit_floor_paise, open.deposit_months_of_income * income)`; the second account opens at a quarter of that. Opening cash is lognormal. Both are at least 100 paise. No account means no deposit.

- [ ] **Step 1: Write the failing test**

```python
import re
import numpy as np
from arthasim import Config
from arthasim.build import categories as c
from arthasim.build.attributes import attach_attributes
from arthasim.build.banking import assign_banking
from arthasim.build.identifiers import REAL_FORMATS, branch_code, pan_like, token, vpa
from arthasim.build.orgs import build_orgs
from arthasim.build.population import synthesise_persons
from helpers import D, PR, P, l1

CFG = Config.tier("S", persons=20_000)
p = synthesise_persons(D, PR, 20_000, seed=7)
a = attach_attributes(p, D, P, seed=7)
o = build_orgs(p, a, D, 20, P, seed=7)
b = assign_banking(p, a, o, D, CFG, P, seed=7)
SAL = p.life_stage == c.SALARIED


def test_bank_codes_and_market_shares():
    assert b.bank_codes.tolist() == [f"SYNB{i:02d}" for i in range(1, 13)] + ["SYNX00"]
    assert b.nbfc_codes.tolist() == ["SYNN01", "SYNN02"] and len(b.bank_archetype) == 12
    for d, col in ((0, 1), (1, 2)):
        s = (p.district == d) & b.person_has_account & ~SAL
        target = [row[col] for row in P.get("bank.archetypes")]
        assert l1(np.bincount(b.person_primary_bank[s], minlength=12), target) < 0.05


def test_ownership_rules():
    assert b.person_has_account[SAL].all()
    for d, kind in ((0, "metro"), (1, "rural")):
        s = (p.district == d) & ~SAL
        assert abs(b.person_has_account[s].mean() - P.get("inclusion.account_ownership")[kind]) < 0.03
    none = ~b.person_has_account
    assert none.any() and (b.person_primary_bank[none] == -1).all() and (b.opening_deposit[none] == 0).all()
    assert not b.person_upi[none].any() and not b.person_has_card[none].any()
    assert (b.opening_deposit[~none] >= 100).all() and (b.opening_cash >= 100).all()
    two = b.person_second_bank >= 0
    assert two.any() and (b.person_second_bank[two] != b.person_primary_bank[two]).all() and not two[none].any()
    assert (b.person_primary_bank[SAL] == b.employer_bank[o.person_employer[SAL]]).mean() > 0.55
    assert b.person_has_pan[SAL].mean() > 0.9 > b.person_has_pan[~SAL].mean()
    assert not (b.person_upi & ~b.person_has_mobile).any()
    assert (a.digital_literacy[b.person_upi] > 0.45).all()
    assert b.person_basic_account[~none & (a.monthly_income_paise < 1_000_000)].all()


def test_identifiers_cannot_be_real():
    ids = np.arange(5000)
    samples = {"pan": pan_like(ids, ids % 26), "aadhaar": token("u", 7, 1, ids),
               "mobile": token("m", 7, 2, ids), "ifsc": branch_code(ids % 12, ids % 2, ids % 20)}
    for name, values in samples.items():
        assert not any(REAL_FORMATS[name].match(v) for v in values)
        assert len(set(values)) == (5000 if name != "ifsc" else 12 * 20)
    assert all(re.match(r"^SY[0-9]{2}0[0-9]{6}$", v) for v in samples["ifsc"])
    assert all(re.match(r"^SY[0-9]P[A-Z][0-9]{4}[A-Z]$", v) for v in samples["pan"])
    assert all(v == f"p{i}@syn{(i % 12) + 1:02d}" for i, v in zip(ids.tolist(), vpa(ids, ids % 12)))


def test_deterministic():
    again = assign_banking(p, a, o, D, CFG, P, seed=7)
    assert np.array_equal(again.person_primary_bank, b.person_primary_bank)
    assert np.array_equal(again.opening_deposit, b.opening_deposit)
```

- [ ] **Step 2: Run** `pytest tests/test_banking.py -v`. Expected: FAIL, modules not found.
- [ ] **Step 3: Implement** as described under Rules. `pan_like` and `token` replace the private helper in `build/world.py`, which now calls them.
- [ ] **Step 4: Run** `pytest -q`. Expected: PASS, including phase 0.
- [ ] **Step 5: Commit** `git commit -am "feat: identifiers, banks and accounts"`.

### Task 9: Social graph

**Files:**
- Create: `src/arthasim/build/graph.py`
- Test: `tests/test_graph.py`

**Interfaces:**
- Consumes: `Persons`, `Households`, `Orgs`, `DistrictMarginals`, `ParamRegistry`, `rng`.
- Produces: constants `HOUSEHOLD, COWORKER, NEIGHBOUR, REMITTANCE = 1, 2, 3, 4`; `build_edges(persons, households, orgs, districts, params, seed) -> pl.DataFrame` with `Int64` columns `src, dst, type`, where `src` and `dst` are person indices.

Method:
- **Household.** Every ordered pair of members.
- **Co-worker.** Within each employer, put staff in keyed order (`graph.coworker`) and link each to the next `(degree + 1) // 2` on the ring. Store both directions, without duplicates or self-links.
- **Neighbour.** The same ring construction over household heads within one district and locality (`graph.neighbour`).
- **Remittance.** Each earner in a metro district is a migrant with probability `graph.migrant_share` (`graph.migrant`) and gets one directed edge to the head of a keyed-random household in a rural district (`graph.origin`). No rural district means no such edges.

- [ ] **Step 1: Write the failing test**

```python
import numpy as np
import polars as pl
from arthasim.build import categories as c
from arthasim.build.attributes import attach_attributes
from arthasim.build.graph import build_edges
from arthasim.build.households import form_households
from arthasim.build.orgs import build_orgs
from arthasim.build.population import synthesise_persons
from helpers import D, PR, P

p = synthesise_persons(D, PR, 20_000, seed=7)
h = form_households(p, D, 20, P, seed=7)
a = attach_attributes(p, D, P, seed=7)
o = build_orgs(p, a, D, 20, P, seed=7)
E = build_edges(p, h, o, D, P, seed=7)


def of(t):
    e = E.filter(pl.col("type") == t)
    return e["src"].to_numpy(), e["dst"].to_numpy()


def test_schema_no_self_loops_and_symmetry():
    assert E.columns == ["src", "dst", "type"] and E.schema["src"] == pl.Int64
    assert (E["src"] != E["dst"]).all() and E.unique().height == E.height
    for t in (1, 2, 3):
        s, d = of(t)
        pairs = set(zip(s.tolist(), d.tolist()))
        assert pairs == {(y, x) for x, y in pairs}


def test_each_type_stays_inside_its_group():
    s, d = of(1)
    assert np.array_equal(h.household_of_person[s], h.household_of_person[d])
    assert len(s) == int((h.adults * (h.adults - 1)).sum())
    s, d = of(2)
    assert np.array_equal(o.person_employer[s], o.person_employer[d]) and (o.person_employer[s] >= 0).all()
    assert np.bincount(s).max() <= 6
    s, d = of(3)
    hs, hd = h.household_of_person[s], h.household_of_person[d]
    assert (hs != hd).all() and np.array_equal(h.locality[hs], h.locality[hd])
    assert np.array_equal(h.district[hs], h.district[hd])
    assert np.array_equal(h.head[hs], s) and np.array_equal(h.head[hd], d) and np.bincount(s).max() <= 4


def test_remittance_edges():
    s, d = of(4)
    metro_earner = (p.district == 0) & np.isin(p.life_stage, c.EARNING)
    assert metro_earner[s].all() and len(np.unique(s)) == len(s)
    assert (p.district[d] == 1).all() and np.array_equal(h.head[h.household_of_person[d]], d)
    assert abs(len(s) / metro_earner.sum() - 0.15) < 0.02


def test_single_district_and_determinism():
    one = [D[0]]
    p1 = synthesise_persons(one, PR, 3_000, seed=7)
    h1 = form_households(p1, one, 20, P, seed=7)
    a1 = attach_attributes(p1, one, P, seed=7)
    e1 = build_edges(p1, h1, build_orgs(p1, a1, one, 20, P, seed=7), one, P, seed=7)
    assert e1.filter(pl.col("type") == 4).height == 0 and e1.filter(pl.col("type") == 1).height > 0
    assert build_edges(p, h, o, D, P, seed=7).equals(E)
```

- [ ] **Step 2: Run** `pytest tests/test_graph.py -v`. Expected: FAIL, module not found.
- [ ] **Step 3: Implement** as described under Method. Rows are sorted by `type`, `src`, `dst`.
- [ ] **Step 4: Run** `pytest tests/test_graph.py -v`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "feat: social graph"`.

### Task 10: Pipeline, tables and World integration

**Files:**
- Create: `src/arthasim/build/pipeline.py`
- Modify: `src/arthasim/build/world.py` (`WorldState.population` field, default `None`; `build_state` dispatches on `config.builder`), `src/arthasim/world.py` (tables and manifest), `src/arthasim/store/parquet.py` (`DIM_TABLES` gains `households, instruments, edges, geo, truth_person_latent`)
- Test: `tests/test_pipeline.py`

**Interfaces:**
- `PopulationBundle` with `districts, persons, households, attributes, orgs, banking, edges, report`. `report` is a dict: `l1` (district id to margin name to error, for `age_band, sex, education, life_stage_F, life_stage_M`) and `max_l1`.
- `build_population_state(config, params, seed) -> WorldState` with `state.population` set.

Entity ids, contiguous in this order: persons, employers, merchants, billers, banks, boundary bank, NBFCs, central bank, boundary entity.

How the phase 0 fields are filled:

| `WorldState` field | Population build |
| :--- | :--- |
| `person_bank`, `person_deposit` | Primary bank and account, −1 when unbanked |
| `person_digital` | `person_upi` |
| `person_employer`, `person_salary` | From `Orgs`; salary is the monthly income of salaried persons, 0 otherwise |
| `employer_payday`, `employer_payroll` | Keyed day 1 to 28 (`org.payday`); sum of staff salaries |
| `merchant_deposit`, `merchant_cash` | Every merchant has a current account and a cash balance of 0 |
| Bank reserves, vaults, equity | Same rule as phase 0, over 12 banks plus the boundary bank |
| `deposit_for_cash` | −1 for unbanked persons |

Second accounts become extra `DEPOSIT` instruments. Billers get a current account and no flows yet. NBFCs hold no instruments.

Tables written at build:

| Table | Columns |
| :--- | :--- |
| `persons` | `entity_id, household_id, district, locality, age, sex, education, life_stage, sector, employer_entity_id, monthly_income_paise, has_account, primary_bank, has_pan, pan_like, uid_token, mobile_token` |
| `households` | `household_id, district, locality, adults, dependants, head_entity_id` |
| `orgs` | `entity_id, kind, district, locality, sector, category, bank_code, accepts_upi, accepts_card, payday` |
| `banks` | `entity_id, bank_code, kind, archetype` |
| `accounts` | As in phase 0; subtypes `basic, savings, current, cash_in_hand, vault, reserve, boundary` |
| `instruments` | `instrument_id, account_id, kind, value`; kinds `VPA, DEBIT_CARD, DEVICE, MOBILE, BRANCH` |
| `edges` | `src_entity_id, dst_entity_id, type` |
| `geo` | `district, district_id, kind, locality` |
| `truth_person_latent` | `entity_id, month`, then the seven trait and literacy columns |

Category columns store names, not indices. `pan_like` is null without a PAN and `mobile_token` is null without a mobile. The manifest gains `builder`, `districts`, `scale_factor` (sum of `adult_population` over persons) and `build_report`. Spike runs record `builder: "spike"` and omit the other three.

- [ ] **Step 1: Write the failing test**

```python
import polars as pl
from arthasim import Config, World

TRUTH_ONLY = {"domain_skill", "digital_literacy", "financial_literacy", "risk_appetite",
              "habit_strength", "price_sensitivity", "trust_in_offers"}
PERSON_COLUMNS = ["entity_id", "household_id", "district", "locality", "age", "sex", "education",
                  "life_stage", "sector", "employer_entity_id", "monthly_income_paise", "has_account",
                  "primary_bank", "has_pan", "pan_like", "uid_token", "mobile_token"]


def cfg(tmp_path, **kw):
    base = dict(persons=5_000, out_dir=str(tmp_path))
    base.update(kw)
    return Config.tier("S", **base)


def test_population_world_builds_and_runs(tmp_path):
    world = World.build(cfg(tmp_path), seed=7)
    s = world.state
    assert s.population is not None and len(s.person_ids) == 5_000
    assert list(s.bank_codes) == [f"SYNB{i:02d}" for i in range(1, 13)] + ["SYNX00"]
    unbanked = s.person_deposit == -1
    assert unbanked.any() and not s.person_digital[unbanked].any() and (s.person_employer[unbanked] == -1).all()
    run = world.run(until="2025-04-10")
    m = run.manifest
    assert m["days"] == 10 and m["builder"] == "population" and m["districts"] == ["metro_archetype", "rural_archetype"]
    assert abs(m["scale_factor"] - 1000.0) < 1e-9 and m["build_report"]["max_l1"] < 0.05
    assert set(run.tables()) == {"payments", "journal", "postings", "persons", "households", "orgs", "banks",
                                 "accounts", "instruments", "edges", "geo", "truth_person_latent"}
    pay = run.table("payments").collect()
    cash = s.person_cash[unbanked].tolist()
    theirs = pay.filter(pl.col("payer_account_id").is_in(cash))
    assert theirs.height > 0 and (theirs["rail"] == "CASH").all()
    assert pay.filter((pl.col("rail") == "ATM") & pl.col("payee_account_id").is_in(cash)).height == 0


def test_tables_and_truth_separation(tmp_path):
    run = World.build(cfg(tmp_path), seed=7).run(until="2025-04-01")
    persons = run.table("persons").collect()
    assert persons.columns == PERSON_COLUMNS and persons.height == 5_000
    assert not TRUTH_ONLY & set(persons.columns)
    assert set(persons["life_stage"].unique()) <= {"studying", "seeking", "salaried", "self_employed", "gig",
                                                    "farm", "casual", "homemaker", "retired"}
    assert persons.filter(~pl.col("has_pan"))["pan_like"].null_count() == persons.filter(~pl.col("has_pan")).height
    latent = run.table("truth_person_latent").collect()
    assert TRUTH_ONLY <= set(latent.columns) and latent.height == 5_000 and latent["month"].unique().to_list() == ["2025-04"]
    assert set(run.table("banks").collect()["kind"].unique()) == {"BANK", "NBFC", "BOUNDARY"}
    assert set(run.table("instruments").collect()["kind"].unique()) <= {"VPA", "DEBIT_CARD", "DEVICE", "MOBILE", "BRANCH"}
    assert run.table("households").collect().columns == ["household_id", "district", "locality", "adults",
                                                         "dependants", "head_entity_id"]
    assert run.sql("select count(*) n from edges e join persons p on e.src_entity_id = p.entity_id")["n"][0] \
        == run.table("edges").collect().height


def test_single_district_determinism_and_spike(tmp_path):
    one = World.build(cfg(tmp_path / "one", districts=["metro_archetype"]), seed=7)
    assert one.state.population.edges.filter(pl.col("type") == 4).height == 0
    assert one.run(until="2025-04-03").manifest["days"] == 3
    a = World.build(cfg(tmp_path / "a"), seed=7).run(until="2025-04-03").manifest["content_hash"]
    b = World.build(cfg(tmp_path / "b"), seed=7).run(until="2025-04-03").manifest["content_hash"]
    assert a == b
    spike = World.build(Config.tier("XS", persons=500, employers=10, merchants=30,
                                    out_dir=str(tmp_path / "xs")), seed=7).run(until="2025-04-02")
    assert spike.manifest["builder"] == "spike" and "scale_factor" not in spike.manifest
```

- [ ] **Step 2: Run** `pytest tests/test_pipeline.py -v`. Expected: FAIL, tier S cannot build.
- [ ] **Step 3: Implement.** The pipeline calls Tasks 2 to 9 in order with `config.localities_per_district`. The fit report recomputes each margin from the synthesised persons.
- [ ] **Step 4: Run** `pytest -q`. Expected: PASS for the whole suite.
- [ ] **Step 5: Commit** `git commit -am "feat: population pipeline, tables and World integration"`.

### Task 11: Exit gate

**Files:**
- Modify: `scripts/bench.py` (works for tier S; adds `build_seconds`, `households`, `employers`, `merchants`, `accounts`, `edges_by_type`, `unbanked_share`, `max_l1` to its output when the builder is `population`)
- Create: `docs/phase1a_results.md`
- Test: `tests/test_gate_1a.py`

Exit criteria for this plan:

1. Tier S builds from the two district files with `max_l1 < 0.01`.
2. The phase 0 day loop runs 30 days on it with every invariant passing.
3. Two builds with the same seed give identical tables.
4. Build time, run time and peak memory are recorded.

- [ ] **Step 1: Write the failing test**

```python
import pytest
from arthasim import Config, World


@pytest.mark.slow
def test_plan_1a_gate(tmp_path):
    runs = [World.build(Config.tier("S", out_dir=str(tmp_path / d)), seed=7).run(until="2025-04-30")
            for d in ("a", "b")]
    a, b = (r.manifest for r in runs)
    assert a["days"] == 30 and a["build_report"]["max_l1"] < 0.01
    assert a["content_hash"] == b["content_hash"]
    assert abs(a["scale_factor"] - 50.0) < 1e-9
    assert runs[0].table("persons").collect().height == 100_000
```

- [ ] **Step 2: Run** `pytest tests/test_gate_1a.py -v -m slow`. Expected: PASS if Tasks 1 to 10 are correct. A failure here is a defect in an earlier task: fix it there with a test that reproduces it.
- [ ] **Step 3: Extend `scripts/bench.py`** as listed under Files.
- [ ] **Step 4: Run** `python scripts/bench.py --tier S --days 30 --seed 7 --out runs`. Expected: the numbers print and no exception is raised.
- [ ] **Step 5: Write `docs/phase1a_results.md`** with the bench numbers, the fit error per district and margin, the share of payments by status, and a pass or fail against each of the four exit criteria.
- [ ] **Step 6: Commit** `git commit -am "feat: plan 1a gate and results"`.

---

## What follows this plan

Plan 1b (behaviour) replaces the two spike modules: life course with alignment, income for every earning group, shocks, category consumption with merchant choice by locality, rail choice, deposits, and cash returning to banks. It also adds the full instrument set and the column half of invariant 6.
