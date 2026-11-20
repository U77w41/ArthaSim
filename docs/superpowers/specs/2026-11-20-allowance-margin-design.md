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
| Pay the margin only from surplus left after every shortfall is covered | Nobody receives less than without a margin; stretched households get no margin | Chosen (revised 20 November 2026) |
| Inflate every adult's need by a margin before pooling | One input change, but padding earners' need shrinks their surplus: in the first build, 18% of recipients received less and failed more often | Built first, replaced after review |
| Top each recipient up to a target balance | Bounded balances, but it reads balances ("rescue", which the allowance design ruled out) and fights mid-month pay days | Dropped |

## Design

- New registry parameter `transfer.allowance_margin`, value 0.15, status `assumption`.
- Recipients and payers are classified on the unpadded need, as before: shortfall `max(0, need - income)`, surplus `max(0, income - need)`. Nobody both gives and receives.
- Stage 1 is unchanged: every shortfall is covered pro rata to surplus, scaled down alike if surplus falls short.
- Stage 2: surplus left after stage 1 pays each recipient a margin of `margin * need`, pro rata to surplus, scaled down alike if the leftover falls short. A household scaled down in stage 1 has no leftover and pays no margin.
- One payment per (payer, recipient) pair carries both stages: `rint(surplus_p / total_surplus * (shortfall_r * scale + margin * need_r * margin_scale))`.
- A margin of 0 reproduces the behaviour without one exactly; for a given month's state, a margin never lowers what any recipient receives.

## Success measure

Rerun the tier S gate (90 days, seed 7) with the margin at 0, 0.10, 0.15 and 0.20. Report insufficient-funds declines overall, by life stage and by days since the recipient's last allowance, and the share of households scaled down. Keep 0.15 unless the numbers argue otherwise, and say so if they do.
