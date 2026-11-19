# tests/world_fixture.py
import functools
import tempfile
from arthasim import Config, World


@functools.lru_cache(maxsize=None)
def small_world(persons=5_000, seed=7):
    """A population world shared by tests that only read state or call module hooks."""
    out = tempfile.mkdtemp(prefix="arthasim-test-")
    return World.build(Config.tier("S", persons=persons, out_dir=out), seed=seed)
