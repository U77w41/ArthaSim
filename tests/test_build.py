import re
import numpy as np
import pathlib
from arthasim import Config, ParamRegistry
from arthasim.build.world import build_state
from arthasim.ledger.invariants import check_day
import polars as pl

P = ParamRegistry.load(pathlib.Path(__file__).parents[1] / "params" / "registry.yaml")
EMPTY_J = pl.DataFrame(schema={c: pl.Int64 for c in ["journal_id", "ts", "kind", "flow_type", "payment_id"]})
EMPTY_P = pl.DataFrame(schema={c: pl.Int64 for c in ["journal_id", "line_no", "account_id", "delta_paise", "balance_after_paise"]})


def invariants_hold(s):
    check_day(s.book, EMPTY_J, EMPTY_P, s.posted_total, list(s.bank_ids), s.equity, s.currency_issued, s.sector)


def test_counts_accounts_and_balance_sheets():
    s = build_state(Config.tier("XS"), P, seed=7)
    assert (len(s.person_ids), len(s.employer_ids), len(s.merchant_ids)) == (10_000, 100, 300)
    assert list(s.bank_codes) == ["SYNB01", "SYNB02", "SYNB03", "SYNX00"]
    assert (s.book.balance[s.person_deposit] > 0).all() and (s.book.balance[s.person_cash] == 100_000).all()
    assert abs((s.person_employer >= 0).mean() - 0.6) < 0.02
    assert abs(np.bincount(s.person_bank, minlength=3)[:3] / 10_000 - np.array([0.5, 0.3, 0.2])).max() < 0.02
    assert set(np.unique(s.employer_payday)) <= set(range(1, 29))
    invariants_hold(s)


def test_identifiers_cannot_be_real():
    s = build_state(Config.tier("XS"), P, seed=7)
    real_pan = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
    assert not any(real_pan.match(p) for p in s.pan_like)
    assert all(re.match(r"^SY[0-9]P[A-Z][0-9]{4}[A-Z]$", p) for p in s.pan_like)
    assert len(set(s.pan_like)) == len(s.pan_like)


def test_seed_determinism():
    a, b = (build_state(Config.tier("XS", persons=500), P, seed=7) for _ in range(2))
    c = build_state(Config.tier("XS", persons=500), P, seed=8)
    assert np.array_equal(a.book.balance, b.book.balance) and list(a.pan_like) == list(b.pan_like)
    assert not np.array_equal(a.book.balance, c.book.balance)


def test_degenerate_configs():
    s = build_state(Config.tier("XS", persons=200, banks=1), P, seed=7)
    assert list(s.bank_codes) == ["SYNB01", "SYNX00"]
    invariants_hold(s)
    s = build_state(Config.tier("XS", persons=200, employers=0), P, seed=7)
    assert (s.person_employer == -1).all() and len(s.employer_ids) == 0
    invariants_hold(s)
