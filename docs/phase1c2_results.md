# Safe partner exports: results

Measured on 23 November 2026 at tier S (100,000 adults), seed 7, from 1 April 2025, over 90 days. The machine was an Apple M5 with Python 3.12, numba 0.68.1, polars 2.1.0 and duckdb 2.0.1, with `PYTHONPATH=src` from a scratch virtual environment.

- **Before:** `main` at `b188ed0` (plan 1c), exported with `git archive`.
- **After:** this branch.

Spec: `docs/superpowers/specs/2026-11-23-safe-partner-exports-design.md`. Plan: `docs/superpowers/plans/2026-11-23-arthasim-safe-partner-exports.md`.

Commands:
- `python scripts/bench.py --tier S --days 90 --seed 7` for the baseline and the branch;
- the same with `--release`, with `ARTHASIM_RELEASE_SECRET` set to a fresh `secrets.token_hex(32)`;
- a bank export of SYNB01, the largest bank, from each run.

Every figure below was re-queried from those runs.

## What changed

- **`Config.release_secret`.** An optional field: at least 32 hex digits, made by `arthasim.new_release_secret()`. When set:
  - every random draw comes from SipHash-2-4 under a 128-bit key derived from the secret;
  - every identifier is keyed with it: customer and account numbers, VPAs, terminals, `pan_like`, and the device, card, mobile and Aadhaar tokens;
  - the export's `source_run` label is keyed with it.

  The secret is never written. `to_yaml` leaves it out, `repr` hides it, and the run folder and exports hold neither the secret nor any key derived from it; tests check every file's bytes. The run manifest and the export manifest say `release_secret: true` or `false`.
- **`pan_like`** is now a keyed Feistel permutation (22 bits, ten rounds, cycle-walked) of the person's index over 2,600,000 slots, in the same `SY{digit}P{initial}{4 digits}{letter}` shape. Without a secret it is keyed from the seed.
- **The bank view's `customers`** gains `uid_token` for a customer whose account at that bank has received a successful APBS credit or made an AePS withdrawal by the view's date. It is null otherwise.
- **Bank exports** list `customers` by `customer_no`, `accounts` and `instruments` by `account_no`, and `balances_monthly` by month then `account_no`. The Python views keep simulator order.

## Without a secret, only `persons` changes

The content hashes of the branch's 90-day run match `main`'s for 17 of 18 tables:
- **Equal:** `payments`, `journal`, `postings`, `instruments`, `bank_customers`, `accounts`, `balances_monthly` and every truth table.
- **Different:** `persons`, because `pan_like` changed.

Three branch runs gave identical hashes. Both runs make 15,282,932 payment attempts.

The config hash is unchanged. For the baseline's settings, the branch computes `08112731`, the same folder suffix as `main`. The unit tests also pin `Config.tier("S").hash()` and `Config.tier("XS").hash()` to their values on `main`.

## With a secret, a different world of the same kind

Every table's hash differs from the run without a secret except `geo`, which is built from the config with no random draws. The two worlds look alike in aggregate:

| | Without a secret | With a secret |
| :--- | ---: | ---: |
| Payment attempts | 15,282,932 | 15,302,535 |
| Success share | 95.65% | 95.60% |
| Declined for funds | 4.13% | 4.18% |
| Payments per person per day | 1.698 | 1.700 |
| Unbanked share at the end | 8.46% | 8.36% |
| Accounts | 214,395 | 214,838 |
| Old-age pension credits | 4,742 | 4,789 |
| Women's transfer credits | 11,945 | 12,245 |
| Largest margin error of the build (max L1) | 0.00031 | 0.00061 |

PM-Kisan pays no credits in either 90-day window: its first instalment date in the registry is 2 August 2025.

## Runtime

The first baseline (`main`, 10.7 s of simulation) was measured on a quieter machine. So `main`, the branch without a secret and the branch with one were then run in turn, twice:

| | Run 1 (s) | Run 2 (s) |
| :--- | ---: | ---: |
| `main` | 20.45 | 19.36 |
| Branch, no secret | 19.46 | 19.30 |
| Branch, with a secret | 25.91 | 25.69 |

