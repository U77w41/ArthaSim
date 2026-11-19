# Indian financial ecosystem simulator: architecture blueprint

Version 2.0, draft for approval, 13 November 2026. Replaces `simulation_architrcture.md` (v1). Background reading: `related_works.md`.

How to read this: sections 1 to 4 say what is being built and why. Sections 5 to 12 define the model. Sections 13 and 14 define the data and the Python interface. Sections 15 to 19 cover calibration, delivery and open decisions.

## 0. What changed from v1

| Topic | v1 | v2 |
| :--- | :--- | :--- |
| Use | Generate datasets | Generate datasets and test your own models, products and policies inside the running world, all through Python |
| Primary key | PAN for every entity | Internal `entity_id`. PAN is an optional attribute in a format that cannot be a real PAN |
| Population | PAN register, 80 crore | Census-based synthetic population at a stated scale factor, in tiers from 10,000 to 1,000,000 persons |
| Clock | "Continuous" plus daily, monthly and annual ticks | One daily step with 96 settlement slots. Monthly and annual jobs run at day boundaries |
| Execution | PySpark partitions by district | Single-process vectorised Python. Distribution is deferred |
| Inspector | Re-simulate one agent and its 2-hop network | Read the event log and snapshots of the full run |
| Ledger | Bank accounts only | Every financial instrument: deposits, cash, wallets, loans, card balances, reserves, settlement and boundary accounts |
| Labels | Ground truth mixed into entity and transaction tables | A truth layer kept apart from observer views. Observed labels arrive late and incomplete, as in a bank |
| Fraud engine | Fixed formula and cut-offs | Same five tiers. Every weight is a labelled assumption. Illicit funds are tagged at source |
| Macro | Implied | Inflation, rates, market returns and sector growth are scenario inputs |
| Numbers | Written into the prose from mixed sources | A versioned parameter registry with status and role (appendix A) |
| Privacy | "Zero risk" | No real records used, invalid identifier formats, synthetic bank codes, legal review before release |

## 1. Purpose and uses

The simulator is a small, working copy of Indian retail banking. People earn, spend, save, borrow, invest and get defrauded; banks and payment rails process what they do. A researcher uses it in two ways:

1. **As a data source.** Export what a bank, a bureau or a payment switch would see, with labels.
2. **As a test bench.** Plug a model or a rule into the running world, change a policy, and measure what happens against a paired baseline.

| Use | Example question | What the simulator provides | Phase |
| :--- | :--- | :--- | :---: |
| Fraud and mule detection | Does detector X cut losses at one bank without blocking genuine payments? | Scam and mule typologies, single-bank view, fraud-control hook | 2 |
| Loans | What default rate does underwriting policy P produce over 12 months? | Loan lifecycle, delinquency ladder, bureau, credit-policy hook | 3 |
| Credit cards | How does a limit-increase rule change revolving and default? | Card ledger, statement cycle, card-policy hook | 3 |
| Investments | Who starts, steps up or stops a SIP after a pay rise or a market fall? | Deposits, mutual funds, gold, market path | 4 |
| Product recommendation | Does recommender R lift adoption and retention against the current rule? | Catalogue, offer and response model, recommender hook | 4 |
| Policy effects | What happens to EMI bounces if the repo rate rises 50 bp? To cash withdrawals after a DBT tranche? | Interventions, paired runs, effect estimates with intervals | 1 onward |

## 2. Goals, non-goals and anti-goals

**Goals**

1. Functional transactions. Every payment has a payer, a payee, a purpose, a rail and a balance that covers it, or it is declined.
2. Behaviour with causes. Income, spending, saving, borrowing and fraud follow from agent state, so an intervention changes outcomes.
3. Closed-loop testing through Python hooks (section 11).
4. Reproducible paired experiments (section 12).
5. A year at tier S runs on a laptop.
6. Calibration to public Indian statistics, with a record of what is an input, a target or an assumption.

**Non-goals for v2**

- Macro forecasting. Inflation, interest rates, market returns and sector growth are inputs. Experiments measure household and bank responses to them, without general-equilibrium feedback.
- A one-to-one national run.
- Interbank liquidity and settlement risk beyond daily net positions.
- Securities market microstructure, and F&O trading.
- MSME supply chains, GST, self-help groups, chit funds, Kisan Credit Cards and crop cycles. These move to phase 5.
- LLM agents inside the engine.

**Anti-goals**

- A dataset in which fraud can be found from a planted column or a fixed template.
- Output that could be mistaken for real customer data.
- Results quoted without the assumptions they rest on.

## 3. Approaches considered

| Approach | Strength | Why not chosen |
| :--- | :--- | :--- |
| A. Rule-based agent world in vectorised Python | Causal, what-if capable, no real data needed, fully inspectable | Chosen |
| B. Extend an open AML simulator such as AMLSim | Typology graphs come ready-made | Accounts have no people behind them; no credit or investments; the core is a Java transaction simulator |
| C. Train a generative model on real bank data | Closest fit to one bank | Needs data that is not available, cannot answer what-if questions, and carries privacy risk |
| D. LLM-driven agents | Rich, conversational behaviour | Cost per agent, weak reproducibility. Useful later for scam dialogue only |

Approach A matches AMLworld's method (a virtual world driven by public statistics) and adds what the literature lacks: a life course, credit, Indian rails and models in the loop. Details are in `related_works.md`, sections 3.1 and 5.

## 4. Architecture overview

```
 configs/*.yaml      params/registry.yaml
        |                    |
        v                    v
 +----------------------------------+
 | World builder                    |   population, households, employers,
 | (build/)                         |   merchants, banks, accounts
 +----------------+-----------------+
                  v
 +----------------------------------+
 | World state: arrays in memory    |
 +----------------+-----------------+
                  v   one step per day
 +----------------------------------------------------------+
 | Engine                                                   |
 |  calendar -> behaviour modules -> intents                |
 |  -> settlement (rails, bank rules, hooks, ledger)        |
 |  -> end-of-day jobs -> month-end jobs                    |
 +----------------+-----------------------------------------+
                  v
 +---------------------------+     +------------------------+
 | Store: Parquet tables,    | --> | Views: bank, bureau,   |
 | snapshots, manifest       |     | AA, switch, truth      |
 +---------------------------+     +-----------+------------+
                                               v
                Python API: tasks, experiments, inspect,
                validate, calibrate, extend
```

Package layout (working name `arthasim`):

| Module | Responsibility |
| :--- | :--- |
| `config`, `params` | Run configuration, tiers, parameter registry |
| `build/` | Synthetic population, households, organisations, banks, accounts, social graph |
| `engine/` | Calendar, scheduler, keyed random numbers, settlement loop, end-of-day jobs |
| `ledger/` | Instruments, journal, postings, invariants |
| `modules/` | Life course, income, consumption, payments, saving, credit, cards, investing, fraud, offers |
| `institutions/` | Banks, rails, bureau, government, central bank, markets |
| `hooks` | Interfaces for user models in the loop |
| `scenario`, `interventions`, `experiment` | Scenarios, policy levers, paired experiments |
| `store/`, `views`, `inspect` | Parquet output, observer views, single-entity trace |
| `tasks/`, `metrics` | Labelled datasets and outcome metrics |
| `calibrate`, `validate` | Fitting to targets, acceptance checks |

