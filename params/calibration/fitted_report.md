# Calibration report

200 trials, seeds 1, 2, 3, 8-month runs of 10000 persons from 2025-04-01; sampler seed 1; registry version `a58228ef557dedb8`; optuna 5.1.0, arthasim 0.0.1, polars 2.1.0.

Best loss 0.8771 (the mean squared error in tolerances; 1 is every target at its band's edge).

## Free parameters

| Parameter | Low | High | Scale | Fitted |
| :--- | ---: | ---: | :--- | ---: |
| `earn.base_paise` | 453,308 | 1,019,943 | log | 985,804 |
| `earn.premium.metro` | 0 | 0.2556 | linear | 0.1046 |
| `earn.sigma` | 0.05 | 0.4258 | linear | 0.105 |
| `earn.stage_multiplier:self_employed` | 0.4435 | 1.043 | linear | 1.007 |
| `earn.stage_multiplier:farm` | 0.8588 | 1.2 | linear | 0.8988 |
| `earn.stage_multiplier:casual` | 0.2961 | 0.7961 | linear | 0.5247 |
| `consumption.spend_share` | 0.775 | 1 | linear | 0.9016 |
| `consumption.purchases_per_month:scale` | 1.458 | 3 | log | 2.454 |
| `rail.choice.upi_preference` | 0.3 | 0.5168 | linear | 0.4378 |
| `attr.digital.upi_threshold` | 0.1 | 0.2867 | linear | 0.2795 |
| `rail.choice.card_preference` | 0.01191 | 0.02679 | log | 0.02191 |
| `spike.cash_withdrawal_paise` | 472,994 | 1,064,237 | log | 722,478 |
| `open.deposit_months_of_income` | 0.06826 | 0.1536 | log | 0.07912 |
| `consumption.ticket_sigma` | 1.032 | 1.3 | linear | 1.277 |
| `earn.return_by_education:scale` | 0.3 | 1.5 | linear | 0.3835 |
| `consumption.buffer_target_months` | 0.5 | 6 | log | 3.269 |

## Targets (best trial, mean over seeds)

| Check | Component | Published | Simulated | Score |
| :--- | :--- | ---: | ---: | ---: |
| `pay.regular_monthly` | rural | 17,841 | 18,439 | +0.34 |
| `pay.regular_monthly` | urban | 26,247 | 24,525 | -0.66 |
| `pay.casual_daily` | rural | 433 | 413 | -0.46 |
| `pay.casual_daily` | urban | 549 | 551.2 | +0.04 |
| `pay.self_employed_monthly` | rural | 12,266 | 13,349 | +0.59 |
| `pay.self_employed_monthly` | urban | 23,012 | 21,193 | -0.53 |
| `consumption.mpce` | rural | 4,314 | 4,462 | +0.34 |
| `consumption.mpce` | urban | 7,346 | 6,722 | -0.85 |
| `consumption.gini` | rural | 0.237 | 0.28 | +1.43 |
| `consumption.gini` | urban | 0.284 | 0.3352 | +1.71 |
| `payments.upi_p2m_per_adult` | all | 12.17 | 13.09 | +0.31 |
| `payments.debit_card_per_adult` | all | 0.1073 | 0.1317 | +0.91 |
| `payments.atm_per_adult` | all | 0.4411 | 0.4148 | -0.24 |
| `payments.atm_ticket` | all | 5,286 | 5,985 | +0.66 |
| `payments.p2m_under_500` | all | 0.86 | 0.9694 | +2.19 |
| `balances.basic_mean` | all | 4,808 | 5,768 | +0.80 |

## Best loss so far

| After trial | Best loss |
| ---: | ---: |
| 1 | 1.7 |
| 10 | 1.7 |
| 25 | 1.128 |
| 50 | 0.9872 |
| 100 | 0.9812 |
| 200 | 0.8771 |
