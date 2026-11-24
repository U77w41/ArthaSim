"""Save, load and fork at month ends (plan 1d-2, Tasks 3 and 4)."""
import json
from datetime import date
from pathlib import Path

import polars as pl
import pytest

from arthasim import Config, World
from arthasim.engine.rng import KeyedSeed
from helpers import run_files
from run_fixture import RELEASE_SECRET


def S(out, **kw):
    return Config.tier("S", persons=3_000, out_dir=str(out), **kw)


def XS(out, **kw):
    return Config.tier("XS", persons=500, employers=10, merchants=30, out_dir=str(out), **kw)


# -- Task 3: save and load ------------------------------------------------------------------------------------------

def test_save_load_continue_is_byte_identical(tmp_path):
    plain = World.build(S(tmp_path), 7, path=tmp_path / "plain", checkpoints=False).run("2025-06-02")
    w = World.build(S(tmp_path), 7, path=tmp_path / "b", checkpoints=False)
    w.run("2025-04-30")
    w.save(tmp_path / "ck")
    resumed = World.load(tmp_path / "ck", path_out=tmp_path / "c", checkpoints=False).run("2025-06-02")
    assert run_files(resumed.path) == run_files(plain.path)
    assert resumed.manifest["content_hash"] == plain.manifest["content_hash"]
    assert resumed.manifest["forked_from"] == {"run_id": "b", "month": "2025-04", "how": "load"}
    assert plain.manifest["forked_from"] is None and plain.manifest["checkpoints"] is False
    assert resumed.manifest["days"] == plain.manifest["days"] == 63


def test_spike_save_load(tmp_path):
    plain = World.build(XS(tmp_path), 7, path=tmp_path / "plain", checkpoints=False).run("2025-05-03")
    w = World.build(XS(tmp_path), 7, path=tmp_path / "b", checkpoints=False)
    w.run("2025-04-30")
    w.save(tmp_path / "ck")
    resumed = World.load(tmp_path / "ck", path_out=tmp_path / "c", checkpoints=False).run("2025-05-03")
    assert run_files(resumed.path) == run_files(plain.path)
    assert resumed.manifest["content_hash"] == plain.manifest["content_hash"]


def test_save_needs_a_month_end(tmp_path):
    w = World.build(S(tmp_path), 7, checkpoints=False)
    w.run("2025-04-10")
    with pytest.raises(ValueError, match="2025-05-01"):
        w.save(tmp_path / "ck")


def test_mid_month_start_saves_before_the_first_day_and_at_the_first_month_end(tmp_path):
    cfg = S(tmp_path, start="2025-04-20")
    plain = World.build(cfg, 7, path=tmp_path / "plain", checkpoints=False).run("2025-05-03")
    w = World.build(cfg, 7, path=tmp_path / "w", checkpoints=False)
    assert w.label == "start"
    w.save(tmp_path / "ck0")
    a = World.load(tmp_path / "ck0", path_out=tmp_path / "a", checkpoints=False).run("2025-05-03")
    w.run("2025-04-30")
    assert w.label == "2025-04"
    w.save(tmp_path / "ck1")
    b = World.load(tmp_path / "ck1", path_out=tmp_path / "b", checkpoints=False).run("2025-05-03")
    assert run_files(a.path) == run_files(b.path) == run_files(plain.path)


def test_checkpoint_never_holds_the_secret(tmp_path):
    cfg = S(tmp_path, release_secret=RELEASE_SECRET)
    plain = World.build(cfg, 7, path=tmp_path / "plain", checkpoints=False).run("2025-05-02")
    w = World.build(cfg, 7, path=tmp_path / "w", checkpoints=False)
    w.run("2025-04-30")
    w.save(tmp_path / "ck")
    blob = b"".join(f.read_bytes() for f in sorted((tmp_path / "ck").rglob("*"))
                    if f.is_file() and f.suffix in (".pkl", ".json"))
    keys = KeyedSeed.derive(7, bytes.fromhex(RELEASE_SECRET))
    for needle in (bytes.fromhex(RELEASE_SECRET), RELEASE_SECRET.encode(), RELEASE_SECRET.upper().encode(),
                   keys.id_key, keys.id_key.hex().encode(), keys.k0.to_bytes(8, "little"),
                   keys.k1.to_bytes(8, "little"), str(keys.k0).encode(), str(keys.k1).encode()):
        assert needle not in blob
    for wrong in (None, "6b" * 32):
        with pytest.raises(ValueError) as e:
            World.load(tmp_path / "ck", release_secret=wrong)
        assert RELEASE_SECRET not in str(e.value) and "6b" * 32 not in str(e.value)
    again = World.load(tmp_path / "ck", path_out=tmp_path / "c", release_secret=RELEASE_SECRET, checkpoints=False)
    assert run_files(again.run("2025-05-02").path) == run_files(plain.path)


