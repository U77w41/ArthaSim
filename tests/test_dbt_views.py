"""Government transfers (plan 1d-1) as each observer sees them."""
import polars as pl

from run_fixture import small_run

BANKS = [f"SYNB{i:02d}" for i in range(1, 13)]
SCHEMES = {"DBT_PM_KISAN", "DBT_OLD_AGE_PENSION", "DBT_WOMEN"}


def test_bank_statements_name_pfms_and_the_scheme():
    run = small_run()
    lines = pl.concat([run.view("bank", bank=c).table("statement_lines").filter(pl.col("rail") == "APBS").collect()
                       for c in BANKS])
    truth = run.table("payments").filter(pl.col("rail") == "APBS").collect()
    assert lines.height == truth.height > 0
    assert (lines["direction"] == "CR").all() and lines["counterparty_handle"].eq_missing("PFMS").all()
    assert lines["counterparty_bank"].null_count() == lines.height          # the government banks with RBI
    assert lines["narration"].str.contains(r"^APBS/CR/[0-9]{12}/PFMS/DBT_(PM_KISAN|OLD_AGE_PENSION|WOMEN)$").all()
    pay = run.view("bank", bank="SYNB01").table("payments").filter(pl.col("rail") == "APBS").collect()
    assert pay["counterparty_handle"].eq_missing("PFMS").all() and pay["mcc"].null_count() == pay.height


def test_apbs_switch_routes_on_aadhaar():
    run = small_run()
    sw = run.view("switch", network="apbs").table("payments").collect()
    truth = run.table("payments").filter(pl.col("rail") == "APBS").collect()
    assert sorted(sw["payment_id"].to_list()) == sorted(truth["payment_id"].to_list())
    assert sw["payer_handle"].eq_missing("PFMS").all() and sw["payer_bank"].null_count() == sw.height
    assert sw["payee_handle"].str.starts_with("u_").all() and sw["payee_bank"].str.starts_with("SYNB").all()
    uid = run.sql("""select y.payment_id, p.uid_token from payments y join accounts a on a.account_id = y.payee_account_id
                     join persons p on p.entity_id = a.holder_entity_id where y.rail = 'APBS'""")
    joined = sw.join(uid, on="payment_id")
    assert (joined["payee_handle"] == joined["uid_token"]).all()


def test_truth_view_cuts_dbt_table_by_month():
    v = small_run().view("truth", asof="2025-04-30")
    assert v.table("truth_dbt_monthly").collect()["month"].unique().to_list() == ["2025-04"]


def test_inspect_the_government():
    run = small_run()
    gov = int(run.sql("select entity_id from orgs where kind = 'GOVERNMENT'")["entity_id"][0])
    t = run.inspect(gov)
    p = t.profile()
    assert p["kind"] == "GOVERNMENT" and p["state"] is None and [a["type"] for a in p["accounts"]] == ["GOVERNMENT"]
    apbs = run.table("payments").filter(pl.col("rail") == "APBS").collect().height
    pb = t.passbook()
    assert pb.height == apbs and (pb["direction"] == "DR").all() and pb["narration"].null_count() == apbs
