"""Minimal world for the phase 0 spike: persons, employers, merchants, banks."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any
from enum import IntEnum

import numpy as np

from arthasim.config import Config
from arthasim.build.identifiers import pan_like
from arthasim.engine import rng
from arthasim.ledger.instruments import InstrumentBook, InstrumentType as T
from arthasim.params import ParamRegistry


class EntityKind(IntEnum):
    PERSON = 1
    EMPLOYER = 2
    MERCHANT = 3
    BANK = 4
    CENTRAL_BANK = 5
    BOUNDARY = 6
    BILLER = 7
    NBFC = 8
    GOVERNMENT = 9


class Sector(IntEnum):
    HOUSEHOLD = 1
    FIRM = 2
    BANK = 3
    CENTRAL_BANK = 4
    BOUNDARY = 5
    GOVERNMENT = 6


@dataclass
class WorldState:
    book: InstrumentBook
    kind: np.ndarray
    sector: np.ndarray
    person_ids: np.ndarray
    person_bank: np.ndarray
    person_deposit: np.ndarray
    person_cash: np.ndarray
    person_employer: np.ndarray
    person_salary: np.ndarray
    person_digital: np.ndarray
    pan_like: np.ndarray
    employer_ids: np.ndarray
    employer_bank: np.ndarray
    employer_deposit: np.ndarray
    employer_payday: np.ndarray
    employer_payroll: np.ndarray
    merchant_ids: np.ndarray
    merchant_bank: np.ndarray
    merchant_deposit: np.ndarray
    merchant_cash: np.ndarray
    bank_ids: np.ndarray
    bank_codes: np.ndarray
    bank_reserve: np.ndarray
    bank_vault: np.ndarray
    equity: dict[int, int]
    central_bank_id: int
    boundary_id: int
    boundary_deposit: int
    deposit_for_cash: np.ndarray
    vault_for_deposit: np.ndarray
    bank_of_account: np.ndarray
    currency_issued: int
    posted_total: np.ndarray
    start: dt.date
    population: Any = None          # PopulationBundle for population builds
    boundary_cash: int = -1         # population builds only, from here on
    biller_deposit: Any = None
    biller_cash: Any = None
    withdraw_rail: Any = None       # per cash account: rail of an automatic withdrawal
    behaviour: Any = None           # BehaviourState
    life: Any = None                # LifeState (population builds)
    account_opened_on: Any = None   # per account, datetime64[D] (population builds)


def build_state(config: Config, params: ParamRegistry, seed: int) -> WorldState:
    """Build the world with the builder the config names."""
    if config.builder == "population":
        from arthasim.build.pipeline import build_population_state
        return build_population_state(config, params, seed)
    return build_spike_state(config, params, seed)


def build_spike_state(config: Config, params: ParamRegistry, seed: int) -> WorldState:
    P, E, M, B = config.persons, config.employers, config.merchants, config.banks
    S = rng.stream_id

    person_ids = np.arange(P, dtype=np.int64)
    employer_ids = P + np.arange(E, dtype=np.int64)
    merchant_ids = P + E + np.arange(M, dtype=np.int64)
    bank_ids = P + E + M + np.arange(B + 1, dtype=np.int64)        # last one is the boundary bank
    central_bank_id = int(P + E + M + B + 1)
    boundary_id = central_bank_id + 1
    n_entities = boundary_id + 1

    kind = np.empty(n_entities, dtype=np.int8)
    sector = np.empty(n_entities, dtype=np.int8)
    for ids, k, s in ((person_ids, EntityKind.PERSON, Sector.HOUSEHOLD),
                      (employer_ids, EntityKind.EMPLOYER, Sector.FIRM),
                      (merchant_ids, EntityKind.MERCHANT, Sector.FIRM),
                      (bank_ids, EntityKind.BANK, Sector.BANK)):
        kind[ids], sector[ids] = k, s
    kind[central_bank_id], sector[central_bank_id] = EntityKind.CENTRAL_BANK, Sector.CENTRAL_BANK
    kind[boundary_id], sector[boundary_id] = EntityKind.BOUNDARY, Sector.BOUNDARY

    # Bank assignment by market share, truncated or padded to the configured bank count.
    shares = list(params.get("spike.bank_shares"))[:B]
    shares += [shares[-1]] * (B - len(shares))
    cum = np.cumsum(np.array(shares, dtype=np.float64) / sum(shares))

    def assign_bank(ids: np.ndarray) -> np.ndarray:
        u = rng.uniform(seed, S("build.bank"), ids, 0)
        return np.minimum(np.searchsorted(cum, u, side="right"), B - 1).astype(np.int64)

    person_bank, employer_bank, merchant_bank = (assign_bank(x) for x in (person_ids, employer_ids, merchant_ids))

    salaried = np.zeros(P, dtype=bool)
    person_employer = np.full(P, -1, dtype=np.int64)
    if E > 0:
        salaried = rng.uniform(seed, S("build.salaried"), person_ids, 0) < params.get("spike.salaried_share")
        pick = np.minimum((rng.uniform(seed, S("build.employer"), person_ids, 0) * E).astype(np.int64), E - 1)
        person_employer = np.where(salaried, pick, -1)
    salary = np.maximum(1, np.rint(rng.lognormal(seed, S("build.salary"), person_ids, 0,
                                                 params.get("spike.salary.median_paise"),
                                                 params.get("spike.salary.sigma")))).astype(np.int64)
    person_salary = np.where(salaried, salary, 0)
    opening = np.maximum(1, np.rint(rng.lognormal(seed, S("build.opening"), person_ids, 0,
                                                  params.get("spike.opening_balance.median_paise"),
                                                  params.get("spike.opening_balance.sigma")))).astype(np.int64)
    person_digital = rng.uniform(seed, S("build.digital"), person_ids, 0) < params.get("spike.digital_share")
    initial = np.minimum((rng.uniform(seed, S("build.pan"), person_ids, 0) * 26).astype(np.int64), 25)

    employer_payday = 1 + np.minimum((rng.uniform(seed, S("build.payday"), employer_ids, 0) * 28).astype(np.int64), 27)
    employer_payroll = np.zeros(E, dtype=np.int64)
    np.add.at(employer_payroll, person_employer[salaried], person_salary[salaried])
    boundary_opening = int(round(24 * int(employer_payroll.sum()) * params.get("spike.employer_revenue_multiple")))

    # Instruments. Person deposits come first, so person_deposit is ascending.
    book = InstrumentBook()
    cb = central_bank_id
    person_deposit = book.add_many(T.DEPOSIT, person_ids, bank_ids[person_bank], opening)
    person_cash = book.add_many(T.CASH, person_ids, cb, params.get("spike.opening_cash_paise"))
    employer_deposit = book.add_many(T.DEPOSIT, employer_ids, bank_ids[employer_bank], 2 * employer_payroll)
    merchant_deposit = book.add_many(T.DEPOSIT, merchant_ids, bank_ids[merchant_bank], 0)
    merchant_cash = book.add_many(T.CASH, merchant_ids, cb, 0)
    boundary_deposit = book.add(T.DEPOSIT, boundary_id, int(bank_ids[B]), boundary_opening)

    deposits_issued = np.zeros(B + 1, dtype=np.int64)
    np.add.at(deposits_issued, person_bank, opening)
    np.add.at(deposits_issued, employer_bank, 2 * employer_payroll)
    deposits_issued[B] += boundary_opening
    customers = np.bincount(person_bank, minlength=B + 1).astype(np.int64)
    vault_cash = customers * int(params.get("spike.vault_cash_per_customer_paise"))
    base_equity = int(params.get("spike.bank_equity_paise"))
    bank_reserve = book.add_many(T.RESERVE, bank_ids, cb, deposits_issued + base_equity)
    bank_vault = book.add_many(T.CASH, bank_ids, cb, vault_cash)
    book.freeze()

    n_accounts = len(book)
    deposit_for_cash = np.full(n_accounts, -1, dtype=np.int64)
    deposit_for_cash[person_cash] = person_deposit
    bank_of_account = np.full(n_accounts, -1, dtype=np.int64)
    bank_of_account[person_deposit] = person_bank
    bank_of_account[employer_deposit] = employer_bank
    bank_of_account[merchant_deposit] = merchant_bank
    bank_of_account[boundary_deposit] = B
    vault_for_deposit = np.full(n_accounts, -1, dtype=np.int64)
    has_bank = bank_of_account >= 0
    vault_for_deposit[has_bank] = bank_vault[bank_of_account[has_bank]]

    return WorldState(
        book=book, kind=kind, sector=sector,
        person_ids=person_ids, person_bank=person_bank, person_deposit=person_deposit,
        person_cash=person_cash, person_employer=person_employer, person_salary=person_salary,
        person_digital=person_digital, pan_like=pan_like(person_ids, initial),
        employer_ids=employer_ids, employer_bank=employer_bank, employer_deposit=employer_deposit,
        employer_payday=employer_payday, employer_payroll=employer_payroll,
        merchant_ids=merchant_ids, merchant_bank=merchant_bank, merchant_deposit=merchant_deposit,
        merchant_cash=merchant_cash,
        bank_ids=bank_ids,
        bank_codes=np.array([f"SYNB{b + 1:02d}" for b in range(B)] + ["SYNX00"], dtype=object),
        bank_reserve=bank_reserve, bank_vault=bank_vault,
        equity={int(bank_ids[b]): base_equity + int(vault_cash[b]) for b in range(B + 1)},
        central_bank_id=central_bank_id, boundary_id=boundary_id, boundary_deposit=int(boundary_deposit),
        deposit_for_cash=deposit_for_cash, vault_for_deposit=vault_for_deposit,
        bank_of_account=bank_of_account,
        currency_issued=int(book.balance[book.type == T.CASH].sum()),
        posted_total=np.zeros(n_accounts, dtype=np.int64),
        start=config.start,
    )
