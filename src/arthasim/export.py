"""Write a view to Parquet for use outside Python, with a manifest and a data dictionary.

Observer views (bank, switch, bureau) drop every simulator ID: what remains is what that observer could hand over.
A truth export copies the run's files as they are."""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

import duckdb
import polars as pl

from arthasim.store.hashing import content_hash
from arthasim.store.parquet import table_files
from arthasim.views import DESCRIPTIONS, Date, View, as_date, make_view

if TYPE_CHECKING:
    from arthasim.world import Run

ID_COLUMNS = {"entity_id", "account_id", "payment_id", "journal_id", "household_id"}


def is_id(column: str) -> bool:
    return column in ID_COLUMNS or column.endswith(("_entity_id", "_account_id"))


def _prepare(dest: Path) -> Path:
    dest = Path(dest)
    if dest.exists() and (not dest.is_dir() or any(dest.iterdir())):
        raise FileExistsError(f"export destination exists and is not an empty directory: {dest}")
    dest.mkdir(parents=True, exist_ok=True)
    return dest


def _copy_truth(run: "Run", dest: Path) -> dict[str, dict[str, Any]]:
    from arthasim.store.parquet import FACT_TABLES
    tables = {}
    for t in run.tables():
        files = table_files(Path(run.path), t)
        fact = t in FACT_TABLES
        for f in files:
            target = dest / t / f.parent.name / f.name if fact else dest / f.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, target)
        schema = pl.scan_parquet(files[0], hive_partitioning=False).collect_schema()
        rows = sum(pl.scan_parquet(f, hive_partitioning=False).select(pl.len()).collect().item() for f in files)
        tables[t] = {"rows": rows, "layout": "month" if fact else "file",
                     "columns": [[c, str(d)] for c, d in schema.items()],
                     "content_hash": content_hash(dest, t, fact=fact)}
    return tables


def _export_table(con: duckdb.DuckDBPyConnection, definition: str, name: str, fact: bool, drop_ids: bool,
                  dest: Path) -> dict[str, Any]:
    """Build the table once (in an on-disk database, so it can spill), then copy it out, one file per month for
    fact tables. Copies read the built table in its insertion order, which is the definition's order."""
    con.execute(f"create or replace table _export as {definition}")
    rel = con.sql("select * from _export limit 0")
    columns = [(c, str(t)) for c, t in zip(rel.columns, rel.types)]
    keep = [(c, t) for c, t in columns if not (drop_ids and is_id(c))]
    names = [c for c, _ in keep]
    rows = con.sql("select count(*) from _export").fetchall()[0][0]
    month_of = "month" if "month" in names else "strftime(date, '%Y-%m')" if "date" in names else None
    try:
        if fact and rows and month_of is not None:
            out = [c for c in names if c != "month"]
            listing = ", ".join(f'"{c}"' for c in out)
            months = [r[0] for r in con.sql(f"select distinct {month_of} from _export order by 1").fetchall()]
            for m in months:
                folder = dest / name / f"month={m}"
                folder.mkdir(parents=True)
                con.execute(f"""copy (select {listing} from _export where {month_of} = '{m}')
                                to '{folder / 'part-0.parquet'}' (format parquet, compression zstd)""")
            return {"rows": rows, "layout": "month", "columns": [[c, t] for c, t in keep if c != "month"],
                    "content_hash": content_hash(dest, name, fact=True)}
        listing = ", ".join(f'"{c}"' for c in names)
        con.execute(f"""copy (select {listing} from _export)
                        to '{dest / f'{name}.parquet'}' (format parquet, compression zstd)""")
        return {"rows": rows, "layout": "file", "columns": [[c, t] for c, t in keep],
                "content_hash": content_hash(dest, name, fact=False)}
    finally:
        con.execute("drop table _export")


def _readme(view: View, run: "Run", tables: dict[str, dict[str, Any]], asof: str | None) -> str:
    lines = [f"# {view.kind.capitalize()} view export", "",
             f"Source run `{run.manifest['run_id']}`, view `{view.kind}`, scope `{json.dumps(view.scope)}`, "
             f"as of {asof or 'the end of the run'}. Money is in paise; times are epoch microseconds; dates are "
             "Asia/Kolkata. Synthetic data: no record describes a real person, account or bank.", ""]
    if view.kind != "truth":
        lines += ["Simulator IDs are removed. Customers and accounts carry the bank's own numbers; the other side of a "
                  "payment appears only as a handle and a bank code.", ""]
    for t, meta in tables.items():
        layout = "one folder per month (`month=YYYY-MM`)" if meta["layout"] == "month" else "one file"
        lines += [f"## {t}", "", f"{meta['rows']:,} rows, {layout}.", "", "| Column | Type | Meaning |",
                  "| :--- | :--- | :--- |"]
        meanings = DESCRIPTIONS.get(t, {})
        lines += [f"| {c} | {ty} | {meanings.get(c, '')} |" for c, ty in meta["columns"]]
        lines.append("")
    return "\n".join(lines)


def export_view(run: "Run", dest: str | Path, view: str = "bank", asof: Date | None = None, **scope: Any) -> Path:
    """Write the view's tables under `dest`, which must not exist or be an empty directory."""
    v = make_view(run, view, asof=asof, **scope)
    if view == "truth" and asof is not None:
        raise ValueError("a truth export copies the run's files; asof applies to observer views only")
    dest = _prepare(Path(dest))
    asof_text = as_date(asof).isoformat() if asof is not None else None
    if view == "truth":
        tables = _copy_truth(run, dest)
    else:
        defs = v._definitions()
        with tempfile.TemporaryDirectory(prefix="arthasim-export-") as scratch:
            con = duckdb.connect(str(Path(scratch) / "export.duckdb"))
            try:
                tables = {t: _export_table(con, defs[t], t, t in v.fact_tables, True, dest) for t in sorted(defs)}
            finally:
                con.close()
    manifest = {"source_run_id": run.manifest["run_id"], "source_content_hash": run.manifest["content_hash"],
                "view": view, "scope": v.scope, "asof": asof_text, "tables": tables}
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    (dest / "README.md").write_text(_readme(v, run, tables, asof_text))
    return dest