- **Without a secret,** the branch runs as fast as `main`.
- **With a secret,** simulation takes about 33% longer and the whole bench, build included, about 30% longer. The spec estimated 25–30%.
- **Why.** In a micro-benchmark of 5 million uniform draws (best of seven), SipHash-2-4 makes 42 million draws a second against 379 million for the original mixer: about 9 times slower. Draws are a small share of a run, so the run slows by a third. Three alternating runs of each gave the same picture: median simulation 19.77 s against 26.56 s (+34%), build 1.69 s against 1.79 s (+6%).

## The bank export

SYNB01, from each run:

| | Without a secret | With a secret |
| :--- | :--- | :--- |
| Customers | 25,933 | 24,323 |
| With `uid_token` | 6,725 | 6,243 |
| `release_secret` in the manifest | false | true |
| `source_run` | SHA-256 of the run name | keyed with the secret |
| README | "not anonymised", not for release | names the secret and SipHash-2-4; not a formal anonymity guarantee |
| Rows ordered by `customer_no` and `account_no` | yes | yes |
| Simulator ID columns | none | none |
| "seed" in the manifest or README | no | no |

Each customer's `pan_like` is unique: 13,004 and 11,282 customers hold one.

## Who carries an Aadhaar token

The table counts (bank, customer) pairs across all banks in the run without a secret, over 90 days.

| Reason the bank holds the link | Pairs |
| :--- | ---: |
| APBS credit only | 4,331 |
| AePS withdrawal only | 21,578 |
| Both | 1,450 |
| **With a token** | **27,359** |
| All customer pairs | 111,862 |

That is 24% of customer pairs, or 25% of the 108,715 person pairs. AePS users dominate, because every banked person without a debit card withdraws through AePS.

The rule follows the RBI KYC Master Direction, 2016, updated as on 14 August 2025, read word for word on rbi.org.in:
- **Paragraph 16(a)** has a bank obtain the Aadhaar number from an individual in two cases. The first is a person "desirous of receiving any benefit or subsidy" under a scheme notified under section 7 of the Aadhaar Act. The second is a person who decides to submit it "voluntarily to a bank" (or to an RE notified under section 11A of the PML Act).
- **Explanation 1** requires the number to be redacted "where the authentication of Aadhaar number is not required".

The model has no voluntary e-KYC, so the token marks only the two cases that need the link. The plan 1c spec's line "No Aadhaar token" in the `customers` row is superseded.

## Tests

- **Fast suite:** 333 passed, against 299 on `main`.
- **Slow gates:** all 6 (plans 0, 1a, 1b-1, 1b-2, 1c and 1d-1) pass in 289 s.
- **Notable new tests:**
  - the keyed generator reproduces the published SipHash-2-4 vectors;
  - integer-seed draws are pinned to `main`'s values;
  - `pan_like` is a full permutation of its 2,600,000 slots and unique for 1,000,000 persons;
  - no file in a secret run's folder or export contains the secret or a derived key;
  - the same secret rebuilds the same run byte for byte;
  - tokens recomputed without the secret match none of the run's.

## Review

A fresh Opus reviewer read the whole branch, ran the fast suite and the slow gates, and checked the work independently:
- the SipHash kernel against its own reference on 200 random keys, with no mismatches;
- the Feistel permutation;
- the byte identity of runs without a secret;
- the `uid_token` counts, recomputed in Polars;
- the export order at tier S.

Verdict: "with fixes". There was no critical finding.

**Fixed, each with a test:**
- **A pydantic validation error printed the release secret.** A malformed secret showed in full, and a valid one leaked its last 22 digits through any other config error. `Config` now hides inputs in errors.
- **The README of an export from a run made before this change** said `pan_like` was keyed. It now says what such a run's `pan_like` is: the person's place in the population.
- **The export leak test** now also checks that no key derived from the secret appears in an export, as this note claims.

**Deferred minors:**
- a secret over 128 hex digits fails late, with a BLAKE2b error;
- one validation case is not tested on its own;
- stale `seed: int` annotations;
- no domain tag on the source label key.

## Limits

- **What a release export still shows.** It shows what the bank would know: birth year, sex, district, locality, amounts and times. The secret protects the link back to the simulator and its truth, not these attributes.
- **`ref`.** It is still the payment's sequence number. Once the run cannot be re-created, it shows only order and volume (plan 1c ruling).
- **Exports of runs without a secret** are still allowed, for internal use. Their README says they are not for release.
- **Release runs are slower:** about a third longer to simulate.
- **A config reloaded from `to_yaml`** has no secret. Its runs say `release_secret: false` and get a different folder.
