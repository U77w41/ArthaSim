"""Exports say whether the run had a release secret, key the source label with it, and list rows by the bank's own
numbers rather than by simulator IDs."""
import hashlib
import json

import polars as pl

from arthasim.engine.rng import KeyedSeed
from arthasim.world import Run
from run_fixture import RELEASE_SECRET, secret_run, small_run


def _sha16(text):
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _biggest_bank(run):
    counts = run.table("bank_customers").collect().group_by("bank_code").len()
    return counts.sort(["len", "bank_code"], descending=[True, False])["bank_code"][0]


def test_secret_run_export_says_so_and_carries_nothing_secret(tmp_path):
    run = secret_run()
    dest = run.export(tmp_path / "e", view="bank", bank=_biggest_bank(run))
    m = json.loads((dest / "manifest.json").read_text())
    assert m["release_secret"] is True
    assert m["source_run"] == run.manifest["source_label"] != _sha16(run.manifest["run_id"])
    readme = (dest / "README.md").read_text()
    assert "release secret" in readme and "SipHash-2-4" in readme and "not anonymised" not in readme
    assert "seed" not in ((dest / "manifest.json").read_text() + readme).lower()
    ks = KeyedSeed.derive(7, bytes.fromhex(RELEASE_SECRET))
    draws = ks.k0.to_bytes(8, "little") + ks.k1.to_bytes(8, "little")
    needles = [RELEASE_SECRET.encode(), bytes.fromhex(RELEASE_SECRET), ks.id_key, ks.id_key.hex().encode(),
               draws, draws.hex().encode(), str(ks.k0).encode(), str(ks.k1).encode()]
    files = [f for f in dest.rglob("*") if f.is_file()]
    assert files
    for f in files:
        data = f.read_bytes()
        assert not any(n in data for n in needles), f


def test_plain_run_export_says_it_is_not_for_release(tmp_path):
    dest = small_run().export(tmp_path / "e", view="bank", bank="SYNB03")
    assert json.loads((dest / "manifest.json").read_text())["release_secret"] is False
    readme = (dest / "README.md").read_text()
    assert "not anonymised" in readme and "pan_like" in readme and "ref" in readme and "SipHash" not in readme


def test_runs_written_before_release_secrets_still_export(tmp_path):     # Review Focus 4
    run = small_run()
    old = Run(run.path, {k: v for k, v in run.manifest.items() if k not in ("source_label", "release_secret")})
    m = json.loads((old.export(tmp_path / "e", view="bank", bank="SYNB03") / "manifest.json").read_text())
    assert m["source_run"] == _sha16(run.manifest["run_id"]) and m["release_secret"] is False


def test_bank_export_rows_follow_the_banks_own_numbers(tmp_path):
    run = small_run()
    dest = run.export(tmp_path / "e", view="bank", bank="SYNB03")
    cust = pl.read_parquet(dest / "customers.parquet")
    assert cust.height > 1 and cust["customer_no"].is_sorted() and not cust["customer_no"].is_duplicated().any()
    acc = pl.read_parquet(dest / "accounts.parquet")
    assert acc.height > 1 and acc["account_no"].is_sorted()
    inst = pl.read_parquet(dest / "instruments.parquet")
    assert inst.height > 1 and inst.equals(inst.sort(["account_no", "kind", "value"]))
    bal = pl.read_parquet(str(dest / "balances_monthly" / "**" / "*.parquet"), hive_partitioning=True)
    assert bal.height > 1 and bal.equals(bal.sort(["month", "account_no"]))
    view = run.view("bank", bank="SYNB03").table("customers").collect()
    assert view["entity_id"].is_sorted()          # the Python view keeps simulator order


def test_readme_describes_pan_like_as_the_run_made_it(tmp_path):     # final review, Minor 2 re-graded
    run = small_run()
    new = (run.export(tmp_path / "new", view="bank", bank="SYNB03") / "README.md").read_text()
    assert "`pan_like` is a keyed shuffle" in new and "encodes the person's place" not in new
    old_run = Run(run.path, {k: v for k, v in run.manifest.items() if k not in ("source_label", "release_secret")})
    old = (old_run.export(tmp_path / "old", view="bank", bank="SYNB03") / "README.md").read_text()
    assert "`pan_like` encodes the person's place in the population" in old and "keyed shuffle" not in old
    assert "not anonymised" in old
