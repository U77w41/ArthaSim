"""The registry's sources (plan 1e): targets and holdouts cite a document, verified rows say where in it, and no
value carried from `main` at 29dd4a6 changes."""
import re

from arthasim import ParamRegistry
from helpers import P

# Rows plan 1e adds. Everything else was in the registry at 29dd4a6.
NEW_IDS = (
    "labour.lfpr.15plus", "labour.wpr.15plus", "labour.ur.15plus", "labour.ur.by_area", "labour.ur.educated",
    "labour.ur.graduate_15_29", "labour.share.regular_salaried", "labour.share.self_employed",
    "pay.regular_monthly", "pay.casual_daily", "pay.self_employed_monthly", "pay.increment.corporate_mean",
    "pay.attrition.annual", "pay.switch_jump", "pay.skill_premium",
    "consumption.mpce", "consumption.gini", "consumption.food_share", "consumption.hces_uprate",
    "wealth.household_mean",
    "inclusion.pmjdy.operative_share", "inclusion.pmjdy.zero_balance_share", "inclusion.pmjdy.average_balance",
    "inclusion.debit_card_ownership",
    "population.adults_18plus", "population.urban_share",
    "upi.volume.fy26", "upi.value.fy26", "upi.volume.monthly", "upi.value.monthly", "upi.p2m.share",
    "upi.p2m.share_under_500", "upi.p2p.share_under_500", "upi.month_start_spike", "upi.lite.limits",
    "upi.limit.listed_categories_paise", "rtgs.minimum_paise", "imps.volume.fy26", "aeps.volume.monthly",
    "cards.debit.volume_monthly", "cards.debit.value_monthly", "atm.withdrawal.volume_monthly",
    "atm.withdrawal.value_monthly",
    "sip.inflow.monthly", "cc_on_upi.value.monthly", "credit.classification.buckets", "fraud.loss.cy24",
    "fraud.actor_share", "festival.diwali.upi_uplift", "dbt.cashout_lag",
)
# ParamRegistry.version() of params/registry.yaml at main 29dd4a6 (134 rows).
MAIN_VERSION = "637a9eb84698c9d99eb6e53f95a927ac7820ce3a5926cb7dab8e2a31ad9c9e3e"
WHERE = re.compile(r"\b(table|statement|section|para|paragraph|item|clause|page|p\.|annex|figure|fig|question|"
                   r"schedule|rule|q\d)", re.IGNORECASE)


def _rows():
    return {r["id"]: r for r in P.table().iter_rows(named=True)}


def test_target_and_holdout_rows_cite_a_document():
    bad = [i for i, r in _rows().items() if r["role"] in ("target", "holdout")
           and "http" not in r["source"] and "docs/sources/" not in r["source"]]
    assert not bad


def test_verified_rows_name_where():
    """A verified row names the table, section or page, or points to the source notes that do."""
    bad = [i for i, r in _rows().items() if r["status"] == "verified"
           and not WHERE.search(r["source"]) and "docs/sources/" not in r["source"]]
    assert not bad


def test_new_rows_present_and_counted():
    rows = _rows()
    assert not [i for i in NEW_IDS if i not in rows]
    assert len(rows) == 134 + len(NEW_IDS)


def test_no_value_carried_from_main_changed():
    rows = _rows()
    old = ParamRegistry({i: dict(r, value=P.get(i)) for i, r in rows.items() if i not in NEW_IDS})
    assert old.version() == MAIN_VERSION


def test_core_target_values():
    assert P.get("pay.regular_monthly") == {"rural": 17841, "urban": 26247}
    assert P.get("pay.casual_daily") == {"rural": 433, "urban": 549}
    assert P.get("pay.self_employed_monthly") == {"rural": 12266, "urban": 23012}
    assert P.get("consumption.mpce") == {"rural": 4122, "urban": 6996}
    assert P.get("consumption.gini") == {"rural": 0.237, "urban": 0.284}
    assert P.get("upi.p2m.share") == {"volume": 0.63, "value": 0.29}
    assert P.get("upi.p2m.share_under_500") == 0.86 and P.get("upi.p2p.share_under_500") == 0.59
    assert P.get("dbt.cashout_lag") == {"d0_5": 0.179, "d6_15": 0.234, "d16_30": 0.173}
    assert P.get("inclusion.pmjdy.average_balance") == 4808
    assert P.get("upi.volume.monthly")["2025-10"] == 20700.921
    assert len(P.get("atm.withdrawal.volume_monthly")) == 12


def test_roles_and_statuses():
    rows = _rows()
    assert rows["festival.diwali.upi_uplift"]["role"] == rows["dbt.cashout_lag"]["role"] == "holdout"
    assert rows["consumption.hces_uprate"]["status"] == "assumption"      # derived by CPI uprating
    assert rows["population.adults_18plus"]["status"] == "assumption"     # derived from five-year bands
    assert rows["pay.regular_monthly"]["status"] == "verified"
