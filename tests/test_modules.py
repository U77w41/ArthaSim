import datetime as dt
import pathlib
import numpy as np
from arthasim import Config, ParamRegistry
from arthasim.build.world import build_state
from arthasim.engine.intents import Rail
from arthasim.ledger.journal import Kind, FlowType
from arthasim.modules import income, consumption

P = ParamRegistry.load(pathlib.Path(__file__).parents[1] / "params" / "registry.yaml")
S = build_state(Config.tier("XS"), P, seed=7)
D = dt.date(2025, 4, 10)


def test_payroll_only_on_payday_and_matches_salaries():
    paid = np.zeros(len(S.person_ids), dtype=np.int64)
    for dom in range(1, 31):
        it = income.intents(S, P, 7, dt.date(2025, 4, dom))
        wage = it.flow_type == FlowType.WAGE
        assert ((it.slot[wage] >= 36) & (it.slot[wage] <= 47)).all() and (it.rail[wage] == Rail.NACH_CR).all()
        idx = np.searchsorted(S.person_deposit, it.payee_acct[wage])
        np.add.at(paid, idx, it.amount[wage])
        top = it.flow_type == FlowType.TRANSFER
        assert top.sum() == (len(S.employer_ids) if dom == 1 else 0)
    assert np.array_equal(paid, np.where(S.person_employer >= 0, S.person_salary, 0))


def test_consumption_volume_amounts_and_rails():
    it = consumption.intents(S, P, 7, D)
    it.validate()
    assert abs(len(it.amount) / 10_000 - 1.2) < 0.04
    assert it.amount.min() >= 100 and abs(np.median(it.amount) / 20_000 - 1.0) < 0.05
    digital_dep = set(S.person_deposit[S.person_digital].tolist())
    upi = it.rail == Rail.UPI_P2M
    assert set(it.payer_acct[upi].tolist()) <= digital_dep and (it.kind[upi] == Kind.PAYMENT).all()
    assert (it.kind[~upi] == Kind.CASH_PAYMENT).all() and (it.rail[~upi] == Rail.CASH).all()
    assert ((it.slot >= 28) & (it.slot <= 87)).all()


def test_subset_equals_slice_of_full_run():
    full = consumption.intents(S, P, 7, D)
    sub = consumption.intents(S, P, 7, D, persons=np.arange(100))
    payers = set(S.person_deposit[:100].tolist()) | set(S.person_cash[:100].tolist())
    mask = np.isin(full.payer_acct, list(payers))
    for f in ("kind", "payer_acct", "payee_acct", "amount", "rail", "slot", "offset_s"):
        assert np.array_equal(np.sort(getattr(full, f)[mask]), np.sort(getattr(sub, f)))
    again = consumption.intents(S, P, 7, D)
    assert np.array_equal(full.amount, again.amount)
