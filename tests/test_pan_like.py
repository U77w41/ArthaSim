"""pan_like is a keyed permutation of the person index in the PAN shape; identifier keys accept a KeyedSeed."""
import re

import numpy as np
import pytest

from arthasim.build.identifiers import PAN_SLOTS, REAL_FORMATS, pan_like, pan_permutation, token
from arthasim.engine.rng import KeyedSeed


def test_permutation_is_a_bijection_on_every_slot():
    p = pan_permutation(np.arange(PAN_SLOTS), 7)
    assert p.min() >= 0 and p.max() < PAN_SLOTS and np.unique(p).size == PAN_SLOTS


def test_tier_m_is_unique_and_never_real():
    ids = np.arange(1_000_000)
    v = pan_like(ids, ids % 26, 7)
    assert len(set(v.tolist())) == 1_000_000
    assert not any(REAL_FORMATS["pan"].match(x) for x in v[:50_000])
    assert all(re.fullmatch(r"SY[0-9]P[A-Z][0-9]{4}[A-Z]", x) for x in v[:50_000])


def test_keyed_and_not_the_old_encoding():
    ids = np.arange(10_000)
    old = np.array([f"SY{(i // 26 // 10_000) % 10}P{chr(65 + i % 26)}{(i // 26) % 10_000:04d}{chr(65 + i % 26)}"
                    for i in ids.tolist()])
    ks = KeyedSeed.derive(7, b"\x01" * 32)
    a, b, c = pan_like(ids, ids % 26, 7), pan_like(ids, ids % 26, 8), pan_like(ids, ids % 26, ks)
    assert (a == pan_like(ids, ids % 26, 7)).all()
    assert (a == b).sum() <= 2 and (a == c).sum() <= 2 and (a == old).sum() <= 2


def test_range_and_empty():                       # Review Focus 5
    assert pan_like(np.array([], dtype=np.int64), np.array([], dtype=np.int64), 7).size == 0
    with pytest.raises(ValueError, match="2,600,000"):
        pan_like(np.array([PAN_SLOTS]), np.array([0]), 7)


def test_tokens_with_a_secret_are_keyed():
    ids = np.arange(1000)
    ks, ks2 = KeyedSeed.derive(7, b"\x01" * 32), KeyedSeed.derive(7, b"\x02" * 32)
    a, p, b = token("u", ks, 5, ids), token("u", 7, 5, ids), token("u", ks2, 5, ids)
    assert not set(a) & set(p) and not set(a) & set(b) and (a == token("u", ks, 5, ids)).all()