def _edit_meta(path: Path, **changes) -> None:
    meta = json.loads((path / "checkpoint.json").read_text())
    meta.update(changes)
    (path / "checkpoint.json").write_text(json.dumps(meta))


def test_load_refuses_other_versions(tmp_path):
    w = World.build(XS(tmp_path), 7, checkpoints=False)
    w.save(tmp_path / "ck")
    original = (tmp_path / "ck" / "checkpoint.json").read_text()
    _edit_meta(tmp_path / "ck", code_version="9.9.9")
    with pytest.raises(ValueError, match="code version"):
        World.load(tmp_path / "ck")
    (tmp_path / "ck" / "checkpoint.json").write_text(original)
    _edit_meta(tmp_path / "ck", polars="0.0.0")
    with pytest.raises(ValueError, match="Polars"):
        World.load(tmp_path / "ck")


def test_load_never_overwrites(tmp_path):
    w = World.build(XS(tmp_path), 7, path=tmp_path / "r", checkpoints=False)
    w.run("2025-04-30")
    w.save(tmp_path / "ck")
    first, second = World.load(tmp_path / "ck"), World.load(tmp_path / "ck")
    assert (first.path.name, second.path.name) == ("r-from-2025-04", "r-from-2025-04-2")
    with pytest.raises(FileExistsError):
        World.load(tmp_path / "ck", path_out=first.path)
    with pytest.raises(FileExistsError):
        w.save(tmp_path / "ck")


def test_load_detects_a_changed_file(tmp_path):
    w = World.build(XS(tmp_path), 7, checkpoints=False)
    w.run("2025-04-30")
    w.save(tmp_path / "ck")
    part = tmp_path / "ck" / "run" / "payments" / "month=2025-04" / "part-0.parquet"
    short = pl.read_parquet(part).head(10)
    part.unlink()                                  # break the hard link before writing, so the run is untouched
    short.write_parquet(part)
    with pytest.raises(ValueError, match="payments"):
        World.load(tmp_path / "ck")


# -- Task 4: fork, monthly checkpoints and run.fork_at --------------------------------------------------------------

def test_fork_is_byte_identical_and_isolated(tmp_path):
    plain = World.build(S(tmp_path), 7, path=tmp_path / "plain", checkpoints=False).run("2025-06-02")
    w = World.build(S(tmp_path), 7, path=tmp_path / "b", checkpoints=False)
    w.run("2025-04-30")
    child = w.fork(path_out=tmp_path / "c")
    snap = run_files(child.path)
    parent = w.run("2025-06-02")                                   # the parent continues first
    assert run_files(child.path) == snap
    snap_parent = run_files(parent.path)
    done = child.run("2025-06-02")
    assert run_files(parent.path) == snap_parent                   # and the child never touches the parent
    assert run_files(done.path) == run_files(plain.path) == snap_parent
    assert done.manifest["forked_from"] == {"run_id": "b", "month": "2025-04", "how": "fork"}
    assert done.manifest["content_hash"] == plain.manifest["content_hash"]


def test_fork_mid_month_raises(tmp_path):
    w = World.build(S(tmp_path), 7, checkpoints=False)
    w.run("2025-04-10")
    with pytest.raises(ValueError, match="2025-05-01"):
        w.fork()


def test_monthly_checkpoints_and_fork_at(tmp_path):
    run = World.build(S(tmp_path), 7, path=tmp_path / "m").run("2025-06-02")
    assert sorted(p.name for p in (Path(run.path) / "checkpoints").iterdir()) == ["2025-04", "2025-05"]
    assert run.manifest["checkpoints"] is True
    w = run.fork_at("2025-05-01", path_out=tmp_path / "f", checkpoints=False)
    assert w.date == date(2025, 5, 1)
    assert run_files(w.run("2025-06-02").path) == run_files(run.path)
    for bad in ("2025-05-02", "2025-04-01", "2025-08-01"):
        with pytest.raises(ValueError):
            run.fork_at(bad)


def test_spike_fork(tmp_path):
    plain = World.build(XS(tmp_path), 7, path=tmp_path / "plain", checkpoints=False).run("2025-05-03")
    w = World.build(XS(tmp_path), 7, path=tmp_path / "b", checkpoints=False)
    w.run("2025-04-30")
    child = w.fork(path_out=tmp_path / "c").run("2025-05-03")
    assert run_files(child.path) == run_files(plain.path)
