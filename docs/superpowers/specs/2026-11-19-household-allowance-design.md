# Household allowance: design

Approved 19 November 2026. Fixes the finding in `docs/phase1b1_results.md` ("Non-earning members cannot pay").

## Intent

Each adult spends an equal share of the household budget from their own accounts, and the head also pays the household's utilities and medical bills. Income lands only in earners' accounts and nothing moves it within the household, so 21% of payment attempts fail for insufficient funds, 86% of them by homemakers, students and job seekers. Earners should pass money to the members who need it, as a visible family transfer.

## Goals

- Non-earning and low-earning adults who live with an earner can pay for their share of the budget.
- Family transfers appear in the payments table with their own purpose. A mule detector will later need to tell this benign pattern apart from layering.
- The ledger stays closed and every invariant passes; same seed, same output.

## Non-goals

- Households where nobody earns (6.6% at tier S, seed 7). They still spend down savings and fail; government transfers (DBT, plan 1d) are the fix.
- Calibration. The rule adds no tunable number.
- Changing how budgets are set or who pays which purchase.

## Facts that shaped it (tier S, seed 7)

- 31% of adults have zero income; 87% of them live with an earner.
- 26% of household heads have zero income, and the head pays utilities and medical bills.
- Non-earners: 87% banked, 47% with UPI.

## Approaches

| Approach | Trade-off | Verdict |
| :--- | :--- | :--- |
| Allowance transfers from earners to members who fall short | Adds a payment stream; keeps every adult a payer | Chosen |
| Earners pay for everything | No transfers needed, but homemakers and students vanish as payers and the family-transfer pattern is lost | Dropped |
| Non-earners spend nothing | Same loss, and household spending no longer matches its budget | Dropped |

## Design

**Need.** Each month, after `Budget.monthly` has set budgets, each adult's need is their spending share, `person_budget * (1 - utilities share)` (the categories and telecom they pay themselves), plus, for the head only, the household's utilities bill (`budget * utilities share`) and `medical_due`.

**Pooling.** `shortfall = max(0, need - own monthly income)`, `surplus = max(0, own monthly income - need)`. Within a household, each shortfall is covered by every member with surplus, pro rata to surplus. If total shortfall exceeds total surplus, every shortfall is scaled by `total surplus / total shortfall`. One payment per (payer, recipient) pair with a positive rounded amount. Balances are not considered: the allowance is a habit, not a rescue.

**Timing.** Salaried payers pay the day after their employer's payday, capped at the month's last day (payday 28 in a 28-day February pays the same day, after the salary slot). Other payers pay on a fixed day of their own, keyed per person, from 1 to 28. A month starting mid-way pays only on the remaining days, like every other monthly payment.

**Rail.** Sent to where the recipient spends from:

- recipient has UPI: UPI P2P if the payer also has UPI and the amount is within the UPI limit; else IMPS if the payer is banked; else cash;
- recipient has no UPI: cash, from payer's cash to recipient's cash. A payer short of cash withdraws first through the existing automatic withdrawal.

**Accounting.** New `Purpose.ALLOWANCE` and `FlowType.HOUSEHOLD_TRANSFER`. Digital transfers are `Kind.PAYMENT` (deposit to deposit); cash is `Kind.CASH_PAYMENT` (cash to cash). Both nets are zero inside the household sector, so the flow-matrix invariants hold unchanged.

**Placement.** A new module `modules/allowance.py`, run after `Budget` and before `Consumption`. Monthly hook computes the pairs and amounts; daily hook emits the day's intents. Stream names start with `allow.`.

## Success measure

Rerun the plan 1b-1 gate (tier S, 90 days, seed 7). Report insufficient-funds declines by life stage before and after. Homemakers, students and job seekers should fall from about 70% towards the earners' rates; what remains should come mostly from households with no income. All invariants pass and two runs with the same seed give the same hash.

## Left to the builder (calls made here)

- Pro rata across all members with surplus, not only the top earner.
- No new registry parameters; slot window 48 to 79, after the salary slots (36 to 47).
- The day after payday is capped at the month's last day rather than rolling into the next month.
