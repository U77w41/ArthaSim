"""Cheaper flushes and checkpoints: the account tables are rebuilt only when what they are made from changes, each
identifier is made once per world, and a dimension's content hash is read once per file."""
import datetime as dt
import os

import numpy as np
import polars as pl

from arthasim import Config, World
from arthasim.build import identifiers, pipeline
from arthasim.build.identifiers import branch_code, customer_no
from arthasim.build.pipeline import account_frames
from arthasim.build.world import EntityKind
from arthasim.ledger.instruments import InstrumentType as T
from arthasim.life.accounts import open_accounts
from arthasim.store import parquet
from arthasim.store.parquet import Store

ACCOUNT_TABLES = ("accounts", "instruments", "bank_customers")


def S(out, **kw):
    return Config.tier("S", persons=3_000, out_dir=str(out), **kw)


def inodes(path):
    return {t: (path / f"{t}.parquet").stat().st_ino for t in ACCOUNT_TABLES}


def parquet_bytes(frame, tmp_path, name):
    f = tmp_path / f"expected-{name}.parquet"
    frame.write_parquet(f)
    return f.read_bytes()


def assert_tables_match_state(world, tmp_path):
    """Each account table on disk is byte for byte what a full rebuild from the world's state writes."""
    fresh = account_frames(world.state, world.config, world.seed)
    for t in ACCOUNT_TABLES:
        assert (world.path / f"{t}.parquet").read_bytes() == parquet_bytes(fresh[t], tmp_path, t), t


def unbanked(world, n):
    return np.flatnonzero(world.state.person_deposit < 0)[:n]


# -- skipping unchanged tables ---------------------------------------------------------------------------------------

def test_a_flush_with_no_new_accounts_leaves_the_account_tables_in_place(tmp_path):
    w = World.build(S(tmp_path), 7, path=tmp_path / "w", checkpoints=False)
    w.step(1)
    before, n = inodes(w.path), len(w.state.book)
    w.step(2)                                         # 2-3 April: accounts open only on the 1st of a month
    assert len(w.state.book) == n
    assert inodes(w.path) == before
    assert_tables_match_state(w, tmp_path)


def test_the_build_marks_its_account_tables(tmp_path):
    w = World.build(S(tmp_path), 7, path=tmp_path / "w", checkpoints=False)
    before = inodes(w.path)
    w._flush()
    assert inodes(w.path) == before


def test_opening_an_account_rewrites_the_account_tables(tmp_path):
    w = World.build(S(tmp_path), 7, path=tmp_path / "w", checkpoints=False)
    w.step(1)
    before = inodes(w.path)
    who = unbanked(w, 5)
    open_accounts(w.state, w.params, who, np.array([0, 1, 2, 0, 1]), w.date, w.seed)
    w.step(1)
    after = inodes(w.path)
    assert all(after[t] != before[t] for t in ACCOUNT_TABLES)
    assert pl.read_parquet(w.path / "accounts.parquet").height == len(w.state.book)
    assert_tables_match_state(w, tmp_path)


def test_a_banking_flag_changed_without_opening_an_account_rewrites_the_tables(tmp_path):
    """A swapped-in module may change who has UPI without opening an account; the instruments must follow."""
    w = World.build(S(tmp_path), 7, path=tmp_path / "w", checkpoints=False)
    w.step(1)
    k = w.state.population.banking
    who = np.flatnonzero(k.person_has_account & ~k.person_upi)[:5]
    assert who.size == 5
    vpas = lambda: pl.read_parquet(w.path / "instruments.parquet").filter(pl.col("kind") == "VPA").height
    n_vpa = vpas()
    k.person_upi[who] = True
    w.step(1)
    assert vpas() == n_vpa + 5
    assert_tables_match_state(w, tmp_path)


def test_month_ends_with_new_accounts_match_a_full_rebuild(tmp_path):
    w = World.build(S(tmp_path), 7, path=tmp_path / "w")
    n = len(w.state.book)
    w.run("2025-06-02")
    assert len(w.state.book) > n                      # the life course and DBT opened accounts on 1 May and 1 June
    assert_tables_match_state(w, tmp_path)
    for label in ("2025-04", "2025-05"):
        ck = w.path / "checkpoints" / label / "run"
        loaded = World.load(w.path / "checkpoints" / label, path_out=tmp_path / f"l-{label}", checkpoints=False)
        for t in ACCOUNT_TABLES:
            assert pl.read_parquet(ck / f"{t}.parquet").equals(pl.read_parquet(loaded.path / f"{t}.parquet")), t


def test_load_and_fork_rewrite_the_account_tables_from_their_own_state(tmp_path):
    w = World.build(S(tmp_path), 7, path=tmp_path / "w", checkpoints=False)
    w.run("2025-04-30")
    w.save(tmp_path / "ck")
    child = w.fork(path_out=tmp_path / "c")
    loaded = World.load(tmp_path / "ck", path_out=tmp_path / "l")
    for world, source in ((child, w.path), (loaded, tmp_path / "ck" / "run")):
        mine, theirs = inodes(world.path), inodes(source)
        assert all(mine[t] != theirs[t] for t in ACCOUNT_TABLES)
        assert_tables_match_state(world, tmp_path)


