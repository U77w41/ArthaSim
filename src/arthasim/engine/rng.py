"""Keyed random numbers.

Every draw is a pure function of (run_seed, stream, entity_id, day, index).
There is no generator state, so results do not depend on processing order and
a baseline and a treatment run share every draw.
"""
from __future__ import annotations

import hashlib

import numpy as np
from numba import njit

_G = np.uint64(0x9E3779B97F4A7C15)
_M1 = np.uint64(0xBF58476D1CE4E5B9)
_M2 = np.uint64(0x94D049BB133111EB)
_TWO_NEG_53 = 1.0 / 9007199254740992.0


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


def bits(seed: int, stream: int, entity, day: int, index: int = 0) -> np.ndarray:
    """Raw 64-bit keyed values, aligned with `entity`. Used for opaque tokens."""
    return _bits(seed, stream, np.ascontiguousarray(entity, dtype=np.int64), day, index)


def stream_id(name: str) -> int:
    """Stable 63-bit id for a named stream."""
    return int.from_bytes(hashlib.sha256(name.encode()).digest()[:8], "little") >> 1


def uniform(seed: int, stream: int, entity, day: int, index: int = 0) -> np.ndarray:
    """Uniform draws in [0, 1), aligned with `entity`."""
    return _uniform(seed, stream, np.ascontiguousarray(entity, dtype=np.int64), day, index)


def normal(seed: int, stream: int, entity, day: int, index: int = 0) -> np.ndarray:
    u1 = uniform(seed, stream, entity, day, 2 * index + 1_000_003)
    u2 = uniform(seed, stream, entity, day, 2 * index + 1_000_004)
    return np.sqrt(-2.0 * np.log(1.0 - u1)) * np.cos(2.0 * np.pi * u2)


def lognormal(seed: int, stream: int, entity, day: int, median: float, sigma: float,
              index: int = 0) -> np.ndarray:
    return median * np.exp(sigma * normal(seed, stream, entity, day, index))


def poisson(seed: int, stream: int, entity, day: int, lam: float, index: int = 0) -> np.ndarray:
    return _poisson_inverse(uniform(seed, stream, entity, day, index), float(lam))
