# tests/run_fixture.py
import functools
import tempfile

from arthasim import Config, World


@functools.lru_cache(maxsize=None)
def small_run(persons=3_000, seed=7):
    """Population run from 2025-04-20 to 2025-05-25 (crosses one month end), stopped mid-May. Read-only."""
    out = tempfile.mkdtemp(prefix="arthasim-run-")
    world = World.build(Config.tier("S", persons=persons, start="2025-04-20", out_dir=out), seed=seed)
    return world.run(until="2025-05-25")


RELEASE_SECRET = "5a" * 32


@functools.lru_cache(maxsize=None)
def secret_run(persons=3_000, seed=7):
    """`small_run` made with a release secret: same persons, dates and seed. Read-only."""
    out = tempfile.mkdtemp(prefix="arthasim-secret-run-")
    config = Config.tier("S", persons=persons, start="2025-04-20", out_dir=out, release_secret=RELEASE_SECRET)
    return World.build(config, seed=seed).run(until="2025-05-25")
