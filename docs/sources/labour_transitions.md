# Indian labour-market transition rates: published figures

Compiled 21 Nov 2026 from sources read directly (PDF, HTML, XLSX). Every number below comes from the cited table, chart label or text, or, where marked **[derived]**, from simple arithmetic on cited numbers (the arithmetic is stated). Nothing is estimated from memory.

Conventions:
- "Quarterly" means the state is observed one quarter apart (PLFS urban revisits). "Monthly" means one month apart. "Per wave" means four months apart (CMIE CPHS).
- In all PLFS-based tables, status is **Current Weekly Status (CWS)**, meaning the activity in the 7 days before the interview.
- Row = state at t, column = state at t+1, unless noted otherwise.

---

## 0. What was found (index)

| # | Source | Coverage | Time unit | States | By sex | Section |
|---|---|---|---|---|---|---|
| A | Bhattacharya, arXiv 2110.05482v2, Table 4 | Urban, ages 15–65, 2017-Q3 to 2019-Q4 | Quarterly | self-emp, casual, salaried, unemployed, NLF (not split), sick, "had work but didn't work", attrited | Yes | 1.1 |
| B | MoSPI PLFS Quarterly Bulletin Oct–Dec 2024, Appendix Table (5) | Urban, 15+, four quarter pairs Oct-Dec 2023 → Oct-Dec 2024 | Quarterly (joint % of persons) | own-account/employer, unpaid helper, regular, casual, unemployed, NLF | Yes | 1.4 |
| C | Joshi & Joshi, *Sarvekshana* 114 (Mar 2023), Tables 3–5 | Urban, 15+, 14 quarters Jul-Sep 2018 to Oct-Dec 2021 | Quarterly | employed / unemployed / NLF | Yes | 1.5 |
| D | Menon & Nath, *The India Forum* (10 Jun 2022), Tables 1–3 | Urban, from the unemployed state only, 2017-18 and 2018-19 | Q1 → Q4 (3 quarters apart) | U→E, U→U, U→O | Yes; also by education | 1.6 |
| E | Deshpande & Singh, IZA DP 14639 (2021), Tables A.1/A.2 | **Rural** and urban women, CPHS, 2016–2019 | Per 4-month wave | in / out of labour force | Women (men only in text) | 2.1 |
| F | Sarkar, Sahoo & Klasen, IZA DP 11086 (2017), Table 2 | **Rural** and urban women aged 25–55, IHDS | 7 years (2005 → 2012) | employed / not employed / attrited | Women | 2.5 |
| G | PLFS monthly and quarterly bulletins, Apr 2025 – Oct 2026 | **Rural** and urban | Monthly / quarterly **stocks** (net change, not flows) | LFPR, WPR, UR, status mix, agriculture share | Yes | 2.2–2.4 |

**Not obtained** (details in section 6): Das (2023), IJLE s41027-022-00425-2, which has the four 2019-20 panels and the Markov matrices, is paywalled, and none of its matrices could be read. Singh (2023), the gross-flows paper, is also paywalled; only the numbers in its abstract are available. **Note:** DOI s41027-023-00434-9 is *not* Singh. It is the published version of Bhattacharya, "Indian Urban Workers' Labour Market Transitions", IJLE 66(2):471–494 (27 Apr 2023), also paywalled. Singh's paper is s41027-022-00417-2 (IJLE 66:81–111, 18 Jan 2023). The DOI-to-title mapping was checked in Crossref metadata.

---

## 1. Urban transition matrices

### 1.1 Bhattacharya (2021), "Indian urban workers' labour market transitions", arXiv 2110.05482v2 (14 Nov 2021), Table 4, p. 10

- **Data:** PLFS urban rotational panel. Panels P11–P22 were linked across the 2017-18, 2018-19 and 2019-20 releases using the author's FSU re-matching. Ages 15–65. Period 2017-Q3 to 2019-Q4, with COVID excluded (p. 7). Status is CWS, using NSSO sampling weights.
- **Time unit:** quarterly (t to t+1). Each matrix is the **average of the quarterly matrices** over the study period (p. 9).
- **States** (Table 2, p. 8):

| State | PLFS codes |
|---|---|
| slf-emp: own-account, employer or helper in a household enterprise | 11, 12, 21 |
| csl-emp: casual wage labour | 41, 42, 51 |
| sal-emp: regular salaried / wage | 31 |
| sck-emp: had work, did not work because of sickness | 61, 71 |
| nwrk: had work, did not work for other reasons | 62, 72 |
| unemp: unemployed | 81, 82 |
| nopart: not in labour force | 91, 92, 93, 94, 95, 97, 98, 99 |
| attrit: attrited from the sample | — |

- **Out of labour force is NOT split** into students, domestic duties and others. All NLF codes 91–99 are pooled (Table 2; repo `src/lib/code_values.R`). The only split-related figures are in the text on p. 21: 81.1% of the "very young" (15–20) who are not employed report attending an educational institution, and 27.55% of those in that age group who leave employment report attending one the next quarter.
- Rows sum to 100 **including the attrition column**. To use a row as a closed Markov row, drop `attrit` and renormalise **[derived step, not done here]**.
- "Occupancy" is the row total: the % of the sex's population in the state at t.

**Female: quarterly transition probabilities, % of row (Table 4, numbers in parentheses)**

| t \ t+1 | slf-emp | csl-emp | sal-emp | unemp | nopart | sck-emp | nwrk | attrit | occupancy at t (%) |
|---|---|---|---|---|---|---|---|---|---|
| slf-emp | 79.97 | 0.66 | 1.52 | 0.92 | 13.53 | 0.29 | 1.58 | 1.52 | 5.82 |
| csl-emp | 3.44 | 67.27 | 5.11 | 4.25 | 17.66 | 0.07 | 0.28 | 1.91 | 1.78 |
| sal-emp | 0.77 | 0.52 | 86.98 | 1.02 | 5.72 | 0.17 | 1.74 | 3.09 | 10.06 |
| unemp | 1.78 | 3.31 | 4.10 | 63.60 | 22.92 | 0.01 | 0.12 | 4.16 | 2.46 |
| nopart | 0.96 | 0.32 | 0.71 | 0.63 | 95.12 | 0.01 | 0.04 | 2.22 | 79.43 |
| sck-emp | 23.93 | 0.00 | 38.05 | 1.82 | 17.68 | 11.50 | 4.99 | 2.03 | 0.06 |
| nwrk | 25.87 | 1.19 | 42.27 | 1.29 | 11.76 | 0.76 | 13.71 | 3.15 | 0.39 |
| ALL (occupancy at t+1) | 5.71 | 1.63 | 9.78 | 2.31 | 77.85 | 0.05 | 0.36 | 2.31 | 100 |

**Male: quarterly transition probabilities, % of row (Table 4)**

| t \ t+1 | slf-emp | csl-emp | sal-emp | unemp | nopart | sck-emp | nwrk | attrit | occupancy at t (%) |
|---|---|---|---|---|---|---|---|---|---|
| slf-emp | 90.27 | 1.22 | 2.16 | 1.34 | 1.31 | 0.25 | 1.21 | 2.23 | 26.73 |
| csl-emp | 3.63 | 82.06 | 3.60 | 4.98 | 2.39 | 0.06 | 0.38 | 2.90 | 9.62 |
| sal-emp | 1.69 | 0.87 | 90.69 | 1.52 | 1.04 | 0.14 | 0.86 | 3.18 | 33.16 |
| unemp | 5.50 | 7.93 | 7.22 | 65.29 | 8.70 | 0.04 | 0.37 | 4.96 | 6.80 |
| nopart | 1.44 | 0.93 | 1.33 | 2.45 | 90.97 | 0.02 | 0.06 | 2.82 | 22.52 |
| sck-emp | 42.38 | 4.68 | 27.04 | 3.01 | 5.94 | 10.76 | 3.25 | 2.94 | 0.20 |
| nwrk | 42.18 | 5.01 | 30.61 | 4.40 | 2.47 | 0.59 | 11.16 | 3.59 | 0.96 |
| ALL (occupancy at t+1) | 26.23 | 9.31 | 32.14 | 6.38 | 22.04 | 0.15 | 0.80 | 2.94 | 100 |