## 5. Entities and state

### 5.1 Entity kinds

| Kind | Examples | Notes |
| :--- | :--- | :--- |
| Person | Student, salaried worker, shopkeeper, pensioner | The only kind with a life course |
| Household | Family sharing a budget | Pools income for consumption; links members |
| Organisation | Employer, merchant, biller, AMC | One organisation can be both employer and merchant |
| Bank and lender | Public, private, small finance, payments and co-operative banks; NBFC lenders | Tier S default: 12 synthetic banks and 2 NBFCs |
| System operator | UPI switch, NACH, card network, ATM and AePS network | Applies rail rules and nets settlement |
| Bureau | Credit bureau | Holds tradelines, enquiries and scores |
| Government | Treasury and DBT schemes | Pays transfers, collects tax |
| Central bank | Policy rate, reserves, currency | Issuer of cash and reserves |
| Fraud ring | Operators running campaigns | Exists in the truth layer only |
| Boundary | Out-of-sample employers, merchants, relatives | Closes flows that leave the sample |

Persons are adults aged 18 and over. Children are counted as household dependants and enter as persons when they turn 18.

### 5.2 Person state

| Group | Variables | Visible to a bank? |
| :--- | :--- | :---: |
| Identity and place | `entity_id`, `household_id`, home district and PIN, current location | Partly (KYC fields) |
| Demographics | Age, sex, marital status, dependants | Partly |
| Human capital | Education level, domain skill, digital literacy, financial literacy | No |
| Work | Life stage, secondary activity, employer, sector, tenure, monthly pay | Inferred from credits |
| Finances | Balances by instrument, net worth, buffer in months | Own bank only |
| Credit | Loans, card limits, days past due, asset class, bureau score | Own bank and bureau |
| Traits | Risk appetite, habit strength, price sensitivity, trust in offers | No |
| Stress and risk | Financial stress index, scam susceptibility by typology | No |
| Illicit | Role, tier, capability, experience, ring | No |

Everything marked "No" lives in truth tables and never appears in an observer view.

### 5.3 Identifiers

- `entity_id` and `account_id` are 64-bit integers and are the only keys.
- `pan_like` keeps the PAN shape (entity-type letter in position 4, name initial in position 5) but has a digit in position 3, which no real PAN has. A `has_pan` flag is calibrated, so accounts without PAN exist.
- No Aadhaar-format numbers are generated. Where a link key is needed for DBT or AePS, a random `uid_token` is used.
- Banks get synthetic codes such as `SYNB03`. Branch codes are IFSC-shaped but start with `SY` followed by two digits, which a real IFSC cannot.
- Mobile numbers and devices are opaque tokens. VPA handles use made-up suffixes.
- State, district and PIN codes are real, and are used as locations only.

### 5.4 Scale tiers

| Tier | Persons | Purpose | Hardware | Transactions in 12 months (planning figure) |
| :--- | ---: | :--- | :--- | ---: |
| XS | 10,000 | Tests, tutorials, calibration trials | Laptop | 5.5 million |
| S | 100,000 | Development and most experiments | Laptop | 55 million |
| M | 1,000,000 | Benchmark datasets | One server, 64 GB RAM or more | 550 million |
| L | 10,000,000 and up | Deferred to phase 5 | Cluster | 5.5 billion |

The planning figure allows 1.5 transactions per person per day. v1's UPI volume works out to roughly 0.5 per resident per day, so the allowance leaves room for other rails, cash and declined attempts. It will be replaced by the calibrated value.

Each run states its scale factor: real population represented divided by simulated persons. Institutions do not shrink in proportion. Bank count is fixed per tier, employer and merchant counts follow registry ratios with floors, and national billers (telecom, utilities, e-commerce, AMCs) exist once each. Payments to parties outside the sample post to boundary accounts.

## 6. Time and scheduling

The base step is one calendar day. A calendar table carries weekday, bank holidays, pay days and regional festivals.

**Within a day**

1. **Start of day.** Apply interventions dated today. Advance macro paths. Create scheduled intents: salary runs, EMI and SIP debits, DBT credits, card statements.
2. **Intents.** Each behaviour module emits the day's intents: payer, payee, amount, purpose, preferred rail, slot.
3. **Settlement.** The day has 96 slots of 15 minutes. Within a slot, intents are ordered by time and id and settled one at a time against live balances. Each intent passes rail rules, bank rules and any fraud-control hook, then posts to the ledger or is declined. Reactive behaviour (a mule forwarding money, a retry after a decline, an account sweep) adds intents to later slots.
4. **End of day.** Batch rail results, interest accrual, days-past-due counters and asset classification, complaints filed, invariant checks, output flush.

**Month end.** Life-course transitions and alignment, hiring and layoffs, bureau reporting and score refresh, saving and investment allocation, monthly state snapshot, checkpoint.

**Year.** Pay increments in April, ageing, entry of new adults, exits.

**Randomness.** Every draw is a pure function of `(run_seed, stream, entity_id, day, index)`, using a counter-based generator. Each module has its own streams. Two consequences: output does not depend on processing order, and a baseline and a treatment run share every draw, which makes paired comparison possible.

**Parallelism.** One world runs in one process. Parallelism is across runs (seeds and treatments). Partitioning a single world is a tier L problem and is out of scope.

## 7. Money and accounting

### 7.1 Instruments

Every balance in the world is a financial instrument with a holder and an issuer. One record serves both sides, so a bank's deposit liabilities equal its customers' deposit balances by construction.

| Instrument | Holder (asset) | Issuer (liability) |
| :--- | :--- | :--- |
| Deposit: savings, current, salary, basic, FD, RD | Customer | Bank |
| Wallet: UPI Lite, prepaid | Customer | Issuing bank |
| Cash | Anyone, including bank vaults and ATMs | Central bank |
| Reserve balance | Bank | Central bank |
| Loan: personal, vehicle, home, gold, overdraft | Lender | Borrower |
| Card balance | Card-issuing bank | Cardholder |
| Merchant settlement payable | Merchant | Acquiring bank |
| Government balance | Government | Central bank |
| Fund units, valued at NAV | Investor | AMC scheme |
| Boundary deposit | Boundary entity | Boundary bank |

Gold and property are real assets with a holder and no issuer. They sit in a holdings table and change value with the market path.

### 7.2 Journal and postings

A transaction is a journal entry with two or more postings. Each posting changes one instrument's balance. Amounts are integers in paise. Each journal entry has a kind and a flow type (wage, consumption, transfer, interest, fee, tax, principal, cash conversion), and each kind has a shape that is validated:

| Kind | Postings |
| :--- | :--- |
| Payment | Payer deposit down, payee deposit up, equal amounts |
| Cash withdrawal | Customer deposit down, customer cash up, bank vault cash down |
| Loan disbursal | Loan up, borrower deposit up |
| Repayment | Borrower deposit down, loan down (principal), interest as a flow to the bank |
| Card purchase | Card balance up, merchant settlement payable up |
| Interbank settlement | Reserve balances between banks, netted per rail cycle |
| Government transfer | Government balance down, beneficiary deposit up, bank reserves up |

Money is created and destroyed only by listed kinds: lending and repayment, government and central bank operations, and boundary flows. Broad money (deposits and cash held outside banks) is reported daily.

