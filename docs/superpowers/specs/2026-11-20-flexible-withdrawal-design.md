# Flexible automatic withdrawal: design

Approved 20 November 2026 (option chosen by the project owner: "₹2,000, adapt at edges").

## Intent

When a payer is short of cash for a cash payment, the settlement kernel withdraws a fixed ₹2,000 (`spike.cash_withdrawal_paise`), and only if the account holds at least that. A person with ₹1,500 in the bank cannot pay ₹300 in cash, and a purchase needing more than ₹2,000 beyond the cash in hand fails. In the gate run, 91% of the 656,012 failed cash payments are under ₹2,000.

## Approaches

| Approach | Trade-off | Verdict |
| :--- | :--- | :--- |
| Keep ₹2,000 as the usual amount; take what the account holds when it is less, or enough when the purchase needs more | ATM visit counts stay about the same (measured afterwards: about 10% more); only today's failures change | Chosen |
| Withdraw exactly the shortfall each time | Many small withdrawals (₹300 at an ATM), unlike real use, and it distorts the withdrawal patterns a fraud model learns | Dropped |

## Design

- `need = amount - cash in hand`. Withdrawal `= max(usual amount, need rounded up to the note size)`, capped at the deposit balance rounded down to the note size. It goes ahead only if it covers `need` and the vault holds it; otherwise nothing is withdrawn and the payment fails as today.
- New registry parameter `cash.withdrawal_note_paise`, value 10,000 (₹100), status `assumption`. `settle_day` takes it as `withdrawal_note`, default 1 (no rounding), so existing callers and tests keep their units.
- Rails (ATM or AePS), journal shape and slot are unchanged. The allowance module's own pre-withdrawal is unchanged.

## Success measure

Rerun the tier S gate (90 days, seed 7). Report cash funds declines, withdrawal counts and average size by rail, overall funds declines and life stages, before and after.
