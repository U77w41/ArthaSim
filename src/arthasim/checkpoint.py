"""Checkpoints: a world pickled at a month end, beside hard links to its run's files so far.

A checkpoint folder holds `world.pkl` (the world without its store, watchers, release secret or derived keys),
`checkpoint.json` (versions, the config without the secret, content hashes, interventions) and `run/` (hard links to
every file of the run). Loading a pickle runs code: load only checkpoints from your own runs."""
from __future__ import annotations

import datetime as dt
import json
import os
import pickle
import platform
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numba
import numpy as np
import polars as pl

if TYPE_CHECKING:
    from arthasim.world import World

_SKIP = {"checkpoints"}          # top-level folders a checkpoint or fork never links


def at_month_end(world: "World") -> bool:
    return world.days_simulated == 0 or world.date.day == 1


def _next_month(day: dt.date) -> dt.date:
    return (day.replace(day=1) + dt.timedelta(days=32)).replace(day=1)


def require_month_end(world: "World") -> None:
    if not at_month_end(world):
        raise ValueError(f"save and fork need a month end; the next is {_next_month(world.date).isoformat()}")


def label(world: "World") -> str:
    """The month that has just ended, or "start" before the first simulated day."""
    if world.days_simulated == 0:
        return "start"
    return f"{world.date - dt.timedelta(days=1):%Y-%m}"


def link_tree(src: Path, dst: Path) -> None:
    """Hard-link every file under `src` into `dst`, keeping relative paths; copy where a link is refused. The
    top-level checkpoints folder and temporary files are left out."""
    src, dst = Path(src), Path(dst)
    dst.mkdir(parents=True, exist_ok=True)
    for root, dirs, files in os.walk(src):
        here = Path(root)
        if here == src:
            dirs[:] = [d for d in dirs if d not in _SKIP]
        dirs.sort()
        for name in sorted(files):
            if name.endswith(".tmp"):
                continue
            target = dst / (here / name).relative_to(src)
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.link(here / name, target)
            except OSError:
                shutil.copy2(here / name, target)


def next_free(base: Path) -> Path:
    """`base`, or the first of `base-2`, `base-3`, ... that does not exist."""
    base = Path(base)
    if not base.exists():
        return base
    i = 2
    while Path(f"{base}-{i}").exists():
        i += 1
    return Path(f"{base}-{i}")


def versions() -> dict[str, str]:
    return {"python": platform.python_version(), "numpy": np.__version__, "numba": numba.__version__,
            "polars": pl.__version__}


def metadata(world: "World") -> dict[str, Any]:
    from arthasim.world import _CODE_VERSION
    config = world.config
    return {"run_id": world.path.name, "label": label(world), "next_date": world.date.isoformat(),
            "seed": world.run_seed, "config": config.model_dump(mode="json", exclude={"release_secret"}),
            "config_hash": config.hash(), "release_secret": config.release_secret is not None,
            "registry_version": world.params.version(), "code_version": _CODE_VERSION, **versions(),
            "content_hash": world._content_hashes(), "interventions": world._intervention_details()}


def write(world: "World", path: Path) -> None:
    """Save the world at a month end into a new folder `path`."""
    path = Path(path)
    require_month_end(world)
    if path.exists():
        raise FileExistsError(f"checkpoint path already exists: {path}")
    world._flush()
    path.mkdir(parents=True)
    with open(path / "world.pkl", "wb") as f:
        pickle.dump(world, f, protocol=5)
    (path / "checkpoint.json").write_text(json.dumps(metadata(world), indent=2))
    link_tree(world.path, path / "run")


def read(path: Path, release_secret: str | None) -> tuple["World", dict[str, Any]]:
    """The checkpoint's world with its config and seed restored, and its metadata. Refuses another code or Polars
    version, a missing secret and a wrong one; no message shows a secret."""
    from arthasim.config import Config
    from arthasim.engine.rng import KeyedSeed
    from arthasim.world import _CODE_VERSION
    path = Path(path)
    meta = json.loads((path / "checkpoint.json").read_text())
    if meta["code_version"] != _CODE_VERSION:
        raise ValueError(f"this checkpoint was made by code version {meta['code_version']}; "
                         f"this is code version {_CODE_VERSION}")
    if meta["polars"] != pl.__version__:
        raise ValueError(f"this checkpoint was made with Polars {meta['polars']} and this is Polars {pl.__version__}; "
                         "another Polars can change bytes and content hashes")
    if meta["release_secret"] and release_secret is None:
        raise ValueError("this checkpoint was made with a release secret; pass release_secret")
    fields = dict(meta["config"])
    if release_secret is not None:
        fields["release_secret"] = release_secret
    config = Config(**fields)
    if config.hash() != meta["config_hash"]:
        raise ValueError("the release secret or config does not match this checkpoint")
    with open(path / "world.pkl", "rb") as f:
        world = pickle.load(f)
    secret = config.secret_bytes()
    world.config = config
    world.seed = world.run_seed if secret is None else KeyedSeed.derive(world.run_seed, secret)
    return world, meta
