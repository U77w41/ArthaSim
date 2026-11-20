# Card only if funded: design

Approved 20 November 2026 (approach chosen by the project owner).

## Intent

A payer with a debit card uses it at a card-accepting merchant about half the time, whether or not their bank account holds the money. Allowance recipients with a card but no UPI receive cash, so 17.7% of their card attempts fail for funds (June, margin 0.15), while their cash attempts fail 2.3%. People check their balance before paying by card. They should here too.

## Approaches

| Approach | Trade-off | Verdict |
| :--- | :--- | :--- |
| Pay by card only when the deposit balance at the start of the day covers the amount; else cash | Small change to rail choice; applies to every payer; two card purchases on one day are each checked against the morning balance | Chosen |
| Send card holders their allowance by bank transfer | Fixes the card side but makes their cash purchases (92% of attempts) depend on the fixed ₹2,000 automatic withdrawal, which fails below ₹2,000 | Dropped |
| Split the allowance into a card share by transfer and the rest in cash | Precise, but needs a per-person card-share estimate and a second monthly payment | Dropped |

## Design

- In `Consumption`, the card leg of rail choice requires `deposit balance at the start of the day >= amount`, in addition to holding a card and the merchant accepting cards. A payer without a deposit account never pays by card.
- `choose_rail` is unchanged; `Consumption` passes `has_card & funded` as the payer's card flag. The random draws are unchanged, so a funded payer makes the same choice as before.
- UPI, cash, bills and online orders are unchanged. The allowance is unchanged.

## Success measure

Rerun the tier S gate (90 days, seed 7, margin 0.15). Report the funds-decline rate by rail, the rail mix, and declines for allowance recipients with a card and no UPI, before and after.
