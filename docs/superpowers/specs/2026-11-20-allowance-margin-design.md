# Allowance margin: design

Approved 20 November 2026. Follows `docs/superpowers/specs/2026-11-19-household-allowance-design.md`.

## Intent

An allowance equals the recipient's expected spending exactly, so recipients run short late in each cycle. In June of the gate run, non-earners fail 3% of attempts in the 10 days after their allowance and 18% at 25 to 29 days. That is now the largest source of insufficient-funds declines. Give everyone some headroom.

## Goals and non-goals

- Goal: fewer late-cycle declines for allowance recipients, with the pooling rule unchanged.
- Non-goals: first-month declines (allowances arrive after payday) and households with no income (plan 1d).
- Anti-goal: a person who both gives and receives an allowance.

## Approaches

| Approach | Trade-off | Verdict |
| :--- | :--- | :--- |
| Inflate every adult's need by a margin before pooling | One parameter; recipients accumulate the unspent margin, but the household buffer is unchanged because it already counts every member | Chosen |
| Margin on recipients only | Someone whose income lies between need and need plus margin would both give and receive | Dropped |
| Top each recipient up to a target balance | Bounded balances, but it reads balances ("rescue", which the allowance design ruled out) and fights mid-month pay days | Dropped |

## Design

- New registry parameter `transfer.allowance_margin`, value 0.15, status `assumption`.
- `Allowance.monthly` passes `need * (1 + margin)` to `allowance_pairs`. Nothing else changes: shortfall, surplus, scaling, days and rails stay as they are.
- A margin of 0 reproduces the current behaviour exactly.

## Success measure

Rerun the tier S gate (90 days, seed 7) with the margin at 0, 0.10, 0.15 and 0.20. Report insufficient-funds declines overall, by life stage and by days since the recipient's last allowance, and the share of households scaled down. Keep 0.15 unless the numbers argue otherwise, and say so if they do.
