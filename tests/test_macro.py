"""Macro paths in the registry and the run-metadata tables (plan 1d-2, Task 1)."""
import os
from datetime import date

import pytest

from arthasim import Config, Run, World, macro
from arthasim.store.parquet import LOG_SCHEMA, content_hash
from helpers import P


def xs(tmp_path):
    return Config.tier("XS", persons=500, employers=10, merchants=30, out_dir=str(tmp_path))


def test_registry_rows():
    assert P.table().height == 134
    assert macro.steps(P, "policy_rate") == [(date(2025, 2, 7), 6.25), (date(2025, 4, 9), 6.0),
                                             (date(2025, 6, 6), 5.5), (date(2025, 12, 5), 5.25)]
    cpi = macro.steps(P, "cpi_inflation")
    assert len(cpi) == 12 and cpi[0] == (date(2025, 4, 1), 3.16) and cpi[6] == (date(2025, 10, 1), 0.25)
    assert cpi[-1] == (date(2026, 3, 1), 3.4)


def test_value_on_holds_and_carries_forward():
    s = macro.steps(P, "policy_rate")
    assert macro.value_on(s, date(2025, 2, 6)) is None
    assert macro.value_on(s, date(2025, 6, 5)) == 6.0 and macro.value_on(s, date(2025, 6, 6)) == 5.5
    assert macro.value_on(s, date(2027, 1, 1)) == 5.25


def test_replace_from_keeps_history():
    out = macro.replace_from(macro.steps(P, "policy_rate"), [(date(2025, 6, 6), 5.75), (date(2025, 9, 1), 6.0)])
    assert out == {"2025-02-07": 6.25, "2025-04-09": 6.0, "2025-06-06": 5.75, "2025-09-01": 6.0}
    assert list(out) == sorted(out)


def test_add_from_shifts_later_steps_and_inserts_one():
    s = macro.steps(P, "policy_rate")
    out = macro.add_from(s, date(2025, 8, 1), -0.25)
    assert out == {"2025-02-07": 6.25, "2025-04-09": 6.0, "2025-06-06": 5.5, "2025-08-01": 5.25, "2025-12-05": 5.0}
    assert list(out) == sorted(out)
    assert macro.add_from(s, date(2025, 6, 6), 0.1)["2025-06-06"] == 5.6


def test_unknown_series():
    with pytest.raises(ValueError, match="policy_rate"):
        macro.steps(P, "repo")


def test_runs_write_the_metadata_tables(tmp_path):
    world = World.build(xs(tmp_path), seed=7)
    run = world.run(until="2025-04-03")
    paths = run.table("macro_paths").collect()
    assert dict(paths.schema) == macro.MACRO_SCHEMA and paths.height == 16
    log = run.table("interventions_log").collect()
    assert log.height == 0 and dict(log.schema) == LOG_SCHEMA
    for t in ("macro_paths", "interventions_log"):
        assert run.manifest["content_hash"][t] == content_hash(run.path, t)
    assert world.macro("policy_rate", "2025-04-08") == 6.25 and world.macro("cpi_inflation", "2025-04-30") == 3.16


def test_rewrites_never_touch_a_hard_linked_copy(tmp_path):
    world = World.build(xs(tmp_path / "w"), seed=7)
    world.run(until="2025-04-02")
    names = ("persons.parquet", "run_manifest.json")
    for name in names:
        os.link(world.path / name, tmp_path / name)
    before = {n: (tmp_path / n).read_bytes() for n in names}
    world._store.write_dimension("persons", Run.open(world.path).table("persons").head(3).collect())
    world.run(until="2025-04-04")                               # rewrites the manifest
    assert {n: (tmp_path / n).read_bytes() for n in names} == before
    assert (world.path / "persons.parquet").read_bytes() != before["persons.parquet"]
