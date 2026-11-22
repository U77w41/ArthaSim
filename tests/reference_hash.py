# tests/reference_hash.py
"""The content hash as it was before plan 1c, copied verbatim: the reference the live hash must equal."""
from __future__ import annotations

import hashlib
from pathlib import Path

import polars as pl

from arthasim.store.parquet import DIM_TABLES, read_table, table_files


def _ipc_bytes(frame: pl.DataFrame) -> bytes:
    """Bytes that depend only on the schema and the values, in order. Serialised IPC is not
    enough: equal frames joined from different parts can lay out null bitmaps and string
    buffers differently. Row hashes under two seeds give 128 bits per row."""
    schema = repr([(name, str(dtype)) for name, dtype in frame.schema.items()]).encode()
    if frame.height == 0:
        return schema
    return (schema + frame.hash_rows(seed=0).to_numpy().tobytes()
            + frame.hash_rows(seed=1).to_numpy().tobytes())


def reference_content_hash(path: Path, name: str) -> str:
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