Stylised facts from the text (pp. 11–13):
- Each quarter, on average, **6.32% of women and 10.68% of men change labour-market state** (p. 11).
- Salaried → (unemployed + NLF) per quarter is **6.74% for women** (1.02 + 5.72) and **2.56% for men** (1.52 + 1.04) (p. 11).
- Each quarter, 0.10% of women move salaried → unemployed and 0.10% move back (p. 11).
- Of the male population, 0.49% move unemployed → salaried each quarter, against 0.35% casual → salaried and 0.58% self-employed → salaried. The author treats these as evidence that "job-to-job flows are significant", but **employer changes are not observable** because PLFS has no employer identifier (p. 12).
- Each quarter, 0.17% of women move salaried → "nwrk" against 0.10% salaried → unemployed (pp. 12–13).
- Earnings on entering "nwrk" (Figure 1, p. 13):
  - Salaried: about 50% have unchanged earnings, about 25% higher and about 25% lower.
  - Self-employed: about 25% unchanged, about 25% higher and about 50% lower.

Attrition of households by visit (Table 3, p. 8):

| Panel | Visit 2 (%) | Visit 3 (%) | Visit 4 (%) |
|---|---|---|---|
| P11 | 2.6 | 4.0 | 5.3 |
| P12 | 2.1 | 3.6 | 4.0 |
| P13 | 2.5 | 3.1 | 3.8 |
| P14 | 1.8 | 2.9 | 3.8 |
| P15 | 1.5 | 2.7 | 2.6 |
| P16 | 1.7 | 1.6 | 4.7 |
| P17 | 0.0 | 3.9 | 0.4 |
| P18 | 2.5 | 0.2 | — |
| P21 | 0.7 | — | — |

The author notes that attrition is of the same magnitude as the gross flows (pp. 8–9).

### 1.2 Bhattacharya: dependence on age, education, family and employment history (Table 7, p. 20)

- **Method:** logit with outcomes Lost (employed at t, not employed at t+1) and Gained (not employed at t, employed at t+1), estimated separately by sex. Values are **average marginal effects on the quarterly probability** (standard errors in parentheses). Period and visit dummies are included.
- **Variables:**
  - Very.Young: age < 21.
  - Young: age 21–30.
  - Graduate: graduate or higher.
  - Has.Child: household has a child under 5.
  - Married.
  - E.Ratio = (quarters employed − quarters not employed) / visit number.
  - EN.Streak: consecutive quarters in the current state. The baseline is 1.

| Variable | Gained (Female) | Gained (Male) | Lost (Female) | Lost (Male) |
|---|---|---|---|---|
| Very.Young | −0.015*** (0.001) | −0.054*** (0.004) | 0.077*** (0.013) | 0.027*** (0.003) |
| Young | 0.001 (0.001) | 0.019*** (0.004) | 0.022*** (0.005) | 0.007*** (0.002) |
| Graduate | −0.003** (0.001) | −0.028*** (0.002) | −0.043*** (0.004) | −0.012*** (0.001) |
| Has.Child | −0.005*** (0.001) | 0.014*** (0.003) | 0.009 (0.005) | 0.002 (0.001) |
| Married | −0.007*** (0.001) | 0.037*** (0.005) | 0.036*** (0.004) | −0.026*** (0.002) |
| E.Ratio | 0.052*** (0.003) | 0.120*** (0.008) | −0.089*** (0.012) | −0.039*** (0.004) |
| EN.Streak=2 | −0.014*** (0.003) | −0.030*** (0.007) | −0.065*** (0.012) | −0.021*** (0.005) |
| EN.Streak=3 | −0.020*** (0.004) | −0.046*** (0.011) | −0.099*** (0.015) | −0.034*** (0.006) |

Significance: *** p<0.001, ** p<0.01, * p<0.05.

Interpretation (pp. 20–22):
- **Duration dependence:** inertia rises with streak length, in both employment and non-employment.
- **Employment history:** past employment raises the gain probability and lowers the loss probability, even after controlling for streaks (E.Ratio).
- **Marriage:** married men lose jobs less and gain more; married women lose more and gain less.

### 1.3 Bhattacharya: turnover by industry and state (Tables 5–6, pp. 17–18)

- **Dependent variable:** quarterly gross flow rate = entry rate + exit rate (bounded 0–2). Each rate is computed on average occupancy at t and t+1 (p. 14).
- **Coverage:** only coefficients significant at 5% are shown. There is no intercept.

**Table 5: industry × employment type × sex coefficients (gross flow rate)**

| Industry (NIC 2008, 2-digit) | Type | Female | Male |
|---|---|---|---|
| Manufacture of chemicals (20) | sal | | 0.26 |
| Food & beverage service (56) | sal | | 0.27 |
| Manufacture of food products (10) | slf | | 0.27 |
| Wholesale trade (46) | sal | | 0.30 |
| Land transport (49) | csl | | 0.33 |
| Other manufacturing (32) | sal | | 0.34 |
| Land transport (49) | slf | | 0.34 |
| Wholesale trade (46) | slf | | 0.39 |
| Computer programming (62) | sal | 0.47 | 0.32 |
| Security & investigation (80) | sal | | 0.40 |
| Public administration & defence (84) | sal | 0.50 | 0.30 |
| Education (85) | sal | 0.47 | 0.34 |
| Land transport (49) | sal | | 0.41 |
| Wearing apparel (14) | sal | 0.55 | 0.29 |
| Textiles (13) | sal | 0.49 | 0.34 |
| Food & beverage service (56) | slf | 0.49 | 0.36 |
| Human health (86) | sal | 0.43 | |
| Households as employers of domestic personnel (97) | sal | 0.46 | 0.41 |
| Other personal services (96) | sal | 0.44 | |
| Retail trade (47) | slf | 0.54 | 0.33 |
| Crop & animal production (01) | slf | 0.52 | 0.35 |
| Wearing apparel (14) | slf | 0.65 | 0.27 |
| Financial services (64) | sal | 0.63 | 0.30 |
| Tobacco products (12) | slf | 0.46 | |
| Retail trade (47) | sal | 0.55 | 0.43 |
| Specialised construction (43) | csl | | 0.50 |
| Construction of buildings (41) | slf | | 0.51 |
| Textiles (13) | slf | 0.57 | 0.44 |
| Crop & animal production (01) | csl | 0.72 | 0.30 |
| Construction of buildings (41) | csl | 0.60 | 0.49 |
| Other personal services (96) | slf | 0.86 | 0.33 |
| Education (85) | slf | 0.64 | |
| Textiles (13) | csl | 1.00 | |
| Rubber & plastic products (22) | sal | | 1.06 |

**Table 6: significant state effects** (baseline Maharashtra-Male; Female / Male)

| State | Female | Male |
|---|---|---|
| Telangana | −0.16 | −0.08 |
| Karnataka | −0.11 | |
| Gujarat | −0.09 | −0.05 |
| Maharashtra | −0.08 | |
| Andhra Pradesh | −0.08 | −0.06 |
| Tamil Nadu | −0.07 | |
| Madhya Pradesh | | +0.04 |
| Uttar Pradesh | | +0.06 |
| Haryana | | +0.09 |
| Kerala | | +0.09 |

### 1.3a Replication repository (github.com/jmoy/plfs-jb), checked 21 Nov 2026

- **No CSV or log output contains a transition matrix.**
- Results are stored only as R binary save files: `artefacts/res_transitions.rds`, `res_gross_flows.rds` and `res_gained_lost.rds`. `src/transitions.Rmd` shows that `res_transitions.rds` holds the objects behind Table 4 (`tab_transmat`). The files could not be read because R is not installed. They should reproduce the paper's tables.
- **Potentially useful:** `artefacts/linked_pers.parquet` (28 MB) and `rewritten_pp.parquet` (30 MB) hold the linked person-level urban panel with raw status codes. From these, a quarterly matrix **with NLF split into 91 (education) / 92–93 (domestic duties) / other** could be computed. That would be a new estimate, not a published figure, so it was not done here.

### 1.4 MoSPI PLFS Quarterly Bulletin, Oct–Dec 2024 (urban; 25th bulletin), Appendix A, Table (5), pp. A-27 to A-30

- **Source:** "Percentage distribution of persons of age 15 years and above by different activity statuses between adjacent quarters in current weekly status". This is the official urban panel cross-tabulation (the most recent one; urban-only bulletins ended in Dec 2024).
- **Cells are joint % of all persons of that sex surveyed in both quarters.** The whole table sums to 100; the "all" column is the row total. These are **not** row-conditional probabilities.
- `*` means nil or negligible.
- "All self-employed" includes self-employed persons who had work but did not work, so it can exceed the sum of the first two columns.
- Time unit: quarterly. NLF is not split.
- The fourth table's header prints the from-quarter as "July - September 2023". From the sequence it must be Jul–Sep 2024 (a typo in the bulletin).

