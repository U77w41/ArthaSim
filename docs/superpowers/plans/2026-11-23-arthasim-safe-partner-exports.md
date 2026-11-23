# Safe Partner Exports Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A bank export can be handed to a partner who has the simulator's code: with a release secret, neither its identifiers nor the run behind it can be reproduced. The bank's customers carry an Aadhaar token where the bank must hold the Aadhaar link.

**Architecture:**
- **The run key.** An optional `Config.release_secret` becomes a `KeyedSeed` that travels wherever the integer seed travels today. `engine/rng.py` sends it to SipHash-2-4 kernels, and the identifier functions key BLAKE2b with it. A plain integer keeps today's code paths, so runs without a secret are unchanged except for `pan_like`, which becomes a keyed Feistel permutation either way.
- **The bank view** gains `uid_token` for customers with APBS credits or AePS withdrawals.
- **The export** reports whether a secret was used, keys `source_run` with it, and orders rows by the bank's own numbers.

**Tech Stack:** Python 3.12, NumPy, numba, Polars, DuckDB, pydantic 2, pytest. Run everything with `PYTHONPATH=src` from a virtual environment holding the `pyproject.toml` dependencies.

**Spec:** `docs/superpowers/specs/2026-11-23-safe-partner-exports-design.md`

## Global Constraints

- **Output.** Without a secret, output is byte-identical to `main` except the `persons` table (`pan_like`). The config hash and run folder name are unchanged.
- **Pinned values on `main`:**
  - `Config.tier("S").hash()` = `22ed10f6ba78d66b6da6ca2b35d8345aa048f86b4b75de27ead52c4a5b5ddd79`
  - `Config.tier("XS").hash()` = `10ae0bac368e147423c3854d946546d66d3705527f432bba5209cdaa224768c7`
