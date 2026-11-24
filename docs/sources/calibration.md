# Sources for calibration and validation (plan 1e)

Each figure behind the registry's target and holdout rows, the appendix A rows, and the source checks of existing rows, with where it was read. Read between 24 November 2026 and the date of the plan 1e merge.

Status in the registry:
- `verified`: read in the primary document named, at the table and page given.
- `unverified`: from a weaker source (a news report, a summary, a search result), or the primary document could not be opened; the row says which.
- `assumption`: chosen or derived here; the derivation is given.

Page convention: "PDF p." is the page index in the file; "printed" is the number on the page.

## PLFS Annual Report 2025 (January–December 2025)

- **Document.** Annual Report, Periodic Labour Force Survey (PLFS), January–December 2025. National Statistics Office, MoSPI. Cover dated March 2026; the file is the revision uploaded 29 May 2026 (653 pages): https://www.mospi.gov.in/uploads/publications_reports/publications_reports1780040415321_0624fb13-fb47-40bc-b470-7c7e9635c3ef_PLFS_2025_F_REV_29052026.pdf
- **Press note,** 27 March 2026: https://www.mospi.gov.in/uploads/latestReleases/latest_release_1774607827733_3e8964a9-268b-4cc9-ad65-cfc8a9e32f08_Press_note_AR_PLFS_2025_23032025_V2.1_26032026_final.pdf
- Survey period January–December 2025, first-visit schedules. The report warns that 2025 is not strictly comparable with earlier PLFS reports, because the sample design changed in January 2025.
- Page mapping: in the Summary of Findings, printed page = PDF page − 30; in Appendix A, printed A-n = PDF page − 77.
- The life course's own PLFS inputs (Table 15, the CWS tables, the monthly and quarterly bulletins) are in `docs/sources/plfs_2025_annual.md` and `plfs_bulletins_2025_26.md` (plan 1b-2).

### Labour force rates, ages 15 and over, rural and urban (appendix A rows)

Usual status (ps+ss), person, all-India:

| Row | Value | Table | PDF p. / printed |
| :--- | ---: | :--- | :--- |
| `labour.lfpr.15plus` | 59.3% | Statement 2 (also Highlights Table 1, Table 16.0) | 41 / 11 |
| `labour.wpr.15plus` | 57.4% | Statement 5 (also Highlights Table 2, Table 17.0) | 45 / 15 |
| `labour.ur.15plus` | 3.1% | Highlights Table 3, Table 18.0 | 24 / xix; 154 / A-77 |

The design doc's values match the usual-status basis, not CWS (CWS gives 55.7, 52.8 and 5.3, Tables 30–32). By area, usual status, person: LFPR rural 62.8, urban 52.2; WPR rural 61.2, urban 49.7; UR rural 2.4, urban 4.8.

### Unemployment by education (`labour.ur.educated`)

Statement 17 (PDF p. 56 / printed 26), ages 15+, usual status, "secondary and above": rural 6.0%, urban 7.2%, all-India **6.5%** (person). The all-India figure is also in the Highlights (PDF p. 21 / xvi) and the press note.

Table 24 (PDF pp. 220–228 / A-143–151) gives the detailed levels. Person, ages 15+: graduates rural 11.8%, urban 10.6%, all-India 11.2%.

**Not found:** the design doc's "UR graduates aged 21–29: 22.2%". The report has no 21–29 age group. The nearest cell is graduates aged 15–29, all-India person, 22.3% (Table 21, PDF p. 183 / A-106). The row enters the registry as `labour.ur.graduate_15_29` with that cell; the doc's label and value are recorded as unfound.

### Workers by status in employment (`labour.share.regular_salaried`, `labour.share.self_employed`)

Statement 7 (PDF p. 47 / printed 17) and Table 19 (PDF pp. 157–165 / A-80–88), usual status, all workers (no age limit stated), person:

| | Rural | Urban | All-India |
| :--- | ---: | ---: | ---: |
| Regular wage/salaried | 14.1% | 47.6% | 23.6% |
| All self-employed | 62.4% | 40.4% | 56.2% |
| Casual labour | 23.5% | 12.0% | 20.2% |