**Pair 1: Oct–Dec 2023 (rows) → Jan–Mar 2024 (columns), p. A-27**

Male

| row → col | own account/employer | helper (unpaid family) | all self-employed# | regular wage/salary | casual labour | unemployed | not in labour force | all |
|---|---|---|---|---|---|---|---|---|
| own account worker, employer | 23.3 | 0.1 | 23.7 | 0.3 | 0.1 | 0.1 | 0.2 | 24.4 |
| helper in household enterprise | 0.1 | 2.9 | 3.0 | * | * | * | 0.1 | 3.2 |
| self employed | 23.90 | 3.0 | 27.4 | 0.3 | 0.2 | 0.2 | 0.3 | 28.4 |
| regular wage/ salary | 0.3 | * | 0.3 | 32.1 | 0.2 | 0.4 | 0.1 | 33.1 |
| casual labour | 0.1 | * | 0.2 | 0.1 | 7.7 | 0.5 | 0.1 | 8.6 |
| unemployed | 0.1 | * | 0.1 | 0.2 | 0.4 | 3.4 | 0.1 | 4.2 |
| not in labour force | 0.1 | * | 0.2 | 0.1 | 0.2 | 0.1 | 25.2 | 25.7 |
| all | 24.5 | 3.1 | 28.2 | 32.9 | 8.6 | 4.5 | 25.8 | 100.0 |

Female

| row → col | own account/employer | helper (unpaid family) | all self-employed# | regular wage/salary | casual labour | unemployed | not in labour force | all |
|---|---|---|---|---|---|---|---|---|
| own account worker, employer | 5.5 | 0.1 | 5.7 | 0.1 | * | * | 0.4 | 6.2 |
| helper in household enterprise | 0.1 | 2.7 | 2.7 | * | * | * | 0.3 | 3.1 |
| self employed | 5.8 | 2.8 | 8.8 | 0.1 | * | * | 0.7 | 9.6 |
| regular wage/ salary | 0.1 | * | 0.1 | 11.5 | * | 0.1 | 0.3 | 12.0 |
| casual labour | * | * | 0.1 | * | 1.2 | 0.1 | 0.2 | 1.5 |
| unemployed | * | * | * | 0.1 | 0.1 | 1.8 | 0.2 | 2.1 |
| not in labour force | 0.3 | 0.2 | 0.6 | 0.3 | 0.1 | 0.2 | 73.5 | 74.7 |
| all | 6.2 | 3.0 | 9.5 | 12.0 | 1.4 | 2.1 | 74.9 | 100.0 |

**Pair 2: Jan–Mar 2024 → Apr–Jun 2024, p. A-28**

Male

| row → col | own account/employer | helper (unpaid family) | all self-employed# | regular wage/salary | casual labour | unemployed | not in labour force | all |
|---|---|---|---|---|---|---|---|---|
| own account worker, employer | 23.3 | 0.1 | 23.8 | 0.2 | 0.1 | 0.1 | 0.1 | 24.3 |
| helper in household enterprise | 0.1 | 3.0 | 3.1 | * | * | * | 0.1 | 3.2 |
| self employed | 23.90 | 3.0 | 27.5 | 0.2 | 0.1 | 0.1 | 0.2 | 28.2 |
| regular wage/ salary | 0.2 | * | 0.2 | 32.2 | 0.1 | 0.3 | 0.1 | 32.9 |
| casual labour | 0.1 | * | 0.1 | 0.1 | 8.1 | 0.3 | 0.1 | 8.8 |
| unemployed | 0.1 | 0.1 | 0.2 | 0.3 | 0.4 | 3.6 | 0.1 | 4.6 |
| not in labour force | 0.1 | 0.1 | 0.1 | 0.1 | 0.1 | 0.1 | 25.1 | 25.5 |
| all | 24.4 | 3.2 | 28.2 | 32.9 | 8.9 | 4.4 | 25.7 | 100.0 |

Female

| row → col | own account/employer | helper (unpaid family) | all self-employed# | regular wage/salary | casual labour | unemployed | not in labour force | all |
|---|---|---|---|---|---|---|---|---|
| own account worker, employer | 5.7 | * | 5.9 | 0.1 | 0.1 | * | 0.5 | 6.5 |
| helper in household enterprise | * | 2.5 | 2.6 | * | * | * | 0.4 | 3.0 |
| self employed | 5.9 | 2.6 | 8.7 | 0.1 | 0.1 | * | 0.9 | 9.8 |
| regular wage/ salary | 0.1 | * | 0.1 | 11.9 | * | 0.1 | 0.3 | 12.3 |
| casual labour | * | * | * | * | 1.2 | 0.1 | 0.2 | 1.6 |
| unemployed | * | * | * | 0.1 | 0.1 | 1.8 | 0.2 | 2.2 |
| not in labour force | 0.3 | 0.2 | 0.5 | 0.3 | 0.1 | 0.2 | 73.0 | 74.1 |
| all | 6.4 | 2.8 | 9.4 | 12.3 | 1.4 | 2.2 | 74.7 | 100.0 |

**Pair 3: Apr–Jun 2024 → Jul–Sep 2024, p. A-29**

Male

| row → col | own account/employer | helper (unpaid family) | all self-employed# | regular wage/salary | casual labour | unemployed | not in labour force | all |
|---|---|---|---|---|---|---|---|---|
| own account worker, employer | 23.2 | 0.1 | 23.7 | 0.2 | 0.1 | 0.1 | 0.1 | 24.2 |
| helper in household enterprise | 0.1 | 2.7 | 2.8 | * | * | * | 0.1 | 3.0 |
| self employed | 23.70 | 2.8 | 27.3 | 0.2 | 0.1 | 0.1 | 0.2 | 27.9 |
| regular wage/ salary | 0.2 | * | 0.3 | 33.0 | 0.1 | 0.3 | 0.2 | 33.8 |
| casual labour | 0.2 | * | 0.2 | 0.1 | 8.1 | 0.5 | 0.2 | 9.0 |
| unemployed | 0.1 | 0.1 | 0.1 | 0.3 | 0.4 | 3.1 | 0.1 | 4.1 |
| not in labour force | 0.1 | 0.1 | 0.2 | 0.1 | 0.1 | 0.1 | 24.7 | 25.3 |
| all | 24.3 | 3.0 | 28.0 | 33.7 | 8.8 | 4.1 | 25.4 | 100.0 |

Female

| row → col | own account/employer | helper (unpaid family) | all self-employed# | regular wage/salary | casual labour | unemployed | not in labour force | all |
|---|---|---|---|---|---|---|---|---|
| own account worker, employer | 5.7 | * | 5.9 | 0.1 | * | * | 0.4 | 6.3 |
| helper in household enterprise | 0.0 | 2.2 | 2.3 | * | * | * | 0.2 | 2.5 |
| self employed | 5.9 | 2.3 | 8.3 | 0.1 | * | * | 0.6 | 9.1 |
| regular wage/ salary | * | * | 0.1 | 12.0 | * | 0.1 | 0.3 | 12.5 |
| casual labour | * | * | * | 0.0 | 1.1 | 0.1 | 0.2 | 1.4 |
| unemployed | * | * | * | 0.1 | 0.1 | 1.7 | 0.2 | 2.2 |
| not in labour force | 0.4 | 0.3 | 0.7 | 0.3 | 0.2 | 0.2 | 73.5 | 74.9 |
| all | 6.3 | 2.6 | 9.2 | 12.6 | 1.3 | 2.2 | 74.8 | 100.0 |

**Pair 4: Jul–Sep 2024 (header misprinted "2023") → Oct–Dec 2024, p. A-30**

Male

