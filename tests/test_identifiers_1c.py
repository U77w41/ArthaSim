import datetime as dt

import numpy as np
import polars as pl

import arthasim.build.pipeline as pipeline
from arthasim import Config, World
from arthasim.build.world import EntityKind


def _world(tmp_path, **kw):
    return World.build(Config.tier("S", persons=2_000, out_dir=str(tmp_path), **kw), seed=7)


def test_handles_are_opaque_unique_and_keyed(tmp_path):
    w = _world(tmp_path)
    s = w.state
    run = w.run(until="2025-04-02")
    inst = run.table("instruments").collect()
    assert set(inst["kind"].unique()) == {"VPA", "DEVICE", "DEBIT_CARD", "MOBILE", "BRANCH", "ACCOUNT_NO", "TERMINAL"}
    acc = run.table("accounts").collect()
    banks = run.table("banks").collect().select(pl.col("entity_id").alias("issuer_entity_id"), "bank_code")
    deposits = acc.filter(pl.col("type") == "DEPOSIT").join(banks, on="issuer_entity_id")

    nos = inst.filter(pl.col("kind") == "ACCOUNT_NO").join(deposits, on="account_id", how="left")
    assert sorted(nos["account_id"].to_list()) == sorted(deposits["account_id"].to_list())
    assert nos["value"].n_unique() == nos.height
    assert (nos["value"].str.slice(0, 6) == nos["bank_code"]).all()
    assert nos["value"].str.contains(r"^SYN[BX]\d\d-[0-9a-f]{16}$").all()

    k, o = s.population.banking, s.population.orgs
    vpa = inst.filter(pl.col("kind") == "VPA").join(deposits, on="account_id", how="left")
    expect = (set(s.person_deposit[k.person_upi].tolist()) | set(s.merchant_deposit[o.merchant_accepts_upi].tolist())
              | set(s.biller_deposit.tolist()))
    assert set(vpa["account_id"].to_list()) == expect
    assert vpa["value"].str.contains(r"^[pmb]_[0-9a-f]{16}@syn\d\d$").all()
    assert (vpa["value"].str.slice(-2) == vpa["bank_code"].str.slice(-2)).all()
    assert vpa["value"].n_unique() == vpa.height

    term = inst.filter(pl.col("kind") == "TERMINAL")
    assert set(term["account_id"].to_list()) == set(s.merchant_deposit[o.merchant_accepts_card].tolist())
    assert term["value"].str.contains(r"^t_[0-9a-f]{16}$").all()

    cust = run.table("bank_customers").collect()
    assert cust.columns == ["bank_code", "entity_id", "customer_no"]
    assert cust["customer_no"].n_unique() == cust.height
    assert cust["customer_no"].str.contains(r"^CIFSYNB\d\d-[0-9a-f]{16}$").all()
    assert (cust["customer_no"].str.slice(3, 6) == cust["bank_code"]).all()
    holders = deposits.filter(pl.col("bank_code") != "SYNX00").select("bank_code", pl.col("holder_entity_id")
                                                                      .alias("entity_id")).unique()
    kinds = s.kind[holders["entity_id"].to_numpy()]
    assert np.isin(kinds, [EntityKind.PERSON, EntityKind.EMPLOYER, EntityKind.MERCHANT, EntityKind.BILLER]).all()
    assert cust.select("bank_code", "entity_id").sort(["bank_code", "entity_id"]).equals(
        holders.sort(["bank_code", "entity_id"]))
    assert cust.equals(cust.sort(["bank_code", "entity_id"]))


def test_birth_year_matches_monthly_ages(tmp_path):
    run = _world(tmp_path, start="2025-04-01").run(until="2026-04-30")
    ages = run.sql("""select e.age, e.month, p.birth_year, p.birth_month from entity_state_monthly e
                      join persons p using (entity_id)""")
    year = ages["month"].str.slice(0, 4).cast(pl.Int64)
    month = ages["month"].str.slice(5, 2).cast(pl.Int64)
    assert ages.height == 2_000 * 13
    assert (ages["age"] == year - ages["birth_year"] - (month < ages["birth_month"]).cast(pl.Int64)).all()
    cols = run.table("persons").collect_schema().names()
    assert cols[cols.index("birth_month") + 1] == "birth_year"


def test_new_identifiers_do_not_change_simulation(tmp_path, monkeypatch):
    real = _world(tmp_path / "real").run(until="2025-04-03").manifest["content_hash"]
    const = lambda *a, **kw: np.full(len(np.asarray(a[1])), "x", dtype=object)
    for name in ("vpa", "account_no", "terminal"):
        monkeypatch.setattr(pipeline, name, const)
    monkeypatch.setattr(pipeline, "customer_no", lambda seed, ids, *a: np.array([f"c{i}" for i in range(len(ids))],
                                                                                dtype=object))
    fake = _world(tmp_path / "fake").run(until="2025-04-03").manifest["content_hash"]
    for t in ("payments", "journal", "postings", "life_events", "entity_state_monthly", "truth_household_monthly"):
        assert real[t] == fake[t], t


def test_opening_balance_and_mid_run_accounts(tmp_path):
    w = _world(tmp_path, start="2025-04-01")
    run = w.run(until="2025-06-02")
    acc = run.table("accounts").collect()
    assert acc.columns[-1] == "opening_balance_paise"
    assert (acc["opening_balance_paise"].to_numpy() == w.state.book.opening).all()
    late = acc.filter(pl.col("opened_on") > dt.date(2025, 4, 1))
    assert late.height > 0 and (late["opening_balance_paise"] == 0).all()
    nos = run.table("instruments").filter(pl.col("kind") == "ACCOUNT_NO").collect()
    assert set(late["account_id"].to_list()) <= set(nos["account_id"].to_list())
    cust = run.table("bank_customers").collect()
    assert set(late["holder_entity_id"].to_list()) <= set(cust["entity_id"].to_list())
