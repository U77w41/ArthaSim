"""Month-partitioned Parquet output and table reads. Rows are written in chunks as they arrive, so memory does
not grow with the size of a month."""
from __future__ import annotations

import os
import shutil
import tempfile
import weakref
from pathlib import Path

import polars as pl

from arthasim.store.hashing import RunningHash, content_hash, fact_files  # noqa: F401  (content_hash re-exported)

FACT_TABLES = ["payments", "journal", "postings", "truth_household_monthly", "life_events",
               "entity_state_monthly", "truth_dbt_monthly", "balances_monthly"]
DIM_TABLES = ["persons", "households", "orgs", "banks", "accounts", "instruments", "edges", "geo",
              "truth_person_latent", "bank_customers"]
# Run metadata: one file each, rewritten at every flush.
META_TABLES = ["macro_paths", "interventions_log"]
LOG_SCHEMA = {"seq": pl.Int64, "kind": pl.String, "effective": pl.Date, "ends": pl.Date, "details": pl.String,
              "affected": pl.Int64, "read_after": pl.Boolean}
ROW_GROUP_ROWS = 1_000_000


def write_atomic(path: Path, data: bytes | str) -> None:
    """Write under a temporary name and move it into place, so a file shared by hard link is never changed."""
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    if isinstance(data, str):
        temporary.write_text(data)
    else:
        temporary.write_bytes(data)
    os.replace(temporary, path)


class Store:
    """Fact rows are queued per table. Once `row_group_rows` are queued, they are written as one complete Parquet
    file (`part-N.parquet` in the table's month folder); `flush` writes what is queued. Each file is written under
    a temporary name and renamed when complete, so a reader never meets a half-written file. Each fact table's
    content hash is kept as rows are written."""

    def __init__(self, path: Path, row_group_rows: int = ROW_GROUP_ROWS) -> None:
        self.path = Path(path)
        self.row_group_rows = row_group_rows
        self._queue: dict[str, list[pl.DataFrame]] = {}
        self._queued: dict[str, int] = {}
        self._month: dict[str, str] = {}
        self._hash: dict[str, RunningHash] = {}
        self.max_queued_rows = 0
        # The open month's seed-1 row hashes wait here, outside the run folder; removed with the store or at exit.
        self.spool_dir = Path(tempfile.mkdtemp(prefix="arthasim-spool-"))
        self._cleanup = weakref.finalize(self, shutil.rmtree, str(self.spool_dir), True)

    def add(self, table: str, month: str, frame: pl.DataFrame) -> None:
        if not frame.height:
            return
        if self._month.get(table, month) != month:
            self._write(table)
        self._month[table] = month
        if table not in self._hash:
            self._hash[table] = RunningHash(self.spool_dir, table)
        self._hash[table].update(month, frame)
        self._queue.setdefault(table, []).append(frame)
        self._queued[table] = self._queued.get(table, 0) + frame.height
        self.max_queued_rows = max(self.max_queued_rows, self._queued[table])
        if self._queued[table] >= self.row_group_rows:
            self._write(table)

    def _write(self, table: str) -> None:
        frames = self._queue.get(table)
        if not frames:
            return
        folder = self.path / table / f"month={self._month[table]}"
        folder.mkdir(parents=True, exist_ok=True)
        final = folder / f"part-{len(list(folder.glob('part-*.parquet')))}.parquet"
        temporary = final.with_name(final.name + ".tmp")
        pl.concat(frames).write_parquet(temporary)
        temporary.rename(final)
        self._queue[table], self._queued[table] = [], 0

    def flush(self) -> None:
        """Write every queued row."""
        for table in list(self._queue):
            self._write(table)

    def end_month(self, month: str) -> None:
        """The month is over: write its rows and fold every table's spool for it into the running hash."""
        self.flush()
        for h in self._hash.values():
            if h.month == month:
                h.close_month()

    def restore(self, hashes: dict[str, RunningHash]) -> None:
        """Continue from running hashes rebuilt from disk or copied from another store (all months closed)."""
        self._hash = dict(hashes)
        self._month = {t: h.month for t, h in hashes.items() if h.month is not None}

    def content_hashes(self) -> dict[str, str]:
        """Live content hashes of the fact tables written so far."""
        return {t: h.digest() for t, h in self._hash.items()}

    def write_dimension(self, name: str, frame: pl.DataFrame) -> None:
        """Dimension and metadata tables are replaced whole, never rewritten in place (see `write_atomic`)."""
        final = self.path / f"{name}.parquet"
        temporary = final.with_name(final.name + ".tmp")
        frame.write_parquet(temporary)
        os.replace(temporary, final)


def table_files(path: Path, name: str) -> list[Path]:
    """Files of a table, facts in month then part order."""
    path = Path(path)
    if name in DIM_TABLES or name in META_TABLES:
        f = path / f"{name}.parquet"
        return [f] if f.exists() else []
    return fact_files(path, name)


def read_table(path: Path, name: str) -> pl.LazyFrame:
    files = table_files(path, name)
    if not files:
        raise FileNotFoundError(f"no table {name!r} in {path}")
    return pl.concat([pl.scan_parquet(f, hive_partitioning=False) for f in files])
