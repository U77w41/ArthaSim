"""Synthetic identifiers. None of them can match a real format."""
from __future__ import annotations

import hashlib
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


def keyed_bits(seed: int, stream: int, ids) -> list[int]:
    """64 bits per id from a keyed BLAKE2b digest. One-way: unlike the simulation's counter-based draws, a token
    cannot be turned back into the id it was made from. The key depends on the run seed and the stream."""
    key = hashlib.blake2b(f"arthasim.ids/{seed}/{stream}".encode(), digest_size=32).digest()
    return [int.from_bytes(hashlib.blake2b(i.to_bytes(8, "little", signed=True), key=key, digest_size=8).digest(),
                           "little") for i in np.asarray(ids, dtype=np.int64).tolist()]


def token(prefix: str, seed: int, stream: int, ids) -> np.ndarray:
    """Opaque token: prefix, underscore, 16 hex digits."""
    return np.array([f"{prefix}_{v:016x}" for v in keyed_bits(seed, stream, ids)], dtype=object)


def branch_code(bank_index, district_index, locality) -> np.ndarray:
    """IFSC-shaped, but starts SY plus two digits, which a real IFSC cannot."""
    rows = zip(np.asarray(bank_index).tolist(), np.asarray(district_index).tolist(), np.asarray(locality).tolist())
    return np.array([f"SY{b + 1:02d}0{d:02d}{loc:04d}" for b, d, loc in rows], dtype=object)


def vpa(seed: int, account_ids, bank_index, prefix: str = "p") -> np.ndarray:
    """Opaque VPA: a token keyed on the account, then the bank. It encodes no simulator ID."""
    tokens = token(prefix, seed, rng.stream_id("id.vpa"), account_ids)
    return np.array([f"{t}@syn{b + 1:02d}" for t, b in zip(tokens.tolist(), np.asarray(bank_index).tolist())],
                    dtype=object)


def account_no(seed: int, account_ids, bank_codes) -> np.ndarray:
    """The bank's own account number: bank code, hyphen, 16 hex digits keyed on the account."""
    values = keyed_bits(seed, rng.stream_id("id.account_no"), account_ids)
    return np.array([f"{c}-{v:016x}" for c, v in zip(np.asarray(bank_codes).tolist(), values)], dtype=object)


def customer_no(seed: int, entity_ids, bank_index, bank_codes) -> np.ndarray:
    """The bank's own customer number for (bank, entity): CIF, bank code, hyphen, 16 hex digits."""
    key = np.asarray(entity_ids, dtype=np.int64) * 64 + np.asarray(bank_index, dtype=np.int64)
    values = keyed_bits(seed, rng.stream_id("id.customer_no"), key)
    return np.array([f"CIF{c}-{v:016x}" for c, v in zip(np.asarray(bank_codes).tolist(), values)], dtype=object)


def terminal(seed: int, account_ids) -> np.ndarray:
    """A card-accepting merchant's terminal ID, keyed on its account."""
    return token("t", seed, rng.stream_id("id.terminal"), account_ids)
