"""Synthetic identifiers. None of them can match a real format."""
from __future__ import annotations

import re

import numpy as np

from arthasim.engine import rng

REAL_FORMATS = {
    "pan": re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$"),
    "ifsc": re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$"),
    "aadhaar": re.compile(r"^[2-9][0-9]{11}$"),
    "mobile": re.compile(r"^[6-9][0-9]{9}$"),
}
_A = ord("A")


def pan_like(index, initial, type_letter: str = "P") -> np.ndarray:
    """PAN-shaped, with a digit in position 3, which no real PAN has. Unique per index."""
    out = []
    for i, ini in zip(np.asarray(index).tolist(), np.asarray(initial).tolist()):
        last, rest = i % 26, i // 26
        four, digit = rest % 10_000, (rest // 10_000) % 10
        out.append(f"SY{digit}{type_letter}{chr(_A + ini)}{four:04d}{chr(_A + last)}")
    return np.array(out, dtype=object)


def token(prefix: str, seed: int, stream: int, ids) -> np.ndarray:
    """Opaque token: prefix, underscore, 16 hex digits."""
    values = rng.bits(seed, stream, np.asarray(ids, dtype=np.int64), 0)
    return np.array([f"{prefix}_{v:016x}" for v in values.tolist()], dtype=object)


def branch_code(bank_index, district_index, locality) -> np.ndarray:
    """IFSC-shaped, but starts SY plus two digits, which a real IFSC cannot."""
    rows = zip(np.asarray(bank_index).tolist(), np.asarray(district_index).tolist(), np.asarray(locality).tolist())
    return np.array([f"SY{b + 1:02d}0{d:02d}{loc:04d}" for b, d, loc in rows], dtype=object)


def vpa(entity_id, bank_index) -> np.ndarray:
    rows = zip(np.asarray(entity_id).tolist(), np.asarray(bank_index).tolist())
    return np.array([f"p{e}@syn{b + 1:02d}" for e, b in rows], dtype=object)
