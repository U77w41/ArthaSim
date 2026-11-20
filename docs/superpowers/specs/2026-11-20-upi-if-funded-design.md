# UPI only if funded: design

Approved 20 November 2026 ("apply the same balance check to UPI"). Follows `docs/superpowers/specs/2026-11-20-card-if-funded-design.md`.

## Intent

After the card change, UPI_P2M is the rail with the highest funds-decline rate (7.5%). Payers choose UPI whether or not their account holds the money, even when they have cash in hand. Apply the card rule to UPI.

## Design

- In `Consumption`, UPI at a merchant or biller requires the deposit balance at the start of the day to cover the amount, as cards now do. An unfunded UPI choice falls through `choose_rail`'s usual order. The same balance check gates cards, so it ends in cash. Bills (UPI-only billers) fall back to cash at the biller.
- Online orders (UPI only) also require funding. An unfunded online order becomes an offline purchase at a merchant in the same category, using the existing merchant draws. This is a builder's call: an online order cannot be paid in cash.
- `choose_rail` keeps its signature and draws. Person-to-person UPI (allowances, remittances, earnings) is unchanged.

## Approaches

One sensible way: the same rule as cards, for the same reason. Leaving online orders ungated was considered; it would keep their failures (UPI from an empty account) while every other purchase falls back, so they are gated too.

## Success measure

Rerun the tier S gate (90 days, seed 7, margin 0.15). Report funds declines by rail, the rail mix, life stages and days since allowance, before and after.