### 7.3 Invariants

These run every simulated day. A failure stops the run.

1. Every journal entry matches the shape for its kind.
2. Opening balance plus postings equals closing balance, for every instrument.
3. Deposits are never negative unless an overdraft exists.
4. Each bank's balance sheet balances.
5. Cash held across all holders equals currency issued.
6. The daily transaction-flow matrix by sector sums to zero along every row and every column.
7. Every rupee marked illicit traces back to a fraud case.

## 8. Behaviour modules

Each module is a vectorised function over agent arrays with its own random streams and its own block of registry parameters. Any module can be replaced by a subclass (section 14.2).

### 8.1 Population build

- Persons and households are synthesised by fitting census margins and survey microdata (age, sex, education, household size, occupation, location), following the SynthPop++ and BharatSim approach.
- Income and wealth are attached from survey distributions. Accounts and products are assigned to match penetration targets.
- The social graph has four edge types: household, co-worker, neighbour and remittance (migrant to home household).
- Fallback if microdata access is delayed: a parametric population from published marginals, replaced later without changing the interface.

### 8.2 Life course (monthly)

- States: studying, seeking work, salaried, self-employed, gig, farm, casual labour, homemaker, retired. A secondary activity flag covers mixed livelihoods.
- Transitions are hazards conditional on age, sex, education and time in state.
- After the draw, alignment adjusts transitions so that simulated stocks match targets by group. Published survey rates are stocks, so they are alignment targets and not transition probabilities.
- Events: graduation, hire, switch, layoff, retirement, marriage, birth, death, entry at 18.

### 8.3 Income

- **Salaried.** Starting pay at hire comes from a Mincer-type equation (state, sector, education, experience, skill). After that, pay changes only through the annual increment (inflation path plus a merit draw) and through job switches. This removes v1's double counting of experience and annual hikes.
- **Self-employed, gig, casual.** Daily or weekly earnings with seasonality.
- **Other inflows.** Pension, DBT, remittance, rent, interest.
- Employers pay on their own calendar through NACH or NEFT. Layoffs follow the sector growth path plus firm-level shocks.

### 8.4 Consumption

1. A household sets a monthly budget from income, size, buffer and stress. The rule is buffer-stock: spend less when savings fall below a target number of months.
2. The budget is split across categories by shares that vary with income and location.
3. Categories become purchase events through the month. Each picks a merchant (distance, habit), an amount (category ticket distribution scaled by the price path) and a rail.

### 8.5 Payments and rail choice

- Rails: cash, UPI (P2P, P2M, Lite, AutoPay), debit and credit card, credit card on UPI, IMPS, NEFT, RTGS, NACH, APBS, AePS, ATM, cheque.
- Choice depends on amount, merchant acceptance, the payer's instruments, digital literacy, habit and balance.
- Failures are modelled: technical declines by rail and bank, insufficient funds, limit breaches, retries.

### 8.6 Saving and investing

- Phase 1 has a simple sweep of surplus into deposits.
- Phase 4 adds FD and RD, mutual fund SIPs, gold and insurance premiums. Adoption is a hazard driven by income, education, financial literacy, peers, life events and offers.
- SIPs can step up or stop. Under distress, assets are liquidated in a fixed order. Returns come from the market path.

### 8.7 Credit and cards (phase 3)

- **Origination.** A need arises (durable purchase, medical cost, shortfall, housing). The person applies. The bank's credit-policy hook decides. Disbursal posts to the ledger.
- **Repayment.** EMIs present through NACH on the due date. A shortfall bounces, is retried, and starts the days-past-due counter. Households pay obligations in a priority order when money is short.
- **Classification.** At day end each loan is standard, SMA-0 (1 to 30 days past due), SMA-1 (31 to 60), SMA-2 (61 to 90) or NPA (over 90). An NPA upgrades only when all arrears are cleared.
- **After default.** Collections contact, settlement or write-off, then recovery, which gives realised loss given default.
- **Bureau.** Lenders report monthly. The score is a documented scorecard over payment history, utilisation, age of credit, enquiries and mix. New-to-credit persons have no score.
- **Cards.** Limit, statement cycle, minimum due, revolving interest, late fee, cash advance. Limit reviews go through the card-policy hook.

### 8.8 Stress and shocks

A financial stress index combines buffer months, days past due, income drop and active shocks. Shocks are layoff, pay cut, medical cost and family event. Stress feeds consumption cuts, borrowing, distress redemption, scam susceptibility and illicit entry.

### 8.9 Offers and product response (phase 4)

Contact opportunities arise on app use, salary credit and branch visits. The recommender hook returns offers. Acceptance depends on need, fit, trust and offer fatigue. What happens next (usage, retention, default) comes from the other modules.

## 9. Fraud engine (phase 2)

### 9.1 Design rules

1. Illicit funds are tagged at source and the tag follows the money. Mixing with clean funds is proportional by default.
2. Typologies are scripts with random structure, amounts and timing. They are not fixed templates.
3. Rings react to controls.
4. Labels exist in two forms: truth and observed.
5. Every behavioural weight is a registry parameter with status "assumption".

### 9.2 Actors and tiers

| Tier | Who | What they can run |
| :---: | :--- | :--- |
| 1 | Account renters and deceived forwarders | Receiving and passing funds, cash-out |
| 2 | Opportunistic scammers | Collect-request and QR tricks, marketplace advance fee, fake refunds |
| 3 | Local organisers | Mule recruitment and herding, bust-out borrowing, collusive merchant cash-out |
| 4 | Technical operators | Account takeover, "digital arrest", task and investment scams at scale, automated layering |
| 5 | Corporate launderers | Shell entities and circular trading (phase 5) |

A person's tier ceiling comes from a capability score over education, digital literacy, domain skill and experience. The default weights are v1's and are assumptions.

Entry is demand-driven. A ring that needs accounts sends recruitment offers through the social graph and online exposure. Whether a person accepts follows v1's activation rule: stress and peer exposure, less perceived enforcement, against a personal threshold.

### 9.3 Typology scripts

Each script runs through stages: contact, conversion, payment, layering, exit. Skill sets the evasion settings: structuring under thresholds, dwell time, camouflage spending, account ageing.

- **Authorised scams.** Collect-request and QR, fake KYC or disconnection notice, task scam, investment app, digital arrest, marketplace advance fee.
- **Unauthorised.** Account takeover through a malicious app or SIM swap: device change, payee added, account drained.
- **Mule movement.** Fan-in to a first-layer account, hops with a dwell-time distribution, splitting, exit through ATM, AePS, merchant QR or the boundary.
- **Credit fraud (phase 3).** Bust-out, loan stacking, card cash-out through a collusive merchant.

### 9.4 Victims

Exposure varies by channel and demographic group. Susceptibility varies by typology with age, digital literacy, stress, risk appetite, past victimisation and awareness campaigns. A victim may stop part-way. Complaints are filed with a probability and a delay, and trigger freeze requests to beneficiary banks, which determine recovery.

### 9.5 Controls and adaptation

