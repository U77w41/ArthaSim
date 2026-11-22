from pathlib import Path

import numpy as np
import polars as pl
import pyarrow.parquet as pq

from arthasim import Config, World
from arthasim.store.hashing import content_hash
from arthasim.store.parquet import FACT_TABLES, Store, read_table, table_files
from reference_hash import reference_content_hash


def _cfg(tmp_path, start="2025-04-25"):
    return Config.tier("S", persons=2_000, start=start, out_dir=str(tmp_path))


def test_store_writes_row_groups_and_bounds_the_queue(tmp_path):
    store = Store(tmp_path, row_group_rows=1_000)
    frames = [pl.DataFrame({"a": np.arange(i * 700, (i + 1) * 700), "s": ["x"] * 700}) for i in range(10)]
    for f in frames:
        store.add("payments", "2025-04", f)
    store.flush()
    files = table_files(tmp_path, "payments")
    assert len(files) == 1 and pq.ParquetFile(files[0]).num_row_groups == 5   # 7,000 rows written whenever 1,000 are queued: 5 x 1,400
    assert read_table(tmp_path, "payments").collect().equals(pl.concat(frames))
    assert store.max_queued_rows < 1_000 + 700


def test_second_flush_in_same_month_opens_next_part(tmp_path):
    store = Store(tmp_path)
    store.add("journal", "2025-04", pl.DataFrame({"a": [1, 2]}))
    store.flush()
    store.add("journal", "2025-04", pl.DataFrame({"a": [3]}))
    store.flush()
    assert [f.name for f in table_files(tmp_path, "journal")] == ["part-0.parquet", "part-1.parquet"]


def test_live_hash_equals_disk_and_reference(tmp_path):
    world = World.build(_cfg(tmp_path), seed=7)
    world.step(3)
    run = world.run(until="2025-05-06")
    path, m = run.path, run.manifest
    checked = 0
    for t in FACT_TABLES:
        if table_files(path, t):
            assert m["content_hash"][t] == content_hash(path, t) == reference_content_hash(path, t), t
            checked += 1
    assert checked >= 6


def test_split_run_hashes_equal_single_run(tmp_path):
    one = World.build(_cfg(tmp_path / "one"), seed=7).run(until="2025-05-06")
    w = World.build(_cfg(tmp_path / "two"), seed=7)
    w.step(3)                                           # stops mid-April
    mid = w.run(until="2025-04-27")
    for t, h in mid.manifest["content_hash"].items():
        assert h == content_hash(mid.path, t), t
    w.step(4)
    two = w.run(until="2025-05-06")
    assert one.manifest["content_hash"] == two.manifest["content_hash"]


def test_spool_files_are_removed_when_a_month_closes(tmp_path):
    w = World.build(_cfg(tmp_path), seed=7)
    w.run(until="2025-05-02")
    spool = list(w._store.spool_dir.glob("*"))
    assert spool and not [f for f in spool if "2025-04" in f.name]


def test_manifest_records_polars_version(tmp_path):
    m = World.build(_cfg(tmp_path), seed=7).run(until="2025-04-26").manifest
    assert m["polars_version"] == pl.__version__
