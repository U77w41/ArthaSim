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
