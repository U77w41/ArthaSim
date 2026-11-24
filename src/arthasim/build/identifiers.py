"""Synthetic identifiers. None of them can match a real format."""
from __future__ import annotations

import hashlib
import re

import numpy as np

from arthasim.engine import rng
from arthasim.engine.rng import KeyedSeed, Seed

REAL_FORMATS = {
    "pan": re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$"),
    "ifsc": re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$"),
    "aadhaar": re.compile(r"^[2-9][0-9]{11}$"),
    "mobile": re.compile(r"^[6-9][0-9]{9}$"),
    "account_no": re.compile(r"^[0-9]{9,18}$"),         # Indian bank account numbers are 9 to 18 digits
    "card": re.compile(r"^[0-9]{16}$"),                 # a real card number also passes the Luhn check
}
# Every synthetic VPA ends in a handle of this form; real handles name a bank or an app.
SYNTHETIC_VPA_HANDLE = re.compile(r"^syn[0-9]{2}$")


def luhn(digits: str) -> bool:
    """True when a string of digits passes the Luhn check, as every real card number does."""
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
    return total % 10 == 0
_A = ord("A")
PAN_SLOTS = 26 * 10_000 * 10        # last letter x four digits x the digit in position 3
_HALF, _ROUNDS = 11, 10             # Feistel network on 22 bits (2**22 >= PAN_SLOTS), ten rounds as in NIST FF1
_MASK = (1 << _HALF) - 1


def stream_key(seed: Seed, stream: int) -> bytes:
    """The 32-byte key for one identifier stream. An integer seed gives the original key, which anyone with the code
    and the seed can recompute; a KeyedSeed keys it with the release secret."""
    if isinstance(seed, KeyedSeed):
        return hashlib.blake2b(f"arthasim.ids/{seed.run_seed}/{stream}".encode(), key=seed.id_key,
                               digest_size=32).digest()
    return hashlib.blake2b(f"arthasim.ids/{seed}/{stream}".encode(), digest_size=32).digest()


def pan_permutation(index, seed: Seed) -> np.ndarray:
    """A keyed permutation of [0, PAN_SLOTS): a Feistel network on 22 bits, cycle-walked back into range. Without
    the key, a slot cannot be turned back into the index it came from."""
    idx = np.asarray(index, dtype=np.int64)
    bad = (idx < 0) | (idx >= PAN_SLOTS)
    if bad.any():
        raise ValueError(f"pan_like covers 2,600,000 persons; got index {int(idx[bad][0])}")
    key = stream_key(seed, rng.stream_id("id.pan_perm"))
    tables = np.array([[int.from_bytes(hashlib.blake2b(bytes([r]) + x.to_bytes(2, "little"), key=key,
                                                       digest_size=2).digest(), "little") & _MASK
                        for x in range(1 << _HALF)] for r in range(_ROUNDS)], dtype=np.int64)
    out = idx.copy()
    todo = np.ones(out.size, dtype=bool)
    while todo.any():
        v = out[todo]
        left, right = v >> _HALF, v & _MASK
        for r in range(_ROUNDS):
            left, right = right, left ^ tables[r][right]
        out[todo] = (left << _HALF) | right
        todo = out >= PAN_SLOTS
    return out


def pan_like(index, initial, seed: Seed, type_letter: str = "P") -> np.ndarray:
    """PAN-shaped, with a digit in position 3, which no real PAN has. Unique per index; the slot is a keyed
    permutation of the index, so it does not reveal the person's place in the population."""
    out = [f"SY{j // 260_000}{type_letter}{chr(_A + ini)}{(j // 26) % 10_000:04d}{chr(_A + j % 26)}"
           for j, ini in zip(pan_permutation(index, seed).tolist(), np.asarray(initial).tolist())]
    return np.array(out, dtype=object)


def keyed_bits(seed: Seed, stream: int, ids) -> list[int]:
    """64 bits per id from a keyed BLAKE2b digest. One-way: unlike the simulation's counter-based draws, a token
    cannot be turned back into the id it was made from. The key depends on the run seed and the stream, and on the
    release secret when the run has one."""
    key = stream_key(seed, stream)
    return [int.from_bytes(hashlib.blake2b(i.to_bytes(8, "little", signed=True), key=key, digest_size=8).digest(),
                           "little") for i in np.asarray(ids, dtype=np.int64).tolist()]


def token(prefix: str, seed: Seed, stream: int, ids) -> np.ndarray:
    """Opaque token: prefix, underscore, 16 hex digits."""
    return np.array([f"{prefix}_{v:016x}" for v in keyed_bits(seed, stream, ids)], dtype=object)


