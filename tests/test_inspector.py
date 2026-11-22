import datetime as dt

import polars as pl
import pytest

from arthasim.inspector import EntityTrace
from arthasim.views import asof_us
from run_fixture import small_run


def _salaried():
    """A salaried person with a bank account and life events, from the fixture run."""
    run = small_run()
    q = run.sql("""select e.entity_id from entity_state_monthly e
                   where e.month = '2025-05' and e.life_stage = 'salaried' and e.has_account
                   order by e.entity_id limit 1""")
    return int(q["entity_id"][0])


def _accounts(run, eid):
    return run.sql(f"select account_id from accounts where holder_entity_id = {eid}")["account_id"].to_list()


def test_inspect_returns_trace_and_rejects_unknown():
    run = small_run()
    assert isinstance(run.inspect(_salaried()), EntityTrace)
    with pytest.raises(KeyError):
        run.inspect(10**12)


def test_passbook_balances_chain_and_cover_all_postings():
    run = small_run()
    eid = _salaried()
    pb = run.inspect(eid).passbook()
    assert {"ts", "account_id", "account_type", "rail", "direction", "amount_paise", "balance_after_paise",
            "counterparty_handle", "narration", "purpose", "payment_id"} <= set(pb.columns)
    signed = pl.when(pl.col("direction") == "DR").then(-pl.col("amount_paise")).otherwise(pl.col("amount_paise"))
    chk = pb.sort("account_id", "line_seq").with_columns(
        (pl.col("balance_after_paise") - signed).alias("before"),
        pl.col("balance_after_paise").shift(1).over("account_id").alias("prev")).filter(pl.col("prev").is_not_null())
    assert chk.height > 0 and (chk["before"] == chk["prev"]).all()
    n = run.sql(f"""select count(*) n from postings p join accounts a using (account_id)
                    where a.holder_entity_id = {eid}""")["n"][0]
    assert pb.height == n
    deposit = pb.filter(pl.col("account_type") == "DEPOSIT")
    assert deposit["narration"].null_count() == 0
    assert pb.filter(pl.col("account_type") == "CASH")["narration"].null_count() == \
        pb.filter(pl.col("account_type") == "CASH").height
    one = pb["account_id"][0]
    assert run.inspect(eid).passbook(account_id=one)["account_id"].unique().to_list() == [one]
    with pytest.raises(KeyError):
        run.inspect(eid).passbook(account_id=10**9)


def test_timeline_has_every_payment_and_event():
    run = small_run()
    eid = _salaried()
    tl = run.inspect(eid).timeline()
    assert tl.columns == ["ts", "kind", "rail", "status", "direction", "amount_paise", "account_id",
                          "counterparty_entity_id", "counterparty_account_id", "purpose", "event", "detail"]
    accts = _accounts(run, eid)
    pays = run.table("payments").filter(pl.col("payer_account_id").is_in(accts)
                                        | pl.col("payee_account_id").is_in(accts)).collect()
    events = run.table("life_events").filter(pl.col("entity_id") == eid).collect()
    assert tl.filter(pl.col("kind") == "payment").height == pays.height
    assert tl.filter(pl.col("kind") == "event").height == events.height
    assert tl["ts"].is_sorted()
    assert set(tl["direction"].drop_nulls().unique().to_list()) <= {"DR", "CR", "SELF"}
    salary = tl.filter(pl.col("purpose") == "SALARY")
    assert salary.height > 0 and (salary["direction"] == "CR").all()


def test_profile_asof_in_open_month_uses_postings():
    run = small_run()
    eid = _salaried()
    p = run.inspect(eid).profile(asof="2025-05-10")
    assert p["entity_id"] == eid and p["kind"] == "PERSON" and p["static"]["entity_id"] == eid
    assert p["state"]["month"] == "2025-05" and eid in p["household"]
    cut = asof_us("2025-05-10")
    for a in p["accounts"]:
        last = run.sql(f"""select p.balance_after_paise b from postings p join journal j using (journal_id)
                           where p.account_id = {a['account_id']} and j.ts < {cut}
                           order by p.journal_id desc, p.line_no desc limit 1""")
        opening = run.sql(f"select opening_balance_paise o from accounts where account_id = {a['account_id']}")["o"][0]
        assert a["balance_paise"] == (last["b"][0] if last.height else opening)
    deposit = [a for a in p["accounts"] if a["type"] == "DEPOSIT"]
    assert deposit and deposit[0]["bank_code"].startswith("SYNB") and "ACCOUNT_NO" in deposit[0]["handles"]
    assert run.inspect(eid).profile()["state"]["month"] == "2025-05"


def test_net_worth_matches_monthly_balances():
    run = small_run()
    eid = _salaried()
    nw = run.inspect(eid).net_worth()
    assert nw.columns == ["month", "deposits_paise", "cash_paise", "total_paise"]
    assert nw["month"].to_list() == ["2025-04"]                                # May is still open
    assert (nw["total_paise"] == nw["deposits_paise"] + nw["cash_paise"]).all()
    want = run.sql(f"""select sum(b.balance_paise) s from balances_monthly b join accounts a using (account_id)
                       where a.holder_entity_id = {eid}""")["s"][0]
    assert nw["total_paise"][0] == want


def test_unbanked_person_and_merchant():
    run = small_run()
    u = int(run.sql("""select entity_id from entity_state_monthly where month = '2025-05' and not has_account
                       order by entity_id limit 1""")["entity_id"][0])
    t = run.inspect(u)
    assert set(t.passbook()["account_type"].to_list()) <= {"CASH"}
    assert all(a["type"] == "CASH" and a["handles"] == {} for a in t.profile()["accounts"])
    assert t.net_worth()["deposits_paise"].to_list() == [0]
    m = int(run.sql("select entity_id from orgs where kind = 'MERCHANT' order by entity_id limit 1")["entity_id"][0])
    mt = run.inspect(m)
    assert mt.profile()["state"] is None and mt.profile()["household"] is None and mt.passbook().height > 0
    assert mt.timeline().filter(pl.col("kind") == "event").height == 0


def test_ego_network_and_loans():
    run = small_run()
    eid = _salaried()
    e1 = run.inspect(eid).ego_network()
    e2 = run.inspect(eid).ego_network(hops=2)
    assert e1.columns == ["src_entity_id", "dst_entity_id", "type", "hop"]
    assert e1.height > 0 and set(e1["hop"].to_list()) == {1}
    assert ((e1["src_entity_id"] == eid) | (e1["dst_entity_id"] == eid)).all()
    assert e2.height >= e1.height and set(e2["hop"].to_list()) <= {1, 2}
    assert e2.filter(pl.col("hop") == 1).sort(e1.columns).equals(e1.sort(e1.columns))
    assert run.inspect(eid).loans().height == 0
