"""Month-partitioned Parquet output, table reads and content hashes."""
from __future__ import annotations

import hashlib
from pathlib import Path

import polars as pl

FACT_TABLES = ["payments", "journal", "postings", "truth_household_monthly", "life_events",
               "entity_state_monthly", "truth_dbt_monthly"]
DIM_TABLES = ["persons", "households", "orgs", "banks", "accounts", "instruments", "edges", "geo",
              "truth_person_latent"]


class Store:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._buffer: dict[str, dict[str, list[pl.DataFrame]]] = {t: {} for t in FACT_TABLES}

    def add(self, table: str, month: str, frame: pl.DataFrame) -> None:
        if frame.height:
            self._buffer[table].setdefault(month, []).append(frame)

    def flush(self) -> None:
        """Write one part file per table and month that has buffered rows."""
        for table, months in self._buffer.items():
            for month, frames in months.items():
                folder = self.path / table / f"month={month}"
                folder.mkdir(parents=True, exist_ok=True)
                part = len(list(folder.glob("part-*.parquet")))
                pl.concat(frames).write_parquet(folder / f"part-{part}.parquet")
            months.clear()

    def write_dimension(self, name: str, frame: pl.DataFrame) -> None:
        frame.write_parquet(self.path / f"{name}.parquet")


def table_files(path: Path, name: str) -> list[Path]:
    """Files of a table, facts in month then part order."""
    path = Path(path)
    if name in DIM_TABLES:
        f = path / f"{name}.parquet"
        return [f] if f.exists() else []
    files = (path / name).glob("month=*/part-*.parquet")
    return sorted(files, key=lambda f: (f.parent.name, int(f.stem.split("-")[1])))


def read_table(path: Path, name: str) -> pl.LazyFrame:
    files = table_files(path, name)
    if not files:
        raise FileNotFoundError(f"no table {name!r} in {path}")
    return pl.concat([pl.scan_parquet(f, hive_partitioning=False) for f in files])


def _ipc_bytes(frame: pl.DataFrame) -> bytes:
    """Bytes that depend only on the schema and the values, in order. Serialised IPC is not
    enough: equal frames joined from different parts can lay out null bitmaps and string
    buffers differently. Row hashes under two seeds give 128 bits per row."""
    schema = repr([(name, str(dtype)) for name, dtype in frame.schema.items()]).encode()
    if frame.height == 0:
        return schema
    return (schema + frame.hash_rows(seed=0).to_numpy().tobytes()
            + frame.hash_rows(seed=1).to_numpy().tobytes())


def content_hash(path: Path, name: str) -> str:
    """SHA-256 of a table's content. Fact tables are read one month at a time, joining that
    month's parts, so the hash does not depend on how the run was split and memory stays
    bounded by one month."""
    h = hashlib.sha256()
    if name in DIM_TABLES:
        h.update(_ipc_bytes(read_table(path, name).collect()))
        return h.hexdigest()
    files = table_files(path, name)
    if not files:
        raise FileNotFoundError(f"no table {name!r} in {path}")
    for month in sorted({f.parent.name for f in files}):
        parts = [f for f in files if f.parent.name == month]
        h.update(month.encode())
        h.update(_ipc_bytes(pl.concat([pl.read_parquet(f, hive_partitioning=False) for f in parts])))
    return h.hexdigest()
