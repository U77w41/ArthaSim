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
# Written about a run after it ran (run.validate); one file each, outside the run's content hashes.
REPORT_TABLES = ["validation_report"]
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
        self._markers: dict[str, tuple[tuple, object]] = {}     # name -> (file stamp, marker) as last written
        self._dim_hash: dict[str, tuple[tuple, str]] = {}       # name -> (file stamp, content hash)
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

    def write_dimension(self, name: str, frame: pl.DataFrame, marker: object = None) -> None:
        """Dimension and metadata tables are replaced whole, never rewritten in place (see `write_atomic`).
        `marker` stands for what the frame was made from; `marker(name)` returns it while the file stays."""
        final = self.path / f"{name}.parquet"
        temporary = final.with_name(final.name + ".tmp")
        frame.write_parquet(temporary)
        os.replace(temporary, final)
        if marker is None:
            self._markers.pop(name, None)
        else:
            self._markers[name] = (self._stamp(name), marker)

    def marker(self, name: str) -> object:
        """The marker the table was last written with, or None: never given one, or the file has since been
        replaced or removed."""
        kept = self._markers.get(name)
        return kept[1] if kept is not None and kept[0] == self._stamp(name) else None

    def dimension_hash(self, name: str) -> str:
        """A dimension or metadata table's content hash, read from disk once per file. A file is replaced whole,
        never changed in place, so the same device, inode, size and modification time mean the same content."""
        stamp = self._stamp(name)
        kept = self._dim_hash.get(name)
        if stamp is None or kept is None or kept[0] != stamp:
            kept = (stamp, content_hash(self.path, name, fact=False))
            self._dim_hash[name] = kept
        return kept[1]

    def _stamp(self, name: str) -> tuple | None:
        try:
            st = (self.path / f"{name}.parquet").stat()
        except FileNotFoundError:
            return None
        return st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns


def table_files(path: Path, name: str, months: tuple[str, str] | None = None) -> list[Path]:
    """Files of a table, facts in month then part order. `months` ("YYYY-MM", "YYYY-MM", inclusive) keeps only the
    fact months in that range; other tables are whole."""
    path = Path(path)
    if name in DIM_TABLES or name in META_TABLES or name in REPORT_TABLES:
        f = path / f"{name}.parquet"
        return [f] if f.exists() else []
    files = fact_files(path, name)
    if months is not None:
        lo, hi = months
        files = [f for f in files if lo <= f.parent.name.split("=", 1)[1] <= hi]
    return files


def read_table(path: Path, name: str, months: tuple[str, str] | None = None) -> pl.LazyFrame:
    files = table_files(path, name, months)
    if not files:
        raise FileNotFoundError(f"no table {name!r} in {path}")
    return pl.concat([pl.scan_parquet(f, hive_partitioning=False) for f in files])
