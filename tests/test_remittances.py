import datetime as dt
import numpy as np
import polars as pl
from arthasim.engine.intents import Intents, Purpose, Rail
from arthasim.ledger.journal import FlowType, Kind
from arthasim.modules.remittances import Remittances
from helpers import P
from world_fixture import small_world

W = small_world()
S, B = W.state, W.state.population
INC = B.attributes.monthly_income_paise
EDGES = B.edges.filter(pl.col("type") == 4)
SRC, DST = EDGES["src"].to_numpy(), EDGES["dst"].to_numpy()
# Unpaid family helpers earn nothing, so they send nothing.
OK = (S.person_deposit[SRC] >= 0) & (S.person_deposit[DST] >= 0) & (INC[SRC] > 0)


def month(mon):
    days = [(d, Remittances().intents(W, dt.date(2025, mon, d))) for d in range(1, 31)]
    return Intents.concat([it for _, it in days]), np.concatenate([np.full(len(it), d) for d, it in days])


IT, DAY = month(4)


def test_one_transfer_per_eligible_edge():
    assert OK.sum() > 0 and len(IT) == OK.sum()
    assert (IT.kind == Kind.PAYMENT).all() and (IT.flow_type == FlowType.REMITTANCE).all()
    assert (IT.purpose == Purpose.REMITTANCE).all()
    pairs = set(zip(IT.payer_acct.tolist(), IT.payee_acct.tolist()))
    assert pairs == set(zip(S.person_deposit[SRC[OK]].tolist(), S.person_deposit[DST[OK]].tolist()))


def test_amounts_rails_and_stable_day():
    sent = dict(zip(IT.payer_acct.tolist(), IT.amount.tolist()))
    expected = np.rint(0.2 * INC[SRC[OK]]).astype(np.int64)
    assert [sent[a] for a in S.person_deposit[SRC[OK]].tolist()] == expected.tolist()
    sender = np.full(len(S.book), -1, dtype=np.int64)
    sender[S.person_deposit[SRC[OK]]] = SRC[OK]
    upi = B.banking.person_upi[sender[IT.payer_acct]] & (IT.amount <= P.get("rail.upi.limit_paise"))
    assert (IT.rail[upi] == Rail.UPI_P2P).all() and (IT.rail[~upi] == Rail.IMPS).all()
    assert DAY.min() >= 1 and DAY.max() <= 28
    may, may_day = month(5)
    assert dict(zip(IT.payer_acct.tolist(), DAY.tolist())) == dict(zip(may.payer_acct.tolist(), may_day.tolist()))
    IT.validate()