The all-India 23.6% and 56.2% match the design doc. **Not found:** the doc's "49.6% urban" regular and "62.7% rural" self-employed. No cell of the 2025 report, on either basis, has those values; the report's values are used.

### Earnings (`pay.regular_monthly`, `pay.casual_daily`, `pay.self_employed_monthly`)

Current weekly status, person, all ages (no age limit stated):

| Row | Rural | Urban | All-India | Table | PDF p. / printed |
| :--- | ---: | ---: | ---: | :--- | :--- |
| Average wage or salary in the preceding calendar month, regular wage/salaried employees | ₹17,841 | ₹26,247 | ₹22,699 | Statement 11; Table 38 | 52 / 22; 314 / A-237 |
| Average wage per day, casual labour other than public works | ₹433 | ₹549 | ₹453 | Statement 12; Table 39 | 53 / 23; 315 / A-238 |
| Average gross earnings in the last 30 days from self-employment | ₹12,266 | ₹23,012 | ₹14,861 | Statement 13; Table 40 | 53 / 23; 316 / A-239 |

- Self-employment earnings leave out people who reported zero or no earnings (report text, PDF p. 53).
- The press note's casual wages (male ₹455, female ₹315, all-India) differ from the report's (₹489 and ₹324); the other two series agree. The report is the later, revised file, so its values are used.
- The report publishes no quarterly earnings.

## HCES 2023-24 (Household Consumption Expenditure Survey)