- **The secret's format:** hexadecimal, at least 32 digits and an even number of them. `new_release_secret()` returns `secrets.token_hex(32)`.
- **Never written anywhere:** the secret, or any key derived from it, in the run folder, the run manifest, an export, a log, a `repr` or `to_yaml` output.
- **Exports:** the word "seed" (any case) never appears in an export's `manifest.json` or `README.md`.
- **The keyed generator:** SipHash-2-4 with a 128-bit key over the 32-byte message `stream ‖ entity ‖ day ‖ index`, each as 8 bytes little-endian (two's complement for negative values).
- **`pan_like`:**
  - D = 2,600,000.
  - A Feistel network on 22 bits (11 + 11), ten rounds, with cycle-walking to D.
  - Layout `SY{digit}P{initial}{four:04d}{letter}`, where `letter = j % 26`, `four = (j // 26) % 10000` and `digit = j // 260000`.
- **Commits:** every commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Never push. Ask the owner before merging into `main`.

## Review Focus

1. **A malformed secret** (odd length, `0x` prefix, spaces, 31 digits, non-hex) is rejected at `Config` construction with a message naming `release_secret`. Uppercase hex is accepted. *Test in Task 1.*
2. **A config reloaded from `to_yaml`** silently loses the secret. Its run then shows `release_secret: false` and gets a different config hash and folder, never the secret run's folder. *Test in Task 1.*
3. **A `KeyedSeed` reaching code that serialises or prints the seed** (manifest, `watch` payload, `inspect`, exceptions) must not crash and must not leak a key. *Test in Task 4.*
4. **A run written before this change** (manifest without `source_label` and `release_secret`) still exports, with today's `source_run` and `release_secret: false`. *Test in Task 6.*
5. **A bank with no APBS or AePS payments by the cut** gives a `customers` table whose `uid_token` is all null, without error; so does `pan_like` on an empty index. *Tests in Tasks 3 and 5.*

---

### Task 1: The release secret in `Config`

**Files:**
- Modify: `src/arthasim/config.py`, `src/arthasim/__init__.py`
- Test: `tests/test_release_config.py` (new)

**Interfaces:**
- Produces: `Config.release_secret: SecretStr | None`; `Config.secret_bytes() -> bytes | None`; `arthasim.config.new_release_secret() -> str`, re-exported as `arthasim.new_release_secret`.

- [ ] **Step 1: Write the failing tests**

```python
SECRET = "0f" * 32

def test_hash_unchanged_without_a_secret():
    assert Config.tier("S").hash() == "22ed10f6ba78d66b6da6ca2b35d8345aa048f86b4b75de27ead52c4a5b5ddd79"
    assert Config.tier("XS").hash() == "10ae0bac368e147423c3854d946546d66d3705527f432bba5209cdaa224768c7"

def test_secret_changes_the_hash_and_never_shows():
    a, b = Config.tier("S", release_secret=SECRET), Config.tier("S", release_secret="1e" * 32)
    assert len({Config.tier("S").hash(), a.hash(), b.hash()}) == 3
    assert SECRET not in repr(a) and SECRET not in str(a) and SECRET not in a.hash()
    assert a.secret_bytes() == bytes.fromhex(SECRET) and Config.tier("S").secret_bytes() is None
    assert Config.tier("S", release_secret=SECRET.upper()).hash() == a.hash()

@pytest.mark.parametrize("bad", ["ab" * 15 + "a", "0x" + "ab" * 16, " " + "ab" * 16, "ab" * 16 + "g", "ab" * 15 + "abc"])
def test_malformed_secret_is_rejected(bad):          # Review Focus 1
    with pytest.raises(ValueError, match="release_secret"):
        Config.tier("S", release_secret=bad)

def test_to_yaml_never_writes_the_secret(tmp_path):  # Review Focus 2
    a = Config.tier("S", release_secret=SECRET)
    a.to_yaml(tmp_path / "c.yaml")
    assert SECRET not in (tmp_path / "c.yaml").read_text()
    back = Config.from_yaml(tmp_path / "c.yaml")
    assert back.release_secret is None and back.hash() == Config.tier("S").hash() != a.hash()

def test_new_release_secret():
    s = arthasim.new_release_secret()
    assert len(s) == 64 and Config.tier("S", release_secret=s).secret_bytes() == bytes.fromhex(s)
```

- [ ] **Step 2:** Run `pytest tests/test_release_config.py -v`. Expected: FAIL (unknown field `release_secret`).

- [ ] **Step 3: Implement it in `config.py`.**
  - Add the field `release_secret: SecretStr | None = None`. A `field_validator` requires `re.fullmatch(r"[0-9a-fA-F]+", v)`, at least 32 digits and an even length, raising `ValueError` with "release_secret" in the message.
  - `secret_bytes()` returns `bytes.fromhex(...)` or `None`.
  - `hash()` dumps `model_dump(mode="json", exclude={"release_secret"})`. When a secret is set, it adds `"release_secret": blake2b(b"arthasim.config-hash", key=secret, digest_size=32).hexdigest()` before hashing.
  - `to_yaml` dumps with `exclude={"release_secret"}`.
  - `new_release_secret()` returns `secrets.token_hex(32)`.

- [ ] **Step 4:** Run `pytest tests/test_release_config.py tests/test_config.py tests/test_config_s.py -v`. Expected: PASS.

- [ ] **Step 5: Commit** with the message `feat: optional release secret in Config, hashed but never shown or written`.

### Task 2: Keyed generator for runs with a secret

**Files:**
- Modify: `src/arthasim/engine/rng.py`
- Test: `tests/test_keyed_rng.py` (new)

**Interfaces:**
- Produces:
  - A frozen dataclass `rng.KeyedSeed(run_seed: int, k0: int, k1: int, id_key: bytes)`, whose `__repr__` returns `f"KeyedSeed(run_seed={run_seed}, keyed)"`.
  - `KeyedSeed.derive(run_seed: int, secret: bytes) -> KeyedSeed`.
  - `rng.uniform`, `normal`, `lognormal`, `poisson` and `bits` accept `int | KeyedSeed` as `seed`.
  - The type alias `rng.Seed = int | KeyedSeed`.

- [ ] **Step 1: Write the failing tests.**
  - The test file holds a pure-Python `siphash24(key: bytes, msg: bytes) -> int`, the reference algorithm from the SipHash paper. Its first test pins the published vectors:
    - key `bytes(range(16))`, message `bytes(range(15))` → `0xa129ca6149be45e5`;
    - the same key with an empty message → `0x726fdb47dd0e0e31`;
    - the same key with message `bytes(range(32))` → `0x7127512f72f27cce`.

```python
K = KeyedSeed(run_seed=0, k0=int.from_bytes(bytes(range(8)), "little"),
              k1=int.from_bytes(bytes(range(8, 16)), "little"), id_key=b"\0" * 32)
E = np.array([0, 1, 41872, -5], dtype=np.int64)

def test_kernel_matches_reference():
    msg = lambda s, e, d, i: b"".join(int(v).to_bytes(8, "little", signed=True) for v in (s, e, d, i))
    assert rng.bits(K, 123, E, 3, 9).tolist() == [siphash24(bytes(range(16)), msg(123, e, 3, 9)) for e in E]
    u = rng.uniform(K, 123, E, 3, 9)
    assert u.tolist() == [(siphash24(bytes(range(16)), msg(123, e, 3, 9)) >> 11) / 2**53 for e in E]

def test_plain_seed_unchanged():
    e = E[:3]
    assert rng.uniform(7, 123, e, 3, 0).tolist() == [0.07419720641602001, 0.35979117562348784, 0.32791734220037083]
    assert rng.normal(7, 123, e, 3, 0).tolist() == [-0.599005126018669, -0.9632125037890983, 1.627249849022324]
    assert rng.poisson(7, 123, e, 3, 2.5, 0).tolist() == [0, 2, 2]
    assert [hex(x) for x in rng.bits(7, 123, e, 3, 0).tolist()] == ["0x12fe968f02e8fb13", "0x5c1b4644b138cb14", "0x53f264148ab59a10"]

def test_derive_is_keyed_reproducible_and_hidden():
    a, b = KeyedSeed.derive(7, b"\x01" * 32), KeyedSeed.derive(7, b"\x02" * 32)
    assert a == KeyedSeed.derive(7, b"\x01" * 32) and a != b and a != KeyedSeed.derive(8, b"\x01" * 32)
    assert repr(a) == "KeyedSeed(run_seed=7, keyed)"
    ids = np.arange(10_000, dtype=np.int64)
    ua, ub, up = rng.uniform(a, 5, ids, 1), rng.uniform(b, 5, ids, 1), rng.uniform(7, 5, ids, 1)
    assert ((0 <= ua) & (ua < 1)).all() and not np.isclose(ua, ub).any() and not np.isclose(ua, up).any()
    assert rng.poisson(a, 5, ids, 1, 3.0).mean() == pytest.approx(3.0, abs=0.1)
```

- [ ] **Step 2:** Run `pytest tests/test_keyed_rng.py -v`. Expected: FAIL (no `KeyedSeed`).

- [ ] **Step 3: Implement it in `rng.py`.**
  - `KeyedSeed.derive` takes:
    - the generator key from `blake2b(f"arthasim.draws/{run_seed}".encode(), key=secret, digest_size=16)`, with `k0` and `k1` as its two little-endian halves;
    - `id_key = blake2b(f"arthasim.ids-key/{run_seed}".encode(), key=secret, digest_size=32).digest()`.
  - Add the numba kernels `_sip_key(k0, k1, stream, entity, day, index)` (SipHash-2-4 over the four words; the final block is `32 << 56`), `_sip_uniform` and `_sip_bits`, mirroring `_uniform` and `_bits`.
  - `uniform` and `bits` dispatch on `isinstance(seed, KeyedSeed)`. `normal`, `lognormal` and `poisson` already go through `uniform`.
  - The plain-integer kernels are not touched.

- [ ] **Step 4:** Run `pytest tests/test_keyed_rng.py tests/test_rng.py -v`. Expected: PASS.

- [ ] **Step 5: Commit** with the message `feat: SipHash-2-4 keyed draws for a KeyedSeed; integer seeds keep today's mixer`.

### Task 3: Identifier keys and the keyed `pan_like`

**Files:**
- Modify: `src/arthasim/build/identifiers.py`, `src/arthasim/build/pipeline.py:205`, `src/arthasim/build/world.py:195`, `tests/test_banking.py:49` (the call only)
- Test: `tests/test_pan_like.py` (new)

**Interfaces:**
- Consumes: `rng.KeyedSeed`, `rng.Seed` (Task 2).
- Produces:
  - `identifiers.stream_key(seed: Seed, stream: int) -> bytes` (32 bytes). For an integer it is today's `blake2b(f"arthasim.ids/{seed}/{stream}", digest_size=32)`. For a `KeyedSeed` it is `blake2b(f"arthasim.ids/{run_seed}/{stream}", key=id_key, digest_size=32)`.
  - `keyed_bits`, `token`, `vpa`, `account_no`, `customer_no` and `terminal` accept `seed: Seed`.
  - `identifiers.pan_permutation(index, seed: Seed) -> np.ndarray[int64]`.
  - `pan_like(index, initial, seed: Seed, type_letter="P") -> np.ndarray[object]`.
  - `identifiers.PAN_SLOTS = 2_600_000`.

- [ ] **Step 1: Write the failing tests.**

```python
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
```

  Existing tests must keep passing unchanged, except for one line: `test_identifiers_cannot_be_real` changes its call to `pan_like(ids, ids % 26, 7)` and keeps every assertion. `test_identifier_tokens_are_keyed_one_way_hashes` pins the integer path.

- [ ] **Step 2:** Run `pytest tests/test_pan_like.py -v`. Expected: FAIL (no `pan_permutation`).

- [ ] **Step 3: Implement it in `identifiers.py`.** The Feistel network:
  - **Round tables.** The ten tables come from the key `k = stream_key(seed, rng.stream_id("id.pan_perm"))`. Entry `x` of round `r` is `int.from_bytes(blake2b(bytes([r]) + x.to_bytes(2, "little"), key=k, digest_size=2).digest(), "little") & 0x7FF`.
  - **One pass.** `L, R = v >> 11, v & 0x7FF`. Each round does `L, R = R, L ^ T[r][R]`. The result is `(L << 11) | R`.
  - **Cycle-walking.** Values ≥ `PAN_SLOTS` are passed again, as a NumPy loop over the still-out-of-range mask.
  - **Range check.** An index outside `[0, PAN_SLOTS)` raises `ValueError(f"pan_like covers 2,600,000 persons; got index {i}")`.
  - **Call sites.** Both pass the builder's `seed`: `pan_like(person_ids, initial, seed)`.

- [ ] **Step 4:** Run `pytest tests/test_pan_like.py tests/test_banking.py tests/test_review_fixes.py tests/test_identifiers_1c.py -v`. Expected: PASS.

- [ ] **Step 5: Commit** with the message `feat: pan_like is a keyed Feistel permutation of the person index; identifier keys accept a KeyedSeed`.

### Task 4: A world built with a secret

**Files:**
- Modify: `src/arthasim/world.py`, `scripts/bench.py`, `tests/run_fixture.py`
- Test: `tests/test_release_run.py` (new), `tests/test_bench.py`

**Interfaces:**
- Consumes: `Config.secret_bytes()` (Task 1), `KeyedSeed.derive` (Task 2), the identifier functions (Task 3).
- Produces:
  - **`World`.** `World.run_seed: int` is the seed passed to `build`. `World.seed` is the run's `Seed`: an `int` without a secret, a `KeyedSeed` with one.
  - **`run_manifest.json`.** It gains `"release_secret": bool` and `"source_label": str` (16 hex digits).
  - **`bench.py --release`** reads the secret from `ARTHASIM_RELEASE_SECRET` and adds `"release_secret"` to its result.
  - **`run_fixture.secret_run(persons=3_000)`:** an `lru_cache` run like `small_run`, but with `release_secret="5a" * 32` and the same dates.

- [ ] **Step 1: Write the failing tests** in `tests/test_release_run.py`. They use `secret_run()` and `small_run()`, which share persons, dates and seed:
  - **Manifest.** `release_secret` is true for the secret run and false for the plain one. `seed == 7` and the folder name starts `S-seed7-` for both. `source_label` matches `^[0-9a-f]{16}$`. The plain run's label equals `sha256(run_id)[:16]` and the secret run's does not.
  - **Nothing secret on disk.** No file under the secret run's folder contains any of these byte strings: the secret as text, `bytes.fromhex(secret)`, `KeyedSeed.derive(7, secret).id_key`, or the 16 generator-key bytes.
  - **No shared identifiers.** `persons` values of `uid_token`, `mobile_token` and `pan_like` and `instruments.value` share nothing with the plain run, except `BRANCH` values, which are not keyed.
  - **Different world.** `payments` content hashes differ.
  - **Not reproducible without the key.** `token("u", 7, rng.stream_id("id.uid"), person_ids)` shares nothing with the secret run's `uid_token`.
  - **Reproducible with the key.** A second `World.build` with the same secret, in another `out_dir` and over the same dates, gives an identical `content_hash` dictionary.
  - **No leak through other paths (Review Focus 3).** On the secret world, `watch` with a callback that records payloads, `run.inspect(<a person id>).profile()` and `.timeline()` all work. `repr(world.seed)` contains no key, and `json.dumps` of a recorded payload doesn't contain the secret.
  - **Bench.** In `tests/test_bench.py`, `bench.main(["--tier", "XS", "--days", "2", "--release", "--out", str(tmp_path)])` with `ARTHASIM_RELEASE_SECRET` set by `monkeypatch` returns `release_secret` true. Without the variable it exits with an error naming it.

- [ ] **Step 2:** Run `pytest tests/test_release_run.py tests/test_bench.py -v`. Expected: FAIL.

- [ ] **Step 3: Implement it in `world.py` and `bench.py`.**
  - `World.build` computes `draw = seed if config.release_secret is None else KeyedSeed.derive(seed, config.secret_bytes())` and passes `draw` wherever it passes `seed` today. The path still uses `seed`.
  - `World.__init__` gains `run_seed: int | None = None`, defaulting to `seed`.
  - `_flush` writes `"seed": self.run_seed`, `"release_secret": config.release_secret is not None` and `"source_label"`. The label is `sha256(run_id)[:16]` without a secret, and with one it is `blake2b(run_id.encode(), key=secret, digest_size=8).hexdigest()`.
  - `bench.py` gets a `--release` flag that sets `release_secret` from the environment variable.

- [ ] **Step 4:** Run `pytest tests/test_release_run.py tests/test_bench.py -v`, then the full fast suite with `pytest -q`. Expected: PASS, with 299 earlier tests plus the new ones.

- [ ] **Step 5: Commit** with the message `feat: a release secret keys the whole run; manifest records that it was used and a keyed source label`.

### Task 5: Aadhaar token in the bank view

**Files:**
- Modify: `src/arthasim/views.py` (`_bank` customers query, `DESCRIPTIONS["customers"]`), `tests/test_bank_view.py:69`
- Test: `tests/test_dbt_aadhaar.py` (new)

**Interfaces:**
- Produces: the bank view's `customers` gains `uid_token VARCHAR` after `mobile_token`.

- [ ] **Step 1: Write the failing tests** on `small_run()`. Pick the bank with the most qualifying customers, and assert there is at least one APBS-credited and one AePS customer, so the test bites.
  - **Expected set.** From the truth tables, take holders of deposit accounts at the bank that either received an APBS payment with status SUCCESS, or paid an AEPS payment of any status.
  - **The view matches.** `customers` non-null `uid_token` equals that set, and each value equals `persons.uid_token` for the entity.
  - **Organisations** are all null.
  - **`asof`.** For one entity whose first qualifying payment settles on day `d`, the token is null with `asof = d - 1 day` and set with `asof = d`. `asof_us` cuts at the start of the next IST day.
  - **A bank with none (Review Focus 5).** Use the tiny world from `test_empty_bank_export` (20 persons, to 2025-04-03). For every bank with customers, the non-null tokens equal the expected set, and at least one bank has customers and an all-null `uid_token` (chosen from the data).
  - **Existing test.** `test_bank_view.py:69` changes from `"uid_token" not in cust.columns` to `"uid_token" in cust.columns`. `test_every_view_column_is_described` must pass.

- [ ] **Step 2:** Run `pytest tests/test_dbt_aadhaar.py tests/test_bank_view.py -v`. Expected: FAIL.

- [ ] **Step 3: Implement the change in `views._bank`.** A CTE `aadhaar` takes the distinct `holder_entity_id` from a `union all` of two selects:
  - payments where `rail = 'APBS'` and `status = 'SUCCESS'`, joined on `payee_account_id`;
  - payments where `rail = 'AEPS'`, joined on `payer_account_id`.

  Each joins `acct_sql(src)` filtered to `bank_code = '{code}'` and `type = 'DEPOSIT'`, plus `and y.settle_ts < {cut}` when `asof` is set. Select `case when d.entity_id is not null then p.uid_token end as uid_token`, with `aadhaar d` left-joined on `entity_id`.

  Add `DESCRIPTIONS["customers"]["uid_token"]` with exactly the spec's sentence: "Opaque token standing for the Aadhaar number. Present when an account here has received a DBT credit (APBS) or made an AePS withdrawal, both of which need the Aadhaar link; the simulation does not model Aadhaar given voluntarily for e-KYC."

- [ ] **Step 4:** Run `pytest tests/test_dbt_aadhaar.py tests/test_bank_view.py tests/test_export.py tests/test_dbt_views.py -v`. Expected: PASS.

- [ ] **Step 5: Commit** with the message `feat: bank customers carry the Aadhaar token where an APBS credit or AePS withdrawal needs it`.

### Task 6: Export reports the secret and orders rows by the bank's numbers

**Files:**
- Modify: `src/arthasim/export.py`
- Test: `tests/test_export_release.py` (new)

**Interfaces:**
- Consumes: the manifest's `release_secret` and `source_label` (Task 4); `run_fixture.secret_run` (Task 4).
- Produces:
  - `manifest.json` gains `"release_secret": bool`; `source_run = run.manifest.get("source_label")`, falling back to `sha256(run_id)[:16]`.
  - `export.BANK_ORDER = {"customers": "customer_no", "accounts": "account_no", "instruments": "account_no, kind, value", "balances_monthly": "month, account_no"}`.

- [ ] **Step 1: Write the failing tests.**
  - **Secret run export.** A bank export of `secret_run()` has `manifest["release_secret"] is True`, and `source_run == secret_run().manifest["source_label"]`, not equal to `sha256(run_id)[:16]`. The README contains "release secret" and "SipHash-2-4" and does not contain "not anonymised". No exported file contains the secret text or `bytes.fromhex(secret)`, and "seed" appears in neither text file.
  - **Plain run export.** `release_secret is False`, and the README contains "not anonymised", "pan_like" and "ref".
  - **Old runs (Review Focus 4).** `Run(small_run().path, {k: v for k, v in small_run().manifest.items() if k not in ("source_label", "release_secret")})` exports with `source_run == sha256(run_id)[:16]` and `release_secret is False`.
  - **Order.** Read back from the export:
    - `customers.customer_no` is sorted;
    - `accounts.account_no` is sorted;
    - `instruments` is sorted by `(account_no, kind, value)`;
    - `balances_monthly`, read across months with hive partitioning, is sorted by `(month, account_no)`.

    Each table has more than one row. The Python view `run.view("bank", bank=...).table("customers")` still has `entity_id` ascending.

- [ ] **Step 2:** Run `pytest tests/test_export_release.py -v`. Expected: FAIL.

- [ ] **Step 3: Implement it in `export.py`.**
  - **Order.** In `export_view`, for `view == "bank"`, wrap each definition named in `BANK_ORDER` as `select * from ({definition}) order by {BANK_ORDER[t]}` before `_export_table`.
  - **`_source(run)`** prefers the manifest's `source_label`.
  - **`_readme`** chooses one of two warning paragraphs on `run.manifest.get("release_secret", False)`.

  The secret variant:

  > "Simulator ID columns are removed. Customers and accounts carry the bank's own numbers, and the other side of a payment appears only as a handle and a bank code. This run was made with a release secret held by its owner. Customer and account numbers, VPAs, terminals, `pan_like` and the device, card, mobile and Aadhaar tokens are keyed with it, and the simulation's random numbers come from a generator keyed with it (SipHash-2-4). So neither the identifiers nor the run can be reproduced without the secret, even with the simulator's code. This does not hide what the rows themselves show, such as birth year, district and amounts, and it is not a formal anonymity guarantee."

  The plain variant:

  > "Simulator ID columns are removed. Customers and accounts carry the bank's own numbers, and the other side of a payment appears only as a handle and a bank code. Customer and account numbers, VPAs, terminals, `pan_like` and the device, card, mobile and Aadhaar tokens are keyed one-way values, but this run has no release secret: every key comes from the run's settings, so someone with the simulator's code who guesses them can re-create the run and link `ref` to it. This export is not anonymised and is not for release outside the project."

- [ ] **Step 4:** Run `pytest tests/test_export_release.py tests/test_export.py tests/test_review_fixes.py -v`, then `pytest -q`. Expected: PASS.

- [ ] **Step 5: Commit** with the message `feat: export says whether a release secret was used, keys source_run, and orders rows by the bank's numbers`.

### Task 7: Benches, slow gates and results note

**Files:**
- Create: `docs/phase1c2_results.md`
- Modify: `docs/superpowers/ledger.md` (new section "Safe partner exports execution ledger")

- [ ] **Step 1: Bench without a secret.** Run `PYTHONPATH=src python scripts/bench.py --tier S --days 90 --seed 7 --out <scratch>`. Compare `content_hash` in the run manifest with the `main` baseline below, taken at `e2a23f1`, whose code equals `main` at `b188ed0`.
  - **Expected:** every table equal except `persons`, and `config_hash` starting `08112731` (the folder `S-seed7-08112731`).
  - **Baseline:** 15,282,932 payments.

  | Table | `main` content hash |
  | :--- | :--- |
  | `payments` | `cc2f554316011cc46fa809c1e8a4a77af5152f9e05325314145d0e7c0277851f` |
  | `journal` | `f0ef951399ab4341c6873f61e858b76e48c9c2066d4502500c423a4b4c50ca0f` |
  | `postings` | `74ce798fcb093d2d27efca27e2f74deb94ca365bb3529a79e78a0d13d9eca27d` |
  | `persons` | `9c49340f692c6e012f1b9ceff57f9477c159e97ffc27cfd234abc2cd6d52426a` (expected to change) |
  | `instruments` | `fa00df778819d8d5fcf593323d4f6a144bd848e99f8b71f63f2078641a854878` |
  | `bank_customers` | `533859ad5f96f63967b0cd764f01d8bf199ca12eae0a0c6c171d6c1a686dcaa9` |
  | `accounts` | `694ca5ebdb85b0e3ccb2fef142c86f705df7c2423ca3e5eb9e4f88fe989776b1` |
  | `balances_monthly` | `24d59862c0f10f325e1ab6cb64db90832a7c47fd8b544db6aeedbe3f46bd01cf` |

  The rest come from the baseline manifest. Re-run `main` at the merge base if the baseline folder is gone.

- [ ] **Step 2: Bench with a secret.** Run `ARTHASIM_RELEASE_SECRET=$(python -c "import secrets; print(secrets.token_hex(32))") ... --release`, three times for each mode, and record the median wall time.
  - **Expected:** every table's hash differs from Step 1.
  - **Record:** payments, status shares, the DBT and life summaries next to the plain run's, and the slowdown against the spec's estimate of 25–30%.

- [ ] **Step 3: Slow gates.** Run `pytest -m slow -q`. Expected: the 6 gates pass.

- [ ] **Step 4: KYC citation.** Check the citation against the current consolidated KYC Master Direction (updated 14 August 2025): the paragraph number and the wording for the DBT and voluntary cases, read word for word, not from a summary. If it differs from the spec, correct the results note and, if needed, the `DESCRIPTIONS` sentence.

- [ ] **Step 5: Results note and ledger.** Write `docs/phase1c2_results.md` in the style of `docs/phase1c_results.md`: what changed, both benches, the per-table hash comparison, the slowdown, the `uid_token` counts by kind at tier S (APBS only, AePS only, both), limits, and the old-spec supersession. Every number comes from a query run while writing. Add the ledger section in the style of plan 1c's.

- [ ] **Step 6: Commit** with the message `docs: safe partner exports results and execution ledger`.

After Task 7, a fresh Opus reviewer reads the whole branch against the spec. Its findings are fixed with a failing test first, the ledger records the rulings, and the owner is asked before any merge into `main`.
