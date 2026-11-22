"""Opening deposit accounts during a run. A new account starts at zero, so no money moves."""
from __future__ import annotations

import datetime as dt

import numpy as np

from arthasim.engine import rng
from arthasim.engine.intents import Rail
from arthasim.ledger.instruments import InstrumentType as T
from arthasim.params import ParamRegistry


def open_accounts(state, params: ParamRegistry, persons: np.ndarray, banks: np.ndarray, day: dt.date,
                  seed: int) -> np.ndarray:
    """One zero-balance deposit for each person at bank index `banks`; returns the new account ids.
    Every per-account array grows with the book, and the person's banking flags follow the build's rules."""
    persons = np.asarray(persons, dtype=np.int64)
    banks = np.asarray(banks, dtype=np.int64)
    k = state.population.banking
    if persons.size == 0:
        return np.empty(0, dtype=np.int64)
    if (state.person_deposit[persons] >= 0).any() or k.person_has_account[persons].any():
        raise ValueError("open_accounts: some of these people already have an account")
    n = persons.size
    ids = state.book.extend(T.DEPOSIT, state.person_ids[persons], state.bank_ids[banks], np.zeros(n, dtype=np.int64))
    state.posted_total = np.concatenate([state.posted_total, np.zeros(n, dtype=np.int64)])
    state.deposit_for_cash = np.concatenate([state.deposit_for_cash, np.full(n, -1, dtype=np.int64)])
    state.vault_for_deposit = np.concatenate([state.vault_for_deposit, state.bank_vault[banks]])
    state.bank_of_account = np.concatenate([state.bank_of_account, banks])
    state.withdraw_rail = np.concatenate([state.withdraw_rail, np.full(n, int(Rail.ATM), dtype=np.int64)])
    state.account_opened_on = np.concatenate([state.account_opened_on,
                                              np.full(n, np.datetime64(day, "D"))])

    cash = state.person_cash[persons]
    state.deposit_for_cash[cash] = ids
    state.person_deposit[persons] = ids
    k.person_has_account[persons] = True
    k.person_primary_bank[persons] = banks           # the same array as state.person_bank
    card = rng.uniform(seed, rng.stream_id("life.card"), persons, day.toordinal()) < params.get("inclusion.debit_card_share")
    k.person_has_card[persons] = card
    digital = state.population.attributes.digital_literacy[persons] > params.get("attr.digital.upi_threshold")
    k.person_upi[persons] = k.person_has_mobile[persons] & digital      # the same array as state.person_digital
    income = state.population.attributes.monthly_income_paise[persons]
    k.person_basic_account[persons] = income < params.get("inclusion.basic_account_income_paise")
    state.withdraw_rail[cash] = np.where(card, int(Rail.ATM), int(Rail.AEPS))
    return ids
