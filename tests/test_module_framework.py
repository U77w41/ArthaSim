import datetime as dt
import numpy as np
import polars as pl
from arthasim import Config, World
from arthasim.engine.intents import Intents, Purpose, Rail
from arthasim.ledger.journal import FlowType, Kind
from arthasim.modules.base import BehaviourModule


class Gift(BehaviourModule):
    name = "gift"

    def __init__(self, as_frame=False):
        self.months, self.as_frame = [], as_frame

    def monthly(self, world, month):
        self.months.append(month)

    def intents(self, world, day):
        s = world.state
        it = Intents(kind=[Kind.PAYMENT], flow_type=[FlowType.REMITTANCE], payer_acct=[s.boundary_deposit],
                     payee_acct=[s.person_deposit[s.person_deposit >= 0][0]], amount=[12_345],
                     rail=[Rail.NEFT], slot=[30], offset_s=[0], purpose=[Purpose.REMITTANCE])
        return it.to_frame() if self.as_frame else it


def cfg(tmp_path, **kw):
    base = dict(persons=1_000, out_dir=str(tmp_path))
    base.update(kw)
    return Config.tier("S", **base)


def gifts(run):
    return run.table("payments").filter((pl.col("purpose") == "REMITTANCE") & (pl.col("rail") == "NEFT")).collect()


def test_custom_module_and_monthly_hook(tmp_path):
    world = World.build(cfg(tmp_path, start="2025-04-29"), seed=7)
    gift = Gift()
    world.modules.append(gift)
    g = gifts(world.run(until="2025-05-02"))
    assert g.height == 4 and (g["status"] == "SUCCESS").all() and (g["amount_paise"] == 12_345).all()
    assert gift.months == [dt.date(2025, 4, 29), dt.date(2025, 5, 1)]


def test_frame_modules_and_adapters(tmp_path):
    world = World.build(cfg(tmp_path), seed=7)
    world.modules.append(Gift(as_frame=True))
    assert gifts(world.run(until="2025-04-02")).height == 2
    it = Intents(kind=[1, 2], flow_type=[2, 2], payer_acct=[5, 6], payee_acct=[7, 8], amount=[10, 20],
                 rail=[2, 1], slot=[3, 4], offset_s=[0, 9], purpose=[10, 11])
    frame = it.to_frame()
    assert frame.columns == ["kind", "flow_type", "payer_acct", "payee_acct", "amount", "rail", "slot",
                             "offset_s", "purpose"]
    assert np.array_equal(Intents.from_frame(frame).amount, it.amount)
    assert Intents.from_frame(frame.drop("purpose")).purpose.tolist() == [0, 0]


def test_default_modules_and_base_class(tmp_path):
    spike = World.build(Config.tier("XS", persons=300, employers=5, merchants=20, out_dir=str(tmp_path)), seed=7)
    assert [m.name for m in spike.modules] == ["spike_income", "spike_consumption"]
    base = BehaviourModule()
    assert base.monthly(spike, dt.date(2025, 4, 1)) is None and len(base.intents(spike, dt.date(2025, 4, 1))) == 0
