"""Hard checks re-derived from a stored run (plan 1e): the ledger invariants, same seed and same output, and no
synthetic identifier in a real format. Each passes on a clean run and fails on a copy damaged one way."""
import functools
import shutil
import tempfile
from pathlib import Path

import polars as pl

from arthasim import Config, Run, World, checks
from arthasim.build.identifiers import luhn
from run_fixture import RELEASE_SECRET, secret_run


@functools.lru_cache(maxsize=None)
def clean():
    """800 persons, 1 April to 10 May 2025: April closed, May open."""
    out = tempfile.mkdtemp(prefix="arthasim-checks-")
    return World.build(Config.tier("S", persons=800, out_dir=out), seed=5, checkpoints=False).run("2025-05-10")


def copy(tmp_path) -> Path:
    dest = tmp_path / "run"
    shutil.copytree(clean().path, dest)
    return dest


def status(rows, component=None):
    return {r["component"]: r["status"] for r in rows} if component is None else \
        next(r["status"] for r in rows if r["component"] == component)


def rewrite(path: Path, table: str, month: str | None, fn):
    """Apply `fn` to one file of a table (a fact table's first part of `month`, or a dimension table)."""
    f = (path / table / f"month={month}" / "part-0.parquet") if month else path / f"{table}.parquet"
    fn(pl.read_parquet(f)).write_parquet(f)


def test_ledger_passes_on_a_clean_run():
    got = status(checks.ledger(clean()))
    assert got == {"shapes": "pass", "stock_flow": "pass", "non_negative": "pass", "bank_balance_sheets": "pass",
                   "cash_conservation": "pass", "flow_matrix": "skipped"}


def test_ledger_catches_a_changed_posting(tmp_path):
    path = copy(tmp_path)
    rewrite(path, "postings", "2025-04", lambda f: f.with_columns(
        pl.when(pl.int_range(pl.len()) == 7).then(pl.col("delta_paise") + 1).otherwise(pl.col("delta_paise"))
        .alias("delta_paise")))
    got = status(checks.ledger(Run.open(path)))
    assert got["shapes"] == "fail" or got["stock_flow"] == "fail"


def test_ledger_catches_a_changed_month_end_balance(tmp_path):
    path = copy(tmp_path)
    rewrite(path, "balances_monthly", "2025-04", lambda f: f.with_columns(
        pl.when(pl.col("account_id") == 3).then(pl.col("balance_paise") + 1).otherwise(pl.col("balance_paise"))
        .alias("balance_paise")))
    assert status(checks.ledger(Run.open(path)), "stock_flow") == "fail"


def test_ledger_catches_a_drained_vault(tmp_path):
    path = copy(tmp_path)
    acc = pl.read_parquet(path / "accounts.parquet")
    vault = acc.filter(pl.col("subtype") == "vault")["account_id"][0]
    rewrite(path, "balances_monthly", "2025-04", lambda f: f.with_columns(
        pl.when(pl.col("account_id") == vault).then(pl.col("balance_paise") - 100).otherwise(pl.col("balance_paise"))
        .alias("balance_paise")))
    got = status(checks.ledger(Run.open(path)))
    assert got["bank_balance_sheets"] == "fail" and got["cash_conservation"] == "fail"


def test_ledger_catches_negative_money(tmp_path):
    path = copy(tmp_path)
    acc = pl.read_parquet(path / "accounts.parquet")
    deposits = acc.filter(pl.col("type") == "DEPOSIT")["account_id"].to_list()
    rewrite(path, "postings", "2025-04", lambda f: f.with_columns(
        pl.when((pl.col("account_id").is_in(deposits)) & (pl.int_range(pl.len()) == f.with_row_index()
                .filter(pl.col("account_id").is_in(deposits))["index"][0]))
        .then(-1).otherwise(pl.col("balance_after_paise")).alias("balance_after_paise")))
    assert status(checks.ledger(Run.open(path)), "non_negative") == "fail"


def test_identifiers_pass_and_catch_real_formats(tmp_path):
    assert set(status(checks.identifiers(clean())).values()) == {"pass"}
    path = copy(tmp_path)
    rewrite(path, "persons", None, lambda f: f.with_columns(
        pl.when(pl.int_range(pl.len()) == 0).then(pl.lit("ABCPE1234F")).otherwise(pl.col("pan_like")).alias("pan_like")))
    rewrite(path, "instruments", None, lambda f: f.with_columns(
        pl.when((pl.col("kind") == "VPA") & (pl.int_range(pl.len()) == f.with_row_index()
                .filter(pl.col("kind") == "VPA")["index"][0]))
        .then(pl.lit("someone@okaxis")).otherwise(pl.col("value")).alias("value")))
    got = status(checks.identifiers(Run.open(path)))
    assert got["pan"] == "fail" and got["vpa"] == "fail" and got["aadhaar"] == "pass"