| row → col | own account/employer | helper (unpaid family) | all self-employed# | regular wage/salary | casual labour | unemployed | not in labour force | all |
|---|---|---|---|---|---|---|---|---|
| own account worker, employer | 23.3 | 0.1 | 23.8 | 0.2 | 0.1 | 0.1 | 0.1 | 24.3 |
| helper in household enterprise | 0.1 | 2.8 | 2.9 | * | * | * | * | 3.0 |
| self employed | 24.0 | 2.8 | 27.5 | 0.2 | 0.1 | 0.1 | 0.2 | 28.2 |
| regular wage/ salary | 0.3 | * | 0.3 | 33.2 | 0.1 | 0.3 | 0.1 | 34.0 |
| casual labour | 0.1 | * | 0.1 | 0.1 | 8.1 | 0.4 | 0.2 | 8.9 |
| unemployed | 0.1 | * | 0.2 | 0.2 | 0.5 | 3.4 | 0.1 | 4.3 |
| not in labour force | 0.1 | * | 0.2 | 0.2 | 0.1 | 0.1 | 24.1 | 24.7 |
| all | 24.7 | 3.0 | 28.3 | 33.9 | 8.8 | 4.3 | 24.7 | 100.0 |

Female

| row → col | own account/employer | helper (unpaid family) | all self-employed# | regular wage/salary | casual labour | unemployed | not in labour force | all |
|---|---|---|---|---|---|---|---|---|
| own account worker, employer | 5.8 | * | 5.9 | * | * | * | 0.5 | 6.5 |
| helper in household enterprise | 0.1 | 2.4 | 2.5 | * | * | * | 0.3 | 2.8 |
| self employed | 5.9 | 2.5 | 8.6 | 0.1 | * | * | 0.8 | 9.5 |
| regular wage/ salary | 0.1 | 0.0 | 0.1 | 12.0 | 0.0 | 0.1 | 0.2 | 12.4 |
| casual labour | * | * | * | * | 1.1 | 0.1 | 0.2 | 1.4 |
| unemployed | * | * | * | 0.1 | * | 1.7 | 0.2 | 2.0 |
| not in labour force | 0.3 | 0.2 | 0.5 | 0.3 | 0.2 | 0.1 | 73.6 | 74.7 |
| all | 6.3 | 2.7 | 9.2 | 12.4 | 1.4 | 2.0 | 75.0 | 100.0 |

**[derived] Row-conditional quarterly probabilities (% of row), pooled over the four pairs above**

- **Method:** for each cell, sum the cell over the four pairs and divide by the sum of the row's "all" over the four pairs. `*` is treated as 0.
- "Residual" = 100 − shown cells. It covers self-employed persons who had work but did not work, plus rounding.
- **Caution:** the published cells are rounded to 0.1 points. For small rows (female casual 1.4–1.6, female unemployed 2.0–2.2) each 0.1 is worth about 5–7 points of conditional probability, so treat these rows as rough.

Male

| from \ to | own account/employer | helper | regular | casual | unemployed | NLF | residual |
|---|---|---|---|---|---|---|---|
| own account worker, employer | 95.8 | 0.4 | 0.9 | 0.4 | 0.4 | 0.5 | 1.5 |
| helper in household enterprise | 3.2 | 91.9 | 0.0 | 0.0 | 0.0 | 2.4 | 2.4 |
| regular wage/ salary | 0.7 | 0.0 | 97.5 | 0.4 | 1.0 | 0.4 | 0.0 |
| casual labour | 1.4 | 0.0 | 1.1 | 90.7 | 4.8 | 1.7 | 0.3 |
| unemployed | 2.3 | 1.2 | 5.8 | 9.9 | 78.5 | 2.3 | 0.0 |
| not in labour force | 0.4 | 0.2 | 0.5 | 0.5 | 0.4 | 97.9 | 0.1 |

Female

| from \ to | own account/employer | helper | regular | casual | unemployed | NLF | residual |
|---|---|---|---|---|---|---|---|
| own account worker, employer | 89.0 | 0.4 | 1.2 | 0.4 | 0.0 | 7.1 | 2.0 |
| helper in household enterprise | 1.8 | 86.0 | 0.0 | 0.0 | 0.0 | 10.5 | 1.8 |
| regular wage/ salary | 0.6 | 0.0 | 96.3 | 0.0 | 0.8 | 2.2 | 0.0 |
| casual labour | 0.0 | 0.0 | 0.0 | 78.0 | 6.8 | 13.6 | 1.7 |
| unemployed | 0.0 | 0.0 | 4.7 | 3.5 | 82.4 | 9.4 | 0.0 |
| not in labour force | 0.4 | 0.3 | 0.4 | 0.2 | 0.2 | 98.4 | 0.0 |

The same bulletin's Table (6), pp. A-31 onward, gives industry-to-industry (agriculture / secondary / tertiary) joint distributions for workers employed in both quarters. Not transcribed.

### 1.5 Joshi & Joshi, "Recent Estimates of Dynamic Mobility of Persons in Current Weekly Activity Status Based on Markov Chain", *Sarvekshana* 114th issue (MoSPI, March 2023), Tables 3–5, pp. 30–32

- Urban, 15+, CWS. States: 1 = employed, 2 = unemployed, 3 = out of labour force.
- p_ij is the quarterly probability of moving from state i in the previous quarter to state j in the quarter labelled. Rows sum to 1.
- The authors derived these from the bulletins' Table 5, the same kind of table as 1.4 (p. 29). Because that table is rounded to 0.1 points, values such as p21 are very coarse.
- See the data-quality flags below the tables.

Males (Table 4)

| quarter | p11 | p12 | p13 | p21 | p22 | p23 | p31 | p32 | p33 |
|---|---|---|---|---|---|---|---|---|---|
| Jul-Sep 2018 | 0.9612 | 0.0239 | 0.0149 | 0.2540 | 0.6508 | 0.0952 | 0.0337 | 0.0262 | 0.9401 |
| Oct-Dec 2018 | 0.9643 | 0.0223 | 0.0134 | 0.2222 | 0.6825 | 0.0952 | 0.0303 | 0.0265 | 0.9432 |
| Jan-Mar 2019 | 0.9685 | 0.0121 | 0.0135 | 0.2500 | 0.6618 | 0.0882 | 0.0301 | 0.0051 | 0.9511 |
| Apr-Jun 2019 | 0.9673 | 0.0164 | 0.0164 | 0.2031 | 0.7031 | 0.0938 | 0.0303 | 0.0152 | 0.9545 |
| Jul-Sep 2019 | 0.9688 | 0.0148 | 0.0163 | 0.2167 | 0.7000 | 0.0833 | 0.0414 | 0.0188 | 0.9398 |
| Oct-Dec 2019 | 0.9362 | 0.0053 | 0.0585 | 0.1000 | 0.8000 | 0.1000 | 0.0139 | 0.0038 | 0.9823 |
| Jan-Mar 2020 | 0.9620 | 0.0234 | 0.0146 | 0.1481 | 0.7778 | 0.0741 | 0.0230 | 0.0153 | 0.9617 |
| Apr-Jun 2020 | 0.8195 | 0.1420 | 0.0385 | 0.0794 | 0.8571 | 0.0635 | 0.0153 | 0.0153 | 0.9693 |
| Jul-Sep 2020 | 0.9740 | 0.0191 | 0.0069 | 0.4056 | 0.5594 | 0.0350 | 0.0676 | 0.0178 | 0.9146 |
| Oct-Dec 2020 | 0.9799 | 0.0124 | 0.0077 | 0.2667 | 0.6889 | 0.0444 | 0.0227 | 0.0114 | 0.9659 |
| Jan-Mar 2021 | 0.9701 | 0.0179 | 0.0119 | 0.1846 | 0.7692 | 0.0462 | 0.0189 | 0.0113 | 0.9698 |
| Apr-Jun 2021 | 0.9263 | 0.0575 | 0.0162 | 0.1167 | 0.8333 | 0.0500 | 0.0191 | 0.0076 | 0.9733 |
| Jul-Sep 2021 | 0.9736 | 0.0155 | 0.0109 | 0.3218 | 0.6437 | 0.0345 | 0.0297 | 0.0112 | 0.9591 |
| Oct-Dec 2021 | 0.9746 | 0.0164 | 0.0090 | 0.2121 | 0.7273 | 0.0606 | 0.0226 | 0.0113 | 0.9660 |

Females (Table 5)

