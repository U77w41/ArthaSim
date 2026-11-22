import polars as pl
import pytest

from run_fixture import small_run

NETWORK_RAILS = {"upi": ["UPI_P2M", "UPI_P2P"], "imps": ["IMPS"], "nach": ["NACH_CR"], "card": ["DEBIT_CARD"],
                 "atm": ["ATM"], "aeps": ["AEPS"]}


def test_switch_sees_every_attempt_on_its_network_once():
    run = small_run()
    for net, rails in NETWORK_RAILS.items():
        sw = run.view("switch", network=net).table("payments").collect()
        truth = run.table("payments").filter(pl.col("rail").is_in(rails)).collect()
        assert sorted(sw["payment_id"].to_list()) == sorted(truth["payment_id"].to_list()), net
        assert sw.height > 0 or net == "imps", net
        assert not {"payer_account_id", "payee_account_id", "purpose", "balance_after_paise", "journal_id"} \
            & set(sw.columns)


def test_switch_columns_and_handles():
    upi = small_run().view("switch").table("payments").collect()
    assert upi.columns == ["payment_id", "ref", "ts", "date", "rail", "status", "amount_paise", "payer_handle",
                           "payer_bank", "payee_handle", "payee_bank", "mcc", "payer_device_token"]
    assert upi["payer_handle"].null_count() == 0 and upi["payee_handle"].null_count() == 0
    assert upi["status"].n_unique() > 1                                       # declines are seen too
    p2m = upi.filter(pl.col("rail") == "UPI_P2M")
    assert p2m["mcc"].null_count() == 0 and p2m["payer_device_token"].null_count() == 0
    atm = small_run().view("switch", network="atm").table("payments").collect()
    assert atm["payee_handle"].str.starts_with("ATMSY").all() and (atm["payee_bank"] == atm["payer_bank"]).all()
    aeps = small_run().view("switch", network="aeps").table("payments").collect()
    assert aeps["payer_handle"].str.starts_with("u_").all() and aeps["payee_handle"].str.starts_with("MATM").all()
    card = small_run().view("switch", network="card").table("payments").collect()
    assert card["payee_handle"].str.starts_with("t_").all() and card["payer_handle"].str.starts_with("c_").all()


def test_bureau_is_empty_with_columns():
    b = small_run().view("bureau")
    assert b.tables() == ["consumers", "enquiries", "scores", "tradelines"]
    assert all(b.table(t).collect().height == 0 for t in b.tables())
    assert b.table("consumers").collect_schema().names() == ["pan_like", "birth_year", "birth_month", "sex",
                                                             "district", "mobile_token"]
    assert b.table("tradelines").collect_schema().names() == ["pan_like", "lender_code", "product", "month",
                                                              "sanctioned_paise", "balance_paise", "dpd"]
    assert b.sql("select count(*) n from enquiries")["n"][0] == 0


def test_unknown_network_or_scope_raises():
    with pytest.raises(ValueError, match="upi"):
        small_run().view("switch", network="neft")
    with pytest.raises(ValueError):
        small_run().view("bureau", bank="SYNB01")