- Banks run default rules (velocity limits, new-payee cooling, dormant-account checks). A fraud-control hook can replace them and return allow, hold, block or step-up for each payment.
- A synthetic telecom risk flag with configurable accuracy is available to banks as an input.
- Rings observe which banks, rails and amount bands succeed, shift volume toward them, and replace burned accounts. The speed of adaptation is a parameter.

### 9.6 Labels

| Table | Content | Layer |
| :--- | :--- | :--- |
| `fraud_cases` | Case, typology, ring, victim, stages, amounts | Truth |
| `truth_txn_labels` | Payment, case, role (victim payment, layering, exit, camouflage), illicit share | Truth |
| `truth_account_roles` | Account, role, start and end dates | Truth |
| `complaints` | Filed time, reported payments, amount | Observed |
| `bank_actions` | Holds, blocks, freezes, with reason | Observed |

Class balance follows campaign intensity. It is not set by quota.

Benign look-alikes come from the normal modules and are tagged in truth: wedding and medical spikes, DBT lumps, salary fan-out by small employers, family members sharing one account, small merchants on personal accounts.

## 10. Institutions and rails

| Institution | Default behaviour | Replaceable by |
| :--- | :--- | :--- |
| Bank | Products and pricing, onboarding, fraud rules, credit scorecard cut-offs, collections, complaint handling | Hooks and `BankRule` interventions |
| Rails | Limits, timings, fees and decline rates from the registry | `ChangeRailRule` |
| Bureau | Monthly reporting, scorecard, enquiry footprints | Registry parameters |
| Government | DBT schemes with eligibility, amount and schedule; simplified tax deducted at source | `DBTTransfer` |
| Central bank | Policy rate path; pass-through to floating loan and deposit rates with a lag | `SetPolicyRate`, `MacroPath` |
| Markets | Equity, debt and gold return paths | `MarketShock`, `MacroPath` |
| Account aggregator | Consent records that define what an AA view can see | Config |

Rail rules (caps, cut-off times, settlement cycles) are registry entries, so a rule change is a one-line intervention.

## 11. Models in the loop

A hook is a Python object with one method. The engine calls it with a batch, applies what it returns, and logs both.

| Hook | Called | Receives | Returns |
| :--- | :--- | :--- | :--- |
| `FraudControl.decide` | Every slot, per bank | That bank's payments in the slot | `payment_id`, `action` |
| `CreditPolicy.decide` | Daily, per lender | New applications | `application_id`, `approve`, `amount`, `rate`, `tenure_months` |
| `CardPolicy.review` | Monthly, per issuer | Cards due for review | `card_id`, `new_limit` |
| `Recommender.recommend` | Daily, per bank | Customers with a contact opportunity, and the catalogue | `customer_id`, `product_id`, `rank` |

Rules of the contract:

1. A hook sees only its own bank's view, cut off at the current simulated time (`ctx.view`). It cannot read truth tables or the future.
2. `ctx.features()` returns standard rolling features, one row per batch row and in the same order. The engine maintains them incrementally, so a hook does not need to scan history.
3. Decisions within a slot are made before that slot settles.
4. A default implementation exists for every hook, so the world runs without user code.

## 12. Scenarios, interventions and experiments

A scenario is a set of macro paths plus a list of dated interventions.

| Intervention | Effect | Phase |
| :--- | :--- | :---: |
| `MacroPath` | Replace an inflation, rate, market or sector path | 1 |
| `SetPolicyRate` | Shift the policy rate from a date | 1 |
| `IncomeShock` | Layoffs or pay cuts for a selected group | 1 |
| `ExpenseShock` | Medical or other cost shocks at a given rate | 1 |
| `DBTTransfer` | Pay a transfer to eligible persons on given dates | 1 |
| `ChangeRailRule` | Change a limit, fee, cooling period or cut-off | 1 |
| `ParamOverride` | Change any registry parameter | 1 |
| `SetHook` | Swap a model at a bank from a date | 1 |
| `BankRule` | Change a bank's thresholds, pricing or cut-offs | 2 |
| `FraudCampaign` | Run a typology at a given intensity | 2 |
| `AwarenessCampaign` | Lower susceptibility for those reached | 2 |
| `ProductLaunch` | Add a product to a bank's catalogue | 3 |
| `MarketShock` | One-off change in an asset price | 4 |

**How an experiment runs**

1. Run the baseline to the intervention date and checkpoint.
2. Fork the world once per treatment and apply the treatment.
3. Run every arm to the end date.
4. Repeat for each seed.
5. Report the mean paired difference per metric with an interval.

Because arms share random draws, differences come from the intervention and what follows from it. Each report also lists the assumption-status parameters used by the active modules, and `Experiment.sweep` reruns the comparison across values of any one of them.

## 13. Data products

### 13.1 Layers and views

| View | Sees | Does not see |
| :--- | :--- | :--- |
| Truth | Everything | n/a |
| Bank | Its customers' KYC, accounts, statements, loans, cards, applications, offers, complaints and its own decisions; counterparty handle and bank on each payment | Other banks' balances, counterparty identity, traits, truth labels |
| Bureau | Tradelines from all lenders, enquiries, scores | Transactions |
| Account aggregator | Statements of consented accounts across banks | Anything without consent |
| Switch | Payer and payee handles, banks, amount, time, status, merchant category | Balances, KYC |
| Regulator | Aggregates and cross-bank fraud reports | Customer-level detail by default |

### 13.2 Table catalogue

| Table | Grain | Layer | Phase |
| :--- | :--- | :--- | :---: |
| `persons`, `households`, `orgs`, `banks` | One row per entity | Truth; subsets in views | 1 |
| `accounts` | One row per instrument | Truth; own accounts in bank view | 1 |
| `instruments` | VPA, card, device and mobile token per account | Truth; own in bank view | 1 |
| `entity_state_monthly` | Entity by month: all time-varying state | Truth | 1 |
| `employment_spells`, `life_events` | One row per spell or event | Truth | 1 |
| `payments` | One row per payment attempt on any rail, including declines | Truth, switch, bank | 1 |
| `journal`, `postings` | Settled entries and their legs | Truth | 1 |
| `statement_lines` | Posting on an own account with running balance and narration | Bank, AA | 1 |
| `holdings` | Entity by month by asset | Truth | 1 |
| `loans`, `loan_events` | Contract; disbursal, due, paid, bounce, class change, write-off, recovery | Truth, bank | 3 |
| `cards`, `card_statements` | Contract; one row per statement | Truth, bank | 3 |
| `applications` | Application and decision | Truth, bank | 3 |
| `bureau_tradelines`, `bureau_enquiries` | Monthly tradeline; one row per enquiry | Bureau | 3 |
| `offers` | Offer shown and response | Truth, bank | 4 |
| `fraud_cases`, `truth_txn_labels`, `truth_account_roles` | See section 9.6 | Truth | 2 |
| `complaints`, `bank_actions` | See section 9.6 | Bank, regulator | 2 |
| `truth_person_latent` | Person by month: stress, susceptibility, traits | Truth | 1 |
| `macro_paths`, `calendar`, `geo` | Reference | All | 1 |
| `interventions_log`, `run_manifest`, `param_snapshot`, `validation_report` | Run metadata | All | 1 |

### 13.3 Core columns

