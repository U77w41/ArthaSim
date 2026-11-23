"""A run made with a release secret: its draws and identifiers are keyed, and nothing secret is written."""
import hashlib
import json
import re
from pathlib import Path

import polars as pl

from arthasim import Config, World
from arthasim.build.identifiers import token
from arthasim.engine import rng
from arthasim.engine.rng import KeyedSeed
from run_fixture import RELEASE_SECRET, secret_run, small_run


def _sha16(text):
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def test_manifest_says_a_secret_was_used_and_keeps_the_typed_seed():
    s, p = secret_run().manifest, small_run().manifest
    assert s["release_secret"] is True and p["release_secret"] is False
    assert s["seed"] == p["seed"] == 7
    assert s["run_id"].startswith("S-seed7-") and p["run_id"].startswith("S-seed7-") and s["run_id"] != p["run_id"]
    assert all(re.fullmatch(r"[0-9a-f]{16}", m["source_label"]) for m in (s, p))
    assert p["source_label"] == _sha16(p["run_id"]) and s["source_label"] != _sha16(s["run_id"])


def test_nothing_secret_is_written_to_the_run_folder():
    ks = KeyedSeed.derive(7, bytes.fromhex(RELEASE_SECRET))
    draws = ks.k0.to_bytes(8, "little") + ks.k1.to_bytes(8, "little")
    needles = [RELEASE_SECRET.encode(), bytes.fromhex(RELEASE_SECRET), ks.id_key, ks.id_key.hex().encode(),
               draws, draws.hex().encode(), str(ks.k0).encode(), str(ks.k1).encode()]
    files = [f for f in Path(secret_run().path).rglob("*") if f.is_file()]
    assert files
    for f in files:
        data = f.read_bytes()
        assert not any(n in data for n in needles), f


def test_identifiers_share_nothing_with_the_plain_run():
    s, p = secret_run(), small_run()
    for col in ("uid_token", "mobile_token", "pan_like"):
        a = set(s.table("persons").collect()[col].drop_nulls().to_list())
        b = set(p.table("persons").collect()[col].drop_nulls().to_list())
        assert a and not a & b, col
    keyed = lambda r: set(r.table("instruments").filter(pl.col("kind") != "BRANCH").collect()["value"].to_list())
    assert keyed(s) and not keyed(s) & keyed(p)
    cust = lambda r: set(r.table("bank_customers").collect()["customer_no"].to_list())
    assert not cust(s) & cust(p)
    assert s.manifest["content_hash"]["payments"] != p.manifest["content_hash"]["payments"]


def test_tokens_cannot_be_recomputed_without_the_secret():
    persons = secret_run().table("persons").collect()
    ids = persons["entity_id"].to_numpy()
    assert not set(token("u", 7, rng.stream_id("id.uid"), ids).tolist()) & set(persons["uid_token"].to_list())
    ks = KeyedSeed.derive(7, bytes.fromhex(RELEASE_SECRET))
    assert token("u", ks, rng.stream_id("id.uid"), ids).tolist() == persons["uid_token"].to_list()


def test_the_same_secret_rebuilds_the_same_run(tmp_path):
    config = Config.tier("S", persons=3_000, start="2025-04-20", out_dir=str(tmp_path), release_secret=RELEASE_SECRET)
    again = World.build(config, seed=7).run(until="2025-05-25")
    assert again.manifest["content_hash"] == secret_run().manifest["content_hash"]


def test_watch_and_inspect_work_on_a_secret_world_and_leak_nothing(tmp_path):    # Review Focus 3
    w = World.build(Config.tier("S", persons=2_000, out_dir=str(tmp_path), release_secret=RELEASE_SECRET), seed=7)
    assert isinstance(w.seed, KeyedSeed) and w.run_seed == 7 and RELEASE_SECRET not in repr(w.seed) + str(w.seed)
    seen = []
    for pid in w.state.person_ids[:20].tolist():
        w.watch(pid, seen.append)
    run = w.run(until="2025-04-10")
    assert seen and RELEASE_SECRET not in json.dumps(seen, default=str)
    who = seen[0]["entity_id"]
    profile, timeline = run.inspect(who).profile(), run.inspect(who).timeline()
    assert profile and timeline.height and RELEASE_SECRET not in json.dumps(profile, default=str)