def test_luhn():
    assert luhn("4539578763621486") and not luhn("4539578763621487")


def test_determinism_passes_on_a_clean_run_and_catches_a_changed_table(tmp_path):
    assert set(status(checks.determinism(clean())).values()) == {"pass"}
    path = copy(tmp_path)
    rewrite(path, "persons", None, lambda f: f.with_columns(
        pl.when(pl.int_range(pl.len()) == 0).then(pl.col("birth_year") + 1).otherwise(pl.col("birth_year"))
        .alias("birth_year")))
    rewrite(path, "payments", "2025-04", lambda f: f.with_columns(
        pl.when(pl.int_range(pl.len()) == 0).then(pl.col("amount_paise") + 1).otherwise(pl.col("amount_paise"))
        .alias("amount_paise")))
    got = status(checks.determinism(Run.open(path)))
    assert got == {"first_month_facts": "fail", "build_dimensions": "fail"}


def test_determinism_skipped_without_the_secret_and_for_a_fork(tmp_path):
    rows = checks.determinism(secret_run())
    assert {r["status"] for r in rows} == {"skipped"} and "release secret" in rows[0]["detail"]
    assert set(status(checks.determinism(secret_run(), release_secret=RELEASE_SECRET)).values()) == {"pass"}
    world = World.build(Config.tier("S", persons=300, out_dir=str(tmp_path)), seed=2, checkpoints=False)
    world.run("2025-04-30")
    fork = world.fork(tmp_path / "fork")
    rows = checks.determinism(fork.run("2025-05-05"))
    assert {r["status"] for r in rows} == {"skipped"} and "fork" in rows[0]["detail"]


def test_ledger_catches_a_missing_month_end_row(tmp_path):
    path = copy(tmp_path)
    rewrite(path, "balances_monthly", "2025-04", lambda f: f.filter(pl.col("account_id") != 3))
    assert status(checks.ledger(Run.open(path)), "stock_flow") == "fail"


def test_ledger_reports_an_unknown_account_instead_of_raising(tmp_path):
    path = copy(tmp_path)
    rewrite(path, "postings", "2025-04", lambda f: f.with_columns(
        pl.when(pl.int_range(pl.len()) == 5).then(10**9).otherwise(pl.col("account_id")).alias("account_id")))
    got = status(checks.ledger(Run.open(path)))
    assert got["shapes"] == "fail"


def test_ledger_checks_postings_of_the_open_month(tmp_path):
    path = copy(tmp_path)                       # May is the run's last, open month: no month-end balance yet
    rewrite(path, "postings", "2025-05", lambda f: f.with_columns(
        pl.when(pl.int_range(pl.len()) == 7).then(pl.col("balance_after_paise") + 1)
        .otherwise(pl.col("balance_after_paise")).alias("balance_after_paise")))
    assert status(checks.ledger(Run.open(path)), "stock_flow") == "fail"


def test_an_all_digit_account_number_fails_whatever_its_length(tmp_path):
    path = copy(tmp_path)
    rewrite(path, "bank_customers", None, lambda f: f.with_columns(
        pl.when(pl.int_range(pl.len()) == 0).then(pl.lit("1234")).otherwise(pl.col("customer_no")).alias("customer_no")))
    assert status(checks.identifiers(Run.open(path)), "account_no") == "fail"


def test_registry_version_check(tmp_path):
    assert status(checks.registry(clean()), "version") == "pass"
    path = copy(tmp_path)
    manifest = path / "run_manifest.json"
    manifest.write_text(manifest.read_text().replace(clean().manifest["registry_version"], "0" * 64))
    row = checks.registry(Run.open(path))[0]
    assert row["status"] == "fail" and "changed" in row["detail"]


def test_determinism_skipped_for_an_intervention_in_the_first_month(tmp_path):
    from arthasim.interventions import ParamOverride
    world = World.build(Config.tier("S", persons=300, out_dir=str(tmp_path)), seed=2, checkpoints=False)
    world.apply(ParamOverride("consumption.spend_share", 0.7, "2025-04-10"))
    rows = checks.determinism(world.run("2025-05-02"))
    assert {r["status"] for r in rows} == {"skipped"} and "intervention" in rows[0]["detail"]