| quarter | p11 | p12 | p13 | p21 | p22 | p23 | p31 | p32 | p33 |
|---|---|---|---|---|---|---|---|---|---|
| Jul-Sep 2018 | 0.8935 | 0.0118 | 0.0947 | 0.0833 | 0.7083 | 0.2083 | 0.0223 | 0.0074 | 0.9703 |
| Oct-Dec 2018 | 0.8817 | 0.0178 | 0.1006 | 0.0455 | 0.6818 | 0.2727 | 0.0173 | 0.0037 | 0.9790 |
| Jan-Mar 2019 | 0.8953 | 0.0058 | 0.0988 | 0.1304 | 0.6087 | 0.2609 | 0.0174 | 0.0075 | 0.9752 |
| Apr-Jun 2019 | 0.8817 | 0.0178 | 0.1006 | 0.0455 | 0.6818 | 0.2727 | 0.0173 | 0.0037 | 0.9790 |
| Jul-Sep 2019 | 0.9123 | 0.0058 | 0.0819 | 0.0909 | 0.6364 | 0.2727 | 0.0235 | 0.0050 | 0.9715 |
| Oct-Dec 2019 | 0.9704 | 0.0091 | 0.0205 | 0.1579 | 0.7632 | 0.0789 | 0.0153 | 0.0057 | 0.9790 |
| Jan-Mar 2020 | 0.9050 | 0.0200 | 0.0750 | 0.0476 | 0.7619 | 0.1905 | 0.0141 | 0.0039 | 0.9820 |
| Apr-Jun 2020 | 0.7413 | 0.0945 | 0.1642 | 0.0435 | 0.8261 | 0.1304 | 0.0052 | 0.0039 | 0.9910 |
| Jul-Sep 2020 | 0.9161 | 0.0129 | 0.0710 | 0.1951 | 0.6829 | 0.1220 | 0.0199 | 0.0025 | 0.9776 |
| Oct-Dec 2020 | 0.9379 | 0.0056 | 0.0565 | 0.1250 | 0.7500 | 0.1250 | 0.0076 | 0.0025 | 0.9899 |
| Jan-Mar 2021 | 0.9227 | 0.0166 | 0.0608 | 0.1111 | 0.7778 | 0.1111 | 0.0101 | 0.0025 | 0.9874 |
| Apr-Jun 2021 | 0.8505 | 0.0412 | 0.1082 | 0.0870 | 0.7826 | 0.1304 | 0.0064 | 0.0038 | 0.9898 |
| Jul-Sep 2021 | 0.9017 | 0.0116 | 0.0867 | 0.1786 | 0.6786 | 0.1429 | 0.0125 | 0.0025 | 0.9850 |
| Oct-Dec 2021 | 0.9106 | 0.0056 | 0.0838 | 0.0870 | 0.7391 | 0.1739 | 0.0113 | 0.0038 | 0.9850 |

**Data-quality flags (implausible or copied values in the published tables):**
- Female Oct-Dec 2018 and Apr-Jun 2019 are identical in every cell. The same is true of persons (Table 3).
- Female Oct-Dec 2019 is identical to persons Oct-Dec 2019 in every cell. It is almost certainly a copy error, and it is why female E→NLF drops to 0.0205 that quarter against 0.08–0.10 in neighbouring quarters.
- Male Oct-Dec 2019 p13 = 0.0585 is about 4× its neighbours.
- Male Jan-Mar 2019 row 1 sums to 0.9941, not 1.

Use the 2024 official table (1.4) in preference to this one.

### 1.6 Menon & Nath, "How Dynamic are India's Labour Markets?", *The India Forum*, 10 June 2022, Tables 1–3

- Urban PLFS, CWS. Persons unemployed in Quarter 1 of 2017-18 or 2018-19 are followed to Quarter 4 of the same survey year, which is **three quarters later**, although the authors call it "over a given year".
- Only rows starting from unemployment are published. NLF is not split.

| U in Q1 → status in Q4 | All 2017-18 | All 2018-19 | Men 2017-18 | Men 2018-19 | Women 2017-18 | Women 2018-19 |
|---|---|---|---|---|---|---|
| U → E | 22.2% | 24.3% | 27.6% | 29.1% | 8.4% | 13% |
| U → U | 58.1% | 58.2% | 59.1% | 60.2% | 55.6% | 53.5% |
| U → O (out of LF) | 19.7% | 17.5% | 13.3% | 10.7% | 36% | 33.5% |
| n unemployed in Q1 (sample) | 1,564 | 1,550 | 1,125 | 1,088 | 439 | 462 |

By education (Table 3):

| U in Q1 → Q4 | Schooling 2017-18 | Schooling 2018-19 | Graduates 2017-18 | Graduates 2018-19 |
|---|---|---|---|---|
| U → E | 28.9% | 30.7% | 13.2% | 14.9% |
| U → U | 52.6% | 51.4% | 67.6% | 68.2% |
| U → O | 18.5% | 18% | 19.2% | 16.9% |
| n | 813 | 740 | 689 | 724 |

Table 4 gives the share of jobs created / lost by sector:

| Sector | Created 2017-18 | Lost 2017-18 | Created 2018-19 | Lost 2018-19 |
|---|---|---|---|---|
| Agriculture | 6.67% | 9.7% | 6.63% | 10% |
| Construction | 24.93% | 22.99% | 23.34% | 17.33% |
| Manufacturing | 13.62% | 19.67% | 15.12% | 17.33% |
| Services | 54.51% | 46.43% | 52.51% | 54.33% |
| Wholesale & retail trade | 16.81% | 16.82% | 12.73% | 24.67% |

### 1.7 Singh (2023), "Unemployment Fluctuations in Urban Labour Market in India", IJLE 66:81–111 (DOI 10.1007/s41027-022-00417-2): abstract only (paywalled)

- Urban PLFS quarterly gross flows, three states (E, U, N). No matrix is accessible.
- In upturns the employment margin contributes about **80%** of the decline in unemployment. In downturns it contributes about **98%** of the rise.
- Women's higher UR comes from lower job finding and higher U→U persistence. Women have a higher probability of dropping out of the labour force.
- Youth face higher job loss and longer unemployment spells.
- The better educated face difficulty finding jobs, higher job-loss chances and longer unemployment.

---

## 2. Rural and seasonal evidence

**Bottom line:** no published rural gross-flow matrix (monthly or seasonal) exists for India as of Nov 2026.
- The revamped PLFS (from Jan 2025) has a **rural rotational panel**: 4 consecutive monthly visits, 75% FSU overlap month to month (PIB 15 Jul 2025, Annexure II). MoSPI publishes only stock indicators from it.
- The PLFS 2025 annual report press release (PIB, 27 Mar 2026) says "the unit-level data pertaining to the first visit have been disseminated". The microdata portal catalogue 292 lists quarterly files for Apr-Jun 2025 to Oct-Dec 2025 (seen in search results only; not opened). Whether revisit records are released and linkable was **not confirmed**.

### 2.1 CMIE CPHS, rural and urban women: Deshpande & Singh, "Dropping Out, Being Pushed Out or Can't Get In?", IZA DP 14639 (2021)

- **Data:** CPHS waves 7–18 (Jan-Apr 2016 to Sep-Dec 2019). Status is the day of or the day before the survey (p. 10).
- **Time unit:** **one wave = about 4 months** (p. 10).
- **Labour force definition:** "unemployed, willing but not looking" is counted as in the labour force (p. 11).
- **Entry** = out of labour force (OLF) → in labour force (ILF) by the next wave. **Exit** = ILF → OLF by the next wave.

**Table A.1, Rural women (15+), p. 61: entry and exit per 4-month wave**

| Group | ILF share | OLF share | Entry (from OLF) | Exit (from ILF) | Obs |
|---|---|---|---|---|---|
| **All rural women** | 0.154 | 0.846 | **0.041** | **0.285** | 745,458 |
| Age 15-25 | 0.112 | 0.888 | 0.042 | 0.389 | 190,589 |
| Age 26-40 | 0.187 | 0.813 | 0.045 | 0.250 | 240,081 |
| Age 41-55 | 0.177 | 0.823 | 0.042 | 0.249 | 204,605 |
| Age 55+ | 0.107 | 0.893 | 0.030 | 0.345 | 110,183 |
| Illiterate | 0.184 | 0.816 | 0.048 | 0.300 | 137,520 |
| Primary & below | 0.145 | 0.855 | 0.034 | 0.249 | 258,647 |
| Middle & secondary | 0.127 | 0.873 | 0.037 | 0.315 | 236,592 |
| Higher secondary | 0.152 | 0.848 | 0.052 | 0.317 | 80,809 |
| UG | 0.267 | 0.733 | 0.081 | 0.264 | 26,505 |
| PG & above | 0.399 | 0.601 | 0.091 | 0.177 | 5,385 |
| Married | 0.127 | 0.873 | 0.026 | 0.199 | 102,054 |
| Unmarried | 0.107 | 0.893 | 0.037 | 0.234 | 27,675 |
| Widowed/separated | 0.253 | 0.747 | 0.036 | 0.141 | 11,425 |
| SC | 0.176 | 0.824 | 0.042 | 0.246 | 172,392 |
| ST | 0.238 | 0.762 | 0.070 | 0.273 | 72,937 |
| OBC | 0.143 | 0.857 | 0.039 | 0.303 | 293,886 |
| Upper caste | 0.094 | 0.906 | 0.027 | 0.318 | 103,580 |

