"""Who an intervention selects: a SQL boolean expression over one row per person, evaluated by DuckDB on the
month's state after the life course has run. Columns use the names of `persons` and `entity_state_monthly`."""
from __future__ import annotations

from typing import TYPE_CHECKING

import duckdb
import numpy as np
import polars as pl

from arthasim.build import categories as c

if TYPE_CHECKING:
    from arthasim.world import World

WHERE_SCHEMA = {
    "entity_id": pl.Int64, "household_id": pl.Int64, "age": pl.Int64, "sex": pl.String, "education": pl.String,
    "district": pl.String, "district_kind": pl.String, "life_stage": pl.String, "helper": pl.Boolean,
    "sector": pl.String, "monthly_income_paise": pl.Int64, "household_income_paise": pl.Int64,
    "transfer_income_paise": pl.Int64, "has_account": pl.Boolean, "has_upi": pl.Boolean, "has_card": pl.Boolean,
    "primary_bank": pl.String, "bpl": pl.Boolean}
COLUMNS = tuple(WHERE_SCHEMA)


def _names(labels: list[str], index: np.ndarray) -> pl.Series:
    values = np.array(list(labels) + [None], dtype=object)[np.where(index >= 0, index, len(labels))]
    return pl.Series(values.tolist(), dtype=pl.String)


def person_frame(world: "World") -> pl.DataFrame:
    """One row per person, in person order. `transfer_income_paise` is the DBT monthly value the last `dbt` step
    set (last month's, wherever an intervention evaluates `where`)."""
    s = world.state
    pop = s.population
    if pop is None:
        raise ValueError("where needs a population world (tier S and above); this is a spike world")
    p, k, life = pop.persons, pop.banking, s.life
    n = len(p)
    hh = pop.households.household_of_person.astype(np.int64)
    income = pop.attributes.monthly_income_paise.astype(np.int64)
    hh_income = np.zeros(pop.households.adults.size, dtype=np.int64)
    np.add.at(hh_income, hh, income)
    beh = s.behaviour
    transfer = (beh.person_transfer.astype(np.int64) if beh is not None and beh.person_transfer is not None
                else np.zeros(n, dtype=np.int64))
    bpl = s.government.bpl[hh] if s.government is not None else np.zeros(n, dtype=bool)
    frame = pl.DataFrame({
        "entity_id": s.person_ids.astype(np.int64), "household_id": hh, "age": p.age.astype(np.int64),
        "sex": _names(c.SEX, p.sex.astype(np.int64)), "education": _names(c.EDUCATION, p.education.astype(np.int64)),
        "district": _names([d.id for d in pop.districts], p.district.astype(np.int64)),
        "district_kind": _names([d.kind for d in pop.districts], p.district.astype(np.int64)),
        "life_stage": _names(c.LIFE_STAGE, p.life_stage.astype(np.int64)), "helper": life.helper.astype(bool),
        "sector": _names(c.SECTORS, pop.attributes.sector.astype(np.int64)), "monthly_income_paise": income,
        "household_income_paise": hh_income[hh], "transfer_income_paise": transfer,
        "has_account": k.person_has_account.astype(bool), "has_upi": k.person_upi.astype(bool),
        "has_card": k.person_has_card.astype(bool),
        "primary_bank": _names(k.bank_codes.tolist(), k.person_primary_bank.astype(np.int64)),
        "bpl": np.asarray(bpl, dtype=bool)}, schema=WHERE_SCHEMA)
    return frame


def _run(frame: pl.DataFrame, expr: str) -> np.ndarray:
    if ";" in expr:
        raise ValueError(f"where {expr!r}: one expression only, without ';'")
    con = duckdb.connect()
    try:
        con.register("persons_now", frame.with_row_index("_i").to_arrow())
        rows = con.execute(f"select _i from persons_now where ({expr}) order by _i").fetchnumpy()["_i"]
    except duckdb.Error as e:
        first = str(e).strip().splitlines()[0] if str(e).strip() else type(e).__name__
        raise ValueError(f"where {expr!r}: {first}") from None
    finally:
        con.close()
    return np.asarray(rows, dtype=np.int64)


def check(expr: str) -> None:
    """Raise ValueError for a syntax error or an unknown column, without a world."""
    _run(pl.DataFrame(schema=WHERE_SCHEMA), expr)


def select(world: "World", expr: str) -> np.ndarray:
    """Person indices (ascending) for whom `expr` is true now."""
    return _run(person_frame(world), expr)
