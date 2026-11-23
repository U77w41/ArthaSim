# Safe partner exports: design

23 November 2026. This closes the identifier gaps that plan 1c left open (ledger, "Plan 1c (data products) execution ledger", "Rulings on the review"; `docs/phase1c_results.md`, "Limits").

The project owner decided the following in conversation:
- A partner **may have the simulator's code**, now or later.
- **Approach A:** a release secret in `Config`.
- **A keyed generator (SipHash-2-4) for runs with a secret**, accepting slower release runs.
- **`uid_token` for customers whose account at the bank has received an APBS credit or made an AePS withdrawal.**

A builder check read the first draft; its questions are settled here. Calls marked **Builder's call** or **My call** were made by the writer and are open to the owner's correction.

## Intent

A bank export (`run.export(dest, view="bank", bank=...)`) is meant to be handed to partners. Blueprint section 17 puts it at the partner release level: views and labels, but not the truth tables or typology settings. A partner must not be able to work back from an export to the simulator's people, meaning their `entity_id`, truth tables, latent traits and life events. That has to hold even if the partner has the code.

Four things stop that today:

1. **`pan_like` spells out the person's index.** `identifiers.pan_like` writes the index into the PAN's digits and last letter, so it decodes to `entity_id` directly.
2. **Everything else is derived from the seed.** Token keys come only from the run seed, which is a small integer, typically 7. The seed also drives every random draw. Someone with the code can guess the seed, re-run the world, and join the export on `ref`, which is the payment ID padded to 12 digits (`views.ref_sql`). That gives them every payer, payee and `entity_id`, whatever the tokens look like.
   - Every draw passes through one 64-bit value (`_mix(seed + G)` in `engine/rng.py`), so even a long secret folded into the seed would cap the work of re-creating the run at about 2⁶³ guesses.
   - The SplitMix64-style mixer can also be inverted, so in principle someone could work back from observed values to that state.
   - So the secret has to key the random generator itself, not just the identifiers.
3. **The export manifest gives the seed away.** `source_run` is the SHA-256 of the run folder name, `S-seed7-<config hash>`. For a standard tier config, trying seeds one by one finds it in moments.
4. **Exported rows come in simulator-ID order.** The bank's `customers` table is sorted by `entity_id`, and `accounts`, `instruments` and `balances_monthly` by `account_id`. Accounts opened at build are numbered in person order. A partner therefore learns each customer's rank by `entity_id`. Because the number of persons per district is fixed by the config, that rank narrows the ID to a few hundred values.

Separately, the bank view's `customers` table carries no Aadhaar token. The RBI KYC Master Direction, 2016, as amended on 29 May 2019, lets a bank obtain a customer's Aadhaar number in two cases, set out in section 16:
- the customer wants a benefit or subsidy under a scheme notified under section 7 of the Aadhaar Act, that is, a DBT beneficiary;
- the customer chooses to give it to a bank for authentication.

Customers who hand over a copy of their Aadhaar that isn't authenticated must redact the number. (Sources: [RBI notice on the 2019 amendment](https://rbi.org.in/Commonman/English/Scripts/Notification.aspx?Id=2968); [consolidated Master Direction, updated 14 August 2025](https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=11566).)

Two cases in the model mean the bank must hold the customer's Aadhaar link:
- **DBT by APBS.** APBS routes a credit by Aadhaar number to the account linked to it.
- **AePS withdrawals.** Every person without a debit card withdraws through AePS at their own bank (plan 1c counted about 978,000 such payments on the switch), and AePS authenticates with Aadhaar against the account it is linked to.

## Goals

- **A release secret.** `Config` gets an optional field, `release_secret`. When it is set:
  - every random draw comes from SipHash-2-4 with a 128-bit key derived from the secret, so the run cannot be re-created without it, even with the code and the seed;
  - every token, customer and account number, VPA, terminal and `pan_like` is keyed with it;
  - `source_run` is keyed with it;
  - the export manifest and README say a secret was used, without revealing it.