Marital status is available for the last three waves only.

**Table A.2, Urban women, p. 62**
- All: ILF 0.141; entry **0.041**; exit **0.317**.
- Age 15-25: entry 0.059, exit 0.365.
- Age 55+: entry 0.018, exit 0.432.
- Married: entry 0.023, exit 0.289.
- Unmarried: entry 0.062, exit 0.223.

From the text:
- **Men (rural and urban pooled), per wave:** about **5% of men in the labour force exit** and about **15% of men out of it enter** (p. 13). Women's exit rate is about 30% (24–30% across waves) and entry about 4% (p. 13).
- **Employed ↔ not employed (women):** "around three percent of women from 'not employed' are found 'employed' in the next wave" and "more than 18 percent of the 'employed' women are found to be 'not employed' in the next wave" (p. 15).
- **Ever in the labour force:** over 12 waves, more than **44%** of women were in the labour force at least once (about 30% employed in at least one wave), against an average LFPR of **14.6%**. Only about 2% were in the labour force in all waves (p. 14).
- **Rural women observed in all 12 waves and in the labour force at least once:** about 34% made one transition, 36% two, and 25% more than three. Only about 5% of women were in the labour force in every wave, against more than 70% of men (pp. 15–16).
- **Seasonality:** the authors test whether rural entry and exit are seasonal. They find no "considerable systematic difference in LFPR across months" for rural men or women in CPHS (p. 15). They cannot date transitions within the 4-month gap.

### 2.2 PLFS monthly bulletins (rural panel design, CWS, age 15+): monthly stocks, Apr 2025 – Oct 2026

Sources:
- Apr–Jun 2025: PIB release 2144849 (15 Jul 2025), Statements 1–2.
- Apr–Sep 2025: MoSPI press note for the Sep 2025 bulletin (15 Oct 2025), charts on pp. 3–4.
- Oct 2025 – Oct 2026: MoSPI press note for the Oct 2026 bulletin (16 Nov 2026), charts on pp. 3–5.
- Rural male LFPR for Apr–Aug 2026: Monthly Bulletin Aug 2026, Statement 1.

These are **monthly cross-section rates (net), not flows**. Oct 2025 appears in both the Sep 2025 and Oct 2026 sources, and the values agree.

| Month | Rural female LFPR | Rural female WPR | Rural male LFPR | Rural male WPR | Rural person LFPR |
|---|---|---|---|---|---|
| Apr-2025 | 38.2 | 36.8 | 79.0 | 75.1 | 58.0 |
| May-2025 | 36.9 | 35.2 | 78.3 | 74.2 | 56.9 |
| Jun-2025 | 35.2 | 33.6 | 78.1 | 74.1 | 56.1 |
| Jul-2025 | 36.9 | 35.5 | — | 74.5 | 56.9 |
| Aug-2025 | 37.4 | 35.9 | — | 74.4 | 57.0 |
| Sep-2025 | 37.9 | 36.3 | — | 74.4 | 57.4 |
| Oct-2025 | 38.4 | 36.9 | — | 74.8 | 57.8 |
| Nov-2025 | 39.7 | 38.4 | — | 75.4 | 58.6 |
| Dec-2025 | 40.1 | 38.6 | — | 76.0 | 59.0 |
| Jan-2026 | 39.7 | 38.0 | — | 75.7 | 58.7 |
| Feb-2026 | 40.0 | 38.4 | — | 75.4 | 58.7 |
| Mar-2026 | 38.9 | 37.3 | — | 75.0 | 58.0 |
| Apr-2026 | 38.2 | 36.5 | 78.1 | 74.5 | 57.5 |
| May-2026 | 36.7 | 35.0 | 77.7 | 73.7 | 56.6 |
| Jun-2026 | 36.6 | 34.7 | 77.9 | 74.1 | 56.6 |
| Jul-2026 | 38.8 | 37.2 | 78.3 | 74.7 | 58.0 |
| Aug-2026 | 39.4 | 37.8 | 78.4 | 75.0 | 58.2 |
| Sep-2026 | 38.9 | 37.4 | — | 74.9 | 58.0 |
| Oct-2026 | 39.5 | 38.0 | — | 75.3 | 58.4 |

"—" means the figure was not in the documents read.

**Seasonal amplitude [derived from the table]:**
- Rural female WPR peaks in Nov–Feb (38.0–38.6) and troughs in May–Jun (33.6–35.2). The swing is about 4 percentage points in both years (2025: 36.8 Apr → 33.6 Jun; 2025-26: 38.6 Dec → 34.7 Jun). That is roughly a 10% relative swing in the rural female workforce.
- Rural male WPR swings about 2.3 points (76.0 Dec-25 → 73.7 May-26).
- A net swing gives a **lower bound** on gross seasonal flows, not the flows themselves.

**MoSPI's own explanations (the only official text on seasonal movement between work and domestic duties):**
- **May 2025** (press note, 16 Jun 2025, p. 3):
  - "In rural areas, employment shifted away from the primary sector (agriculture) (from 45.9% in April to 43.5% in May 2025)".
  - The decline in female LFPR, especially rural (more than 1 percentage point), came from "fewer women working as casual labourers and unpaid helpers".
  - "Reduction in agricultural activities with the end of Rabi harvest season".
  - "movement of some unpaid helpers to domestic chores, especially in the higher income (top 3 decile) rural households".
- **June 2025** (PIB, 15 Jul 2025):
  - Rural female workforce participation fell by more than 1 percentage point against May, "primarily due to a reduction in unpaid helpers typically engaged in agricultural work".
  - "several unpaid helpers in June 2025 reported themselves as engaged in domestic duties".
  - The share of rural female workers in agriculture fell from 70.2% in May to 69.8% in June 2025.

### 2.3 PLFS Quarterly Bulletin Jul–Sep 2026 (31st; rural + urban, CWS, 15+): quarterly composition, Statements 1, 3, 4, 5, pp. 3–9

**Rural LFPR, UR and WPR (15+)**

| Quarter | LFPR male | LFPR female | UR male | UR female | WPR male | WPR female |
|---|---|---|---|---|---|---|
| Jul-Sep 2025 | 78.2 | 37.5 | 4.7 | 4.0 | 74.6 | 36.0 |
| Oct-Dec 2025 | 78.8 | 39.4 | 4.2 | 3.6 | 75.5 | 37.9 |
| Jan-Mar 2026 | 78.6 | 39.2 | 4.3 | 4.1 | 75.2 | 37.6 |
| Apr-Jun 2026 | 77.9 | 37.2 | 4.8 | 4.7 | 74.1 | 35.4 |
| Jul-Sep 2026 | 78.4 | 39.2 | 4.4 | 4.1 | — (page break; not read) | — |

**Rural workers by status in employment (% of workers, Statement 3)**

| Quarter | Male own-account/employer | Male contributing family worker | Male regular | Male casual | Female own-account/employer | Female contributing family worker | Female regular | Female casual |
|---|---|---|---|---|---|---|---|---|
| Jul-Sep 2025 | 47.3 | 9.6 | 17.2 | 24.9 | 37.5 | 34.2 | 10.8 | 17.0 |
| Oct-Dec 2025 | 47.6 | 9.4 | 17.1 | 24.9 | 36.6 | 35.6 | 10.4 | 16.8 |
| Jan-Mar 2026 | 47.0 | 9.1 | 17.9 | 25.0 | 38.4 | 33.8 | 11.2 | 16.1 |
| Apr-Jun 2026 | 45.7 | 8.8 | 18.3 | 25.8 | 40.8 | 30.4 | 12.0 | 16.0 |
| Jul-Sep 2026 | 47.1 | 9.2 | 18.0 | 24.8 | 39.0 | 33.4 | 11.2 | 16.0 |

**Share of rural workers in agriculture, NIC 01-03 (Statement 4)**

