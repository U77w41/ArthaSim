"""Cash management: merchants, billers and cash-rich persons take cash back to the bank."""
from __future__ import annotations

import datetime as dt

import numpy as np

from arthasim.engine import rng
from arthasim.engine.intents import Intents, Purpose, Rail
from arthasim.ledger.journal import FlowType, Kind
from arthasim.modules.base import BehaviourModule


class CashManagement(BehaviourModule):
    name = "cash"

    def intents(self, world, day: dt.date) -> Intents:
        s, params, seed = world.state, world.params, world.seed
        bal = s.book.balance
        payer, payee, amount = [], [], []

        # Merchants, then billers, deposit cash above their float.
        float_ = int(params.get("cash.merchant_float_paise"))
        for cash, deposit in ((s.merchant_cash, s.merchant_deposit), (s.biller_cash, s.biller_deposit)):
            over = bal[cash] > float_
            payer.append(cash[over]); payee.append(deposit[over]); amount.append(bal[cash[over]] - float_)

        # Banked persons with a lot of cash sometimes take most of it to the bank.
        threshold = int(params.get("cash.person_deposit_threshold_paise"))
        keep = int(params.get("cash.person_keep_paise"))
        banked = np.flatnonzero(s.person_deposit >= 0)
        rich = banked[bal[s.person_cash[banked]] > threshold]
        go = rng.uniform(seed, rng.stream_id("cash.person"), rich, day.toordinal()) < params.get("cash.person_deposit_daily_prob")
        rich = rich[go]
        payer.append(s.person_cash[rich]); payee.append(s.person_deposit[rich]); amount.append(bal[s.person_cash[rich]] - keep)

        payer_a, payee_a, amount_a = (np.concatenate(x).astype(np.int64) for x in (payer, payee, amount))
        n = payer_a.size
        return Intents(np.full(n, int(Kind.CASH_DEPOSIT)), np.full(n, int(FlowType.CASH_CONVERSION)), payer_a, payee_a,
                       amount_a, np.full(n, int(Rail.BRANCH)), np.full(n, 40), np.zeros(n), np.full(n, int(Purpose.CASH_DEPOSIT)))