`payments`: `payment_id`, `intent_ts`, `settle_ts`, `rail`, `status`, `amount_paise`, `payer_account_id`, `payee_account_id`, `payer_bank`, `payee_bank`, `payer_handle`, `payee_handle`, `mcc`, `narration`, `channel`, `device_token`, `location_pin`, `journal_id`, and `purpose` (truth only).

`status` is one of `SUCCESS`, `DECLINED_TECH`, `DECLINED_FUNDS`, `DECLINED_LIMIT`, `BLOCKED_RISK`, `HELD`, `REVERSED`.

`journal`: `journal_id`, `ts`, `kind`, `flow_type`, `payment_id`.

`postings`: `journal_id`, `line_no`, `account_id`, `delta_paise`, `balance_after_paise`.

`accounts`: `account_id`, `type`, `subtype`, `holder_entity_id`, `issuer_entity_id`, `opened_on`, `status`.

Time-varying attributes are never stored on the entity row. They are read from `entity_state_monthly` or from events, so features built for a past date cannot leak later information.

### 13.4 Tasks and labels

| Builder | Unit | Label | Phase |
| :--- | :--- | :--- | :---: |
| `tasks.fraud.transactions` | Payment | Part of a fraud case (truth) or reported (observed) | 2 |
| `tasks.fraud.mule_accounts` | Account at a date | Used to move illicit funds within the horizon | 2 |
| `tasks.fraud.scam_victims` | Person at a date | Loss to scams within the horizon | 2 |
| `tasks.credit.default` | Loan or applicant at a date | Over 90 days past due within the horizon | 3 |
| `tasks.credit.lgd` | Defaulted loan | Realised loss fraction | 3 |
| `tasks.credit.distress` | Person at a date | Bounce or near-zero balance within 30 days | 1 |
| `tasks.cards.default` | Card at a date | Over 90 days past due within the horizon | 3 |
| `tasks.cards.revolve` | Card at a statement | Balance carried forward | 3 |
| `tasks.invest.sip_adoption` | Person at a date | Starts or steps up a SIP within the horizon | 4 |
| `tasks.invest.sip_stop` | SIP at a date | Stopped within the horizon | 4 |
| `tasks.reco.next_product` | Customer at a date | Next product taken | 4 |
| `tasks.reco.offer_response` | Offer | Accepted, and still active after 6 months | 4 |

Every builder returns features cut off at the observation date, labels, and temporal splits.

Built-in metrics: `txn_volume`, `consumption`, `deposit_balance`, `cash_withdrawal`, `emi_bounce_rate`, `npa_rate`, `credit_loss`, `approval_rate`, `net_interest_income`, `card_revolve_share`, `fraud_loss`, `fraud_loss_prevented`, `genuine_block_rate`, `sip_active_share`, `sip_stop_rate`, `redemption_value`, `offer_acceptance`, `product_holding`. Any function of a run can be registered as a metric.

## 14. Python interface

Everything the simulator does is reached from Python. There is no separate tool to learn.

### 14.1 What you want, and the call that does it

| You want to | Call | Phase |
| :--- | :--- | :---: |
| Build a world | `World.build(config, seed)` | 1 |
| Run, pause, resume | `world.run`, `world.step`, `world.save`, `World.load` | 1 |
| Reopen a finished run | `Run.open(path)` | 1 |
| Read any table | `run.table(name)`, `run.sql(query)` | 1 |
| See what one bank, the bureau or the switch sees | `run.view("bank", bank=...)` and so on | 1 |
| Follow one person | `run.inspect(entity_id)`, `world.watch(entity_id, callback)` | 1 |
| Test a policy or shock | `Scenario.add(...)`, `Experiment(...).run()`, `result.effect(metric)` | 1 |
| Check sensitivity to an assumption | `Experiment.sweep(param_id, values)` | 1 |
| Build a fraud dataset | `tasks.fraud.*` | 2 |
| Run a fraud campaign | `interventions.FraudCampaign` | 2 |
| Put a fraud model in the loop | `interventions.SetHook("fraud_control", ...)` | 2 |
| Build loan and card datasets | `tasks.credit.*`, `tasks.cards.*` | 3 |
| Test an underwriting or limit policy | `SetHook("credit_policy", ...)`, `SetHook("card_policy", ...)` | 3 |
| Study investment behaviour | `tasks.invest.*`, `interventions.MarketShock` | 4 |
| Test a recommender | `SetHook("recommender", ...)`, `tasks.reco.*` | 4 |
| Compute an outcome | `run.metric(name)`, `register.metric` | 1 |
| Calibrate | `calibrate(config, params)` | 1 |
| Validate | `run.validate()` | 1 |
| Change or add behaviour | Subclass `BehaviourModule` or `Typology`, then `register` | 1, 2 |
| Export for other tools | `run.export(dest, view=...)`, `TaskDataset.to_parquet` | 1 |

### 14.2 Reference signatures

