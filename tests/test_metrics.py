import polars as pl
import pytest

import arthasim as sim
from arthasim.metrics import METRICS, SPENDING
from run_fixture import small_run


def _one(frame):
    assert frame.columns == ["value"] and frame.height == 1
    return frame["value"][0]


def test_builtins_agree_with_sql():
    run = small_run()
    assert set(METRICS) >= {"txn_volume", "decline_rate", "consumption", "cash_withdrawal", "deposit_balance"}
    assert _one(run.metric("txn_volume")) == run.sql("select count(*) n from payments where status = 'SUCCESS'")["n"][0]
    assert _one(run.metric("txn_volume", status=None)) == run.table("payments").collect().height
    assert _one(run.metric("txn_volume", status="DECLINED_FUNDS")) == \
        run.sql("select count(*) n from payments where status = 'DECLINED_FUNDS'")["n"][0]
    dr = _one(run.metric("decline_rate"))
    assert abs(dr - run.sql("select avg((status <> 'SUCCESS')::int) r from payments")["r"][0]) < 1e-12
    spend = "', '".join(SPENDING)
    want = run.sql(f"""select sum(amount_paise) s from payments where status = 'SUCCESS'
                       and purpose in ('{spend}')""")["s"][0]
    assert _one(run.metric("consumption")) == want > 0
    want = run.sql("""select sum(amount_paise) s from payments where status = 'SUCCESS'
                      and purpose = 'CASH_WITHDRAWAL'""")["s"][0]
    assert _one(run.metric("cash_withdrawal")) == want > 0
    db = run.metric("deposit_balance")
    want = run.sql("""select sum(b.balance_paise) s from balances_monthly b join accounts a using (account_id)
                      join persons p on p.entity_id = a.holder_entity_id where a.type = 'DEPOSIT'""")["s"][0]
    assert db.columns == ["month", "value"] and db["month"].to_list() == ["2025-04"] and db["value"][0] == want


@pytest.mark.parametrize("name", ["txn_volume", "consumption", "cash_withdrawal"])
@pytest.mark.parametrize("by", ["month", "rail", "bank", "district", "life_stage", ["month", "rail"]])
def test_grouped_values_sum_to_total(name, by):
    run = small_run()
    grouped = run.metric(name, by=by)
    cols = [by] if isinstance(by, str) else by
    assert grouped.columns == cols + ["value"]
    assert grouped["value"].sum() == _one(run.metric(name))


def test_groupings_take_sensible_values():
    run = small_run()
    months = run.metric("txn_volume", by="month")["month"].to_list()
    assert months == ["2025-04", "2025-05"]
    stages = set(run.metric("consumption", by="life_stage")["life_stage"].drop_nulls().to_list())
    assert {"salaried", "homemaker"} <= stages
    rates = run.metric("decline_rate", by="rail")
    assert ((rates["value"] >= 0) & (rates["value"] <= 1)).all()
    db = run.metric("deposit_balance", by=["bank", "district"])
    assert db.columns == ["month", "bank", "district", "value"]
    assert db["value"].sum() == _one(run.metric("deposit_balance").drop("month"))


def test_register_and_errors():
    run = small_run()

    @sim.register.metric
    def upi_share(run, by=None):
        return run.sql("select avg((rail like 'UPI%')::double) as value from payments where status = 'SUCCESS'")

    try:
        assert 0 < _one(run.metric("upi_share")) < 1
        with pytest.raises(ValueError, match="upi_share"):
            sim.register.metric(upi_share)
    finally:
        METRICS.pop("upi_share")
    assert _one(run.metric(lambda r: r.sql("select 7 as value"))) == 7
    with pytest.raises(ValueError, match="rail"):
        run.metric("deposit_balance", by="rail")
    with pytest.raises(ValueError, match="month"):
        run.metric("txn_volume", by="weekday")
    with pytest.raises(KeyError, match="txn_volume"):
        run.metric("nope")