# -- the marker ------------------------------------------------------------------------------------------------------

class Recorder:
    """Stands in for an object and records the path of every attribute, key and length read through it."""

    def __init__(self, obj, path, seen):
        self._obj, self._path, self._seen = obj, path, seen

    def __getattr__(self, name):
        return _wrap(getattr(self._obj, name), f"{self._path}.{name}", self._seen)

    def __getitem__(self, key):
        return _wrap(self._obj[key], f"{self._path}[{key!r}]", self._seen)

    def __len__(self):
        self._seen.add(f"len({self._path})")
        return len(self._obj)


def _wrap(value, path, seen):
    if isinstance(value, dict) or (hasattr(value, "__dict__") and not isinstance(value, (np.ndarray, type))):
        return Recorder(value, path, seen)
    seen.add(path)
    return value


def test_the_marker_reads_everything_the_account_tables_are_made_from(tmp_path):
    w = World.build(S(tmp_path), 7, path=tmp_path / "w", checkpoints=False)
    by_frames, by_marker = set(), set()
    account_frames(Recorder(w.state, "state", by_frames), w.config, w.seed)
    pipeline.account_marker(Recorder(w.state, "state", by_marker))
    assert by_frames and by_frames <= by_marker, sorted(by_frames - by_marker)


def test_the_marker_changes_with_any_input(tmp_path):
    w = World.build(S(tmp_path), 7, path=tmp_path / "w", checkpoints=False)
    s, k = w.state, w.state.population.banking
    m = pipeline.account_marker(s)
    assert pipeline.account_marker(s) == m
    for arr, i in ((k.person_has_card, 0), (s.bank_of_account, 0), (s.book.holder, 3),
                   (s.population.tokens["device"], 1), (s.population.households.locality, 2)):
        old = arr[i]
        arr[i] = "x" if arr.dtype == object else (not old if arr.dtype == bool else old + 1)
        assert pipeline.account_marker(s) != m
        arr[i] = old
        assert pipeline.account_marker(s) == m


def test_the_marker_tells_apart_string_lists_that_join_alike():
    enc = pipeline._object_bytes
    assert enc(["a\x00b", "c"]) != enc(["a", "b\x00c"])
    assert enc(["ab"]) != enc(["a", "b"]) and enc([]) != enc([""])
    assert enc(["['a']"]) != enc(["a"]) and enc(["a", None]) != enc(["a", "None"])


# -- identifiers made once -------------------------------------------------------------------------------------------

def _count_keyed_bits(monkeypatch):
    made = []
    real = identifiers.keyed_bits

    def counting(seed, stream, ids):
        out = real(seed, stream, ids)
        made.append(len(out))
        return out
    monkeypatch.setattr(identifiers, "keyed_bits", counting)
    return made


def _assert_same(a, b, tmp_path):
    for t in ACCOUNT_TABLES:
        assert a[t].equals(b[t]), t
        assert parquet_bytes(a[t], tmp_path, "a") == parquet_bytes(b[t], tmp_path, "b"), t


def test_identifiers_made_once_give_the_same_tables(tmp_path, monkeypatch):
    w = World.build(S(tmp_path), 7, path=tmp_path / "w", checkpoints=False)
    memo = identifiers.IdentifierMemo()
    _assert_same(account_frames(w.state, w.config, w.seed, memo), account_frames(w.state, w.config, w.seed),
                 tmp_path)
    who = unbanked(w, 7)
    open_accounts(w.state, w.params, who, np.array([0, 1, 2, 3, 0, 1, 2]), dt.date(2025, 5, 1), w.seed)
    made = _count_keyed_bits(monkeypatch)
    warm = account_frames(w.state, w.config, w.seed, memo)
    assert 0 < sum(made) <= 7 * 3                      # account number, customer number and VPA: new accounts only
    monkeypatch.undo()
    _assert_same(warm, account_frames(w.state, w.config, w.seed), tmp_path)


def test_a_memo_made_for_another_seed_is_not_used(tmp_path):
    w = World.build(S(tmp_path), 7, path=tmp_path / "w", checkpoints=False)
    memo = identifiers.IdentifierMemo()
    account_frames(w.state, w.config, w.seed, memo)
    _assert_same(account_frames(w.state, w.config, 8, memo), account_frames(w.state, w.config, 8), tmp_path)


def test_a_checkpoint_holds_no_identifier_memo(tmp_path):
    w = World.build(S(tmp_path), 7, path=tmp_path / "w", checkpoints=False)
    w.step(1)
    assert not any(isinstance(v, identifiers.IdentifierMemo) for v in w.__getstate__().values())


