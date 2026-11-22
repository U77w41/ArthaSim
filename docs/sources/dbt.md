# Sources for government transfers (plan 1d-1)

Each figure the registry's `dbt.` rows use, where it comes from, and how it was turned into a parameter. Read on 22 November 2026. Status `unverified` means transcribed from the source named, not yet checked again by a person; `assumption` means derived or chosen here, with the reasoning given.

## PM-Kisan

| Figure | Value | Source |
| :--- | :--- | :--- |
| Benefit | ₹6,000 a year in three instalments of ₹2,000 to landholding farmer families | PM-Kisan portal, https://pmkisan.gov.in/; architecture appendix A row `dbt.pm_kisan` |
| 20th instalment | 2 August 2025; about ₹20,500 crore to 9.7 crore beneficiaries | Business Today, 19 November 2025, https://www.businesstoday.in/personal-finance/news/story/pm-kisan-21st-instalment-pm-modi-releases-rs-18000-cr-for-over-9-cr-farmers-how-to-check-payment-status-502820-2025-11-19 |
| 21st instalment | 19 November 2025, Coimbatore; over ₹18,000 crore to about 9 crore farmers | PIB fact sheet, https://static.pib.gov.in/WriteReadData/specificdocs/documents/2025/nov/doc20251120700401.pdf |
| 22nd instalment | 13 March 2026, Guwahati; over ₹18,640 crore to about 9.32 crore farmers | PIB, https://static.pib.gov.in/WriteReadData/specificdocs/documents/2026/jun/doc2026620898101.pdf |
| 23rd instalment | 20 June 2026, Hooghly; over ₹18,880 crore to about 9.44 crore farmers | Same PIB document |
| Exclusions | Institutional landholders; families with a serving or retired government officer or employee (other than multi-tasking staff, Class IV and Group D); retired pensioners with a monthly pension of ₹10,000 or more (same exception); anyone who paid income tax in the last assessment year; registered professionals | PM-Kisan operational guidelines, exclusion criteria, https://pmkisan.gov.in/ |
| Operational holdings | 14.645 crore (146.45 million) | Agriculture Census 2015-16, Phase I (Ministry of Agriculture and Farmers Welfare) |

Derived:
- **Coverage 0.66 (assumption).** 9.7 crore families paid in August 2025 against 14.645 crore operational holdings. Holdings stand for farmer families; some families hold more than one holding, and some holdings are excluded, so this is the share of farm households paid, not a measured take-up.
- **Taxpayer threshold ₹7 lakh a year (assumption).** Instalments paid during financial year 2025-26 check the assessment year 2025-26, that is income earned in 2024-25. Under the new tax regime for 2024-25, the section 87A rebate made income up to ₹7 lakh tax-free. One person's earned income above ₹7 lakh a year stands for "paid income tax".

## Social old-age pension (NSAP and state top-ups)

| Figure | Value | Source |
| :--- | :--- | :--- |
| Central assistance (IGNOAPS) | ₹200 a month at ages 60–79, ₹500 from 80, to people in below-poverty-line (BPL) households | PIB note on NSAP, November 2025, https://static.pib.gov.in/WriteReadData/specificdocs/documents/2025/nov/doc2025117686801.pdf |
| State top-up | States add ₹50 to ₹5,700 a month, giving an average pension of around ₹1,100 in many states | Same PIB note |
| Beneficiaries | 2.21 crore under IGNOAPS | Same PIB note |
| Receipt among the poor | About 30% of BPL people aged 60+ received IGNOAPS in 2017-18 | LASI Wave 1 (IIPS, 2021), as reported by Down To Earth, https://www.downtoearth.org.in/economy/less-than-a-third-bpl-senior-citizens-benefit-from-old-age-pension-scheme-health-ministry-survey-74962 |
| Work-related pensions | 8.6% of people aged 60+ (urban 19.8%, rural 4.9%) | LASI Wave 1 India factsheet, https://www.iipsindia.ac.in/sites/default/files/other_files/LASI_W1_Factsheet_INDIA.pdf |
| Poverty headcount, 2011-12 | Rural 30.9%, urban 26.4% of persons | Report of the Expert Group to Review the Methodology for Measurement of Poverty (Rangarajan), Planning Commission, June 2014 |
| Elderly population | 13.8 crore aged 60+ in 2021, projected 19.4 crore in 2031 | MoSPI, Elderly in India 2021 |

