import numpy as np
import polars as pl
from arthasim import Config, World
from arthasim.build.world import EntityKind, Sector
from arthasim.build.pipeline import dbt_inputs
from arthasim.dbt.schemes import enrolled_payees
from arthasim.ledger.instruments import InstrumentType as T
from arthasim.life.accounts import open_accounts
from helpers import P
from world_fixture import small_world

NO_DBT = {"dbt.pm_kisan.coverage": 0.0, "dbt.old_age.coverage": 0.0, "dbt.women.coverage": 0.0}


def _world(tmp_path, persons=5_000, **params):
    config = Config.tier("S", persons=persons, out_dir=str(tmp_path)).with_params(**params)
    return World.build(config, seed=7)


def test_government_entity_balance_and_frames():
    world = small_world()
    s = world.state
    g = s.government
    assert s.kind[g.entity_id] == EntityKind.GOVERNMENT and s.sector[g.entity_id] == Sector.GOVERNMENT
    assert g.entity_id == s.boundary_id + 1 and s.kind.size == g.entity_id + 1
    book = s.book
    assert book.type[g.balance_account] == T.GOVERNMENT and book.holder[g.balance_account] == g.entity_id
    assert book.issuer[g.balance_account] == s.central_bank_id and book.opening[g.balance_account] == 0
    assert (book.type == T.GOVERNMENT).sum() == 1
    deposits = np.flatnonzero(s.bank_of_account >= 0)
    assert (book.holder[s.reserve_for_deposit[deposits]] == book.issuer[deposits]).all()
    assert (book.type[s.reserve_for_deposit[deposits]] == T.RESERVE).all()
    assert (s.reserve_for_deposit[s.bank_of_account < 0] == -1).all()
    orgs = pl.read_parquet(f"{world.path}/orgs.parquet").filter(pl.col("kind") == "GOVERNMENT")
    assert orgs["entity_id"].to_list() == [g.entity_id]
    acct = pl.read_parquet(f"{world.path}/accounts.parquet").filter(pl.col("account_id") == g.balance_account)
    assert acct.select("type", "subtype").row(0) == ("GOVERNMENT", "treasury")


def test_bpl_shares_by_district_kind():
    s = small_world().state
    h = s.population.households
    members = h.adults + h.dependants
    metro = np.array([d.kind == "metro" for d in s.population.districts])[h.district]
    for kind, mask, share in (("metro", metro, 0.264), ("rural", ~metro, 0.309)):
        got = members[mask & s.government.bpl].sum() / members[mask].sum()
        assert share <= got < share + members[mask].max() / members[mask].sum(), kind


def test_every_enrolee_is_banked_and_ownership_is_unchanged(tmp_path):
    base = _world(tmp_path / "a", **NO_DBT).state
    s = _world(tmp_path / "b").state
    payees = enrolled_payees(dbt_inputs(s), P, 7)
    assert payees.sum() > 500 and (s.person_deposit[payees] >= 0).all()
    district = s.population.persons.district
    for d in np.unique(district):
        assert (base.person_deposit[district == d] >= 0).sum() == (s.person_deposit[district == d] >= 0).sum()
    salaried = s.population.persons.life_stage == 2
    assert (s.person_deposit[salaried] >= 0).all()
    assert ((base.person_deposit >= 0) != (s.person_deposit >= 0)).sum() > 0


def test_tiny_world_with_too_few_donors_still_builds(tmp_path):
    world = _world(tmp_path, persons=300, **{"dbt.pm_kisan.coverage": 1.0, "dbt.old_age.coverage": 1.0,
                                             "dbt.women.coverage": 1.0,
                                             "inclusion.account_ownership": {"metro": 0.3, "rural": 0.3}})
    s = world.state
    payees = enrolled_payees(dbt_inputs(s), world.params, 7)
    assert payees.any() and (s.person_deposit[payees] >= 0).all()


def test_open_accounts_grows_the_reserve_lookup(tmp_path):
    world = _world(tmp_path, persons=300)
    s = world.state
    who = np.flatnonzero(s.person_deposit < 0)[:1]
    ids = open_accounts(s, world.params, who, np.array([2]), world.date, world.seed)
    assert s.reserve_for_deposit.size == len(s.book)
    assert s.reserve_for_deposit[ids[0]] == s.bank_reserve[2]


def test_spike_world_has_no_government(tmp_path):
    s = World.build(Config.tier("XS", persons=300, employers=5, merchants=20, out_dir=str(tmp_path)), seed=7).state
    assert s.government is None and s.reserve_for_deposit is None