- **Without a secret, the run matches today's output** in every table except `persons`, where `pan_like` changes (next goal). The config hash, run folder name and every other content hash stay the same.
- **`pan_like` is a keyed format-preserving permutation of the person's index.** It keeps today's shape (`SY`, a digit in position 3, `P`, the initial, four digits, a letter), which no real PAN can have. It is unique for up to 2,600,000 persons, enough for tiers S and M. It cannot be decoded without the key.
- **The bank's `customers` table gets `uid_token`** for a customer whose account at that bank has received a successful APBS credit or made an AePS withdrawal, by the view's date. The column is null for every other customer.
- **Exported tables are ordered by the bank's own numbers**, not by simulator IDs.
- **Tests** show that tokens and `pan_like` from a run with a secret cannot be reproduced without it, differ between secrets, are reproducible with the same secret, and are unique. They also show that the keyed generator matches published SipHash-2-4 values.
- **Two benches at tier S, 90 days, seed 7.** The no-secret bench shows only `persons` changing against `main`. The secret bench shows a different world whose invariants still hold, and records how much slower it runs.

## Non-goals

- **Changing `ref`.** It stays the payment ID padded to 12 digits; labels are keyed on it (plan 1c ruling). Once the run cannot be re-created, `ref` only shows payment order and volume, which the plan 1c ruling accepted.
- **Coarser geography, the DPDP legal review and public release.** These belong to the public release level (blueprint section 17).
- **The truth export.** It stays a copy of the run's files and is internal by definition.
- **Aadhaar given voluntarily for e-KYC.** That would need a modelled share of customers, a sourced parameter, and a change to the run beyond `persons`. It can follow as a calibration step.
- **A keyed generator for runs without a secret.** Those keep today's mixer and stay byte-identical.
- **Changing the row order of the Python views.** They show simulator IDs anyway; only exports reorder.

## Anti-goals

- **The secret on disk or in an export.** The secret, and any key derived from it, must never be written into the run folder, the run manifest, an export, a log or the repo. `Config.to_yaml` never writes it, and `repr` hides it.
- **A silent change to no-secret runs.** Apart from `pan_like`, a run without a secret must be byte-identical to `main`, with the same content hashes and the same config hash.
- **A false promise.** The README must not claim more than the design delivers, and an export of a run without a secret says plainly that it is not for release.

## Constraints

- Output is byte-identical for the same seed unless a change is intended and documented. Check with `scripts/bench.py --tier S --days 90 --seed 7` and the manifest's `content_hash`.
- `tests/test_banking.py::test_identifiers_cannot_be_real` keeps its assertions and passes (see section 3 for its call).
- `tests/test_review_fixes.py::test_export_carries_no_seed_and_says_what_it_protects` requires that the word "seed" never appears in an export's manifest or README. Every new README sentence and `DESCRIPTIONS` entry must avoid it, including in "Aadhaar-seeded".
- Every random draw goes through the public functions of `engine/rng.py` (`uniform`, `normal`, `lognormal`, `poisson`, `bits`). No other code calls the numba kernels or uses the seed in arithmetic; this was checked by search on 23 November 2026 and the plan re-checks it. Everything else receives the seed as a value and passes it on.
- The run folder stores no config, only its hash (`World._flush`), so the config reaches the run only through `World.build`.
- **Measured starting point** (20,000 persons, 37 days, M5): draws take about 5% of run time. In a NumPy loop under numba, SipHash-2-4 makes 84 million draws a second against 590 million for today's mixer, about 7 times slower. A secret run is therefore expected to take about 25–30% longer. The bench measures the real figure.

## Approaches considered

- **A. A release-secret field in `Config` (picked by the owner).** When it is set, the random generator and every identifier are keyed with the secret. The folder name and manifest keep the seed as typed. Cost: a release run is a different world from seed 7 and needs its own checks, and it runs slower.
- **B. The seed is the secret.** No new field: release runs use a large random seed that is kept private. Less code, but the secret would sit in run folder names and manifests that get passed around, keys would be capped at 64 bits, and nothing would stop a seed-7 run from being exported by mistake.
- **Dropped: keying only the identifiers** (the first brief). With the code and a guessed seed, `ref` joins a re-created run to the export.
- **Within A, how the secret reaches the draws.**
  - **Picked: SipHash-2-4 keyed with 128 bits for secret runs only.** It is a standard keyed function, runs without a secret don't change, and the cost is the slowdown above.
  - **Rejected: folding the secret into a 63-bit working seed and keeping today's mixer.** It is free, but capped at 2⁶³ and invertible in principle, so the README would need a caveat.

