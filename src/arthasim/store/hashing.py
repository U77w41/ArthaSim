"""Content hashes. The digest is the same whether it is computed live, as rows are written, or from disk.

A fact table's hash is one SHA-256 over its months in order. Each month contributes its name, its schema,
the seed-0 row hashes of every row, then the seed-1 row hashes of every row. A dimension table's hash is
the schema and both row-hash runs of the whole table."""
from __future__ import annotations

import hashlib
from pathlib import Path

import polars as pl
import pyarrow.parquet as pq

_CHUNK = 1 << 20


def schema_bytes(schema) -> bytes:
    return repr([(name, str(dtype)) for name, dtype in schema.items()]).encode()


def ipc_bytes(frame: pl.DataFrame) -> bytes:
    """Bytes that depend only on the schema and the values, in order. Serialised IPC is not
    enough: equal frames joined from different parts can lay out null bitmaps and string
    buffers differently. Row hashes under two seeds give 128 bits per row."""
    schema = schema_bytes(frame.schema)
    if frame.height == 0:
        return schema
    return schema + frame.hash_rows(seed=0).to_numpy().tobytes() + frame.hash_rows(seed=1).to_numpy().tobytes()


def _stream_into(h, path: Path) -> None:
    with open(path, "rb") as f:
        while chunk := f.read(_CHUNK):
            h.update(chunk)


class RunningHash:
    """A fact table's hash, fed frame by frame in write order. The seed-1 row hashes of the open month wait
    in a spool file until the month closes, so memory does not grow with the month."""

    def __init__(self, spool_dir: Path, name: str) -> None:
        self._dir, self._name = Path(spool_dir), name
        self._h = hashlib.sha256()
        self._month: str | None = None
        self._schema = None
        self._spool = None

    def _spool_path(self, month: str) -> Path:
        return self._dir / f"{self._name}-{month}.bin"

    def update(self, month: str, frame: pl.DataFrame) -> None:
        if frame.height == 0:
            return
        if month != self._month:
            if self._month is not None and month < self._month:
                raise ValueError(f"{self._name}: month {month} arrived after {self._month}")
            self._close_month()
            self._month, self._schema = month, frame.schema
            self._h.update(f"month={month}".encode())       # the folder name, as the from-disk hash reads it
            self._h.update(schema_bytes(frame.schema))
            self._dir.mkdir(parents=True, exist_ok=True)
            self._spool = open(self._spool_path(month), "wb")
        elif self._spool is None:
            raise ValueError(f"{self._name}: month {month} is already closed")
        elif frame.schema != self._schema:
            raise ValueError(f"{self._name}: schema changed within {month}")
        self._h.update(frame.hash_rows(seed=0).to_numpy().tobytes())
        self._spool.write(frame.hash_rows(seed=1).to_numpy().tobytes())

    @property
    def month(self) -> str | None:
        return self._month

    def close_month(self) -> None:
        """Fold the open month's spool into the hash and delete it; no more rows may come for that month."""
        self._close_month()

    def _close_month(self) -> None:
        if self._spool is None:
            return
        self._spool.close()
        path = self._spool_path(self._month)
        _stream_into(self._h, path)
        path.unlink()
        self._spool = None

    @classmethod
    def from_disk(cls, spool_dir: Path, name: str, run_path: Path) -> "RunningHash":
        """The running hash of a table's closed months, rebuilt by reading them exactly as `content_hash` does
        (a SHA-256 state cannot be saved). The result is closed: the next row starts a new month."""
        out = cls(spool_dir, name)
        files = fact_files(run_path, name)
        months = sorted({f.parent.name for f in files})
        for month in months:
            parts = [f for f in files if f.parent.name == month]
            out._h.update(month.encode())
            out._schema = _feed_month(out._h, parts)
        if months:
            out._month = months[-1].split("=", 1)[1]
        return out

    def clone(self, spool_dir: Path) -> "RunningHash":
        """A copy of a closed hash that spools into `spool_dir`."""
        if self._spool is not None:
            raise ValueError(f"{self._name}: month {self._month} is still open")
        out = RunningHash(spool_dir, self._name)
        out._h, out._month, out._schema = self._h.copy(), self._month, self._schema
        return out

    def digest(self) -> str:
        """The hash of everything fed so far; the running state is left as it was."""
        h = self._h.copy()
        if self._spool is not None:
            self._spool.flush()
            _stream_into(h, self._spool_path(self._month))
        return h.hexdigest()


def fact_files(path: Path, name: str) -> list[Path]:
    """A fact table's part files, in month then part order."""
    files = (Path(path) / name).glob("month=*/part-*.parquet")
    return sorted(files, key=lambda f: (f.parent.name, int(f.stem.split("-")[1])))


def content_hash(path: Path, name: str, fact: bool | None = None) -> str:
    """SHA-256 of a table's content, from disk. Fact tables are streamed one row group at a time (two passes
    per month), so memory stays bounded by a row group. `fact=None` decides by the run's table lists."""
    path = Path(path)
    if fact is None:
        from arthasim.store.parquet import FACT_TABLES
        fact = name in FACT_TABLES
    h = hashlib.sha256()
    if not fact:
        f = path / f"{name}.parquet"
        if not f.exists():
            raise FileNotFoundError(f"no table {name!r} in {path}")
        h.update(ipc_bytes(pl.read_parquet(f, hive_partitioning=False)))
        return h.hexdigest()
    files = fact_files(path, name)
    if not files:
        raise FileNotFoundError(f"no table {name!r} in {path}")
    for month in sorted({f.parent.name for f in files}):
        parts = [f for f in files if f.parent.name == month]
        h.update(month.encode())
        _feed_month(h, parts)
    return h.hexdigest()


def _feed_month(h, parts: list[Path]):
    """One month's schema, then the seed-0 and seed-1 row hashes of its parts, one row group at a time. Returns
    the month's schema."""
    schema = pl.scan_parquet(parts[0], hive_partitioning=False).collect_schema()
    h.update(schema_bytes(schema))
    for seed in (0, 1):
        for f in parts:
            pf = pq.ParquetFile(f)
            for i in range(pf.num_row_groups):
                frame = pl.from_arrow(pf.read_row_group(i))
                h.update(frame.hash_rows(seed=seed).to_numpy().tobytes())
    return schema
