# tests/test_build_1b.py
import numpy as np
from arthasim import Config, World
from arthasim.engine.intents import Rail
from arthasim.ledger.instruments import InstrumentType as T
from helpers import P
from world_fixture import small_world


def test_new_accounts_lookups_and_state():
    s = small_world().state
    b, book = s.population, s.book
    income = int(b.attributes.monthly_income_paise.sum())
    assert book.type[s.boundary_cash] == T.CASH and book.holder[s.boundary_cash] == s.boundary_id
    assert book.opening[s.boundary_cash] == 36 * income
    assert book.opening[s.boundary_deposit] == round(36 * income * P.get("spike.employer_revenue_multiple"))
    assert len(s.biller_cash) == 4 and len(s.biller_deposit) == 4 and (book.opening[s.biller_cash] == 0).all()
    assert s.currency_issued == int(book.opening[book.type == T.CASH].sum())
    card = b.banking.person_has_card
    assert (s.withdraw_rail[s.person_cash[card]] == Rail.ATM).all()
    assert (s.withdraw_rail[s.person_cash[~card]] == Rail.AEPS).all()
    households = len(b.households.adults)
    for name in ("income", "balance", "budget", "medical_due", "buffer_months", "stress"):
        assert getattr(s.behaviour, name).shape == (households,)
    assert s.behaviour.person_budget.shape == (5_000,) and P.table().height == 89


def test_spike_world_has_none_of_this(tmp_path):
    s = World.build(Config.tier("XS", persons=300, employers=5, merchants=20, out_dir=str(tmp_path)), seed=7).state
    assert s.behaviour is None and s.withdraw_rail is None and s.boundary_cash == -1 and s.biller_cash is None