| Quarter | Male | Female |
|---|---|---|
| Jul-Sep 2025 | 49.2 | 74.2 |
| Oct-Dec 2025 | 49.4 | 75.5 |
| Jan-Mar 2026 | 46.3 | 73.5 |
| Apr-Jun 2026 | 43.9 | 70.7 |
| Jul-Sep 2026 | 47.2 | 74.5 |

These show the Apr–Jun (post-rabi, summer) dip in women's unpaid family farm work: contributing family workers fall to 30.4% from 35.6% in Oct-Dec.

### 2.4 Usual status vs weekly status, rural 2025

PLFS Annual Report 2025 press release (PIB 2246009, 27 Mar 2026), usual status (ps+ss, 365-day reference):

| Rural, 15+ | Female | Male |
|---|---|---|
| LFPR | **45.9%** | 80.5% |
| WPR | 44.9% | 78.4% |
| UR | 2.1% | 2.6% |

Weekly (CWS) rural female LFPR in 2025 months was only 35.2–40.1% (section 2.2). The gap between usual-status and weekly participation indicates women who work part of the year (subsidiary or seasonal) but not in a given week. This is a stock comparison, not a flow rate.

Reasons for being outside the labour force (same release, all-India): **44.4% of women** cite "child care/personal commitments in home-making"; **69.8% of men** cite wanting to continue studies.

### 2.5 IHDS 2005 → 2012, women aged 25–55 in 2005

Sarkar, Sahoo & Klasen, "Employment Transitions of Women in India: A Panel Analysis", IZA DP 11086 (Oct 2017); published in *World Development* 115 (2019). Table 2, p. 32.

- **Time unit:** 7 years.
- **Employment definition:** more than 240 hours in income-generating work in the past year.
- Values are % of row, including attrition.

| Status 2005 (share) | Not employed 2012 | Employed 2012 | Attrited |
|---|---|---|---|
| Rural, not employed (31.03%) | 52.5 | 26.99 | 20.51 |
| Rural, employed (68.97%) | 32.8 | 54.9 | 12.3 |
| Urban, not employed (75.02%) | 55.93 | 10.85 | 33.21 |
| Urban, employed (24.98%) | 35.72 | 38.46 | 25.82 |
| All, not employed (46.79%) | 54.47 | 17.72 | 27.81 |
| All, employed (53.21%) | 33.29 | 52.14 | 14.57 |

Text (p. 8):
- Women on the **family farm or in family business** were significantly more likely to exit than casual wage or salaried workers.
- About 78% of employed women in 2005 worked on the family farm or as agricultural casual labourers.
- The family farm has "the most number of exits as well as entries", which the authors read as a volatile, possibly "disguised unemployment" state.

### 2.6 ICRISAT Village Dynamics Studies (VDSA)

Poster "Rural Labor Market: Insights from Village Dynamics Studies" (vdsa.icrisat.org, RLMIVDS.pdf). Study villages in Maharashtra and Telangana, **household-level, 2005 → 2012**:
- "Two thirds of the farmers in 2005 remained in farming in the later year".
- "Seventy percent of the labor households remained as wage laborers although about one-fourth of them have moved from agriculture to non-agriculture labor".
- "About 60 percent of businessmen remained in business".

No monthly or seasonal labour-day figures by gender were found in published VDSA material. The microdata (VDS-K employment schedule) records days worked per month, but no published summary was found.

---

## 3. Job switching, separations and layoffs

### 3.1 EPFO payroll (formal sector) flows

**Source and coverage**
- Economic Survey 2025-26 Statistical Appendix, Table 9.5 ("Set 5 – High frequency indicators: Trends in EPFO subscription (in lakhs)"), p. 223.
- The PDF page prints Sep-17 to Jan-21 and then "Contd....". The companion **tab9.5.xlsx** at the same URL holds the full series to **Jul-2025**, with the note "Source: EPFO (latest release: September 2025)".
- Apr–Jul 2025 values were checked against EPFO's own "Provisional Estimate of Net Payroll" report dated 20 Sep 2025 (epfo.gov.in Data Hub, file September-2025.pdf, pp. 1, 6–7). They match.
- **Net payroll = new + rejoined − exited.**

| Month | New EPF subscribers (lakh) | Members exited (lakh) | Exited members who rejoined (lakh) | Net payroll addition (lakh) |
|---|---|---|---|---|
| Apr-2024 | 9.86 | 17.82 | 18.77 | 10.81 |
| May-2024 | 10.64 | 17.72 | 17.92 | 10.84 |
| Jun-2024 | 10.93 | 17.65 | 17.45 | 10.73 |
| Jul-2024 | 11.43 | 17.48 | 18.38 | 12.32 |
| Aug-2024 | 10.10 | 16.90 | 16.91 | 10.11 |
| Sep-2024 | 10.20 | 17.42 | 17.27 | 10.05 |
| Oct-2024 | 8.15 | 18.10 | 15.21 | 5.25 |
| Nov-2024 | 9.39 | 17.20 | 16.44 | 8.64 |
| Dec-2024 | 9.06 | 15.72 | 16.62 | 9.96 |
| Jan-2025 | 8.74 | 12.26 | 16.73 | 13.21 |
| Feb-2025 | 7.86 | 8.98 | 14.39 | 13.27 |
| Mar-2025 | 7.54 | 6.20 | 13.23 | 14.58 |
| **Apr-2025** | 9.33 | 14.46 | 19.44 | 14.32 |
| **May-2025** | 9.95 | 13.13 | 17.80 | 14.62 |
| **Jun-2025** | 11.01 | 10.05 | 18.08 | 19.05 |
| **Jul-2025** | 9.79 | 5.18 | 16.43 | 21.04 |

xlsx values are rounded here to 2 decimals.

**FY 2024-25 totals** (EPFO report, 20 Sep 2025, p. 5, in persons):

| Measure | Persons |
|---|---|
| New subscribers | 11,391,301 |
| Exited | 18,344,519 |
| Exited and rejoined | 19,931,386 |
| Net payroll | 12,978,168 |

The 12 monthly xlsx values sum to the same totals: 113.91 / 183.45 / 199.31 / 129.78 lakh.

By age, FY 2024-25:

| Age | New | Exited | Rejoined | Net |
|---|---|---|---|---|
| <18 | 96,588 | 37,765 | 11,488 | 70,311 |
| 18-21 | 3,679,149 | 2,558,066 | 2,011,334 | 3,132,417 |
| 22-25 | 2,850,611 | 3,964,342 | 4,352,142 | 3,238,411 |
| 26-28 | 1,086,130 | 2,755,090 | 3,360,162 | 1,691,202 |
| 29-35 | 1,675,291 | 4,399,779 | 5,310,857 | 2,586,369 |
| >35 | 2,003,532 | 4,629,477 | 4,885,403 | 2,259,458 |

**What "rejoined" means** (PIB release 2169975, 23 Sep 2025, July 2025 data): "These members switched their jobs and re-joined the establishments covered under the ambit of EPFO and opted to transfer their accumulations instead of applying for final settlement".
- So **rejoined is EPFO's own proxy for formal-sector job-to-job moves**: about 16–19 lakh a month in Apr–Jul 2025.
- The same release reports 9.79 lakh new subscribers in Jul 2025, of whom 5.98 lakh (61.06%) were aged 18–25, and 2.80 lakh new female subscribers.

**Aug 2025 – Mar 2026: not published.**
- The EPFO Data Hub (epfo.gov.in/data-hub, page footer "Last Updated: November 20, 2026") lists its newest payroll file as **20 Sep 2025, which contains data to Jul 2025**.
- StartupFeed (A. Mishra, 14 Sep 2026): "EPFO's monthly payroll data has not been published since September 2025."
- The Economic Survey table also ends at Jul-2025.

**[derived] Rough annual rates, for orientation only**
- EPFO's FY 2023-24 annual report, as reported by Business Standard and seen only in a search-result excerpt, counts **73.7 million active contributing subscribers**.
- Dividing FY 2024-25 flows by that FY 2023-24 stock:

| Flow | Calculation | Annual rate | Monthly average |
|---|---|---|---|
| Exits | 183.45 lakh / 737 lakh | ≈ 24.9% | ≈ 2.1% |
| Rejoins (job switches) | 199.31 / 737 | ≈ 27.0% | ≈ 2.3% |
| New first-time members | 113.91 / 737 | ≈ 15.5% | ≈ 1.3% |

The years are mismatched and both series are provisional, so treat these as orders of magnitude.

### 3.2 PLFS-based cross-status moves (no employer identifier in any PLFS data)

