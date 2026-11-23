# Sources for macro paths and scenario decisions (plan 1d-2)

These notes give each figure behind the registry's `macro.` rows and the behavioural calls in the scenarios and experiments design (`docs/superpowers/specs/2026-11-23-scenarios-experiments-design.md`), with where it comes from. They were read on 23 November 2026.

Status `verified` means the figure was read from the primary document named.

## Policy repo rate (`macro.policy_rate`)

| In force from | Repo rate | Source |
| :--- | ---: | :--- |
| 7 February 2025 | 6.25% | RBI Annual Report 2024-25, which describes the April 2025 decision as a cut "from 6.25 per cent", https://rbi.org.in/scripts/AnnualReportPublications.aspx?Id=1473. The February 2025 statement itself is not pinned. |
| 9 April 2025 | 6.00% | Resolution of the Monetary Policy Committee, 7–9 April 2025, https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=60279 |
| 6 June 2025 | 5.50% | Governor's statement, 6 June 2025: a 50 bp cut, with immediate effect, https://rbidocs.rbi.org.in/rdocs/PressRelease/PDFs/PR490F9F47F74F55146D48D4F15690DE513AE.PDF |
| 5 December 2025 | 5.25% | Monetary Policy Statement 2025-26, 5 December 2025: a 25 bp cut, https://rbidocs.rbi.org.in/rdocs/PressRelease/PDFs/PR16331051154700094ACFB40DE08AE141531C.PDF |
| (held) 6 February 2026 | 5.25% | Monetary Policy Statement 2025-26, 6 February 2026: unchanged, https://rbidocs.rbi.org.in/rdocs/PressRelease/PDFs/PR20530D3EAF28B417497981BA800A7B3C0DCC.PDF |

The rate held at 5.50% in August and October 2025. A hold needs no step in the path.

Status: `verified` for the steps from April 2025 on. The date of the first step is the only figure not read from its own statement. It does not affect a run that starts in April 2025 or later.

## CPI inflation (`macro.cpi_inflation`)

All-India CPI (Combined), general index, year on year, in %.

| Month | Rate | Base | Source |
| :--- | ---: | :--- | :--- |
| 2025-04 | 3.16 | 2012=100 | MoSPI, CPI release for December 2025 (12 January 2026), annex "Time Series Data for All India Year-on-year inflation rates (%) based on General CPI (Base 2012=100)", https://static.pib.gov.in/WriteReadData/specificdocs/documents/2026/jan/doc2026112755501.pdf |
| 2025-05 | 2.82 | 2012=100 | Same |
| 2025-06 | 2.10 | 2012=100 | Same |
| 2025-07 | 1.61 | 2012=100 | Same (final; the first estimate was 1.55) |
| 2025-08 | 2.07 | 2012=100 | Same |
| 2025-09 | 1.44 | 2012=100 | Same (final; the first estimate was 1.54) |
| 2025-10 | 0.25 | 2012=100 | Same |
| 2025-11 | 0.71 | 2012=100 | Same |
| 2025-12 | 1.33 | 2012=100 | Same, provisional. The press release is https://static.pib.gov.in/WriteReadData/specificdocs/documents/2026/jan/doc2026112755001.pdf |
| 2026-01 | 2.75 | 2024=100 | MoSPI, CPI release for January 2026, provisional, https://www.mospi.gov.in/uploads/latestReleases/latest_release_1770891893893_6b458c0a-c327-4fef-a554-41131ea67273_Press_Relase_of_CPI_for_Jan26.pdf |
| 2026-02 | 3.21 | 2024=100 | MoSPI, CPI release for March 2026 (13 April 2026), February final, https://mospi.gov.in/uploads/latestreleasesfiles/1776078391571-Press_Release_of_CPI_March_2026.pdf |
| 2026-03 | 3.40 | 2024=100 | Same, provisional |

The base changes from 2012=100 to 2024=100 in January 2026, and MoSPI publishes no linked series across the change. The values are as published, and each is dated at the first of its month. January 2026 was taken from a search summary of MoSPI's January release; the release itself was not opened here.

Status: `verified`. All values except January 2026 were read from the MoSPI releases.

## Savings rates follow the repo rate (why savings interest is the natural follow-up)

SBI cut its savings rate to a flat 2.50% (from 2.70% below ₹10 crore) from 15 June 2025, nine days after the 50 bp repo cut. HDFC Bank and ICICI Bank moved to 2.75%. Sources: Business Standard, https://www.business-standard.com/finance/personal-finance/sbi-slashes-fd-savings-rates-after-repo-rate-cut-offers-up-to-7-05-125061600600_1.html, and https://www.business-standard.com/amp/finance/personal-finance/hdfc-bank-icici-bank-federal-slash-savings-rates-new-terms-explained-125061800564_1.html.

Plan 1d-2 records macro paths only, by the project owner's choice. Nothing in phase 1 earns interest.

## A one-off transfer is spent in the month it arrives (`DBTTransfer` transfer income)

The 2020 PMGKY payments of ₹500 a month were made to women's Jan Dhan accounts, April to June 2020.

| Finding | Source |
| :--- | :--- |
| 94% of women respondents who received the transfer withdrew it. 11% saved it, 8% made online payments and 3% invested it. | Vidhi Centre for Legal Policy, "Financial Inclusion of Women during the Pandemic", https://vidhilegalpolicy.in/research/financial-inclusion-of-women-during-the-pandemic-the-role-of-jan-dhan-accounts-and-cash-transfers/ |
| About 76% of recipients had already withdrawn the amount; a third of those who had not cited the lockdown | RCRC, Jan Dhan DBT status report (rapid survey, April 2020), https://idronline.org/wp-content/uploads/2020/05/RCRC_Jan-Dhan-DBT-Status-Report.pdf |
| By 20 May 2020, about 46% of all such accounts had withdrawn, across the whole account base | Business Standard, 24 May 2020, https://www.business-standard.com/amp/article/economy-policy/covid-19-crisis-only-46-women-with-jan-dhan-accounts-availed-of-scheme-120052401045_1.html |

The surveys of recipients agree that most withdrew the money soon after it arrived. The 46% figure is lower because it counts every account, including those that may not have been credited yet and the lockdown months when access was hard.

The decision: a scenario DBT scheme counts as transfer income in the month it pays, at the amount paid that month, and in no other month.

## Layoffs move people to job-seeking (`IncomeShock`)

PLFS counts a person without work who is seeking it as unemployed, so the shock's alignment shift moves laid-off salaried workers to `seeking`. After that, the life course's own transitions apply. During and after the 2020 lockdown, many workers who lost salaried jobs moved into informal self-employment or casual work rather than staying unemployed (Azim Premji University, State of Working India 2021, https://cse.azimpremjiuniversity.edu.in/state-of-working-india/swi-2021/).
