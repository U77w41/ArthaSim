"""Banks, account ownership and opening balances."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from arthasim.build import categories as c
from arthasim.build.attributes import Attributes
from arthasim.build.marginals import DistrictMarginals
from arthasim.build.orgs import Orgs
from arthasim.build.population import Persons
from arthasim.config import Config
from arthasim.engine import rng
from arthasim.params import ParamRegistry


@dataclass
class Banking:
    bank_codes: np.ndarray               # SYNB01.., then the boundary bank SYNX00
    bank_archetype: np.ndarray
    nbfc_codes: np.ndarray
    person_has_account: np.ndarray
    person_primary_bank: np.ndarray      # bank index, -1 if none
    person_second_bank: np.ndarray       # bank index, -1 if none
    person_basic_account: np.ndarray
    person_has_pan: np.ndarray
    person_upi: np.ndarray
    person_has_card: np.ndarray
    person_has_mobile: np.ndarray
    opening_deposit: np.ndarray
    opening_second: np.ndarray
    opening_cash: np.ndarray
    employer_bank: np.ndarray
    merchant_bank: np.ndarray


def pick_banks(u: np.ndarray, is_metro: np.ndarray, params: ParamRegistry, n_banks: int) -> np.ndarray:
    """Bank index for each uniform draw, by the bank archetypes' metro or rural customer shares."""
    rows = params.get("bank.archetypes")[:n_banks]
    cum = {kind: np.cumsum(np.array([r[col] for r in rows]) / sum(r[col] for r in rows))
           for kind, col in (("metro", 1), ("rural", 2))}
    out = np.where(is_metro, np.searchsorted(cum["metro"], u, side="right"),
                   np.searchsorted(cum["rural"], u, side="right"))
    return np.minimum(out, n_banks - 1).astype(np.int64)


def assign_banking(persons: Persons, attributes: Attributes, orgs: Orgs, districts: Sequence[DistrictMarginals],
                   config: Config, params: ParamRegistry, seed: int) -> Banking:
    n, B = len(persons), config.banks
    ids = np.arange(n, dtype=np.int64)
    S = rng.stream_id
    rows = params.get("bank.archetypes")[:B]
    kinds = np.array([d.kind for d in districts])
    is_metro = kinds[persons.district] == "metro"

    def u(stream: str, entity: np.ndarray = ids) -> np.ndarray:
        return rng.uniform(seed, S(stream), entity, 0)

    def pick_bank(stream: str, entity: np.ndarray, metro: np.ndarray) -> np.ndarray:
        return pick_banks(u(stream, entity), metro, params, B)

    def by_kind(param: str) -> np.ndarray:
        value = params.get(param)
        return np.where(is_metro, value["metro"], value["rural"])

    employer_bank = pick_bank("bank.employer", np.arange(orgs.employer_district.size),
                              kinds[orgs.employer_district] == "metro")
    merchant_bank = pick_bank("bank.merchant", np.arange(orgs.merchant_district.size),
                              kinds[orgs.merchant_district] == "metro")

    salaried = persons.life_stage == c.SALARIED
    earning = np.isin(persons.life_stage, c.EARNING)
    income = attributes.monthly_income_paise
    has_account = salaried | (u("bank.has") < by_kind("inclusion.account_ownership"))

    primary = pick_bank("bank.primary", ids, is_metro)
    at_employer = salaried & (u("bank.at_employer") < params.get("inclusion.salary_account_at_employer_bank"))
    primary[at_employer] = employer_bank[orgs.person_employer[at_employer]]
    primary[~has_account] = -1

    has_second = has_account & (u("bank.second") < by_kind("inclusion.second_account_share")) & (B > 1)
    second = pick_bank("bank.second_pick", ids, is_metro)
    second = np.where(second == primary, (second + 1) % B, second)
    second[~has_second] = -1

    pan = params.get("identity.pan_share")
    has_pan = u("bank.pan") < np.where(salaried, pan["salaried"], np.where(earning, pan["other_earning"], pan["non_earning"]))
    has_mobile = u("bank.mobile") < params.get("inclusion.mobile_share")
    upi = has_account & has_mobile & (attributes.digital_literacy > params.get("attr.digital.upi_threshold"))
    has_card = has_account & (u("bank.card") < params.get("inclusion.debit_card_share"))

    median = np.maximum(params.get("open.deposit_floor_paise"), params.get("open.deposit_months_of_income") * income)
    deposit = np.maximum(100, np.rint(median * rng.lognormal(seed, S("bank.deposit"), ids, 0, 1.0,
                                                             params.get("open.deposit_sigma")))).astype(np.int64)
    cash = np.maximum(100, np.rint(rng.lognormal(seed, S("bank.cash"), ids, 0, params.get("open.cash_median_paise"),
                                                 params.get("open.cash_sigma")))).astype(np.int64)
    return Banking(
        bank_codes=np.array([f"SYNB{b + 1:02d}" for b in range(B)] + ["SYNX00"], dtype=object),
        bank_archetype=np.array([r[0] for r in rows], dtype=object),
        nbfc_codes=np.array([f"SYNN{i + 1:02d}" for i in range(config.nbfcs)], dtype=object),
        person_has_account=has_account, person_primary_bank=primary, person_second_bank=second,
        person_basic_account=has_account & (income < params.get("inclusion.basic_account_income_paise")),
        person_has_pan=has_pan, person_upi=upi, person_has_card=has_card, person_has_mobile=has_mobile,
        opening_deposit=np.where(has_account, deposit, 0),
        opening_second=np.where(has_second, np.maximum(100, deposit // 4), 0),
        opening_cash=cash, employer_bank=employer_bank, merchant_bank=merchant_bank)
