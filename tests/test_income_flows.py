import datetime as dt
import numpy as np
from arthasim.build import categories as c
from arthasim.engine.intents import Intents, Purpose, Rail
from arthasim.ledger.journal import FlowType, Kind
from arthasim.modules.income_flows import Income
from world_fixture import small_world

W = small_world()
S, B = W.state, W.state.population
STAGE, INC = B.persons.life_stage, B.attributes.monthly_income_paise
BANKED = S.person_deposit >= 0
ACCT_PERSON = np.full(len(S.book), -1, dtype=np.int64)
ACCT_PERSON[S.person_cash] = S.person_ids
ACCT_PERSON[S.person_deposit[BANKED]] = S.person_ids[BANKED]


def month(year, mon, days):
    return Intents.concat([Income().intents(W, dt.date(year, mon, d)) for d in range(1, days + 1)])


IT = month(2025, 4, 30)
PAYEE = ACCT_PERSON[IT.payee_acct]
TO_PERSON = PAYEE >= 0
GOT = np.zeros(len(INC), dtype=np.int64)
np.add.at(GOT, PAYEE[TO_PERSON], IT.amount[TO_PERSON])


def test_salaries_and_pensions_are_exact():
    sal, ret = STAGE == c.SALARIED, STAGE == c.RETIRED
    assert np.array_equal(GOT[sal], INC[sal]) and np.array_equal(GOT[ret], INC[ret])
    pension = IT.purpose == Purpose.PENSION
    assert pension.sum() == ret.sum() and (IT.flow_type[pension] == FlowType.PENSION).all()
    assert (IT.flow_type[IT.purpose == Purpose.SALARY] == FlowType.WAGE).all()
    assert (GOT[np.isin(STAGE, [c.STUDYING, c.SEEKING, c.HOMEMAKER])] == 0).all()


def test_other_earners_are_paid_the_configured_number_of_times():
    events = {c.SELF_EMPLOYED: 26, c.GIG: 4, c.FARM: 1, c.CASUAL: 22}
    for year, mon, days in ((2025, 4, 30), (2025, 5, 31), (2026, 2, 28)):
        it = month(year, mon, days)
        earn = it.flow_type == FlowType.EARNINGS
        count = np.bincount(ACCT_PERSON[it.payee_acct[earn]], minlength=len(INC))
        for stage, f in events.items():
            assert (count[STAGE == stage] == f).all()
    for stage in events:
        g = STAGE == stage
        assert abs(GOT[g].sum() / INC[g].sum() - 1.0) < 0.10


def test_cash_and_digital_split():
    cash = IT.kind == Kind.CASH_PAYMENT
    assert (IT.payer_acct[cash] == S.boundary_cash).all() and (IT.rail[cash] == Rail.CASH).all()
    earn = (IT.flow_type == FlowType.EARNINGS) & TO_PERSON
    person = np.maximum(PAYEE, 0)
    assert cash[TO_PERSON & ~BANKED[person]].all()
    casual = earn & (STAGE[person] == c.CASUAL) & BANKED[person]
    assert abs(cash[casual].mean() - 0.9) < 0.03
    digital = earn & ~cash
    upi = B.banking.person_upi[PAYEE[digital]]
    assert (IT.payer_acct[digital] == S.boundary_deposit).all()
    assert (IT.rail[digital][upi] == Rail.UPI_P2P).all() and (IT.rail[digital][~upi] == Rail.NEFT).all()


def test_revenue_topups_validity_and_determinism():
    IT.validate()
    assert (IT.purpose == Purpose.EMPLOYER_REVENUE).sum() == (S.employer_payroll > 0).sum()
    assert (IT.purpose != Purpose.UNSPECIFIED).all()
    assert np.array_equal(month(2025, 4, 30).amount, IT.amount)