- Off-diagonal moves among own-account, regular and casual work each quarter are in sections 1.1 and 1.4. Examples from the [derived] 2024 table:
  - Male regular → own-account: 0.7%/quarter.
  - Male casual → regular: 1.1%/quarter.
  - Male unemployed → casual: 9.9%/quarter.
- Bhattacharya (p. 12) and the PLFS documentation give **no** employer-change (same-status job-to-job) rate. **No published Indian household-survey estimate of the employer-change rate was found.**

### 3.3 Corporate attrition (formal private sector surveys)

**Aon India Salary Increase and Turnover Study**
- Release of 14 Oct 2026 (aon.com, 1,200+ organisations, 45 industries): "Overall attrition increased to **18% in 2026**, compared with **16.2% in 2025** and **17.1% in 2024**."
- *People Matters* (15 Oct 2026) on the same study: "Involuntary attrition, which covers employee exits initiated by employers, also rose to **4%** from **3.4%** in 2025." This is an annual layoff rate for surveyed firms. Voluntary attrition was not stated in the pages read.
- Aon's previous edition (Oct 2025, seen in search excerpts) gave 2025 = 17.1%, 2024 = 17.7%, 2023 = 18.7%. The figures for the same years were revised in the next edition.
- Same study: actual salary increase **9% in 2026**; projected **9.1% in 2027**.

### 3.4 Pay change on switching jobs (switch premium)

Recruiter figures only. No household-survey or administrative estimate of the realised wage change on an employer switch in India was found.

- **Michael Page India salary guide** (as reported by *HRO Today*, about May 2024):
  - Junior-level professionals in all sectors see salary increases of **25%–40% when switching jobs**, against **7%–20%** for those staying.
  - Junior tech professionals see **35%–45%**.
- **Michael Page 2025 Salary Guide** (as reported by *People Matters*, 14 Feb 2025):
  - Annual hikes of **6%–15%**.
  - **30%–40%** for emerging skills and critical leadership roles.
  - The switch-specific "30–40%" figure attributed to this guide was seen only in a search excerpt (Business Standard was blocked), so it is not confirmed.
- **Related, from Bhattacharya Figure 1 (p. 13):** earnings when moving into "had work but did not work" (section 1.1). This is not a switch premium.

---

## 4. Retirement (superannuation) ages

| Group | Age | Source (read) |
|---|---|---|
| Central government employees | **60** | Fundamental Rule 56(a). Lok Sabha written reply by MoS Jitendra Singh, 19 Mar 2025: "No proposal to change the retirement age of government employees is under consideration" (Business Today, 19 Mar 2025, which gives 60 as the norm and up to 65 for some teaching/scientific posts). FR-56(a) proviso: a person born on the 1st of a month retires on the last day of the previous month (DoPPW OM, quoted on gconnect.in; search excerpt). |
| Gujarat | **58** | *The Secretariat*, 25 Jun 2025: "Gujarat remains an outlier, maintaining 58" (unions are demanding 60). |
| Uttar Pradesh, Tamil Nadu, West Bengal, Rajasthan, Delhi | **60** | *The Secretariat*, 25 Jun 2025 ("States with a 60-year retirement age … include Uttar Pradesh, Tamil Nadu, West Bengal, Rajasthan, and Delhi"). |
| Madhya Pradesh | **62** (raised from 60 in Mar 2018) | Scroll.in, 30 Mar 2018. |
| Andhra Pradesh | **62** (raised from 60 in 2022) | India.com, 1 Feb 2022. |
| Telangana | **61** (raised from 58, effective 30 Mar 2021) | *Telangana Today*, 30 Mar 2021 (gazette notification). |
| Kerala | **56** (proposal to raise to 60 rejected) | Onmanorama, 28 Nov 2024. |
| Maharashtra | **58** (federations demanding 60) | Outlook Money, 12 Aug 2026. |
| Private-sector industrial workers (default) | **58** unless agreed otherwise | Industrial Employment (Standing Orders) Central Rules, Schedule I-B, item 3: "Where there is no such agreed age, retirement or superannuation shall be on completion of 58 years" (comply4hr.com copy). Not checked: whether the Industrial Relations Code 2020's model standing orders change this. |
| EPS-95 pension (EPFO) | Normal pension at **58**. Early (reduced) pension from **50**, cut 4% for each year short of 58. Deferral up to **60**, +4% per completed year after 58. | Rajya Sabha written reply, MoS Shobha Karandlaje, 12 Feb 2026 (via Upstox): early pension from 50, "reduced at the rate of four per cent, for every year, the age falls short of 58 years". Deferral text from EPS para 12, quoted in the same article. EPFO EPS page: "Membership continues until age 58 years"; "a reduced pension can be drawn from age 50". |

---

## 5. Numbers that look implausible or need care

1. **Sarvekshana 114 (section 1.5):**
   - Whole quarter columns are duplicated (female and person Oct-Dec 2018 = Apr-Jun 2019; female Oct-Dec 2019 = person Oct-Dec 2019).
   - Male Oct-Dec 2019 E→NLF = 0.0585 is about 4× its neighbours.
   - One row does not sum to 1.
   - Probabilities are ratios of 1-decimal-rounded percentages, so they are very coarse.
2. **EPFO exits in recent months are understated.** Jul-2025 exits were 5.18 lakh against 17.48 lakh in Jul-2024, and Jan–Mar 2025 exits (12.26, 8.98, 6.20) collapse relative to earlier months. EPFO says exit dates are marked after the report is generated. This inflates the latest months' net payroll (21.04 lakh in Jul-2025).
   - Separately, rejoined (199 lakh) > exited (183 lakh) in FY 2024-25. Stocks of past leavers are rejoining, so "rejoined" is not a clean within-year job-switch count.
3. **CPHS women's exit rate:**
   - Rural 28.5% and urban 31.7% per 4-month wave, against about 6–10% per quarter in PLFS urban data. The derived 2024 table gives female own-account → NLF 7.1% and helper → NLF 10.5%; Bhattacharya gives female salaried → NLF 5.72%.
   - The gap is largely definitional: CPHS uses a day-reference status, counts "willing but not looking" as in the labour force, and measures a female LFPR (~15%) far below PLFS.
4. **Bhattacharya Table 5:** the coefficient 1.06 (male salaried, rubber & plastics) exceeds the "range … to 1.0" stated in the text (p. 16).
5. **PLFS QB Oct–Dec 2024:** the fourth Table (5) mislabels its from-quarter "July - September 2023" (should be 2024).
6. **Aon:** 2025 attrition was revised from 17.1% to 16.2%, and 2024 from 17.7% to 17.1%, between editions.
7. **Menon & Nath:** transitions are described as annual but span Q1 → Q4, which is three quarters.

## 6. Not found or not accessible

- **Das (2023), IJLE 66:225–237** (s41027-022-00425-2): first-order Markov matrices over self-employment / regular / casual / unemployment from four 2019-20 urban panels. **Paywalled; no matrix values obtained.** The abstract says only that movement between job statuses was very low and was mostly job losses.
- **Singh (2023)** gross flows (s41027-022-00417-2): paywalled. Only abstract figures (section 1.7).
- **Bhattacharya's published version** (IJLE 2023, s41027-023-00434-9): paywalled. Not checked for revisions against arXiv v2.
- **Any matrix with NLF split into students / domestic duties / other:** none published. All matrices pool NLF. Can be computed from the plfs-jb linked parquet (urban, 2017–2019) or from PLFS 2025 revisit microdata, if released.
- **Monthly transition matrices:** none published for India. All PLFS matrices are quarterly, and the CPHS rates are per 4 months.
- **Rural gross flows by agricultural season** (farm or casual ↔ domestic duties or unemployment, men or women): no published rates. The only evidence is:
  - net monthly or quarterly stock swings (sections 2.2–2.3);
  - MoSPI's narrative on unpaid helpers moving to domestic duties after the rabi harvest (section 2.2);
  - CPHS per-wave rates for rural women with no seasonal breakdown, where the authors found no monthly pattern (section 2.1);
  - 7-year IHDS rates (section 2.5).
  - Nothing equivalent was found for rural **men**, ICRISAT monthly labour days, or NSSO/MoSPI seasonal flow notes.
- **EPFO payroll Aug 2025 – Mar 2026:** not released (section 3.1).
- **Employer-change (job-to-job) rate from household data**, and a realised switch premium from survey or administrative data: none found for India.
- **Industrial Relations Code 2020 model standing orders:** retirement default not checked.
