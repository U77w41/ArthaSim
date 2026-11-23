"""Draws keyed with a release secret come from SipHash-2-4; integer seeds keep the original mixer."""
import numpy as np
import pytest

from arthasim.engine import rng
from arthasim.engine.rng import KeyedSeed

_M = (1 << 64) - 1


def _rotl(x, b):
    return ((x << b) | (x >> (64 - b))) & _M


def siphash24(key: bytes, msg: bytes) -> int:
    """Reference SipHash-2-4 (Aumasson and Bernstein, 2012), written from the paper."""
    k0, k1 = int.from_bytes(key[:8], "little"), int.from_bytes(key[8:], "little")
    v = [k0 ^ 0x736F6D6570736575, k1 ^ 0x646F72616E646F6D, k0 ^ 0x6C7967656E657261, k1 ^ 0x7465646279746573]

    def rnd():
        v[0] = (v[0] + v[1]) & _M; v[1] = _rotl(v[1], 13); v[1] ^= v[0]; v[0] = _rotl(v[0], 32)
        v[2] = (v[2] + v[3]) & _M; v[3] = _rotl(v[3], 16); v[3] ^= v[2]
        v[0] = (v[0] + v[3]) & _M; v[3] = _rotl(v[3], 21); v[3] ^= v[0]
        v[2] = (v[2] + v[1]) & _M; v[1] = _rotl(v[1], 17); v[1] ^= v[2]; v[2] = _rotl(v[2], 32)

    n = len(msg)
    end = n - n % 8
    for i in range(0, end, 8):
        m = int.from_bytes(msg[i:i + 8], "little")
        v[3] ^= m; rnd(); rnd(); v[0] ^= m
    b = ((n & 0xFF) << 56) | int.from_bytes(msg[end:], "little")
    v[3] ^= b; rnd(); rnd(); v[0] ^= b
    v[2] ^= 0xFF
    for _ in range(4):
        rnd()
    return v[0] ^ v[1] ^ v[2] ^ v[3]


def test_reference_matches_published_vectors():
    key = bytes(range(16))
    assert siphash24(key, bytes(range(15))) == 0xA129CA6149BE45E5      # the paper's worked example
    assert siphash24(key, b"") == 0x726FDB47DD0E0E31                   # vectors.h, first entry
    assert siphash24(key, bytes(range(32))) == 0x7127512F72F27CCE


K = KeyedSeed(run_seed=0, k0=int.from_bytes(bytes(range(8)), "little"),
              k1=int.from_bytes(bytes(range(8, 16)), "little"), id_key=b"\0" * 32)
E = np.array([0, 1, 41872, -5], dtype=np.int64)


def _msg(s, e, d, i):
    return b"".join(int(v).to_bytes(8, "little", signed=True) for v in (s, e, d, i))


def test_kernel_matches_reference():
    assert rng.bits(K, 123, E, 3, 9).tolist() == [siphash24(bytes(range(16)), _msg(123, e, 3, 9)) for e in E]
    u = rng.uniform(K, 123, E, 3, 9)
    assert u.tolist() == [(siphash24(bytes(range(16)), _msg(123, e, 3, 9)) >> 11) / 2**53 for e in E]


def test_plain_seed_unchanged():
    e = E[:3]
    assert rng.uniform(7, 123, e, 3, 0).tolist() == [0.07419720641602001, 0.35979117562348784, 0.32791734220037083]
    assert rng.normal(7, 123, e, 3, 0).tolist() == [-0.599005126018669, -0.9632125037890983, 1.627249849022324]
    assert rng.poisson(7, 123, e, 3, 2.5, 0).tolist() == [0, 2, 2]
    assert [hex(x) for x in rng.bits(7, 123, e, 3, 0).tolist()] == \
        ["0x12fe968f02e8fb13", "0x5c1b4644b138cb14", "0x53f264148ab59a10"]


def test_derive_is_keyed_reproducible_and_hidden():
    a, b = KeyedSeed.derive(7, b"\x01" * 32), KeyedSeed.derive(7, b"\x02" * 32)
    assert a == KeyedSeed.derive(7, b"\x01" * 32) and a != b and a != KeyedSeed.derive(8, b"\x01" * 32)
    assert repr(a) == "KeyedSeed(run_seed=7, keyed)"
    ids = np.arange(10_000, dtype=np.int64)
    ua, ub, up = rng.uniform(a, 5, ids, 1), rng.uniform(b, 5, ids, 1), rng.uniform(7, 5, ids, 1)
    assert ((0 <= ua) & (ua < 1)).all() and not np.isclose(ua, ub).any() and not np.isclose(ua, up).any()
    assert rng.poisson(a, 5, ids, 1, 3.0).mean() == pytest.approx(3.0, abs=0.1)