- **Fact sheet.** Household Consumption Expenditure Survey: 2023-24, Fact Sheet, MoSPI/NSO, released 27 December 2024 (the file on the server was re-saved 25 June 2025): https://mospi.gov.in/sites/default/files/publication_reports/HCES%20FactSheet%202023-24.pdf . PDF page = printed page + 1.
- **Press notes** of 27 December 2024 (https://www.mospi.gov.in/sites/default/files/press_release/HCES_Press_Note_2023-24_27122024_rev.pdf) and 30 January 2025 (https://mospi.gov.in/sites/default/files/press_release/HCES_Report202324_Press_Note_30012025.pdf) repeat the figures below.
- **Not read:** the full report, NSS Report No. 592 (https://mospi.gov.in/sites/default/files/publication_reports/Final_Report_HCES_2023-24L.pdf), which is over the fetch tool's 10 MB limit. Deciles, household size and the size distribution for 2023-24 are in it.
- Survey period August 2023 – July 2024. MPCE is at current prices, rupees per person per month, on the modified mixed reference period. "Without imputation" leaves out free items from social programmes (PDS grain, laptops, uniforms); both bases include home-grown produce and gifts valued at prices.

| Row | Rural | Urban | Statement | PDF p. / printed |
| :--- | ---: | ---: | :--- | :--- |
| `consumption.mpce` (without imputation) | ₹4,122 | ₹6,996 | Statement 1 | 5 / 4 |
| MPCE with imputation (context) | ₹4,247 | ₹7,078 | Statement 10 | 16 / 15 |
| `consumption.gini` (without imputation) | 0.237 | 0.284 | Statement 8 | 14 / 13 |
| `consumption.food_share` (without imputation) | 47.04% | 39.68% | Statement 1 (and Statement 4) | 5 / 4 |

The design doc's appendix values match the without-imputation basis.

MPCE by fractile class of persons (without imputation; Figures 1R and 1U, PDF pp. 6–7 / printed 5–6), rupees:

| Class | 0–5% | 5–10% | 10–20% | 20–30% | 30–40% | 40–50% | 50–60% | 60–70% | 70–80% | 80–90% | 90–95% | 95–100% |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Rural | 1,677 | 2,126 | 2,473 | 2,833 | 3,162 | 3,498 | 3,866 | 4,304 | 4,885 | 5,763 | 6,929 | 10,137 |
| Urban | 2,376 | 3,093 | 3,687 | 4,353 | 4,979 | 5,622 | 6,334 | 7,199 | 8,353 | 10,139 | 12,817 | 20,310 |

Item groups (Statement 4, PDF p. 9 / printed 8, without imputation), % of MPCE, rural / urban: cereals 4.99 / 3.76; pulses 2.04 / 1.40; sugar and salt 0.89 / 0.57; milk 8.44 / 7.19; vegetables 6.03 / 4.12; fruits 3.85 / 3.87; egg, fish and meat 4.92 / 3.56; edible oil 2.77 / 1.82; spices 3.27 / 2.30; beverages, refreshments and processed food (including purchased cooked meals) 9.84 / 11.09; pan, tobacco and intoxicants 3.84 / 2.37; fuel and light 6.11 / 5.59; education 3.24 / 5.97; medical 6.83 / 5.85; conveyance 7.59 / 8.46; consumer services excluding conveyance 5.25 / 5.72; miscellaneous goods and entertainment 6.22 / 6.92; rent 0.56 / 6.58; taxes and cesses 0.21 / 0.33; clothing, bedding and footwear 6.63 / 5.66; durable goods 6.48 / 6.87.

**Household size, 2022-23 (context, derived).** HCES 2022-23 Table A2 (https://www.mospi.gov.in/sites/default/files/publication_reports/HCES-22-23N/Table%20A2.xlsx), persons divided by households: 4.46 rural, 3.84 urban. The simulated archetypes have 4.04 and 3.32 (tier S, adults plus dependants). Household composition is a build input and is not checked in this plan.

## RBI Payment System Indicators, FY 2025-26

- **Documents.** RBI, "Payment System Indicators", monthly HTML releases at https://rbi.org.in/Scripts/PSIUserView.aspx (index). FY 2025-26 totals from the March 2026 release, column "FY 2025-26": https://rbi.org.in/Scripts/PSIUserView.aspx?Id=58 . Months April–October 2025 from the year-ago columns of the April–October 2026 releases (Id=59 to 65); November 2025 – March 2026 from Id=54 to 58. All figures are provisional, as RBI states.
- The PDFs on rbidocs.rbi.org.in serve a CAPTCHA to the fetch tool, so the HTML pages were read; they have no page numbers. For every series below, the twelve months sum to the published FY total.
- Units as published: volume in lakh (1 lakh = 100,000), value in ₹ crore. The registry holds volumes in million (lakh divided by 10) and values in crore.

| Row | Series (PSI item) | FY 2025-26 volume | FY 2025-26 value |
| :--- | :--- | ---: | ---: |
| `cards.debit.volume_monthly`, `cards.debit.value_monthly` | Debit cards, total (Part I item 4.2: PoS 9,601.85 and "Others", which include e-commerce, 3,200.27) | 12,802.12 lakh | ₹4,45,475 crore |
| `atm.withdrawal.volume_monthly`, `atm.withdrawal.value_monthly` | Cash withdrawal at ATMs using debit cards (Part II item 3.2) | 53,394.13 lakh | ₹28,58,626 crore |
| `imps.volume.fy26` | IMPS (Part I item 2.3) | 49,431.09 lakh | ₹76,69,929 crore |
| `aeps.volume.monthly` | AePS cash withdrawal at micro ATMs (Part II item 5.1) | 12,126.36 lakh | ₹3,22,744 crore |
| `upi.volume.fy26`, `upi.value.fy26`, `upi.volume.monthly`, `upi.value.monthly` | UPI (Part I item 2.6) | 24,16,168.86 lakh | ₹3,14,23,250 crore |
| (context) | APBS credits (Part I item 2.2) | 33,854.21 lakh | ₹7,17,040 crore |
| (context) | NACH credit (Part I item 2.4) | 18,284.42 lakh | ₹19,02,293 crore |
| (context) | NEFT (Part I item 2.5) | 1,00,996.15 lakh | ₹5,02,26,505 crore |

Monthly volumes in lakh, April 2025 – March 2026:

| Series | Apr | May | Jun | Jul | Aug | Sep | Oct | Nov | Dec | Jan | Feb | Mar |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Debit cards, total | 1,170.93 | 1,150.47 | 1,085.72 | 1,120.61 | 1,120.80 | 1,047.39 | 1,096.25 | 1,012.11 | 1,049.24 | 1,018.29 | 917.12 | 1,013.17 |
| ATM cash withdrawal, debit cards | 4,578.06 | 4,579.88 | 4,358.58 | 4,447.66 | 4,601.37 | 4,370.90 | 4,636.34 | 4,380.23 | 4,444.02 | 4,412.00 | 4,145.12 | 4,439.99 |
| AePS cash withdrawal | 928.36 | 1,017.25 | 944.62 | 996.95 | 1,245.48 | 1,034.96 | 1,084.34 | 1,048.96 | 926.03 | 956.67 | 867.37 | 1,075.37 |
| UPI | 1,78,934.24 | 1,86,774.60 | 1,83,950.06 | 1,94,679.48 | 2,00,083.10 | 1,96,334.33 | 2,07,009.21 | 2,04,669.79 | 2,16,346.68 | 2,17,034.45 | 2,03,941.84 | 2,26,411.08 |

Monthly values in ₹ crore, for ticket sizes:

| Series | Apr | May | Jun | Jul | Aug | Sep | Oct | Nov | Dec | Jan | Feb | Mar |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Debit cards, total | 38,113 | 36,978 | 35,463 | 38,138 | 37,406 | 36,776 | 42,143 | 34,143 | 37,274 | 37,957 | 33,135 | 37,948 |
| ATM cash withdrawal, debit cards | 2,43,494 | 2,44,945 | 2,28,735 | 2,31,722 | 2,38,883 | 2,29,713 | 2,50,321 | 2,34,055 | 2,38,925 | 2,39,172 | 2,30,242 | 2,48,419 |

Notes:
- **AePS.** RBI's AePS line equals NPCI's inter-bank (off-us) AePS cash withdrawals exactly (April–June 2025: 2,890.23 lakh against NPCI's 289.02 million). Withdrawals at the customer's own bank are not in it. Every simulated AePS withdrawal is at the customer's own bank (plan 1c ruling), so the series is pinned but not checked. The design doc's "92.82 million" is the June 2026 figure (928.19 lakh), outside the window; June 2025 is 944.62 lakh.
- **IMPS.** The design doc's 4.94 billion is confirmed (49,431.09 lakh); it also appears in the RBI Annual Report 2025-26, Table IX.1 (https://www.rbi.org.in/Scripts/AnnualReportPublications.aspx?Id=1469). IMPS fell from 56,249.68 lakh in FY 2024-25.
- **Not checked:** NEFT, IMPS, NACH and APBS. Their volumes include business, interbank and scheme flows that a household simulator does not represent one for one.

## RTGS minimum (`rtgs.minimum_paise`)

RBI, "Frequently Asked Questions – Real Time Gross Settlement (RTGS) System", updated 14 October 2026, Q6: the minimum is ₹2,00,000 with no upper limit. https://www.rbi.org.in/Scripts/FAQView.aspx?Id=65 . The threshold dates from circular RBI/2010-11/259 (3 November 2010), effective 15 November 2010: https://www.rbi.org.in/scripts/NotificationUser.aspx?Id=6075&Mode=0 . The model has no RTGS rail in phase 1, so nothing reads the row.

## Population denominators (`population.adults_18plus`, `population.urban_share`)

The Technical Group on Population Projections report (National Commission on Population, July 2020) is over the fetch tool's 10 MB limit. Its five-yearly points were read as reprinted by MoSPI, which cites the report:
- MoSPI, "Women and Men in India 2023", chapter 2, Table 1.1 (printed p. 9): total population 1,363.00 million (1 March 2021) and 1,425.90 million (1 March 2026); urban 469.34 and 513.45 million. https://mospi.gov.in/sites/default/files/reports_and_publication/statistical_publication/Women_Men/mw23/Population.pdf
- MoSPI, "Women and Men in India 2022", Statement 4.1 (printed p. 23): ages 15–59 923,857 thousand and 60+ 162,829 thousand on 1 March 2026. https://mospi.gov.in/sites/default/files/publication_reports/women-men22/PopulationStatistics22.pdf
- "Women and Men in India 2023", Table 1.2 (printed p. 10): ages 15–19 are 8.3% of males and 8.2% of females in 2026.

Derived (status `assumption`):
- **Adults aged 18+ in FY 2025-26: 1,016 million.** Persons aged 15+ on 1 March 2026 (923.857 + 162.829 = 1,086.69 million), less ages 15–17, taken as three fifths of the 15–19 band (0.6 × 8.25% × 1,425.90 = 70.58 million). The 1 March 2026 point is five months after the fiscal year's midpoint; adults grow by about 1.5% a year, so the figure is high by under 1%.
- **Urban share of persons: 0.36** (513.45 / 1,425.90 in 2026; 0.344 in 2021). The share of adults is taken to equal the share of persons.

## UPI: P2M share and ticket sizes (`upi.p2m.share`, `upi.p2m.share_under_500`, `upi.p2p.share_under_500`)

Ministry of Finance, "UPI completes 10 glorious years, Emerges as World's Largest Real-Time Payments Platform, Anchoring India's Digital Economy", PIB release 2257087, 30 April 2026: https://www.pib.gov.in/PressReleaseIframePage.aspx?PRID=2257087 . The page returns HTTP 403 to the fetch tool; it was read in the built-in browser on 25 November 2026.
- Section IV, "Transaction Segmentation, P2P & P2M Analysis": P2M transactions are 63% of volume and P2P 71% of value (so P2M 29% of value). Fig 7's caption dates the split: "H1 2025, 106.36 Billion Transactions", from NPCI UPI Product Statistics.
- Section "Transaction Distribution by Ticket Size": in FY 2026, 86% of P2M transactions were below ₹500, and 59% of P2P transactions.
- The same release prints FY 2025-26 volume as 24,161.69 crore, which equals RBI's 2,416,168.86 lakh.
- For context, RBI's Payment System Report of December 2024, paragraphs 5.10–5.12, gives calendar 2024 buckets read in primary: P2M 62.1% of volume; 85.2% of P2M and 56.0% of P2P below ₹500.

## UPI by day, May to November 2025 (`upi.month_start_spike`)

NPCI, UPI Product Statistics, "Daily Statistics" tab: https://www.npci.org.in/product/upi/product-statistics . The page renders by JavaScript and was read in the built-in browser on 25 November 2026, month by month (May to November 2025). Each month's daily figures sum to NPCI's printed monthly total, which equals RBI's monthly figure (for example October 2025: 20,700.92 million and ₹27,27,790.71 crore). The 214 daily rows are in `docs/sources/npci_upi_daily_2025.csv` (volume in million, value in ₹ crore).

UPI value rises at the turn of the month: the mean daily value on the 1st to 3rd over the mean on the 10th to 25th was 1.2945 (May), 1.2558 (June), 1.3555 (July), 1.2580 (August) and 1.2661 (September). **Derived (`assumption`): 1.286**, the mean of the five months. October (1.107) and November are left out because the festival raises mid-October. Volume barely moves at the turn of the month (1.02 to 1.07), so the spike is in value: salaries and month-start payments such as rent and transfers.

Salary credits themselves are not published by day. The legal rule behind the month-start timing is the Code on Wages, 2019, s.17(1)(iv): monthly wages are paid "before the expiry of the seventh day of the succeeding month" (text as passed by Lok Sabha: https://prsindia.org/files/bills_acts/bills_parliament/1970/Code%20on%20Wages,%202019%20as%20passed%20by%20LS.pdf), in force from 21 November 2025 (PIB release of the Ministry of Labour and Employment, 21 November 2025, read in a print copy at https://fact.co.in/images/upload/Press-Release_-Press-Information-Bureau_7540.pdf). Before that, the Payment of Wages Act, 1936, s.5(1): before the 7th day after the wage period (under 1,000 employees) or the 10th (others) (Delhi Labour Department copy: https://labour.delhi.gov.in/it/sections-part-1).

## Festival uplift (`festival.diwali.upi_uplift`, holdout)

From RBI's monthly UPI value (Part I item 2.6, above). Per day: September 2025 ₹82,991.2 crore, October ₹87,993.3 crore, November ₹87,721.1 crore. October over the mean of September and November: **1.031** (derived, `assumption`). Diwali was on 20 October 2025.
- The centred ratio removes UPI's steady growth (+20.6% in value over FY 2025-26), which the model does not have. October over September alone (1.060) mixes the festival with that growth.
- On volume the centred ratio is 0.999: the festival shows in value, not in the number of payments.
- NPCI's daily table shows the peak: 754.37 million transactions on 18 October 2025 (Dhanteras), the highest day in the window.
- **The design doc's "+32%"** is not a Diwali 2025 uplift. News reports of 10–11 November 2026 (PTI, citing NPCI) compare Diwali 2026 with "the same day last year"; another "+32%" is November 2025 over November 2024 (RBI: +32.2%). Neither is used.

## DBT cash-out lag (`dbt.cashout_lag`, holdout)

Erica Field, Natalia Rigol, Charity Troyer Moore, Rohini Pande and Simone Schaner, "Banking on Transparency for the Poor: Experimental Evidence from India", CEGA working paper, 12 August 2022: https://escholarship.org/uc/item/6b834220 . Appendix Table A.5, Panel A (p. A-12), control group, May 2018 – March 2019: the probability that the next withdrawal after a DBT deposit day falls 0–5 days later is 0.179, 6–15 days 0.234, 16–30 days 0.173 (31–45: 0.097; 46–60: 0.058; 61–90: 0.074; 91–120: 0.041). Each column keeps deposit days with enough observation left (N from 5,875 down to 4,290).
- Population: 870 married women aged 20–50, Ujjwala LPG beneficiaries, with accounts at 37 bank kiosks in Gwalior and Morena (Madhya Pradesh). The DBTs are LPG subsidy, MGNREGA wages, pensions and others. The average trip to a kiosk took nearly three hours.
- It is the only primary distribution of time to withdrawal found. PMGKY surveys of 2020 (Oxfam India coalition, RCRC, CGD and MSC) report only the share withdrawn by the survey date during the lockdown (76–77%). No timing figure exists for PM-Kisan, NSAP pensions or the state transfers to women.

## PMJDY (`inclusion.pmjdy.*`)

Lok Sabha unstarred question 20, "PM Jan Dhan Yojana", answered 1 December 2025 by the Department of Financial Services: https://sansad.in/getFile/lsapps/loksabhaquestions/annex/186/AU20_ZAwvpe.pdf?source=lsapps . First table (p. 1): 56,98,76,402 accounts on 12 November 2025. Final table (p. 2): 15,07,18,294 inoperative (no customer-induced transaction for over two years), 5,21,65,274 zero-balance, average deposit ₹4,808.
- Operative share 1 − 15,07,18,294 / 56,98,76,402 = 0.7355; zero-balance share 5,21,65,274 / 56,98,76,402 = 0.0915 (ratios of counts in one table, `verified`).
- **The design doc's 81.2% operative and 8.2% zero-balance are from August 2022** (RBI, Report on Trend and Progress of Banking in India 2021-22, para IV.99: https://rbi.org.in/Scripts/PublicationsView.aspx?id=21578). The window's figures are used.
- Lok Sabha unstarred question 4090 (18 August 2025) gives 13,04,52,845 inoperative of 56,03,84,490 on 31 July 2025 (operative 0.767).
- RBI's definition of an inoperative account (no customer-induced transaction for over two years) is in the circular of 1 January 2024, Annex Part I para 1(a)(iv), and since November 2025 in the consolidated Directions, para 4(16).

**Not found:** savings accounts and their balances by population group (RBI BSR-2). The table is published only on RBI's DBIE portal, which needs JavaScript. RBI's Handbook of Statistics 2025-26 Table 47 gives all deposit accounts by population group (31 March 2025), but those include term deposits. So the spec's `balances.savings_mean` check has no source and was dropped; the month-end balance check uses the PMJDY average.

## Account ownership and debit cards (`inclusion.account_ownership`, `inclusion.debit_card_ownership`)

World Bank Global Findex 2025 (India survey fielded in 2024, n = 3,000 adults aged 15+): account ownership 89.02% (rural 89.9%, urban 87.2%, Little Data Book 2025, p. 75); owns a debit card 37.56% (indicator fin2.t.d, https://api.worldbank.org/v2/country/IND/indicator/fin2.t.d?source=28&format=json); made or received a digital payment 48.5%. PIB's backgrounder of 6 August 2025, p. 2, repeats the 89% (https://static.pib.gov.in/WriteReadData/specificdocs/documents/2025/aug/doc202586601201.pdf). The registry's PIB factsheet 150832 returned 403.

Finding, not acted on: `inclusion.debit_card_share` (0.7 of account holders, an input) implies about 62% of adults with a debit card, against Findex's 37.6%. Changing it would change default runs, so it stays; card use is calibrated through `rail.choice.card_preference`.

TRAI tele-density (31 March 2025: rural 58.67%, urban 124.83%, Press Release 35/2025, p. 1: https://trai.gov.in/sites/default/files/2025-05/PR_No.35of2025_0.pdf) counts connections per 100 people, not people with a phone, so it does not pin `inclusion.mobile_share`, which stays an assumption.

## CPI uprating (`consumption.hces_uprate`)

CPI (base 2012=100), general index, final values:
- August 2023 – July 2024 (the HCES 2023-24 survey period): RBI, Handbook of Statistics on the Indian Economy 2024-25, Table 162 (https://www.rbi.org.in/Scripts/PublicationsView.aspx?id=23336), checked against MoSPI's release of 12 September 2024. Means: rural 188.675, urban 184.792.
- April – December 2025: Table 162 (April to June) and MoSPI's monthly releases of 12 September 2025 to 12 February 2026 (July to December finals). Means: rural 197.489, urban 194.044. The 2012 base ends in December 2025.

Ratio (`assumption`): rural 197.489 / 188.675 = 1.0467; urban 194.044 / 184.792 = 1.0501. The core suite compares simulated MPCE with HCES MPCE times this ratio: rural ₹4,314, urban ₹7,347.

## Other appendix A rows

- **`wealth.household_mean`.** MoSPI press note on AIDIS (NSS 77th round), 10 September 2021, section A, p. 2: average value of assets per household ₹15,92,379 rural and ₹27,17,081 urban, as on 30 June 2018 (https://www.mospi.gov.in/sites/default/files/press_release/press_note-AIDIS-240821.pdf). These are **gross assets, not net worth** as the design doc says. Debt per household is ₹59,748 and ₹1,20,336, so net worth would be about ₹15.3 and ₹26.0 lakh (derived). Report No. 588 (44 MB) was not read.
- **`sip.inflow.monthly`.** AMFI Monthly Notes, "SIP trend" tables, read in primary for every month of FY 2025-26 (mean ₹29,132 crore a month over 9.22 crore contributing accounts). The design doc's ₹32,490 crore across 10.06 crore accounts is September 2026 (AMFI Monthly Note September 2026, p. 16), outside the window.
- **`credit.classification.buckets`.** RBI Master Circular on IRACP, RBI/2025-26/13, 1 April 2025: para 2.1.2 (NPA after 90 days overdue) and para 8.1 (SMA-0 up to 30 days, SMA-1 31–60, SMA-2 61–90). The Directions of 28 November 2025 carry the same rules (para 42(1); Resolution of Stressed Assets Directions para 15).
- **`fraud.loss.cy24`.** Lok Sabha unstarred question 344, 22 July 2025 (Ministry of Home Affairs), p. 3: ₹22,845.73 crore reported lost in 2024, with 19,18,865 financial-fraud complaints on NCRP. **The design doc's 22.68 lakh** is all cybercrime incidents registered on the portal in 2024 (p. 2), not the complaints behind the amount.
- **`cc_on_upi.value.monthly`.** No NPCI or RBI series found. A Rajya Sabha answer of 3 December 2024, seen only in Business Standard, gives ₹63,825.80 crore for April–October 2024, about ₹9,100 crore a month (`unverified`).
- **`pay.increment.corporate_mean`, `pay.attrition.annual`.** EY, Future of Pay 2026 (February 2026): p. 23, 2025 actual 9.3% and 2026 projected 9.1%; p. 19, 2025 attrition 16.4% (13.8% voluntary, 2.6% involuntary). Deloitte India Talent Outlook 2026 press release: 9.1% for 2026 (9.0% in 2025) and 17.6% attrition in 2025. Aon release of 24 February 2026: 8.9% actual in 2025, 9.1% projected for 2026, 16.2% attrition in 2025. The design doc's "9.0% to 9.1%" mixes a 2025 actual (Deloitte) with 2026 projections; the row holds the 2026 projection, 9.1%.
- **`pay.skill_premium`, `pay.switch_jump`, `fraud.actor_share`.** No primary source found. Private salary guides (Michael Page, Adecco, Mercer, seen only in news) quote 20–50% ranges.
- **`upi.lite.limits`.** RBI/2024-25/93, 4 December 2024: ₹1,000 per transaction and ₹5,000 in the wallet at any time (https://rbi.org.in/Scripts/NotificationUser.aspx?Id=12752&Mode=0).
- **`upi.limit`.** The standard ₹1 lakh is the existing `rail.upi.limit_paise` (RBI statement of 8 August 2024; RBI Payment System Report June 2025, para 3.3(2)). The ₹5 lakh for listed categories is NPCI OC 185B (28 August 2025), Annexure I, effective 15 September 2025 for verified merchants (`upi.limit.listed_categories_paise`).

## Existing rows checked

| Row | Finding | Status now |
| :--- | :--- | :--- |
| `rail.upi.limit_paise` (₹1 lakh) | RBI statement of 8 August 2024; RBI Payment System Report June 2025, para 3.3(2) | verified |
| `inclusion.account_ownership` (0.89) | Findex 2025: 89% (rural 89.9%, urban 87.2%) | verified |
| `life.gig.nonfarm_share` (2.6%, 6.7%) | NITI Aayog report of 27 June 2022; the PDFs returned 403; the values match Business Today's report of the launch | unverified |
| `life.retire.superannuation_age` (58, 60) | Industrial Employment (Standing Orders) Central Rules, Schedule I-B clause 3 (Delhi Labour Department copy); FR 56(a) in DoPT OM of 1 December 2022. The Industrial Relations Code (in force 21 November 2025) subsumes the Standing Orders Act; transition keeps the old rules | verified |
| `life.study.max_age` (35) | A cut-off chosen from Table 15, not a published figure | assumption |
| `life.within.farm_nonfarm` (0.005) | ICRISAT Policy Brief 27, p. 4: two thirds of 2005 farmers still farming in the later year; about 0.0048 a month over seven years (derived) | assumption |
| `life.switch.monthly_prob` (0.011) | Aon's 16.2% (read) less 3.4% involuntary (secondary only); EY's split gives 0.0123 | assumption |
| `life.raise.mean` (0.089) | Aon releases of 7 October 2025 and 24 February 2026: 8.9% actual in 2025 | verified |
| `life.raise.april_share` (0.56) | Seen only in a search excerpt; it is the share of employee respondents whose company runs an April–March cycle, not the share of employers raising pay in April | unverified |
| `dbt.pm_kisan.amount_paise` (₹2,000) | PM-KISAN scheme document (7 February 2019) and PIB backgrounder of 19 November 2025 | verified |
| `dbt.old_age.min_age`, `dbt.old_age.central_paise` | PIB backgrounder on NSAP (November 2025): ₹200 a month at 60–79, ₹500 from 80 | verified |

No value changed. The other rows keep their status: the `spike.`, `attr.`, `earn.`, `org.`, `bank.`, `open.`, `graph.`, `income.`, `consumption.` and `cash.` placeholders are `assumption`, with no primary source for model weights of this kind.
