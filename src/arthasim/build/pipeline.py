"""Population builder: runs the build steps and fills the WorldState the day loop reads."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import polars as pl

from arthasim.build import categories as c
from arthasim.build.attributes import Attributes, attach_attributes
from arthasim.build.banking import Banking, assign_banking
from arthasim.build.graph import build_edges
from arthasim.build.households import Households, form_households
from arthasim.build.identifiers import branch_code, pan_like, token, vpa
from arthasim.build.marginals import DistrictMarginals, load_district, load_priors
from arthasim.build.orgs import Orgs, build_orgs
from arthasim.build.population import Persons, synthesise_persons
from arthasim.behaviour import BehaviourState
from arthasim.build.world import EntityKind, Sector, WorldState
from arthasim.config import Config
from arthasim.engine import rng
from arthasim.engine.intents import Rail
from arthasim.ledger.instruments import InstrumentBook, InstrumentType as T
from arthasim.params import ParamRegistry

LATENT = ("domain_skill", "digital_literacy", "financial_literacy", "risk_appetite", "habit_strength",
          "price_sensitivity", "trust_in_offers")


@dataclass
class PopulationBundle:
    districts: list[DistrictMarginals]
    persons: Persons
    households: Households
    attributes: Attributes
    orgs: Orgs
    banking: Banking
    edges: pl.DataFrame
    report: dict[str, Any]
    person_second_deposit: np.ndarray
    biller_ids: np.ndarray
    biller_bank: np.ndarray
    nbfc_ids: np.ndarray
    tokens: dict[str, np.ndarray]


def _l1(counts: np.ndarray, target) -> float:
    total = counts.sum()
    return float(np.abs(counts / total - np.asarray(target, dtype=np.float64)).sum()) if total else 0.0


def fit_report(districts: list[DistrictMarginals], p: Persons) -> dict[str, Any]:
    """Sum of absolute share errors for each fitted margin, per district."""
    out: dict[str, dict[str, float]] = {}
    for di, d in enumerate(districts):
        s = p.district == di
        out[d.id] = {
            "age_band": _l1(np.bincount(p.age_band[s], minlength=5), d.age_band),
            "sex": _l1(np.bincount(p.sex[s], minlength=2), d.sex),
            "education": _l1(np.bincount(p.education[s], minlength=5), d.education),
            "life_stage_F": _l1(np.bincount(p.life_stage[s & (p.sex == c.F)], minlength=9), d.life_stage[c.F]),
            "life_stage_M": _l1(np.bincount(p.life_stage[s & (p.sex == c.M)], minlength=9), d.life_stage[c.M]),
        }
    return {"l1": out, "max_l1": max(v for margins in out.values() for v in margins.values())}


def build_population_state(config: Config, params: ParamRegistry, seed: int) -> WorldState:
    S = rng.stream_id
    L, B = config.localities_per_district, config.banks
    districts = [load_district(name) for name in config.districts]
    persons = synthesise_persons(districts, load_priors(), config.persons, seed)
    households = form_households(persons, districts, L, params, seed)
    attributes = attach_attributes(persons, districts, params, seed)
    orgs = build_orgs(persons, attributes, districts, L, params, seed)
    banking = assign_banking(persons, attributes, orgs, districts, config, params, seed)
    edges = build_edges(persons, households, orgs, districts, params, seed)

    # Entity ids: persons, employers, merchants, billers, banks, boundary bank, NBFCs, central bank, boundary.
    P, E, M, NB = len(persons), orgs.employer_capacity.size, orgs.merchant_district.size, len(orgs.billers)
    person_ids = np.arange(P, dtype=np.int64)
    employer_ids = P + np.arange(E, dtype=np.int64)
    merchant_ids = P + E + np.arange(M, dtype=np.int64)
    biller_ids = P + E + M + np.arange(NB, dtype=np.int64)
    bank_ids = P + E + M + NB + np.arange(B + 1, dtype=np.int64)
    nbfc_ids = int(bank_ids[-1]) + 1 + np.arange(config.nbfcs, dtype=np.int64)
    central_bank_id = int(bank_ids[-1]) + 1 + config.nbfcs
    boundary_id = central_bank_id + 1
    kind = np.empty(boundary_id + 1, dtype=np.int8)
    sector = np.empty(boundary_id + 1, dtype=np.int8)
    for ids, k, s in ((person_ids, EntityKind.PERSON, Sector.HOUSEHOLD), (employer_ids, EntityKind.EMPLOYER, Sector.FIRM),
                      (merchant_ids, EntityKind.MERCHANT, Sector.FIRM), (biller_ids, EntityKind.BILLER, Sector.FIRM),
                      (bank_ids, EntityKind.BANK, Sector.BANK), (nbfc_ids, EntityKind.NBFC, Sector.BANK)):
        kind[ids], sector[ids] = k, s
    kind[central_bank_id], sector[central_bank_id] = EntityKind.CENTRAL_BANK, Sector.CENTRAL_BANK
    kind[boundary_id], sector[boundary_id] = EntityKind.BOUNDARY, Sector.BOUNDARY

    salaried = persons.life_stage == c.SALARIED
    person_salary = np.where(salaried, attributes.monthly_income_paise, 0).astype(np.int64)
    employer_payroll = np.zeros(E, dtype=np.int64)
    np.add.at(employer_payroll, orgs.person_employer[salaried], person_salary[salaried])
    employer_payday = 1 + np.minimum((rng.uniform(seed, S("org.payday"), employer_ids, 0) * 28).astype(np.int64), 27)
    # The boundary stands for the economy outside the sample: it pays revenue, earnings and pensions.
    boundary_cash_opening = int(params.get("flows.boundary_cash_months")) * int(attributes.monthly_income_paise.sum())
    boundary_opening = int(round(boundary_cash_opening * params.get("spike.employer_revenue_multiple")))

    # Instruments.
    book = InstrumentBook()
    cb = central_bank_id
    banked = banking.person_has_account
    has_second = banking.person_second_bank >= 0
    biller_bank = np.arange(NB, dtype=np.int64) % B
    person_deposit = np.full(P, -1, dtype=np.int64)
    person_deposit[banked] = book.add_many(T.DEPOSIT, person_ids[banked], bank_ids[banking.person_primary_bank[banked]],
                                           banking.opening_deposit[banked])
    person_cash = book.add_many(T.CASH, person_ids, cb, banking.opening_cash)
    person_second = np.full(P, -1, dtype=np.int64)
    person_second[has_second] = book.add_many(T.DEPOSIT, person_ids[has_second],
                                              bank_ids[banking.person_second_bank[has_second]],
                                              banking.opening_second[has_second])
    employer_deposit = book.add_many(T.DEPOSIT, employer_ids, bank_ids[banking.employer_bank], 2 * employer_payroll)
    merchant_deposit = book.add_many(T.DEPOSIT, merchant_ids, bank_ids[banking.merchant_bank], 0)
    merchant_cash = book.add_many(T.CASH, merchant_ids, cb, 0)
    biller_deposit = book.add_many(T.DEPOSIT, biller_ids, bank_ids[biller_bank], 0)
    biller_cash = book.add_many(T.CASH, biller_ids, cb, 0)
    boundary_deposit = book.add(T.DEPOSIT, boundary_id, int(bank_ids[B]), boundary_opening)
    boundary_cash = book.add(T.CASH, boundary_id, cb, boundary_cash_opening)

    deposits_issued = np.zeros(B + 1, dtype=np.int64)
    np.add.at(deposits_issued, banking.person_primary_bank[banked], banking.opening_deposit[banked])
    np.add.at(deposits_issued, banking.person_second_bank[has_second], banking.opening_second[has_second])
    np.add.at(deposits_issued, banking.employer_bank, 2 * employer_payroll)
    deposits_issued[B] += boundary_opening
    customers = np.bincount(banking.person_primary_bank[banked], minlength=B + 1).astype(np.int64)
    vault_cash = customers * int(params.get("spike.vault_cash_per_customer_paise"))
    base_equity = int(params.get("spike.bank_equity_paise"))
    bank_reserve = book.add_many(T.RESERVE, bank_ids, cb, deposits_issued + base_equity)
    bank_vault = book.add_many(T.CASH, bank_ids, cb, vault_cash)
    book.freeze()

    n_accounts = len(book)
    deposit_for_cash = np.full(n_accounts, -1, dtype=np.int64)
    deposit_for_cash[person_cash[banked]] = person_deposit[banked]
    bank_of_account = np.full(n_accounts, -1, dtype=np.int64)
    bank_of_account[person_deposit[banked]] = banking.person_primary_bank[banked]
    bank_of_account[person_second[has_second]] = banking.person_second_bank[has_second]
    bank_of_account[employer_deposit] = banking.employer_bank
    bank_of_account[merchant_deposit] = banking.merchant_bank
    bank_of_account[biller_deposit] = biller_bank
    bank_of_account[boundary_deposit] = B
    vault_for_deposit = np.full(n_accounts, -1, dtype=np.int64)
    with_bank = bank_of_account >= 0
    vault_for_deposit[with_bank] = bank_vault[bank_of_account[with_bank]]
    withdraw_rail = np.full(n_accounts, int(Rail.ATM), dtype=np.int64)
    withdraw_rail[person_cash[~banking.person_has_card]] = int(Rail.AEPS)

    initial = np.minimum((rng.uniform(seed, S("id.pan"), person_ids, 0) * 26).astype(np.int64), 25)
    tokens = {"uid": token("u", seed, S("id.uid"), person_ids), "mobile": token("m", seed, S("id.mobile"), person_ids),
              "device": token("d", seed, S("id.device"), person_ids), "card": token("c", seed, S("id.card"), person_ids)}
    bundle = PopulationBundle(districts=districts, persons=persons, households=households, attributes=attributes,
                              orgs=orgs, banking=banking, edges=edges, report=fit_report(districts, persons),
                              person_second_deposit=person_second, biller_ids=biller_ids, biller_bank=biller_bank,
                              nbfc_ids=nbfc_ids, tokens=tokens)
    return WorldState(
        book=book, kind=kind, sector=sector,
        person_ids=person_ids, person_bank=banking.person_primary_bank, person_deposit=person_deposit,
        person_cash=person_cash, person_employer=orgs.person_employer, person_salary=person_salary,
        person_digital=banking.person_upi, pan_like=pan_like(person_ids, initial),
        employer_ids=employer_ids, employer_bank=banking.employer_bank, employer_deposit=employer_deposit,
        employer_payday=employer_payday, employer_payroll=employer_payroll,
        merchant_ids=merchant_ids, merchant_bank=banking.merchant_bank, merchant_deposit=merchant_deposit,
        merchant_cash=merchant_cash,
        bank_ids=bank_ids, bank_codes=banking.bank_codes, bank_reserve=bank_reserve, bank_vault=bank_vault,
        equity={int(bank_ids[b]): base_equity + int(vault_cash[b]) for b in range(B + 1)},
        central_bank_id=central_bank_id, boundary_id=boundary_id, boundary_deposit=int(boundary_deposit),
        deposit_for_cash=deposit_for_cash, vault_for_deposit=vault_for_deposit, bank_of_account=bank_of_account,
        currency_issued=int(book.balance[book.type == T.CASH].sum()),
        posted_total=np.zeros(n_accounts, dtype=np.int64), start=config.start, population=bundle,
        boundary_cash=int(boundary_cash), biller_deposit=biller_deposit, biller_cash=biller_cash,
        withdraw_rail=withdraw_rail, behaviour=BehaviourState.zeros(households.adults.size, P))


def _names(labels: list[str], index: np.ndarray, missing: np.ndarray | None = None) -> pl.Series:
    values = np.array(labels + [None], dtype=object)[np.where(index >= 0, index, len(labels))]
    if missing is not None:
        values = np.where(missing, None, values)
    return pl.Series(values.tolist(), dtype=pl.String)


def _nullable(values: np.ndarray, present: np.ndarray, dtype) -> pl.Series:
    return pl.Series(np.where(present, values, None).tolist(), dtype=dtype)


def population_frames(state: WorldState, config: Config) -> dict[str, pl.DataFrame]:
    """Dimension tables for a population build. Category columns hold names."""
    b: PopulationBundle = state.population
    p, h, a, o, k = b.persons, b.households, b.attributes, b.orgs, b.banking
    book = state.book
    district_ids = [d.id for d in b.districts]
    codes = k.bank_codes.tolist()
    hh = h.household_of_person
    locality = h.locality[hh]
    banked = k.person_has_account
    has_job = o.person_employer >= 0

    persons = pl.DataFrame({
        "entity_id": state.person_ids, "household_id": hh, "district": _names(district_ids, p.district),
        "locality": locality, "age": p.age, "sex": _names(c.SEX, p.sex),
        "education": _names(c.EDUCATION, p.education), "life_stage": _names(c.LIFE_STAGE, p.life_stage),
        "sector": _names(c.SECTORS, a.sector.astype(np.int64)),
        "employer_entity_id": _nullable(state.employer_ids[np.maximum(o.person_employer, 0)] if len(state.employer_ids)
                                        else np.zeros(len(p), dtype=np.int64), has_job, pl.Int64),
        "monthly_income_paise": a.monthly_income_paise, "has_account": banked,
        "primary_bank": _names(codes, k.person_primary_bank), "has_pan": k.person_has_pan,
        "pan_like": _nullable(state.pan_like, k.person_has_pan, pl.String),
        "uid_token": pl.Series(b.tokens["uid"].tolist(), dtype=pl.String),
        "mobile_token": _nullable(b.tokens["mobile"], k.person_has_mobile, pl.String)})

    households = pl.DataFrame({
        "household_id": np.arange(h.adults.size, dtype=np.int64), "district": _names(district_ids, h.district),
        "locality": h.locality, "adults": h.adults, "dependants": h.dependants, "head_entity_id": state.person_ids[h.head]})

    org_schema = {"entity_id": pl.Int64, "kind": pl.String, "district": pl.String, "locality": pl.Int64,
                  "sector": pl.String, "category": pl.String, "bank_code": pl.String, "accepts_upi": pl.Boolean,
                  "accepts_card": pl.Boolean, "payday": pl.Int64}
    E, M, NB = len(state.employer_ids), len(state.merchant_ids), len(b.biller_ids)
    orgs = pl.concat([
        pl.DataFrame({"entity_id": state.employer_ids, "kind": ["EMPLOYER"] * E,
                      "district": _names(district_ids, o.employer_district), "locality": [None] * E,
                      "sector": _names(c.SECTORS, o.employer_sector), "category": [None] * E,
                      "bank_code": _names(codes, k.employer_bank), "accepts_upi": [None] * E,
                      "accepts_card": [None] * E, "payday": state.employer_payday}, schema=org_schema),
        pl.DataFrame({"entity_id": state.merchant_ids, "kind": ["MERCHANT"] * M,
                      "district": _names(district_ids, o.merchant_district), "locality": o.merchant_locality,
                      "sector": [None] * M, "category": _names(c.MERCHANT_CATEGORIES, o.merchant_category),
                      "bank_code": _names(codes, k.merchant_bank), "accepts_upi": o.merchant_accepts_upi,
                      "accepts_card": o.merchant_accepts_card, "payday": [None] * M}, schema=org_schema),
        pl.DataFrame({"entity_id": b.biller_ids, "kind": ["BILLER"] * NB, "district": [None] * NB,
                      "locality": [None] * NB, "sector": [None] * NB, "category": o.billers,
                      "bank_code": _names(codes, b.biller_bank), "accepts_upi": [None] * NB,
                      "accepts_card": [None] * NB, "payday": [None] * NB}, schema=org_schema)])

    B = config.banks
    banks = pl.DataFrame({
        "entity_id": np.concatenate([state.bank_ids, b.nbfc_ids]),
        "bank_code": codes + k.nbfc_codes.tolist(),
        "kind": ["BANK"] * B + ["BOUNDARY"] + ["NBFC"] * len(b.nbfc_ids),
        "archetype": k.bank_archetype.tolist() + [None] + ["nbfc"] * len(b.nbfc_ids)},
        schema={"entity_id": pl.Int64, "bank_code": pl.String, "kind": pl.String, "archetype": pl.String})

    subtype = np.full(len(book), "current", dtype=object)
    subtype[state.person_deposit[banked]] = np.where(k.person_basic_account[banked], "basic", "savings")
    subtype[b.person_second_deposit[b.person_second_deposit >= 0]] = "savings"
    subtype[state.boundary_deposit] = "boundary"
    subtype[book.type == T.CASH] = "cash_in_hand"
    subtype[state.bank_vault] = "vault"
    subtype[book.type == T.RESERVE] = "reserve"
    accounts = pl.DataFrame({
        "account_id": np.arange(len(book), dtype=np.int64),
        "type": pl.Series(np.array(["", "DEPOSIT", "CASH", "RESERVE"], dtype=object)[book.type].tolist(), dtype=pl.String),
        "subtype": pl.Series(subtype.tolist(), dtype=pl.String),
        "holder_entity_id": book.holder, "issuer_entity_id": book.issuer,
        "opened_on": pl.Series([config.start] * len(book), dtype=pl.Date),
        "status": pl.Series(["ACTIVE"] * len(book), dtype=pl.String)})

    upi, card, mobile = k.person_upi, k.person_has_card, k.person_has_mobile & banked
    second = b.person_second_deposit >= 0
    parts = [
        ("VPA", state.person_deposit[upi], vpa(state.person_ids[upi], k.person_primary_bank[upi])),
        ("DEVICE", state.person_deposit[upi], b.tokens["device"][upi]),
        ("DEBIT_CARD", state.person_deposit[card], b.tokens["card"][card]),
        ("MOBILE", state.person_deposit[mobile], b.tokens["mobile"][mobile]),
        ("BRANCH", state.person_deposit[banked], branch_code(k.person_primary_bank[banked], p.district[banked], locality[banked])),
        ("BRANCH", b.person_second_deposit[second], branch_code(k.person_second_bank[second], p.district[second], locality[second])),
    ]
    account_id = np.concatenate([x[1] for x in parts])
    instruments = pl.DataFrame({
        "instrument_id": np.arange(account_id.size, dtype=np.int64), "account_id": account_id,
        "kind": pl.Series([x[0] for x in parts for _ in range(x[1].size)], dtype=pl.String),
        "value": pl.Series([v for x in parts for v in x[2].tolist()], dtype=pl.String)})

    edges = b.edges.rename({"src": "src_entity_id", "dst": "dst_entity_id"})
    L = config.localities_per_district
    geo = pl.DataFrame({
        "district": np.repeat(np.arange(len(b.districts), dtype=np.int64), L),
        "district_id": pl.Series(np.repeat(np.array(district_ids, dtype=object), L).tolist(), dtype=pl.String),
        "kind": pl.Series(np.repeat(np.array([d.kind for d in b.districts], dtype=object), L).tolist(), dtype=pl.String),
        "locality": np.tile(np.arange(L, dtype=np.int64), len(b.districts))})
    latent = pl.DataFrame({"entity_id": state.person_ids,
                           "month": pl.Series([f"{config.start:%Y-%m}"] * len(p), dtype=pl.String),
                           **{name: getattr(a, name) for name in LATENT}})
    return {"persons": persons, "households": households, "orgs": orgs, "banks": banks, "accounts": accounts,
            "instruments": instruments, "edges": edges, "geo": geo, "truth_person_latent": latent}
