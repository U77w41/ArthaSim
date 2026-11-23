"""The bank keeps a customer's Aadhaar token only where an APBS credit or an AePS withdrawal needs the link."""
import datetime as dt

import polars as pl

from arthasim import Config, World
from arthasim.views import asof_us
from run_fixture import small_run

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))

# Truth: (bank, holder) of every deposit with a successful APBS credit or an AePS withdrawal, with the first time.
_NEEDS_AADHAAR = """
    with acct as (select a.account_id, a.holder_entity_id as entity_id, b.bank_code
                  from accounts a join banks b on a.issuer_entity_id = b.entity_id where a.type = 'DEPOSIT'),
    q as (select payee_account_id as account_id, settle_ts, 'APBS' as rail from payments
          where rail = 'APBS' and status = 'SUCCESS'
          union all
          select payer_account_id, settle_ts, 'AEPS' from payments where rail = 'AEPS')
    select a.bank_code, a.entity_id, min(q.settle_ts) as first_ts,
           bool_or(q.rail = 'APBS') as apbs, bool_or(q.rail = 'AEPS') as aeps
    from q join acct a using (account_id)
    group by 1, 2"""


def _tokens(run, bank, asof=None):
    return run.view("bank", bank=bank, asof=asof).table("customers").collect()


def test_uid_token_only_where_apbs_or_aeps_needs_it():
    run = small_run()
    need = run.sql(_NEEDS_AADHAAR)
    counts = need.group_by("bank_code").agg(pl.len().alias("n"), pl.col("apbs").sum().alias("na"),
                                            pl.col("aeps").sum().alias("ne"))
    bank = counts.filter((pl.col("na") > 0) & (pl.col("ne") > 0)).sort("n", descending=True)["bank_code"][0]
    cust = _tokens(run, bank)
    assert cust.columns.index("uid_token") == cust.columns.index("mobile_token") + 1
    got = cust.filter(pl.col("uid_token").is_not_null())
    assert set(got["entity_id"].to_list()) == set(need.filter(pl.col("bank_code") == bank)["entity_id"].to_list())
    persons = run.table("persons").select("entity_id", pl.col("uid_token").alias("person_uid")).collect()
    joined = got.join(persons, on="entity_id")
    assert joined.height == got.height and (joined["uid_token"] == joined["person_uid"]).all()
    orgs = cust.filter(pl.col("kind") != "PERSON")
    assert orgs.height and orgs["uid_token"].null_count() == orgs.height


def test_asof_hides_the_token_until_the_first_such_payment():
    run = small_run()
    need = run.sql(_NEEDS_AADHAAR).sort("first_ts")
    start = dt.date(2025, 4, 20)
    for bank, entity, first_ts in need.select("bank_code", "entity_id", "first_ts").iter_rows():
        day = dt.datetime.fromtimestamp(first_ts / 1e6, tz=IST).date()
        if day < start + dt.timedelta(days=2):
            continue
        before = _tokens(run, bank, day - dt.timedelta(days=1)).filter(pl.col("entity_id") == entity)
        if before.height == 0:          # not yet a customer of this bank the day before
            continue
        assert first_ts < asof_us(day) and first_ts >= asof_us(day - dt.timedelta(days=1))
        assert before["uid_token"][0] is None
        after = _tokens(run, bank, day).filter(pl.col("entity_id") == entity)
        assert after["uid_token"][0] is not None
        return
    raise AssertionError("no customer whose first APBS credit or AePS withdrawal comes after the run's second day")


def test_banks_without_such_payments_keep_no_token(tmp_path):     # Review Focus 5
    run = World.build(Config.tier("S", persons=20, out_dir=str(tmp_path)), seed=7).run(until="2025-04-03")
    need = run.sql(_NEEDS_AADHAAR)
    all_null = 0
    for bank in sorted(set(run.table("bank_customers").collect()["bank_code"].to_list())):
        cust = _tokens(run, bank)
        want = set(need.filter(pl.col("bank_code") == bank)["entity_id"].to_list())
        assert set(cust.filter(pl.col("uid_token").is_not_null())["entity_id"].to_list()) == want
        all_null += cust.height > 0 and cust["uid_token"].null_count() == cust.height
    assert all_null