Derived:
- **BPL status (assumption).** BPL lists are old (the 2002 BPL census, then SECC 2011) and fixed for years, with coverage set close to official poverty estimates. The model draws its list once, at build: a household is BPL if its earned income per member (adults plus dependants) is in the poorest 30.9% of persons in a rural district or 26.4% in an urban one, the Rangarajan headcounts. The list does not change during a run. A share-based list does not depend on the level of simulated incomes, which plan 1e has yet to calibrate.
- **State top-up ₹800 (assumption).** It takes the pension to ₹1,000 at ages 60–79 and ₹1,300 from 80, close to the average of around ₹1,100 that PIB reports.
- **Coverage 0.5 (assumption).** About 16 crore people were aged 60+ in 2025 (interpolated between MoSPI's 2021 and 2031 figures). With about 30% of them poor, that gives about 4.8 crore poor elderly, and 2.21 crore IGNOAPS beneficiaries is 0.46 of them. Rounded up for pensions that states pay from their own schemes. LASI's 30% for 2017-18 predates later expansion.

## State cash transfers to women

PRS Legislative Research, State of State Finances 2025, Table 6 (page 29), "Benefits under unconditional cash transfer schemes for women across states", https://prsindia.org/files/budget/SOSF_2025.pdf. Sources given there: scheme websites, state budget documents, PRS. The table's 12 budget provisions sum to the report's total of ₹1,68,040 crore for 2025-26 (budget estimates).

| State | Scheme | Eligibility (as listed) | Benefit (₹ a month) | Budget 2025-26 BE (₹ crore) | Implied beneficiaries (lakh) |
| :--- | :--- | :--- | ---: | ---: | ---: |
| Assam | Orunodoi | Women over 18 | 1,250 | 5,000 | 33.3 |
| Chhattisgarh | Mahtari Vandan | Married women over 21 | 1,000 | 5,500 | 45.8 |
| Delhi | Mahila Samriddhi | – | 2,500 | 5,110 | 17.0 |
| Himachal Pradesh | Indira Gandhi Pyari Behna Sukh Samman Nidhi | Phased; 18–59 | 1,500 | 138 | 0.8 |
| Haryana | Lado Laxmi | Women over 18 | 2,100 | 5,000 | 19.8 |
| Jharkhand | CM Maiyan Samman | 18–50 | 2,500 | 13,363 | 44.5 |
| Karnataka | Gruha Lakshmi | – | 2,000 | 28,608 | 119.2 |
| Maharashtra | Majhi Ladki Bahin | 21–65 | 1,500 | 36,000 | 200.0 |
| Madhya Pradesh | Ladli Behna | 21–60 | 1,250 | 18,669 | 124.5 |
| Odisha | Subhadra | 21–60 | 833 | 10,145 | 101.5 |
| Tamil Nadu | Magalir Urimai Thogai | 21 and above | 1,000 | 13,807 | 115.1 |
| West Bengal | Lakshmir Bhandar | 25–60 | 1,000–1,200 | 26,700 | 202.3 (at ₹1,100) |

Implied beneficiaries are budget ÷ (benefit × 12), so they are a weighting, not a count. In total they come to 10.2 crore, against the EAC-PM's "close to 12 crore women" in more than 15 states by 2025-26 (EAC-PM Working Paper 52/2026, July 2026, https://eacpm.gov.in/wp-content/uploads/2026/07/CBT-Working-Paper.pdf).

Other notes:
- Ladki Bahin's income cap is ₹2.5 lakh a year of family income, and it excludes families with a government employee or an income-tax payer. In April 2025, Maharashtra cut the benefit to ₹500 for women already receiving ₹1,000 a month from another state scheme for women farmers (PRS, page 7).
- Ladli Behna was usually credited around the 10th of the month (news reports, 2024–2026), and rose to ₹1,500 from December 2025.

Derived:
- **Amount tiers (assumption).** Each covered woman gets one of six monthly amounts, fixed for the run, standing for the state she lives in. The weights are the implied beneficiaries above: ₹1,000 (363.2 lakh, including West Bengal at its general rate), ₹1,250 (157.8), ₹1,500 (200.8), ₹2,000 (119.2), ₹2,100 (19.8) and ₹2,500 (61.6). The weighted mean is ₹1,405. Odisha is left out because Subhadra pays ₹5,000 twice a year rather than monthly, a schedule this plan does not model.
- **Eligibility.** Women aged 21–60, which is the Ladli Behna and Subhadra range and the core of the others. Household earned income under ₹2.5 lakh a year (Ladki Bahin), and no household member salaried in public administration.
- **Coverage 0.4 (assumption).** About 12 crore beneficiaries out of roughly 37.5 crore women aged 21–60 is 0.32 of all such women. That estimate takes India's 2025 population as 146 crore, 48.5% female, about 53% of them aged 21–60. If roughly three-quarters of women are under the schemes' caps, coverage of the eligible is about 0.4. That reflects the share of women living in a state with a scheme, times take-up.
- **Pay day: the 10th (assumption)**, following Ladli Behna.
