import polars as pl
from arthasim import Config, World

TRUTH_ONLY = {"domain_skill", "digital_literacy", "financial_literacy", "risk_appetite",
              "habit_strength", "price_sensitivity", "trust_in_offers"}
PERSON_COLUMNS = ["entity_id", "household_id", "district", "locality", "sex", "birth_month", "birth_year", "education",
                  "has_pan", "pan_like", "uid_token", "mobile_token"]


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
                                 "accounts", "instruments", "edges", "geo", "truth_person_latent", "bank_customers",
                                 "truth_household_monthly", "life_events", "entity_state_monthly", "truth_dbt_monthly",
                                 "macro_paths", "interventions_log"}
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
    assert persons["birth_month"].min() >= 1 and persons["birth_month"].max() <= 12
    assert persons.filter(~pl.col("has_pan"))["pan_like"].null_count() == persons.filter(~pl.col("has_pan")).height
    latent = run.table("truth_person_latent").collect()
    assert TRUTH_ONLY <= set(latent.columns) and latent.height == 5_000 and latent["month"].unique().to_list() == ["2025-04"]
    assert set(run.table("banks").collect()["kind"].unique()) == {"BANK", "NBFC", "BOUNDARY"}
    assert set(run.table("instruments").collect()["kind"].unique()) == {"VPA", "DEBIT_CARD", "DEVICE", "MOBILE", "BRANCH",
                                                                     "ACCOUNT_NO", "TERMINAL"}
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
