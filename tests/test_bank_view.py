import polars as pl
import pytest

from arthasim import Config, World
from arthasim.views import MCC
from run_fixture import small_run

BANKS = [f"SYNB{i:02d}" for i in range(1, 13)]
WITHDRAW_OR_DEPOSIT = ["ATM", "AEPS", "BRANCH"]


def _bank_rows(run, table):
    return pl.concat([run.view("bank", bank=c).table(table).collect().with_columns(pl.lit(c).alias("seen_by"))
                      for c in BANKS])


def test_bank_view_tables_and_columns():
    v = small_run().view("bank", bank="SYNB03")
    assert v.tables() == ["accounts", "balances_monthly", "customers", "instruments", "payments", "statement_lines"]
    assert v.table("statement_lines").collect_schema().names() == [
        "account_id", "account_no", "entity_id", "customer_no", "ts", "date", "line_seq", "payment_id", "ref", "rail",
        "direction", "amount_paise", "balance_after_paise", "counterparty_handle", "counterparty_bank", "narration"]
    assert v.table("payments").collect_schema().names() == [
        "payment_id", "ref", "ts", "date", "rail", "status", "amount_paise", "direction", "account_id", "account_no",
        "entity_id", "customer_no", "counterparty_handle", "counterparty_bank", "mcc", "device_token"]


def test_statement_lines_close_on_monthly_balances():
    run = small_run()
    for code in BANKS:
        v = run.view("bank", bank=code)
        last = v.sql("""select account_id, arg_max(balance_after_paise, line_seq) as b from statement_lines
                        where date < date '2025-05-01' group by 1""")
        bal = v.table("balances_monthly").collect()
        joined = last.join(bal, on="account_id")
        assert joined.height == last.height and (joined["b"] == joined["balance_paise"]).all(), code


def test_statement_lines_partition_deposit_postings():
    run = small_run()
    total = sum(run.view("bank", bank=c).table("statement_lines").select(pl.len()).collect().item() for c in BANKS)
    expect = run.sql("""select count(*) n from postings p join accounts a using (account_id) join banks b
                        on a.issuer_entity_id = b.entity_id where a.type = 'DEPOSIT' and b.kind = 'BANK'""")["n"][0]
    assert total == expect > 0


def test_statement_line_balances_chain():
    lines = small_run().view("bank", bank="SYNB02").table("statement_lines").collect()
    signed = pl.when(pl.col("direction") == "DR").then(-pl.col("amount_paise")).otherwise(pl.col("amount_paise"))
    chk = lines.sort("account_id", "line_seq").with_columns(signed.alias("d")).with_columns(
        (pl.col("balance_after_paise") - pl.col("d")).alias("before"),
        pl.col("balance_after_paise").shift(1).over("account_id").alias("prev"))
    chained = chk.filter(pl.col("prev").is_not_null())
    assert chained.height > 0 and (chained["before"] == chained["prev"]).all()


def test_bank_view_hides_other_banks_and_truth():
    v = small_run().view("bank", bank="SYNB03")
    own = set(v.table("accounts").collect()["account_id"].to_list())
    customers = set(v.table("customers").collect()["entity_id"].to_list())
    for t in v.tables():
        frame = v.table(t).collect()
        assert "purpose" not in frame.columns and "journal_id" not in frame.columns, t
        if "account_id" in frame.columns:
            assert set(frame["account_id"].to_list()) <= own, t
        if "entity_id" in frame.columns:
            assert set(frame["entity_id"].to_list()) <= customers, t
    cust = v.table("customers").collect()
    assert "uid_token" not in cust.columns and "education" not in cust.columns and "birth_year" in cust.columns
    assert cust["customer_no"].str.starts_with("CIFSYNB03-").all()
    narr = v.table("statement_lines").collect()["narration"]
    assert narr.null_count() == 0
    assert not narr.str.contains("GROCERY|FOOD|ALLOWANCE|REMITTANCE|EARNINGS|EMPLOYER_REVENUE").any()
    assert narr.str.contains("^NACH/CR/[0-9]{12}/.+/SALARY$").any()


