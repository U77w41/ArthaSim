import json

import polars as pl
import pytest

from arthasim import Config, World
from arthasim.export import ID_COLUMNS, is_id
from arthasim.views import DESCRIPTIONS
from run_fixture import small_run


def _read(dest, t, layout):
    return pl.read_parquet(dest / t, hive_partitioning=True) if layout == "month" else pl.read_parquet(dest / f"{t}.parquet")


def test_bank_export_round_trip(tmp_path):
    run = small_run()
    dest = tmp_path / "b3"
    assert run.export(dest, view="bank", bank="SYNB03") == dest
    v = run.view("bank", bank="SYNB03")
    m = json.loads((dest / "manifest.json").read_text())
    assert m["view"] == "bank" and m["scope"] == {"bank": "SYNB03"} and m["asof"] is None
    assert m["source_run_id"] == run.manifest["run_id"] and m["source_content_hash"] == run.manifest["content_hash"]
    assert set(m["tables"]) == set(v.tables())
    for t in v.tables():
        meta = m["tables"][t]
        got = _read(dest, t, meta["layout"])
        assert not [c for c in got.columns if is_id(c)], t
        want = v.table(t).collect()
        want = want.drop([c for c in want.columns if is_id(c)])
        assert got.height == want.height == meta["rows"], t
        assert [c for c, _ in meta["columns"]] == [c for c in want.columns if c != "month" or meta["layout"] != "month"]
        assert got.select(want.columns).sort(want.columns).equals(want.sort(want.columns)), t
    assert m["tables"]["statement_lines"]["layout"] == "month"
    assert sorted(p.name for p in (dest / "statement_lines").iterdir()) == ["month=2025-04", "month=2025-05"]
    assert "account_no" in _read(dest, "instruments", "file").columns
    readme = (dest / "README.md").read_text()
    assert all(f"## {t}" in readme for t in v.tables()) and "customer_no" in readme


def test_export_is_deterministic(tmp_path):
    a = json.loads((small_run().export(tmp_path / "a", view="switch") / "manifest.json").read_text())
    b = json.loads((small_run().export(tmp_path / "b", view="switch") / "manifest.json").read_text())
    assert a == b and a["scope"] == {"network": "upi"} and a["tables"]["payments"]["rows"] > 0


def test_export_asof(tmp_path):
    m = json.loads((small_run().export(tmp_path / "x", view="bank", bank="SYNB01", asof="2025-04-30")
                    / "manifest.json").read_text())
    assert m["asof"] == "2025-04-30"
    assert sorted(p.name for p in (tmp_path / "x" / "payments").iterdir()) == ["month=2025-04"]


def test_export_refuses_non_empty_dest_and_allows_empty(tmp_path):
    (tmp_path / "full").mkdir()
    (tmp_path / "full" / "x").write_text("x")
    with pytest.raises(FileExistsError):
        small_run().export(tmp_path / "full", view="bureau")
    (tmp_path / "empty").mkdir()
    m = json.loads((small_run().export(tmp_path / "empty", view="bureau") / "manifest.json").read_text())
    assert all(t["rows"] == 0 and t["layout"] == "file" for t in m["tables"].values())
    assert pl.read_parquet(tmp_path / "empty" / "tradelines.parquet").columns == [
        "pan_like", "lender_code", "product", "month", "sanctioned_paise", "balance_paise", "dpd"]


def test_empty_bank_export(tmp_path):
    run = World.build(Config.tier("S", persons=20, out_dir=str(tmp_path / "w")), seed=7).run(until="2025-04-03")
    have = set(run.table("bank_customers").collect()["bank_code"].to_list())
    empty = [f"SYNB{i:02d}" for i in range(1, 13) if f"SYNB{i:02d}" not in have]
    assert empty
    m = json.loads((run.export(tmp_path / "e", view="bank", bank=empty[0]) / "manifest.json").read_text())
    assert all(t["rows"] == 0 and t["layout"] == "file" for t in m["tables"].values())
    assert pl.read_parquet(tmp_path / "e" / "statement_lines.parquet").height == 0


def test_truth_export_keeps_ids_and_hashes(tmp_path):
    run = small_run()
    m = json.loads((run.export(tmp_path / "t", view="truth") / "manifest.json").read_text())
    assert "entity_id" in pl.read_parquet(tmp_path / "t" / "persons.parquet").columns
    for t in run.tables():
        assert m["tables"][t]["content_hash"] == run.manifest["content_hash"][t], t
    with pytest.raises(ValueError, match="asof"):
        run.export(tmp_path / "t2", view="truth", asof="2025-05-01")


def test_every_view_column_is_described():
    for kind, scope in [("bank", {"bank": "SYNB01"}), ("switch", {}), ("bureau", {})]:
        v = small_run().view(kind, **scope)
        for t in v.tables():
            missing = set(v.table(t).collect_schema().names()) - set(DESCRIPTIONS[t])
            assert not missing, (kind, t, missing)
    assert ID_COLUMNS == {"entity_id", "account_id", "payment_id", "journal_id", "household_id"}
    assert is_id("counterparty_entity_id") and is_id("payee_account_id") and not is_id("account_no")
