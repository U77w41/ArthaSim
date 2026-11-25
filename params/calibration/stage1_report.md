# Calibration report

400 trials, seeds 1, 2, 3, 8-month runs of 10000 persons from 2025-04-01; sampler seed 0; registry version `a58228ef557dedb8`; optuna 5.1.0, arthasim 0.0.1, polars 2.1.0.

Best loss 1.7 (the mean squared error in tolerances; 1 is every target at its band's edge).

## Free parameters

| Parameter | Low | High | Scale | Fitted |
| :--- | ---: | ---: | :--- | ---: |
| `earn.base_paise` | 300,000 | 1,500,000 | log | 679,962 |
| `earn.premium.metro` | 0 | 0.8 | linear | 0.05562 |
| `earn.sigma` | 0.2 | 0.9 | linear | 0.2133 (near a bound) |
| `earn.stage_multiplier:self_employed` | 0.3 | 1.5 | linear | 0.7435 |
| `earn.stage_multiplier:farm` | 0.2 | 1.2 | linear | 1.109 |
| `earn.stage_multiplier:casual` | 0.2 | 1.2 | linear | 0.5461 |
| `consumption.spend_share` | 0.5 | 1 | linear | 0.9 |
| `consumption.purchases_per_month:scale` | 0.5 | 3 | log | 2.187 |
| `rail.choice.upi_preference` | 0.3 | 1 | linear | 0.3418 |
| `attr.digital.upi_threshold` | 0.1 | 0.8 | linear | 0.1117 (near a bound) |
| `rail.choice.card_preference` | 0.005 | 0.6 | log | 0.01786 |
| `spike.cash_withdrawal_paise` | 100,000 | 1,500,000 | log | 709,492 |
| `open.deposit_months_of_income` | 0.1 | 3 | log | 0.1024 (near a bound) |
| `consumption.ticket_sigma` | 0.3 | 1.3 | linear | 1.282 (near a bound) |

## Targets (best trial, mean over seeds)

| Check | Component | Published | Simulated | Score |
| :--- | :--- | ---: | ---: | ---: |
| `pay.regular_monthly` | rural | 17,841 | 16,915 | -0.52 |
| `pay.regular_monthly` | urban | 26,247 | 25,455 | -0.30 |
| `pay.casual_daily` | rural | 433 | 388.3 | -1.03 |
| `pay.casual_daily` | urban | 549 | 593.4 | +0.81 |
| `pay.self_employed_monthly` | rural | 12,266 | 12,903 | +0.35 |
| `pay.self_employed_monthly` | urban | 23,012 | 17,458 | -1.61 |
| `consumption.mpce` | rural | 4,314 | 4,321 | +0.02 |
| `consumption.mpce` | urban | 7,346 | 6,576 | -1.05 |
| `consumption.gini` | rural | 0.237 | 0.3092 | +2.41 |
| `consumption.gini` | urban | 0.284 | 0.3739 | +3.00 |
| `payments.upi_p2m_per_adult` | all | 12.17 | 11.96 | -0.07 |
| `payments.debit_card_per_adult` | all | 0.1073 | 0.09712 | -0.38 |
| `payments.atm_per_adult` | all | 0.4411 | 0.4449 | +0.03 |
| `payments.atm_ticket` | all | 5,286 | 5,940 | +0.62 |
| `payments.p2m_under_500` | all | 0.86 | 0.9648 | +2.10 |
| `balances.basic_mean` | all | 4,808 | 6,339 | +1.27 |

## Best loss so far

| After trial | Best loss |
| ---: | ---: |
| 1 | 135.5 |
| 10 | 7.534 |
| 25 | 6.201 |
| 50 | 4.65 |
| 100 | 2.317 |
| 200 | 2.022 |
| 300 | 1.955 |
| 400 | 1.7 |