def test_cross_bank_payments_seen_from_both_sides():
    run = small_run()
    rows = _bank_rows(run, "payments")
    truth = run.table("payments").filter(
        (pl.col("status") == "SUCCESS") & pl.col("payer_bank").str.starts_with("SYNB")
        & pl.col("payee_bank").str.starts_with("SYNB") & ~pl.col("rail").is_in(WITHDRAW_OR_DEPOSIT)).collect()
    refs = set(truth["payment_id"].cast(pl.String).str.zfill(12).to_list())
    pairs = rows.filter(pl.col("ref").is_in(refs)).group_by("ref").agg(
        pl.col("direction").sort().str.join(",").alias("d"), pl.col("amount_paise").n_unique().alias("amounts"))
    assert pairs.height == len(refs) > 0
    assert (pairs["d"] == "CR,DR").all() and (pairs["amounts"] == 1).all()
    declined = rows.filter(pl.col("status") != "SUCCESS")
    assert declined.height > 0 and (declined["direction"] == "DR").all()


def test_counterparty_handles_follow_rail():
    pay = _bank_rows(small_run(), "payments")
    assert pay.filter(pl.col("rail") == "ATM")["counterparty_handle"].str.starts_with("ATMSY").all()
    aeps = pay.filter(pl.col("rail") == "AEPS")["counterparty_handle"]
    assert aeps.str.starts_with("MATMSY").all()
    upi = pay.filter(pl.col("rail").str.starts_with("UPI"))["counterparty_handle"]
    assert upi.null_count() == 0 and upi.str.contains("@syn|^SYN").all()
    assert pay.filter(pl.col("rail").is_in(["NEFT", "IMPS", "NACH_CR"]))["counterparty_handle"].str.contains(
        r"^SYN[BX]\d\d-[0-9a-f]{16}$").all()
    assert pay.filter(pl.col("rail") == "CASH").height == 0
    p2m = pay.filter((pl.col("rail") == "UPI_P2M") & (pl.col("direction") == "DR"))
    assert p2m.height > 0 and p2m["mcc"].is_in(list(MCC.values())).all()
    assert pay.filter(pl.col("rail") == "UPI_P2P")["mcc"].null_count() == pay.filter(pl.col("rail") == "UPI_P2P").height
    upi_dr = pay.filter(pl.col("rail").str.starts_with("UPI") & (pl.col("direction") == "DR"))
    assert upi_dr["device_token"].null_count() == 0
    assert pay.filter(pl.col("direction") == "CR")["device_token"].null_count() == pay.filter(
        pl.col("direction") == "CR").height


def test_bank_view_asof():
    v = small_run().view("bank", bank="SYNB01", asof="2025-04-30")
    assert v.table("payments").collect()["date"].max().isoformat() <= "2025-04-30"
    assert v.table("statement_lines").collect()["date"].max().isoformat() <= "2025-04-30"
    assert v.table("balances_monthly").collect()["month"].unique().to_list() == ["2025-04"]
    assert v.table("payments", asof="2025-04-19").collect().height == 0


def test_bank_with_no_customers_returns_empty_tables(tmp_path):
    run = World.build(Config.tier("S", persons=20, out_dir=str(tmp_path)), seed=7).run(until="2025-04-03")
    have = set(run.table("bank_customers").collect()["bank_code"].to_list())
    empty = [c for c in BANKS if c not in have]
    assert empty
    v = run.view("bank", bank=empty[0])
    full = small_run().view("bank", bank="SYNB01")
    for t in v.tables():
        frame = v.table(t).collect()
        assert frame.height == 0 and frame.columns == full.table(t).collect_schema().names(), t


def test_unknown_or_boundary_bank_raises():
    for code in ("SYNB99", "SYNX00"):
        with pytest.raises(ValueError, match="SYNB01"):
            small_run().view("bank", bank=code)
