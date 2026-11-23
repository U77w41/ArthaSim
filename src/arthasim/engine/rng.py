"""Keyed random numbers.

Every draw is a pure function of (run_seed, stream, entity_id, day, index).
There is no generator state, so results do not depend on processing order and
a baseline and a treatment run share every draw.

A run with a release secret passes a `KeyedSeed` wherever a seed goes. Its draws come from SipHash-2-4 under a
128-bit key derived from the secret, so they cannot be reproduced, or worked back to the key, without it. An integer
seed keeps the original mixer and its exact output.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np
from numba import njit

_G = np.uint64(0x9E3779B97F4A7C15)
_M1 = np.uint64(0xBF58476D1CE4E5B9)
_M2 = np.uint64(0x94D049BB133111EB)
_TWO_NEG_53 = 1.0 / 9007199254740992.0


@dataclass(frozen=True, repr=False)
class KeyedSeed:
    """A run seed keyed with a release secret: `k0`, `k1` key the draws, `id_key` keys identifiers."""
    run_seed: int
    k0: int
    k1: int
    id_key: bytes

    def __repr__(self) -> str:
        return f"KeyedSeed(run_seed={self.run_seed}, keyed)"

    @classmethod
    def derive(cls, run_seed: int, secret: bytes) -> "KeyedSeed":
        draws = hashlib.blake2b(f"arthasim.draws/{run_seed}".encode(), key=secret, digest_size=16).digest()
        ids = hashlib.blake2b(f"arthasim.ids-key/{run_seed}".encode(), key=secret, digest_size=32).digest()
        return cls(run_seed=int(run_seed), k0=int.from_bytes(draws[:8], "little"),
                   k1=int.from_bytes(draws[8:], "little"), id_key=ids)


Seed = int | KeyedSeed


@njit(cache=True)
def _mix(x):
    x = (x ^ (x >> np.uint64(30))) * _M1
    x = (x ^ (x >> np.uint64(27))) * _M2
    return x ^ (x >> np.uint64(31))


@njit(cache=True)
def _key(seed, stream, entity, day, index):
    h = _mix(np.uint64(seed) + _G)
    h = _mix(h ^ np.uint64(stream))
    h = _mix(h ^ np.uint64(entity))
    h = _mix(h ^ np.uint64(day))
    return _mix(h ^ np.uint64(index))


@njit(cache=True)
def _uniform(seed, stream, entity, day, index):
    out = np.empty(entity.shape[0], dtype=np.float64)
    for i in range(entity.shape[0]):
        out[i] = np.float64(_key(seed, stream, entity[i], day, index) >> np.uint64(11)) * _TWO_NEG_53
    return out


@njit(cache=True)
def _poisson_inverse(u, lam):
    out = np.empty(u.shape[0], dtype=np.int64)
    for i in range(u.shape[0]):
        p = np.exp(-lam)
        c = p
        k = 0
        while u[i] > c and k < 1000:
            k += 1
            p *= lam / k
            c += p
        out[i] = k
    return out


@njit(cache=True)
def _bits(seed, stream, entity, day, index):
    out = np.empty(entity.shape[0], dtype=np.uint64)
    for i in range(entity.shape[0]):
        out[i] = _key(seed, stream, entity[i], day, index)
    return out


@njit(cache=True, inline="always")
def _rotl(x, b):
    return (x << np.uint64(b)) | (x >> np.uint64(64 - b))


@njit(cache=True, inline="always")
def _sipround(v0, v1, v2, v3):
    v0 += v1; v1 = _rotl(v1, 13); v1 ^= v0; v0 = _rotl(v0, 32)
    v2 += v3; v3 = _rotl(v3, 16); v3 ^= v2
    v0 += v3; v3 = _rotl(v3, 21); v3 ^= v0
    v2 += v1; v1 = _rotl(v1, 17); v1 ^= v2; v2 = _rotl(v2, 32)
    return v0, v1, v2, v3


@njit(cache=True)
def _sip_key(k0, k1, stream, entity, day, index):
    """SipHash-2-4 under (k0, k1) of the 32-byte message stream, entity, day, index (8 bytes each, little-endian)."""
    v0 = k0 ^ np.uint64(0x736F6D6570736575)
    v1 = k1 ^ np.uint64(0x646F72616E646F6D)
    v2 = k0 ^ np.uint64(0x6C7967656E657261)
    v3 = k1 ^ np.uint64(0x7465646279746573)
    for m in (np.uint64(stream), np.uint64(entity), np.uint64(day), np.uint64(index)):
        v3 ^= m
        v0, v1, v2, v3 = _sipround(v0, v1, v2, v3)
        v0, v1, v2, v3 = _sipround(v0, v1, v2, v3)
        v0 ^= m
    b = np.uint64(32) << np.uint64(56)
    v3 ^= b
    v0, v1, v2, v3 = _sipround(v0, v1, v2, v3)
    v0, v1, v2, v3 = _sipround(v0, v1, v2, v3)
    v0 ^= b
    v2 ^= np.uint64(0xFF)
    for _ in range(4):
        v0, v1, v2, v3 = _sipround(v0, v1, v2, v3)
    return v0 ^ v1 ^ v2 ^ v3


@njit(cache=True)
def _sip_uniform(k0, k1, stream, entity, day, index):
    out = np.empty(entity.shape[0], dtype=np.float64)
    for i in range(entity.shape[0]):
        out[i] = np.float64(_sip_key(k0, k1, stream, entity[i], day, index) >> np.uint64(11)) * _TWO_NEG_53
    return out


@njit(cache=True)
def _sip_bits(k0, k1, stream, entity, day, index):
    out = np.empty(entity.shape[0], dtype=np.uint64)
    for i in range(entity.shape[0]):
        out[i] = _sip_key(k0, k1, stream, entity[i], day, index)
    return out


def bits(seed: Seed, stream: int, entity, day: int, index: int = 0) -> np.ndarray:
    """Raw 64-bit keyed values, aligned with `entity`."""
    entity = np.ascontiguousarray(entity, dtype=np.int64)
    if isinstance(seed, KeyedSeed):
        return _sip_bits(np.uint64(seed.k0), np.uint64(seed.k1), stream, entity, day, index)
    return _bits(seed, stream, entity, day, index)


def stream_id(name: str) -> int:
    """Stable 63-bit id for a named stream."""
    return int.from_bytes(hashlib.sha256(name.encode()).digest()[:8], "little") >> 1


def uniform(seed: Seed, stream: int, entity, day: int, index: int = 0) -> np.ndarray:
    """Uniform draws in [0, 1), aligned with `entity`."""
    entity = np.ascontiguousarray(entity, dtype=np.int64)
    if isinstance(seed, KeyedSeed):
        return _sip_uniform(np.uint64(seed.k0), np.uint64(seed.k1), stream, entity, day, index)
    return _uniform(seed, stream, entity, day, index)


def normal(seed: Seed, stream: int, entity, day: int, index: int = 0) -> np.ndarray:
    u1 = uniform(seed, stream, entity, day, 2 * index + 1_000_003)
    u2 = uniform(seed, stream, entity, day, 2 * index + 1_000_004)
    return np.sqrt(-2.0 * np.log(1.0 - u1)) * np.cos(2.0 * np.pi * u2)


def lognormal(seed: Seed, stream: int, entity, day: int, median: float, sigma: float,
              index: int = 0) -> np.ndarray:
    return median * np.exp(sigma * normal(seed, stream, entity, day, index))


def poisson(seed: Seed, stream: int, entity, day: int, lam: float, index: int = 0) -> np.ndarray:
    return _poisson_inverse(uniform(seed, stream, entity, day, index), float(lam))
