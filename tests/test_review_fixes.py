"""Tests for the final review's findings (plan 1c)."""
import gc
import json
from pathlib import Path

import polars as pl
import pytest

from arthasim import Config, World, Run


def _cfg(tmp_path, name, start="2025-04-20", persons=2_000):
    return Config.tier("S", persons=persons, start=start, out_dir=str(tmp_path / name))


def _salaried(world):
    s = world.state
    return int(s.person_ids[(s.person_employer >= 0) & (s.person_deposit >= 0)][0])


def test_raising_callback_leaves_world_ready_to_continue(tmp_path):
    """I1: a callback that raises must not leave the day half-done; continuing gives the clean run."""
    w = World.build(_cfg(tmp_path, "w"), seed=7)
    eid = _salaried(w)

    def boom(payload):
        if payload["date"].isoformat() == "2025-04-22":
            raise RuntimeError("stop")

    w.watch(eid, boom)
    with pytest.raises(RuntimeError):
        w.run(until="2025-04-25")
    assert w.date.isoformat() == "2025-04-23"                 # the 22nd is done
    w.unwatch(eid)
    resumed = w.run(until="2025-04-25")
    clean = World.build(_cfg(tmp_path, "c"), seed=7).run(until="2025-04-25")
    assert resumed.manifest["content_hash"] == clean.manifest["content_hash"]


def test_run_is_readable_while_running_and_after_an_error(tmp_path):
    """I2: files still being written are not visible under their final names; an error closes them."""
    w = World.build(_cfg(tmp_path, "r"), seed=7)
    w._store.row_group_rows = 1_000                          # so open files hold row groups mid-month
    w.step(1)
    seen = []

    def read_during(payload):
        if payload["date"].isoformat() == "2025-04-25":
            run = Run.open(w.path)
            seen.append(run.table("payments").select(pl.len()).collect().item())
            seen.append(run.view("bank", bank="SYNB03").table("payments").select(pl.len()).collect().item())
        if payload["date"].isoformat() == "2025-04-27":
            raise RuntimeError("stop")

    w.watch(_salaried(w), read_during)
    with pytest.raises(RuntimeError):
        w.run(until="2025-04-30")
    assert len(seen) == 2 and seen[0] > 0
    after = Run.open(w.path)
    assert after.table("payments").select(pl.len()).collect().item() > seen[0]
    assert not list(Path(w.path).rglob("part-*.parquet.tmp"))