def branch_code(bank_index, district_index, locality) -> np.ndarray:
    """IFSC-shaped, but starts SY plus two digits, which a real IFSC cannot. Each distinct branch is formatted
    once: there are few branches and many accounts."""
    b, d, loc = (np.asarray(x, dtype=np.int64).ravel() for x in (bank_index, district_index, locality))
    if b.size == 0:
        return np.empty(0, dtype=object)
    lo = [int(x.min()) for x in (b, d, loc)]
    span = [int(x.max()) - m + 1 for x, m in zip((b, d, loc), lo)]
    if span[0] * span[1] * span[2] >= 1 << 62:         # one int64 per branch would overflow: format every row
        rows = zip(b.tolist(), d.tolist(), loc.tolist())
        return np.array([f"SY{x + 1:02d}0{y:02d}{z:04d}" for x, y, z in rows], dtype=object)
    key = ((b - lo[0]) * span[1] + (d - lo[1])) * span[2] + (loc - lo[2])
    _, first, inverse = np.unique(key, return_index=True, return_inverse=True)
    rows = zip(b[first].tolist(), d[first].tolist(), loc[first].tolist())
    return np.array([f"SY{x + 1:02d}0{y:02d}{z:04d}" for x, y, z in rows], dtype=object)[inverse.ravel()]


def vpa(seed: Seed, account_ids, bank_index, prefix: str = "p") -> np.ndarray:
    """Opaque VPA: a token keyed on the account, then the bank. It encodes no simulator ID."""
    tokens = token(prefix, seed, rng.stream_id("id.vpa"), account_ids)
    return np.array([f"{t}@syn{b + 1:02d}" for t, b in zip(tokens.tolist(), np.asarray(bank_index).tolist())],
                    dtype=object)


def account_no(seed: Seed, account_ids, bank_codes) -> np.ndarray:
    """The bank's own account number: bank code, hyphen, 16 hex digits keyed on the account."""
    values = keyed_bits(seed, rng.stream_id("id.account_no"), account_ids)
    return np.array([f"{c}-{v:016x}" for c, v in zip(np.asarray(bank_codes).tolist(), values)], dtype=object)


def customer_no(seed: Seed, entity_ids, bank_index, bank_codes) -> np.ndarray:
    """The bank's own customer number for (bank, entity): CIF, bank code, hyphen, 16 hex digits."""
    key = np.asarray(entity_ids, dtype=np.int64) * 64 + np.asarray(bank_index, dtype=np.int64)
    values = keyed_bits(seed, rng.stream_id("id.customer_no"), key)
    return np.array([f"CIF{c}-{v:016x}" for c, v in zip(np.asarray(bank_codes).tolist(), values)], dtype=object)


class IdentifierMemo:
    """Identifiers already made, by kind and int64 key, so a rebuild of the account tables makes only new ones.
    Each identifier is a pure function of the seed and its key, so a kept string equals a newly made one. A memo
    serves one seed: asked with another, it starts again."""

    def __init__(self) -> None:
        self._seed: Seed | None = None
        self._kept: dict[str, tuple[np.ndarray, np.ndarray]] = {}       # kind -> (sorted keys, identifiers)

    def strings(self, seed: Seed, kind: str, keys, make) -> np.ndarray:
        """The identifier for each key. `make(rows)` makes those of `keys[rows]` (an index array) not kept yet."""
        if self._seed is None or self._seed != seed:
            self._seed, self._kept = seed, {}
        keys = np.asarray(keys, dtype=np.int64)
        known, values = self._kept.get(kind, (np.empty(0, dtype=np.int64), np.empty(0, dtype=object)))
        pos = np.searchsorted(known, keys)
        hit = pos < known.size
        hit[hit] = known[pos[hit]] == keys[hit]
        out = np.empty(keys.size, dtype=object)
        out[hit] = values[pos[hit]]
        miss = np.flatnonzero(~hit)
        if miss.size:
            made = np.asarray(make(miss), dtype=object)
            out[miss] = made
            new, first = np.unique(keys[miss], return_index=True)
            at = np.searchsorted(known, new)
            self._kept[kind] = (np.insert(known, at, new), np.insert(values, at, made[first]))
        return out


def terminal(seed: Seed, account_ids) -> np.ndarray:
    """A card-accepting merchant's terminal ID, keyed on its account."""
    return token("t", seed, rng.stream_id("id.terminal"), account_ids)
