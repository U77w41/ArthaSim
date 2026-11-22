import numpy as np
import polars as pl
from arthasim import Config, World
from arthasim.build import categories as c
from arthasim.build.pipeline import dbt_inputs
from arthasim.dbt.schemes import old_age_pension, pm_kisan, women

IST_DAY = "strftime(make_timestamp(y.intent_ts) + interval 330 minute, '%Y-%m-%d')"
IST_HOUR = "hour(make_timestamp(y.intent_ts) + interval 330 minute)"
ORDER = ["lifecourse", "income", "remittances", "dbt", "budget", "allowance", "consumption", "cash"]


def cfg(tmp_path, persons=5_000, **kw):
    params = {k: kw.pop(k) for k in list(kw) if k.startswith(("dbt.", "inclusion."))}
    return Config.tier("S", persons=persons, out_dir=str(tmp_path), **kw).with_params(**params)


def dbt_payments(run, purpose):
    return run.sql(f"""
        select {IST_DAY} as day, {IST_HOUR} as hour, a.holder_entity_id as entity_id, y.amount_paise, y.rail,
               y.status, y.payer_account_id
        from payments y join accounts a on a.account_id = y.payee_account_id
        where y.purpose = '{purpose}'""")


def enrolled(run, month, scheme):
    return run.sql(f"""select entity_id, monthly_value_paise from truth_dbt_monthly
                       where month = '{month}' and scheme = '{scheme}' and enrolled""")


def test_module_order_and_tables(tmp_path):
    world = World.build(cfg(tmp_path), seed=7)
    assert [m.name for m in world.modules] == ORDER
    run = world.run(until="2025-04-12")
    assert "truth_dbt_monthly" in run.tables()
    t = run.table("truth_dbt_monthly").collect()
    assert t.columns == ["entity_id", "month", "scheme", "enrolled", "monthly_value_paise", "opened_account"]
    assert set(t["scheme"].unique()) == {"PM_KISAN", "OLD_AGE_PENSION", "WOMEN"}


def test_women_and_pensions_paid_on_their_days_to_enrolled_payees(tmp_path):
    world = World.build(cfg(tmp_path), seed=7)
    run = world.run(until="2025-04-30")
    gov = world.state.government
    total = 0
    for purpose, scheme, day in (("DBT_WOMEN", "WOMEN", "2025-04-10"),
                                 ("DBT_OLD_AGE_PENSION", "OLD_AGE_PENSION", "2025-04-05")):
        pay, want = dbt_payments(run, purpose), enrolled(run, "2025-04", scheme)
        assert want.height > 20 and pay.height == want.height
        assert set(pay["day"].unique()) == {day} and set(pay["rail"].unique()) == {"APBS"}
        assert set(pay["status"].unique()) == {"SUCCESS"} and set(pay["payer_account_id"]) == {gov.balance_account}
        assert pay["hour"].min() >= 6 and pay["hour"].max() <= 9
        got = sorted(zip(pay["entity_id"], pay["amount_paise"]))
        assert got == sorted(zip(want["entity_id"], want["monthly_value_paise"]))
        total += int(pay["amount_paise"].sum())
    assert dbt_payments(run, "DBT_PM_KISAN").height == 0
    assert int(world.state.book.balance[gov.balance_account]) == -total


def test_pm_kisan_pays_on_its_date_only(tmp_path):
    run = World.build(cfg(tmp_path, start="2025-08-01"), seed=7).run(until="2025-08-03")
    pay, want = dbt_payments(run, "DBT_PM_KISAN"), enrolled(run, "2025-08", "PM_KISAN")
    assert want.height > 50 and set(pay["day"].unique()) == {"2025-08-02"}
    assert sorted(pay["entity_id"]) == sorted(want["entity_id"]) and set(pay["amount_paise"]) == {200_000}
    assert set(want["monthly_value_paise"]) == {50_000}


def test_mid_month_start_pays_no_arrears_and_a_start_on_the_pay_day_pays(tmp_path):
    late = World.build(cfg(tmp_path / "late", start="2025-04-11"), seed=7).run(until="2025-04-30")
    assert dbt_payments(late, "DBT_WOMEN").height == 0
    on = World.build(cfg(tmp_path / "on", start="2025-04-10"), seed=7).run(until="2025-04-10")
    assert dbt_payments(on, "DBT_WOMEN").height == enrolled(on, "2025-04", "WOMEN").height > 0