## Design

### 1. The release secret and the run key

**`Config.release_secret: SecretStr | None = None`** (pydantic `SecretStr`).
- **Format.** It must be hexadecimal with at least 32 digits, so 128 bits or more; anything else is rejected with a clear error. `arthasim.new_release_secret()` returns `secrets.token_hex(32)`. *My call:* requiring hex at a minimum length keeps people from using a short passphrase that could be brute-forced.
- **Config hash.** When the secret is unset, the field is left out of the hashed dictionary, so the hash, and with it the run folder name, is unchanged from today. When it is set, the hash covers a keyed digest of the secret, not the secret itself. Two runs that differ only in their secret therefore get different folders.
- **`to_yaml`.** It never writes the field. `from_yaml` and the constructor accept it.
- **Where the secret comes from.** User code passes it. `scripts/bench.py` gets a flag that reads it from the environment variable `ARTHASIM_RELEASE_SECRET`, so it never appears on a command line; the flag's name is the builder's call.

**The run key.**
- **Without a secret,** the value every module receives as `seed` (`World.seed`) is the plain integer, exactly as today.
- **With a secret,** `World.seed` is a small frozen object, for example `KeyedSeed` (the name is the builder's call). It holds:
  - the run seed;
  - the 128-bit generator key: two 64-bit words, the first 16 bytes of BLAKE2b keyed with the secret over a tag such as `arthasim.draws/<seed>`;
  - the bytes that key identifiers (section 2).
- **Its `repr`** shows only the run seed and the word "keyed".
- **Where it goes.** It reaches every place that receives `seed` today (build, modules, account frames, DBT schemes) without any change to their code, because they only pass it on.
- **`engine/rng.py`.** Each public function (`uniform`, `normal`, `lognormal`, `poisson`, `bits`) sends a plain integer to today's kernels, unchanged, and a `KeyedSeed` to SipHash versions of the same kernels. The SipHash kernel replaces `_key(seed, stream, entity, day, index)`. Its output is SipHash-2-4 with the 128-bit key over the 32-byte message made of `stream`, `entity`, `day` and `index`, each as 8 bytes little-endian. Everything downstream of `_key` (the 53-bit uniform, the Poisson inverse and so on) is shared.
- **The folder name and manifest** use the run seed. *Builder's call:* how `World` keeps the run seed apart from `World.seed`, for example `World.run_seed`. Nothing derived from the secret is written.

**Run manifest.**
- It gains `"release_secret": true | false`.
- It also gains `"source_label"`, the 16-hex-digit label that exports use as `source_run`. Without a secret it is today's value, `sha256(run_id)[:16]`. With one, it is BLAKE2b keyed with the secret over `run_id`. The label is worked out at build time and stored, because an export reads only the run folder.
- An export of a run whose manifest has no `source_label`, that is, a run written before this change, falls back to today's formula.

### 2. Identifier keys

The identifier functions are `keyed_bits`, `token`, `vpa`, `account_no`, `customer_no`, `terminal` and `pan_like`. They take the same `seed` value they take today, and call sites don't change.

- **Plain integer:** the per-stream key is exactly today's, `blake2b(f"arthasim.ids/{seed}/{stream}", digest_size=32)`. `tests/test_review_fixes.py::test_identifier_tokens_are_keyed_one_way_hashes` pins this and keeps passing unchanged.
- **`KeyedSeed`:** the per-stream key is `blake2b(f"arthasim.ids/{run_seed}/{stream}", key=<identifier key bytes>, digest_size=32)`. The identifier key bytes are derived from the secret under a separate tag, so they are not the generator key. The per-id digest is unchanged.

### 3. `pan_like`

- **The permutation.** Today's slot is (last letter, four digits, digit in position 3), which gives D = 26 × 10,000 × 10 = 2,600,000 slots. The person's index `i` (person entity IDs are `0..P-1`) is mapped to `π(i)` in `[0, D)`, and `π(i)` is written in today's layout: `SY{digit}P{initial}{four:04d}{letter}`. `π` is a keyed Feistel network on 22 bits (11 + 11, ten rounds, as in NIST FF1), with cycle-walking until the value falls below D. Expect about 1.6 passes, since 2²² / D ≈ 1.61.
- **The round function.** For each round, a table of 2,048 entries holds the first 11 bits of keyed BLAKE2b over (round, x). That is 20,480 hashes per run, and the network then runs as NumPy table lookups, fast at tier M.
- **The key.** It comes from the same `seed` value as in section 2: through the identifier key with a secret, or from the seed and a stream named for example `id.pan_perm` without one.
- **The initial.** The fifth character stays a separate draw (stream `id.pan`). The type letter stays `P`.
- **Range check.** An index of D or more raises an error, because uniqueness would break.
- **Call signature.** `pan_like(index, initial, seed, type_letter="P")`. *My call:* `test_identifiers_cannot_be_real` passes a seed and keeps every assertion. There is no keyless default, because a default would be a decodable path.
- **Spike builder.** `build/world.py` calls `pan_like` too and passes its seed.

### 4. Aadhaar in the bank view

**The `customers` query.** In `views._bank`, the query gets `uid_token`, placed after `mobile_token`. It is `p.uid_token` when the customer holds an account at this bank (`type = 'DEPOSIT'`) and, before the view's cut, either:
- that account received a payment with `rail = 'APBS'` and `status = 'SUCCESS'`, or
- that account paid a payment with `rail = 'AEPS'`, whatever its status, since a declined withdrawal still authenticated with Aadhaar.

The cut uses the same timestamp the bank view's payments use (`settle_ts < cut`); without `asof`, any such payment counts. Otherwise the column is null. Organisations always get null.

**Why this rule.** The state records no Aadhaar linking. A credit or withdrawal at the bank is the first time it would certainly hold the link. Someone enrolled whose first credit hasn't landed yet, and who hasn't withdrawn by AePS, has no token.

**Descriptions.** `DESCRIPTIONS["customers"]["uid_token"]` (no "seed"): "Opaque token standing for the Aadhaar number. Present when an account here has received a DBT credit (APBS) or made an AePS withdrawal, both of which need the Aadhaar link; the simulation does not model Aadhaar given voluntarily for e-KYC."

**Citation.** The results note cites section 16 of the KYC Master Direction for both cases. Before writing, the builder checks the wording and paragraph number against the current consolidated text, updated 14 August 2025. The fetch used here read only a summary of section 16.

**The old spec.** The plan 1c spec's line "No Aadhaar token" in the `customers` row is superseded. This spec says so; the old spec is not edited.

### 5. Export: manifest, README and row order

- **The manifest** gains `"release_secret": true | false`, and `source_run` comes from the run's `source_label`.
- **README with a secret.** It says the run was made with a release secret held by its owner. Customer and account numbers, VPAs, terminals, `pan_like` and the device, card, mobile and Aadhaar tokens are keyed with it, and the simulation's random numbers come from a keyed generator (SipHash-2-4) under it. So neither the identifiers nor the run can be reproduced without it, even with the simulator's code. It also says this does not hide what the rows themselves show, such as ages, districts and amounts, and is not a formal anonymity guarantee.
- **README without a secret.** It keeps the plan 1c warning, reworded: `pan_like` is now a keyed shuffle, but every key comes from the run's settings, so someone with the code who guesses them can re-create the run and link `ref` to it. The export is "not anonymised" and is not for release outside the project. The existing test's phrases (`not anonymised`, `pan_like`, `ref`) stay.
- **Wording.** Neither variant contains the word "seed".
- **No refusal.** *My call:* the export doesn't refuse a run without a secret, because internal use needs it. The manifest flag and README make the difference plain.
- **Row order (bank export only; the Python view keeps its order).**

  | Table | Sorted by |
  | :--- | :--- |
  | `customers` | `customer_no` |
  | `accounts` | `account_no` |
  | `instruments` | `account_no`, `kind`, `value` |
  | `balances_monthly` | `month`, `account_no` |

  `payments` and `statement_lines` keep their time order: it ties only on public values, time, then `ref`, which is already in the file. *Builder's call:* where the export order is set, for example an export-only `order` map applied in `_export_table`. The switch export already orders by time and `ref`.

### 6. Where the code goes (a proposal; the builder may rearrange)

| File | Change |
| :--- | :--- |
| `src/arthasim/config.py` | `release_secret`, validator, hash rule, `to_yaml` rule |
| `src/arthasim/engine/rng.py` | `KeyedSeed`; SipHash-2-4 kernels; dispatch in the public functions |
| `src/arthasim/build/identifiers.py` | `keyed_bits` with a `KeyedSeed`; Feistel `pan_like` |
| `src/arthasim/build/world.py` | pass the seed to `pan_like` |
| `src/arthasim/world.py` | build the run key, `run_seed`, `source_label`, `release_secret` in the manifest |
| `src/arthasim/views.py` | `uid_token` in bank `customers`, `DESCRIPTIONS` |
| `src/arthasim/export.py` | manifest flag, `source_run` from the manifest, README variants, export row order |
| `src/arthasim/__init__.py` | export `new_release_secret` |
| `scripts/bench.py` | read the secret from the environment variable when asked |

## Testing and verification

The work is test-first on a feature branch. New tests:

1. **Config.**
   - A secret that isn't hex, or has fewer than 32 digits, is rejected.
   - `repr` and `str` hide the secret.
   - Without a secret, the hash equals today's for a fixed config (pinned).
   - The hash differs with a secret, and between two secrets.
   - `to_yaml` output does not contain the secret.
2. **Keyed generator.**
   - A pure-Python SipHash-2-4 in the test file reproduces the published test vector: key `00..0f`, message `00..0e`, output `a129ca6149be45e5`, from the SipHash paper. The builder confirms it against the reference `vectors.h`.
   - The numba kernel matches that reference on 32-byte messages.
   - With a `KeyedSeed`, `uniform` and the other functions are reproducible, lie in range, and differ from the plain-integer path and between keys.
   - With a plain integer, every function returns exactly what it does on `main` (pinned values).
3. **`pan_like`.**
   - Every one of the 2,600,000 indices maps to a distinct value (a full permutation); a run of 1,000,000 indices is unique too.
   - The format regex matches, and `REAL_FORMATS["pan"]` never does.
   - The same key gives the same output; different keys share almost no outputs on the same indices.
   - The output is not today's index encoding.
   - An index of D or more raises an error.
4. **Tokens with a secret.**
   - `keyed_bits` with a `KeyedSeed` differs from `keyed_bits` with the plain integer, and between secrets.
   - With the plain integer, it is unchanged (the existing pin).
5. **World with a secret (small tier S world).**
   - The folder name and manifest show the run seed and `release_secret: true`.
   - No file in the run folder contains the secret's hex string or any derived key.
   - Tokens and `pan_like` share no value with the same run built without a secret.
   - Rebuilding with the same secret reproduces every table byte for byte.
   - Payments differ from the no-secret run.
   - "Cannot be reproduced without the key": recomputing the identifier functions with the run seed but no secret matches none of the run's tokens.
6. **Bank view `uid_token`.**
   - It is non-null exactly for customers with a successful APBS credit, or an AePS withdrawal, on an account at that bank by the cut.
   - With `asof` before someone's first such payment, theirs is null.
   - It is null for organisations.
   - It equals the person's `uid_token` in `persons`.
   - `test_every_view_column_is_described` passes.
7. **Export.**
   - The manifest has `release_secret` with the right value.
   - The README variant matches the run.
   - The secret and the word "seed" appear nowhere in the export.
   - `source_run` for a secret run is not `sha256(run_id)[:16]`.
   - The four tables are ordered by the bank's numbers as in section 5.

**Bench (verification, not a test).**
- **`scripts/bench.py --tier S --days 90 --seed 7` without a secret, against `main` at the merge base.** Every content hash matches except `persons`. That includes `payments`, `journal`, `postings`, `instruments` and `bank_customers`. The config hash and run folder name also match.
- **The same with a secret.** Every table's hash differs from the no-secret run, the run's invariant checks pass, the bench numbers land in the same range, and the slowdown is recorded.

The brief expected `instruments` and `bank_customers` to change in the no-secret bench. Under approach A they don't, because their keys are unchanged without a secret. This is intended.

**Final steps.** One fresh Opus final review of the branch, with its findings fixed. Then a short results note, `docs/phase1c2_results.md`, where every statement is re-queried. Then the owner is asked before any merge into `main`. Nothing is pushed.

## Left to the builder

- The name and shape of the run-key object.
- The byte encoding of the domain tags.
- Where the run seed lives on `World`.
- The bench flag's name.
- Where the export order is set.
- The exact README sentences, within section 5.