```python
from __future__ import annotations
import datetime as dt
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol, Sequence
import polars as pl

Date = str | dt.date


class Config:
    @classmethod
    def tier(cls, name: str, **overrides: Any) -> Config: ...
    @classmethod
    def from_yaml(cls, path: str) -> Config: ...
    def with_params(self, **overrides: Any) -> Config: ...


class ParamRegistry:
    @classmethod
    def load(cls, path: str) -> ParamRegistry: ...
    def get(self, param_id: str) -> Any: ...
    def table(self) -> pl.DataFrame: ...


class World:
    @classmethod
    def build(cls, config: Config, seed: int) -> World: ...
    @classmethod
    def load(cls, checkpoint: str) -> World: ...
    def run(self, until: Date, scenario: Scenario | None = None) -> Run: ...
    def step(self, days: int = 1) -> None: ...
    def fork(self) -> World: ...
    def apply(self, intervention: Intervention) -> None: ...
    def set_hook(self, kind: str, impl: Any, bank: str | None = None) -> None: ...
    def watch(self, entity_id: int, callback: Callable[[dict], None]) -> None: ...
    def save(self, path: str) -> None: ...


class Run:
    path: str
    manifest: Mapping[str, Any]
    @classmethod
    def open(cls, path: str) -> Run: ...
    def tables(self) -> list[str]: ...
    def table(self, name: str) -> pl.LazyFrame: ...
    def sql(self, query: str) -> pl.DataFrame: ...
    def view(self, kind: str, **scope: Any) -> View: ...
    def inspect(self, entity_id: int) -> EntityTrace: ...
    def metric(self, name: str | Callable[[Run], Any], **kwargs: Any) -> Any: ...
    def validate(self, suite: str = "core") -> ValidationReport: ...
    def fork_at(self, date: Date) -> World: ...
    def export(self, dest: str, view: str = "bank", **scope: Any) -> None: ...


class View:
    def tables(self) -> list[str]: ...
    def table(self, name: str, asof: Date | None = None) -> pl.LazyFrame: ...
    def sql(self, query: str) -> pl.DataFrame: ...


class EntityTrace:
    def profile(self, asof: Date | None = None) -> dict: ...
    def timeline(self) -> pl.DataFrame: ...
    def passbook(self, account_id: int | None = None) -> pl.DataFrame: ...
    def net_worth(self) -> pl.DataFrame: ...
    def loans(self) -> pl.DataFrame: ...
    def ego_network(self, hops: int = 1) -> pl.DataFrame: ...


class Intervention: ...


class Scenario:
    @classmethod
    def baseline(cls) -> Scenario: ...
    def add(self, *interventions: Intervention) -> Scenario: ...


class Experiment:
    def __init__(self, config: Config, baseline: Scenario,
                 treatments: Mapping[str, Scenario], seeds: Sequence[int],
                 intervene_at: Date, end: Date) -> None: ...
    def run(self, workers: int = 1) -> ExperimentResult: ...
    def sweep(self, param_id: str, values: Sequence[Any],
              workers: int = 1) -> ExperimentResult: ...


class ExperimentResult:
    def effect(self, metric: str | Callable[[Run], Any],
               by: str | None = None) -> pl.DataFrame: ...
    def runs(self, arm: str) -> list[Run]: ...
    def report(self, path: str) -> None: ...


class HookContext:
    now: dt.datetime
    bank: str
    view: View
    params: ParamRegistry
    def features(self, entity: str = "account") -> pl.DataFrame: ...


class FraudControl(Protocol):
    def decide(self, payments: pl.DataFrame, ctx: HookContext) -> pl.DataFrame: ...


class CreditPolicy(Protocol):
    def decide(self, applications: pl.DataFrame, ctx: HookContext) -> pl.DataFrame: ...


class CardPolicy(Protocol):
    def review(self, cards: pl.DataFrame, ctx: HookContext) -> pl.DataFrame: ...


class Recommender(Protocol):
    def recommend(self, customers: pl.DataFrame, catalog: pl.DataFrame,
                  ctx: HookContext) -> pl.DataFrame: ...


class TaskDataset:
    features: pl.LazyFrame
    labels: pl.LazyFrame
    def split(self, train_end: Date,
              valid_end: Date) -> tuple[TaskDataset, TaskDataset, TaskDataset]: ...
    def to_pandas(self) -> Any: ...
    def to_parquet(self, dest: str) -> None: ...
    def describe(self) -> dict: ...


class ValidationReport:
    passed: bool
    def table(self) -> pl.DataFrame: ...
    def failures(self) -> pl.DataFrame: ...


class CalibrationResult:
    best: Mapping[str, Any]
    def apply(self, config: Config) -> Config: ...
    def report(self, path: str) -> None: ...


def calibrate(config: Config, params: Sequence[str],
              targets: Sequence[str] | None = None, trials: int = 200,
              seeds: Sequence[int] = (1, 2, 3)) -> CalibrationResult: ...


class BehaviourModule:
    name: str
    streams: Sequence[str]
    def monthly(self, world: World, month: dt.date) -> None: ...
    def intents(self, world: World, day: dt.date) -> pl.DataFrame: ...
    def react(self, world: World, slot: int,
              settled: pl.DataFrame) -> pl.DataFrame | None: ...


class Typology:
    name: str
    tier: int
    def plan(self, ring: Mapping[str, Any], world: World,
             day: dt.date) -> pl.DataFrame: ...


class register:
    @staticmethod
    def module(cls: type) -> type: ...
    @staticmethod
    def typology(cls: type) -> type: ...
    @staticmethod
    def metric(fn: Callable[[Run], Any]) -> Callable[[Run], Any]: ...
    @staticmethod
    def product(spec: Mapping[str, Any]) -> None: ...
```

Interventions live in `arthasim.interventions`:

```python
@dataclass(frozen=True)
class MacroPath(Intervention):
    name: str
    series: Mapping[str, float]

@dataclass(frozen=True)
class SetPolicyRate(Intervention):
    date: Date
    change_bp: float

@dataclass(frozen=True)
class IncomeShock(Intervention):
    date: Date
    where: str
    kind: str
    rate: float
    months: int = 0

@dataclass(frozen=True)
class ExpenseShock(Intervention):
    date: Date
    where: str
    kind: str
    rate: float

@dataclass(frozen=True)
class DBTTransfer(Intervention):
    scheme: str
    amount: float
    where: str
    dates: Sequence[Date]

@dataclass(frozen=True)
class ChangeRailRule(Intervention):
    date: Date
    rail: str
    rule: str
    value: Any

@dataclass(frozen=True)
class ParamOverride(Intervention):
    param_id: str
    value: Any
    date: Date | None = None

@dataclass(frozen=True)
class SetHook(Intervention):
    kind: str
    impl: Any
    bank: str | None = None
    date: Date | None = None

@dataclass(frozen=True)
class BankRule(Intervention):
    date: Date
    bank: str
    rule: str
    value: Any

@dataclass(frozen=True)
class FraudCampaign(Intervention):
    typology: str
    intensity: float
    start: Date
    end: Date
    where: str | None = None

@dataclass(frozen=True)
class AwarenessCampaign(Intervention):
    date: Date
    typology: str
    reach: float
    effect: float

@dataclass(frozen=True)
class ProductLaunch(Intervention):
    date: Date
    bank: str
    product: str

@dataclass(frozen=True)
class MarketShock(Intervention):
    date: Date
    asset: str
    change: float
```

Task builders live in `arthasim.tasks` and all return a `TaskDataset`:

```python
# arthasim.tasks.fraud
def transactions(run: Run, bank: str, label: str = "truth") -> TaskDataset: ...
def mule_accounts(run: Run, bank: str, asof: Sequence[Date],
                  horizon_days: int = 30, label: str = "truth") -> TaskDataset: ...
def scam_victims(run: Run, asof: Sequence[Date],
                 horizon_days: int = 90) -> TaskDataset: ...

# arthasim.tasks.credit
def default(run: Run, product: str, asof: Sequence[Date],
            horizon_months: int = 12, bank: str | None = None) -> TaskDataset: ...
def lgd(run: Run, product: str, bank: str | None = None) -> TaskDataset: ...
def distress(run: Run, asof: Sequence[Date],
             horizon_days: int = 30) -> TaskDataset: ...

# arthasim.tasks.cards
def default(run: Run, bank: str, asof: Sequence[Date],
            horizon_months: int = 12) -> TaskDataset: ...
def revolve(run: Run, bank: str) -> TaskDataset: ...

# arthasim.tasks.invest
def sip_adoption(run: Run, asof: Sequence[Date],
                 horizon_days: int = 90) -> TaskDataset: ...
def sip_stop(run: Run, asof: Sequence[Date],
             horizon_days: int = 90) -> TaskDataset: ...

# arthasim.tasks.reco
def next_product(run: Run, bank: str, asof: Sequence[Date],
                 horizon_days: int = 90) -> TaskDataset: ...
def offer_response(run: Run, bank: str) -> TaskDataset: ...
```

Conventions: tables come back as Polars frames (`.to_pandas()` when needed). Money is integer paise. Times are in Asia/Kolkata. `where` is a filter expression over person or organisation attributes.

### 14.3 Worked examples

**Build, run, look around**

```python
import arthasim as sim

cfg = sim.Config.tier("S", start="2025-04-01", districts=["Pune", "Gaya"])
world = sim.World.build(cfg, seed=7)
run = world.run(until="2026-03-31")

print(run.validate().failures())

bank = run.view("bank", bank="SYNB03")
payments = bank.table("payments").collect()

trace = run.inspect(entity_id=41872)
print(trace.timeline())
print(trace.passbook())
```

**Fraud: train offline, then test the detector in the loop**

