import pytest
from arthasim import Config, World

PAY_DAY = {"PM_KISAN": None, "OLD_AGE_PENSION": 5, "WOMEN": 10}
PURPOSE = {"PM_KISAN": "DBT_PM_KISAN", "OLD_AGE_PENSION": "DBT_OLD_AGE_PENSION", "WOMEN": "DBT_WOMEN"}
PM_KISAN_DAYS = {"2025-08-02", "2025-11-19", "2026-03-13"}


@pytest.mark.slow
def test_plan_1d1_gate(tmp_path):
    world = World.build(Config.tier("S", out_dir=str(tmp_path)), seed=7)
    run = world.run(until="2026-03-31")            # every invariant is checked daily
    assert run.manifest["days"] == 365
    pay = run.sql("""
        select y.purpose, y.rail, y.status, y.amount_paise, a.holder_entity_id as entity_id,
               strftime(make_timestamp(y.intent_ts) + interval 330 minute, '%Y-%m-%d') as day
        from payments y join accounts a on a.account_id = y.payee_account_id
        where y.purpose like 'DBT_%'""")
    assert set(pay["rail"]) == {"APBS"} and set(pay["status"]) == {"SUCCESS"}
    assert set(pay.filter(pay["purpose"] == "DBT_PM_KISAN")["day"]) == PM_KISAN_DAYS
    enrolled = run.sql("select month, scheme, entity_id, monthly_value_paise from truth_dbt_monthly where enrolled")
    for scheme, purpose in PURPOSE.items():
        got = pay.filter(pay["purpose"] == purpose)
        want = enrolled.filter(enrolled["scheme"] == scheme)
        months = sorted(set(want["month"]))
        assert len(months) == 12
        for month in months:
            paid = got.filter(got["day"].str.starts_with(month))
            if scheme == "PM_KISAN" and not any(d.startswith(month) for d in PM_KISAN_DAYS):
                assert paid.height == 0
                continue
            rows = want.filter(want["month"] == month)
            assert sorted(paid["entity_id"]) == sorted(rows["entity_id"]), (scheme, month)
            if scheme != "PM_KISAN":
                assert set(paid["day"].str.slice(8, 2).cast(int)) == {PAY_DAY[scheme]}
                assert sorted(zip(paid["entity_id"], paid["amount_paise"])) == \
                    sorted(zip(rows["entity_id"], rows["monthly_value_paise"]))
    gov = world.state.government
    assert int(world.state.book.balance[gov.balance_account]) == -int(pay["amount_paise"].sum())