def test_person_enrolled_during_the_run_opens_an_account_and_is_paid(tmp_path):
    world = World.build(cfg(tmp_path, **{"dbt.women.coverage": 1.0}), seed=7)
    s = world.state
    p = s.population.persons
    inp = dbt_inputs(s)
    hh_income = np.bincount(inp.household, weights=inp.income, minlength=inp.n_households)
    gov_emp = np.bincount(inp.household, weights=(p.life_stage == c.SALARIED) & (inp.sector == c.PUBLIC_ADMIN),
                          minlength=inp.n_households) > 0
    hh = inp.household
    who = np.flatnonzero((p.sex == c.F) & ((p.age < 21) | (p.age > 60)) & (s.person_deposit < 0)
                         & (hh_income[hh] * 12 < 25_000_000) & ~gov_emp[hh])[0]
    p.age[who] = 30                                    # now eligible, covered and unbanked
    run = world.run(until="2025-04-10")
    t = run.table("truth_dbt_monthly").collect().filter(pl.col("opened_account"))
    assert int(who) in t["entity_id"].to_list()
    ev = run.table("life_events").collect().filter((pl.col("event") == "ACCOUNT_OPENED")
                                                   & (pl.col("entity_id") == int(who)))
    assert ev.height == 1 and ev["account_id"][0] == s.person_deposit[who]
    esm = run.table("entity_state_monthly").collect().filter(pl.col("entity_id") == int(who))
    assert esm["has_account"].to_list() == [True]
    assert int(who) in dbt_payments(run, "DBT_WOMEN")["entity_id"].to_list()
    assert (t.join(ev, on="entity_id").height == 1)


def test_ineligible_next_month_stops_payment_and_transfer_income(tmp_path):
    world = World.build(cfg(tmp_path, **{"dbt.women.coverage": 1.0}), seed=7)
    s, params = world.state, world.params
    inp = dbt_inputs(s)
    w = women(inp, params, 7)
    old = old_age_pension(inp, params, 7)
    candidates = np.setdiff1d(np.setdiff1d(w.payee[w.enrolled], old.payee), pm_kisan(inp, params, 7).payee)
    who = int(candidates[~s.government.bpl[inp.household[candidates]]][0])
    s.population.persons.age[who] = 60
    s.life.birth_month[who] = 5                         # turns 61 on 1 May
    run = world.run(until="2025-05-31")
    days = dbt_payments(run, "DBT_WOMEN").filter(pl.col("entity_id") == who)["day"].to_list()
    assert days == ["2025-04-10"]
    assert s.behaviour.person_transfer[who] == 0
    rows = run.table("truth_dbt_monthly").collect().filter(pl.col("entity_id") == who)
    assert rows.select("month", "scheme").rows() == [("2025-04", "WOMEN")]


def test_coverage_zero_means_no_dbt_intents(tmp_path):
    zero = {"dbt.pm_kisan.coverage": 0.0, "dbt.old_age.coverage": 0.0, "dbt.women.coverage": 0.0}
    world = World.build(cfg(tmp_path, **zero), seed=7)
    run = world.run(until="2025-04-30")
    assert run.sql("select count(*) as n from payments where purpose like 'DBT_%'")["n"][0] == 0
    t = run.table("truth_dbt_monthly").collect()
    assert t.height > 0 and not t["enrolled"].any() and (t["monthly_value_paise"] == 0).all()
    assert (world.state.behaviour.person_transfer == 0).all()


def test_split_run_equals_single_run_and_determinism(tmp_path):
    one = World.build(cfg(tmp_path / "one", start="2025-04-03"), seed=7).run(until="2025-05-12")
    w = World.build(cfg(tmp_path / "two", start="2025-04-03"), seed=7)
    w.step(8)
    two = w.run(until="2025-05-12")
    assert "truth_dbt_monthly" in one.manifest["content_hash"]
    assert one.manifest["content_hash"] == two.manifest["content_hash"]