```python
import numpy as np
import polars as pl
import arthasim as sim
from arthasim import interventions as iv

ds = sim.tasks.fraud.transactions(run, bank="SYNB03", label="observed")
train, valid, test = ds.split(train_end="2025-09-30", valid_end="2025-11-30")
model = fit_my_model(train, valid)                    # your code


class MyDetector:
    def decide(self, payments, ctx):
        score = model.predict_proba(ctx.features("account").to_numpy())[:, 1]
        return pl.DataFrame({
            "payment_id": payments["payment_id"],
            "action": np.where(score > 0.9, "block", "allow"),
        })


campaign = iv.FraudCampaign("task_scam", intensity=2.0,
                            start="2025-10-01", end="2026-03-31")
base = sim.Scenario.baseline().add(campaign)
treat = base.add(iv.SetHook("fraud_control", MyDetector(),
                            bank="SYNB03", date="2025-10-01"))

exp = sim.Experiment(cfg, base, {"my_detector": treat}, seeds=range(1, 11),
                     intervene_at="2025-10-01", end="2026-03-31")
res = exp.run(workers=4)
print(res.effect("fraud_loss", by="bank"))
print(res.effect("genuine_block_rate", by="bank"))
```

**Loans and credit cards: test a policy**

```python
class MyUnderwriting:
    def decide(self, applications, ctx):
        pd_hat = pd_model.predict_proba(ctx.features("applicant").to_numpy())[:, 1]
        return pl.DataFrame({
            "application_id": applications["application_id"],
            "approve": pd_hat < 0.06,
            "amount": applications["amount_requested"],
            "rate": 0.11 + 0.5 * pd_hat,
            "tenure_months": applications["tenure_requested"],
        })


class LimitRule:
    def review(self, cards, ctx):
        good = (cards["utilisation_6m"] > 0.6) & (cards["max_dpd_12m"] == 0)
        return pl.DataFrame({
            "card_id": cards["card_id"],
            "new_limit": np.where(good, cards["limit"] * 1.25, cards["limit"]),
        })


plain = sim.Scenario.baseline()
arms = {
    "new_underwriting": plain.add(iv.SetHook("credit_policy", MyUnderwriting(),
                                             bank="SYNB03", date="2025-07-01")),
    "limit_rule": plain.add(iv.SetHook("card_policy", LimitRule(),
                                       bank="SYNB03", date="2025-07-01")),
}
exp = sim.Experiment(cfg, plain, arms, seeds=range(1, 11),
                     intervene_at="2025-07-01", end="2026-06-30")
res = exp.run(workers=4)
for metric in ["approval_rate", "npa_rate", "credit_loss", "card_revolve_share"]:
    print(res.effect(metric))
```

**Product recommendation: measure uplift**

```python
class MyRecommender:
    def recommend(self, customers, catalog, ctx):
        scores = reco_model.score(customers, catalog)     # customers x products
        best = scores.argmax(axis=1)
        return pl.DataFrame({
            "customer_id": customers["customer_id"],
            "product_id": catalog["product_id"].to_numpy()[best],
            "rank": np.ones(len(best), dtype=np.int64),
        })


treat = plain.add(iv.SetHook("recommender", MyRecommender(),
                             bank="SYNB03", date="2025-07-01"))
exp = sim.Experiment(cfg, plain, {"my_reco": treat}, seeds=range(1, 11),
                     intervene_at="2025-07-01", end="2026-03-31")
res = exp.run(workers=4)
print(res.effect("offer_acceptance"))
print(res.effect("product_holding", by="product"))
print(res.effect("npa_rate"))
```

**Policy and investments: rate rise, DBT tranche, market fall**

```python
arms = {
    "repo_plus_50": plain.add(iv.SetPolicyRate(date="2025-10-01", change_bp=50)),
    "dbt_2000": plain.add(iv.DBTTransfer("income_support", amount=2000,
                                         where="occupation == 'farmer'",
                                         dates=["2025-11-15"])),
    "equity_minus_15": plain.add(iv.MarketShock(date="2025-10-01",
                                                asset="equity", change=-0.15)),
}
exp = sim.Experiment(cfg, plain, arms, seeds=range(1, 21),
                     intervene_at="2025-10-01", end="2026-03-31")
res = exp.run(workers=4)
print(res.effect("emi_bounce_rate", by="product"))
print(res.effect("cash_withdrawal", by="district"))
print(res.effect("sip_stop_rate", by="age_band"))

sweep = exp.sweep("consumption.buffer_target_months", [2, 3, 4, 6])
print(sweep.effect("consumption"))
```

**Add your own metric**

```python
@sim.register.metric
def upi_lite_share(run):
    return run.sql("""
        select avg(case when rail = 'UPI_LITE' then 1.0 else 0.0 end) as share
        from payments where status = 'SUCCESS'
    """)
```

### 14.4 Environment

```
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

A plain virtual environment is enough; conda is not needed. The engine does not use Spark. Output is Parquet, so an existing PySpark or PyTorch environment can read it without sharing dependencies.

## 15. Calibration and validation

### 15.1 Parameter registry

Every number the model uses is one registry entry:

```yaml
- id: labour.ur.graduate_21_29
  value: 0.222
  unit: share
  as_of: "2025"
  source: "MoSPI PLFS annual report (primary table to be pinned)"
  status: unverified      # verified | unverified | assumption
  role: target            # input | target | holdout
  used_by: [modules.lifecourse]
