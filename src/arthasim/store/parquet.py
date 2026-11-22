"""Month-partitioned Parquet output and table reads. Rows are written in row groups as they arrive, so
memory does not grow with the size of a month."""
from __future__ import annotations

from pathlib import Path

import polars as pl
import pyarrow.parquet as pq

from arthasim.store.hashing import RunningHash, content_hash, fact_files  # noqa: F401  (content_hash re-exported)

FACT_TABLES = ["payments", "journal", "postings", "truth_household_monthly", "life_events",
               "entity_state_monthly", "truth_dbt_monthly", "balances_monthly"]
DIM_TABLES = ["persons", "households", "orgs", "banks", "accounts", "instruments", "edges", "geo",
              "truth_person_latent", "bank_customers"]
ROW_GROUP_ROWS = 500_000


class Store:
    """Fact rows are queued per table and written as a row group to that table's open file for the month
    once `row_group_rows` are queued. `flush` writes what is queued and closes every file; a later write in
    the same month opens the next part file. Each fact table's content hash is kept as rows are written."""

    def __init__(self, path: Path, row_group_rows: int = ROW_GROUP_ROWS) -> None:
        self.path = Path(path)
        self.row_group_rows = row_group_rows
        self._queue: dict[str, list[pl.DataFrame]] = {}
        self._queued: dict[str, int] = {}
        self._month: dict[str, str] = {}
        self._writer: dict[str, pq.ParquetWriter] = {}
        self._hash: dict[str, RunningHash] = {}
        self.max_queued_rows = 0

    def add(self, table: str, month: str, frame: pl.DataFrame) -> None:
        if not frame.height:
            return
        if self._month.get(table, month) != month:
            self._close(table)
        self._month[table] = month
        if table not in self._hash:
            self._hash[table] = RunningHash(self.path / ".spool", table)
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
        arrow = pl.concat(frames).to_arrow()
        writer = self._writer.get(table)
        if writer is None:
            folder = self.path / table / f"month={self._month[table]}"
            folder.mkdir(parents=True, exist_ok=True)
            part = len(list(folder.glob("part-*.parquet")))
            writer = pq.ParquetWriter(folder / f"part-{part}.parquet", arrow.schema, compression="zstd")
            self._writer[table] = writer
        elif arrow.schema != writer.schema:
            arrow = arrow.cast(writer.schema)
        writer.write_table(arrow)
        self._queue[table], self._queued[table] = [], 0

    def _close(self, table: str) -> None:
        self._write(table)
        writer = self._writer.pop(table, None)
        if writer is not None:
            writer.close()

    def flush(self) -> None:
        """Write every queued row and close every open file."""
        for table in list(set(self._queue) | set(self._writer)):
            self._close(table)

    def end_month(self, month: str) -> None:
        """The month is over: close its files and fold every table's spool for it into the running hash."""
        self.flush()
        for h in self._hash.values():
            if h.month == month:
                h.close_month()

    def content_hashes(self) -> dict[str, str]:
        """Live content hashes of the fact tables written so far."""
        return {t: h.digest() for t, h in self._hash.items()}

    def write_dimension(self, name: str, frame: pl.DataFrame) -> None:
        frame.write_parquet(self.path / f"{name}.parquet")


def table_files(path: Path, name: str) -> list[Path]:
    """Files of a table, facts in month then part order."""
    path = Path(path)
    if name in DIM_TABLES:
        f = path / f"{name}.parquet"
        return [f] if f.exists() else []
    return fact_files(path, name)


def read_table(path: Path, name: str) -> pl.LazyFrame:
    files = table_files(path, name)
    if not files:
        raise FileNotFoundError(f"no table {name!r} in {path}")
    return pl.concat([pl.scan_parquet(f, hive_partitioning=False) for f in files])