def _bank_customers_by_rows(state, seed):
    """The bank-customer table as plan 1d-2 made it, with a two-column `np.unique`."""
    book = state.book
    deposits = np.flatnonzero(book.type == T.DEPOSIT)
    holder, bank = book.holder[deposits], state.bank_of_account[deposits]
    kinds = [EntityKind.PERSON, EntityKind.EMPLOYER, EntityKind.MERCHANT, EntityKind.BILLER]
    keep = (bank < len(state.bank_codes) - 1) & np.isin(state.kind[holder], kinds)
    pairs = np.unique(np.stack([bank[keep], holder[keep]], axis=1), axis=0)
    bank, entity = pairs[:, 0], pairs[:, 1]
    codes = state.bank_codes[bank]
    return pl.DataFrame({"bank_code": pl.Series(codes.tolist(), dtype=pl.String), "entity_id": entity,
                         "customer_no": pl.Series(customer_no(seed, entity, bank, codes).tolist(), dtype=pl.String)},
                        schema={"bank_code": pl.String, "entity_id": pl.Int64, "customer_no": pl.String})


def test_bank_customers_are_the_unique_bank_entity_pairs(tmp_path):
    w = World.build(S(tmp_path), 7, path=tmp_path / "w", checkpoints=False)
    who = unbanked(w, 4)
    open_accounts(w.state, w.params, who, np.array([3, 1, 2, 0]), dt.date(2025, 5, 1), w.seed)
    want = _bank_customers_by_rows(w.state, w.seed)
    assert pipeline._bank_customers(w.state, w.seed).equals(want)
    assert pipeline._bank_customers(w.state, w.seed, identifiers.IdentifierMemo()).equals(want)


def test_branch_code_matches_the_per_row_format():
    rng = np.random.default_rng(0)
    b, d, loc = rng.integers(0, 13, 5_000), rng.integers(0, 3, 5_000), rng.integers(0, 120, 5_000)
    b[:3], d[:3], loc[:3] = [99, 0, 7], [0, 41, 2], [12_345, 0, 9_999]
    want = [f"SY{x + 1:02d}0{y:02d}{z:04d}" for x, y, z in zip(b.tolist(), d.tolist(), loc.tolist())]
    assert branch_code(b, d, loc).tolist() == want
    assert branch_code(b.astype(np.int32), d.astype(np.int8), loc).tolist() == want
    assert branch_code(np.empty(0, dtype=np.int64), [], []).tolist() == []
    big = [2**40, 3], [2**30, 1], [2**33, 5]                      # one int64 per branch would overflow
    assert branch_code(*big).tolist() == [f"SY{x + 1:02d}0{y:02d}{z:04d}" for x, y, z in zip(*big)]


# -- dimension hashes read once --------------------------------------------------------------------------------------

def _count_content_hash(monkeypatch):
    read = []
    real = parquet.content_hash

    def counting(path, name, fact=None):
        read.append(name)
        return real(path, name, fact)
    monkeypatch.setattr(parquet, "content_hash", counting)
    return read


def test_store_remembers_the_marker_of_each_dimension_it_wrote(tmp_path):
    store = Store(tmp_path)
    frame = pl.DataFrame({"a": [1, 2]})
    assert store.marker("geo") is None
    store.write_dimension("geo", frame, marker=b"m1")
    assert store.marker("geo") == b"m1"
    store.write_dimension("geo", frame)
    assert store.marker("geo") is None
    store.write_dimension("geo", frame, marker=b"m2")
    pl.DataFrame({"a": [9]}).write_parquet(tmp_path / "other.parquet")
    os.replace(tmp_path / "other.parquet", tmp_path / "geo.parquet")       # replaced from outside the store
    assert store.marker("geo") is None
    store.write_dimension("geo", frame, marker=b"m3")
    (tmp_path / "geo.parquet").unlink()
    assert store.marker("geo") is None


def test_a_dimension_hash_is_read_once_per_file(tmp_path, monkeypatch):
    store = Store(tmp_path)
    store.write_dimension("geo", pl.DataFrame({"a": [1, 2]}))
    want = parquet.content_hash(tmp_path, "geo")
    read = _count_content_hash(monkeypatch)
    first = store.dimension_hash("geo")
    assert store.dimension_hash("geo") == first == want
    assert read == ["geo"]
    store.write_dimension("geo", pl.DataFrame({"a": [1, 3]}))
    second = store.dimension_hash("geo")
    assert second != first and read == ["geo", "geo"]
    monkeypatch.undo()
    assert second == parquet.content_hash(tmp_path, "geo")


def test_a_flush_with_nothing_new_reads_only_the_rewritten_metadata(tmp_path, monkeypatch):
    w = World.build(S(tmp_path), 7, path=tmp_path / "w", checkpoints=False)
    w.run("2025-04-29")
    read = _count_content_hash(monkeypatch)
    w.step(1)                                               # 30 April, the month's last day
    assert sorted(read) == ["interventions_log", "macro_paths"]
    read.clear()
    w.save(tmp_path / "ck")                                 # its flush, then the checkpoint's own hashes
    assert sorted(read) == ["interventions_log", "macro_paths"]
    monkeypatch.undo()
    hashes = w._content_hashes()
    assert hashes == {t: parquet.content_hash(w.path, t) for t in hashes}