```

- **Input.** Read by the model directly, for example a rail limit.
- **Target.** Fitted to during calibration, for example an unemployment rate.
- **Holdout.** Checked after calibration and never fitted, for example a festival uplift.
- **Assumption.** No empirical source, for example fraud capability weights. Reported with every experiment.

### 15.2 Calibration

1. Load inputs.
2. Fit free parameters by simulation at tier XS or S: a Bayesian optimiser proposes values, three-month runs are scored against targets, and the best set is kept.
3. Check holdouts.
4. Store the fitted set, the scores and the registry version with the run.

### 15.3 Acceptance checks

| Check | Type |
| :--- | :--- |
| Ledger invariants (section 7.3) | Hard |
| Same seed and config give identical output | Hard |
| No synthetic identifier matches a real format | Hard |
| Labour stocks by age, sex, education and area | Target |
| Pay and consumption distributions; category shares | Target |
| Transactions per person by rail; ticket-size distribution | Target |
| Salary-day inflow spike; month-end balance distribution | Target |
| Zero-balance and dormant account shares | Target |
| Delinquency roll rates; card revolving share (phase 3) | Target |
| SIP account share and average ticket (phase 4) | Target |
| Fraud loss and complaint rate per capita (phase 2) | Target |
| Festival uplift; cash-out lag after DBT | Holdout |
| Review of 50 random inspector traces by banking practitioners | Face validity |
| Train on simulated bank view, test on real bank data, and the reverse | Transfer |

The transfer test is the one that decides whether simulated results carry over to a real bank. The literature search found no published transfer test for a simulator of this kind (`related_works.md`, section 5), so it is an exit criterion for phase 2.

## 16. Scale, performance and stack

| Concern | Choice | Reason |
| :--- | :--- | :--- |
| Language | Python 3.11 or later | One language for engine and analysis |
| State | NumPy arrays, one per attribute | Vectorised updates; small memory footprint |
| Hot loops | Numba | Settlement is sequential within a slot and needs a compiled loop |
| Tables and I/O | Polars and PyArrow; Parquet partitioned by month | Fast, columnar, readable by Spark and pandas |
| Queries | DuckDB over Parquet | SQL without a server |
| Config | YAML validated with Pydantic | Typed, diffable |
| Tests | pytest and Hypothesis | Property tests suit the invariants |
| Parallel runs | Process pool across seeds and treatments | Runs are independent |
| Optimiser | Optuna or similar | Calibration |

Targets, to be measured in phase 0 and revised:

| Tier | 12 simulated months | Memory |
| :--- | :--- | :--- |
| XS | Under 5 minutes | Under 2 GB |
| S | Under 2 hours on a laptop | Under 8 GB |
| M | Under 24 hours on one server | Under 64 GB |

State is checkpointed at each month end, so a run can resume or fork from any month.

## 17. Privacy and release

- No real customer record is used at any stage. Behaviour comes from published aggregates.
- Identifiers use formats that cannot be real (section 5.3), and an automated test enforces this.
- Banks are synthetic. Simulated fraud or bad loans are never attributed to a real bank or branch.
- Three release levels: internal (truth and typology settings), partner (views, observed and truth labels), public (views, coarser geography, no evasion settings).
- Public release needs a legal review under the DPDP Act first.

## 18. Phases and exit criteria

| Phase | Builds | Exit criteria |
| :---: | :--- | :--- |
| 0. Spike | Tier XS world with salaries, consumption, UPI and cash; ledger with invariants; keyed randomness; Parquet output | 90 simulated days pass all invariants; identical output for identical seed; throughput measured |
| 1. Base world | Population build, life course with alignment, income, consumption, rails, deposits, banks, views, inspector, scenarios, experiments, registry, validation | Phase 1 acceptance checks pass at tier S; a paired experiment returns an effect with an interval; every phase 1 call in section 14.1 works |
| 2. Fraud | Typology library, victims, rings, controls, adaptation, truth and observed labels, fraud tasks and hook | Fraud targets met; a detector can be tested in the loop; transfer test on real bank data run and written up |
| 3. Credit and cards | Loan and card lifecycle, classification ladder, bureau, credit tasks and hooks | Roll-rate targets met; underwriting and limit policies testable in the loop |
| 4. Investments and recommendation | Investment products, market path, offers, recommender hook, tasks | Adoption targets met; uplift experiment runs end to end |
| 5. Scale and breadth | Tier M benchmark release; MSME, GST, self-help groups, farm credit; tier L design | Set when phase 4 closes |

The step after this document is approved is a task-by-task implementation plan for phase 0 and phase 1.

## 19. Decisions

**Open, for the project owner**

1. Districts for tier S. Default: one metro district and one rural district.
2. Simulation window. Default: April 2025 to March 2026.
3. Which real bank data can be used for the transfer test, and on what terms.
4. Whether public release is a goal. It adds work under section 17.
5. Phase order after phase 1. Default: fraud, then credit, then investments.
6. Package name. Working name: `arthasim`.

**Made in this draft, open to change**

1. Python-only engine; no Spark, GPU or LLM in the core.
2. Daily step with 96 settlement slots.
3. Macro variables are scenario inputs.
4. Integer paise for all money.
5. Twelve synthetic banks and two NBFCs at tier S.
6. Proportional mixing of illicit and clean funds.
7. v1's fraud weights and tier cut-offs kept as defaults, marked as assumptions.
8. Hooks are batch calls: per slot for fraud, daily for credit and offers, monthly for card limits.

## Appendix A. Registry starter, carried over from v1

Values are copied from v1 and have not been checked against primary sources. Each one enters the registry with status `unverified` until its primary table is pinned.

| Id | v1 value | v1 source label | Role |
| :--- | :--- | :--- | :--- |
| `labour.lfpr.15plus` | 59.3% | PLFS 2025 | Target |
| `labour.wpr.15plus` | 57.4% | PLFS 2025 | Target |
| `labour.ur.15plus` | 3.1% | PLFS 2025 | Target |
| `labour.ur.educated` | 6.5% | PLFS 2025 | Target |
| `labour.ur.graduate_21_29` | 22.2% | PLFS 2025 | Target |
| `labour.share.regular_salaried` | 23.6% overall, 49.6% urban | PLFS 2025 | Target |
| `labour.share.self_employed` | 56.2% overall, 62.7% rural | PLFS 2025 | Target |
| `pay.increment.corporate_mean` | 9.0% to 9.1% | EY, Deloitte 2026 | Input (organised sector only) |
| `pay.attrition.annual` | 16.2% to 17.6% | Aon, Deloitte | Target |
| `pay.switch_jump` | 20% to 35% | None given | Assumption |
| `pay.skill_premium` | 32% to 47% | Taggd, Aon | Input |
| `consumption.mpce` | ₹4,122 rural, ₹6,996 urban | HCES 2023–24 | Target |
| `consumption.gini` | 0.237 rural, 0.284 urban | HCES 2023–24 | Target |
| `consumption.food_share` | 47% rural, 40% urban | HCES 2023–24 | Target |
| `wealth.household_mean` | ₹15.9 lakh rural, ₹27.2 lakh urban | AIDIS (v1 calls this net worth; confirm whether it is assets) | Target |
| `inclusion.pmjdy.operative_share` | 81.2% | PMJDY | Target |
| `inclusion.pmjdy.zero_balance_share` | 8.2% | PMJDY | Target |
| `upi.volume.fy26` | 24,161.69 crore transactions | PIB | Target (scaled) |
| `upi.value.fy26` | ₹314 lakh crore | PIB | Target (scaled) |
| `upi.p2m.share` | 63% of volume, 29% of value | PIB | Target |
| `upi.p2m.share_under_500` | 86% | PIB | Target |
| `upi.p2p.share_under_500` | 59% | PIB | Target |
| `upi.lite.limits` | ₹1,000 per transaction, ₹5,000 wallet | PIB | Input |
| `upi.limit` | ₹1 lakh standard, ₹5 lakh for listed categories | PIB | Input |
| `rtgs.minimum` | ₹2 lakh | Payments guide (secondary) | Input |
| `imps.volume.fy26` | 4.94 billion | RBI | Target (scaled) |
| `aeps.volume.monthly` | 92.82 million (June 2026) | NPCI | Target (scaled) |
| `sip.inflow.monthly` | ₹32,490 crore across 10.06 crore accounts | AMFI | Target (scaled) |
| `cc_on_upi.value.monthly` | About ₹10,000 crore | Industry blog | Target (scaled) |
| `credit.classification.buckets` | SMA-0 1–30, SMA-1 31–60, SMA-2 61–90, NPA over 90 days | RBI IRACP | Input |
| `dbt.pm_kisan` | ₹2,000 three times a year | Government portal | Input |
| `fraud.loss.cy24` | ₹22,845.73 crore across 22.68 lakh complaints | MHA, I4C | Target (scaled) |
| `fraud.actor_share` | 0.5% to 2.0% of persons | None given | Assumption |
| `festival.diwali.upi_uplift` | +32% | News report | Holdout |
