# Related work: simulating a national financial ecosystem

Companion to `simulation_architrcture.md` (called "the blueprint" below). Literature searched on 13 November 2026. Numbers in square brackets point to the reference list at the end.

## 1. Short answer

No published system does what the blueprint proposes end to end. Each of its parts has a research community behind it, and a handful of projects come close on one or two axes:

- AMLworld [1] builds a multi-bank virtual world of people and companies with circular money flows and fully labelled laundering.
- Project Hertha [2] simulated the retail payments of one jurisdiction: 1.8 million accounts and 308 million transactions.
- FINESSE [3] couples several event streams (transactions, payments, account status changes) through latent agent states and ships labels for four tasks.
- FraudSociety [4] puts LLM-driven scammers and victims on a shared social feed with persistent ledgers.
- Data-driven macroeconomic agent-based models (ABMs) initialise whole national economies from accounts and microdata [5, 6]. Austria has been run at one agent per real person or firm.
- Dynamic microsimulation has modelled education, work and retirement transitions since the 1950s [7, 8].
- For India, BharatSim [9] runs up to 50 million synthetic agents, but for epidemiology.

The search did not find three things: a simulator that joins a life-course model to a closed, transaction-level ledger; one built around Indian rails and institutions (UPI, NACH, AePS, IRACP, SHGs); or one where agents drift into fraud through modelled financial stress and then gain skill. Those are the places where the blueprint is new. Most of the engineering problems it will hit already have published answers, and section 4 lists them.

## 2. Map of the literature

| Strand | What gets simulated | Representative work | Scale reported | Missing relative to the blueprint |
| :--- | :--- | :--- | :--- | :--- |
| Fraud and AML transaction simulators | Accounts and payments, with injected or agent-driven illicit flows | PaySim [10], AMLSim [11], AMLworld [1], AMLgentex [12], TransXion [13] | 180M transactions over 2.1M accounts [1]; 308M transactions [2] | Life course, credit, closed economy, Indian rails |
| LLM-agent fraud societies | Scammer and victim conversations, plus payments | FraudSociety [4], MultiAgentFraudBench [14] | Not the focus | Economy, banks, rails |
| Data-driven macro ABMs | Households, firms, banks and government with balance sheets; monthly or quarterly aggregates | EURACE [15], Poledna et al. [5], Wiese et al. [6], Axtell [16] | Austria at 1:1 [17]; 38 OECD countries with a scale factor [6]; 120M workers [16] | Individual payments, rails, crime |
| Dynamic microsimulation | Individual education, labour, family and pension transitions | LIAM2 [18], SimPaths [19] | Varies by model | Interaction between agents, money flows |
| Synthetic populations | People, households and workplaces with demographic attributes | SPEW [20], SynthPop++ [21], BharatSim [9] | 50M agents [9] | Financial attributes and behaviour |
| Payment-system simulators | Banks settling payments and managing liquidity | Bank of Finland simulator [22], Galbiati and Soramäki [23] | Interbank systems | Retail customers |
| Models of illicit choice | Individuals deciding whether to evade or offend | Becker [24], tax-compliance ABMs [25] | Stylised populations | Transactions, calibration to India |
| Learned generators | Samples that mimic a real dataset | CTGAN [26], Banksformer [27], SynthAML [28], BAF [29] | Size of the source data | Need real data; no causal structure |

## 3. The strands in detail

### 3.1 Transaction simulators built for fraud and AML research

**First generation: fit to a real log.** The oldest line is Lopez-Rojas and Axelsson's multi-agent simulators: RetSim for a shoe retailer [30], BankSim for bank payments [31] and PaySim for mobile money [10]. Each one fits agent behaviour to aggregate statistics from a real transaction log, replays that behaviour with fresh random draws, and adds agents that follow known fraud scripts. Their review [32] makes the case for simulation over anonymisation. The method is cheap and PaySim's public dataset is still a common benchmark, but it needs a real log to start from, and the agents have no attributes beyond their transaction habits. MoMTSim [33] is a recent descendant for mobile money with an iterative calibration loop.

**AMLSim: no source data, typology templates.** IBM's AMLSim [11, 34] removed the need for a real log. A graph generator lays down accounts and typology templates (fan-in, fan-out, cycles), and a simulator built on PaySim executes them. The AMLgentex authors list its limits: it covers the layering stage only, and it treats the network as closed, with no money entering or leaving [12].

**AMLworld: a virtual world.** AMLworld [1] is the closest published relative of the blueprint. Altman first built a virtual world of consumers and merchants for card data [35], which produced the TabFormer dataset [36]. AMLworld extends it to banks, individuals and companies linked in a circular-flow graph. Companies pay salaries and suppliers, people buy things, entities own other entities, and each holds accounts at several banks. How it works:

- Behaviour is drawn from statistical distributions taken from public sources (tax returns, labour-force rates, central-bank payment statistics). No real transactions are used as a seed.
- Parameters are tuned in a feedback loop until output statistics look right.
- Criminal agents earn illicit income from nine sources. The generator tags that money and follows the tag through every later transfer, so labels are complete.
- One bank's view is obtained by filtering the global ledger.
- The largest public dataset has about 180 million transactions across 2.1 million accounts over 97 days.

**Generators that start from real data.** SynthAML [28] was built from Spar Nord's alerts and transactions and reports that model performance on it transfers to the real bank; AMLgentex describes its method as Gaussian copulas [12]. Feedzai's BAF suite [29] trains a GAN on real account-opening fraud data.

**Since 2023: closer to what detection teams face.**

- AMLgentex [12], from AI Sweden with Handelsbanken and Swedbank, is designed around conditions earlier datasets ignore: partial observability, temporal dynamics, strategic behaviour, uncertain labels and class imbalance. It selects simulator parameters by multi-objective Bayesian optimisation.
- SAML-D [37] encodes 28 typologies, some taken from interviews with AML specialists.
- AMLNet [38] scores its generator against AUSTRAC rule coverage.
- TransXion [13] gives entities persistent profiles and synthesises illicit subgraphs stochastically. Its authors argue that template injection makes benchmarks too easy.
- A "hide and seek" framework [39] lets launderers and a detector co-evolve.
- Truman [40] uses LLM agents to generate transactions.
- AML-CFSim [41] models laundering of cyber-fraud proceeds. It is listed here by title and venue only; the full text was not read.
- FINESSE [3] generates several interdependent event streams per agent and supports balance forecasting, fraud detection, missed-payment prediction and next-event prediction from one run.
- A 2026 SEPA Instant study [42] simulates a German retail payment system with mule networks and authorised push payment fraud, each in a plain and an evasive variant, and withholds part of the labels on purpose.

**Central banks.** The BIS Innovation Hub's Project Aurora [43] generated a synthetic dataset of domestic and cross-border payments with embedded laundering patterns to compare siloed, national and cross-border monitoring. Project Hertha [2], with the Bank of England, built a synthetic dataset of 1.8 million accounts and 308 million transactions representing one jurisdiction's retail payments. It found that system-level analytics helped banks find 12% more illicit accounts than they would have found alone.

**Limits of the strand.** Agents are accounts with spending habits. Income is an exogenous draw: nobody is hired, promoted or laid off. Credit and delinquency are mostly absent, and FINESSE's missed-payment stream is the nearest thing to them.

### 3.2 Scam and victim simulations with LLM agents

FraudSociety [4] (October 2026) is the first simulator found that joins the information side of fraud to the money side. LLM agents see posts and messages, decide through a need, intent and action chain, and pay through persistent ledgers, while fraudsters adapt to each target's history. It is checked against aggregate fraud statistics and reproduces loss concentration: the top 10% of victim records carry 81% of losses. MultiAgentFraudBench [14] studies collusion among LLM scammers across 28 scenarios.

Both model the conversation that precedes a scam payment. The blueprint's victim matrix (its section 7.3) reduces that conversation to a probability.

### 3.3 Data-driven macroeconomic ABMs

**Accounting discipline.** EURACE [15] ran households, firms, banks and a government on the FLAME parallel framework in 2008. The Keynes+Schumpeter family [44] and the stock-flow-consistent benchmark of Caiani et al. [45] follow Godley and Lavoie [46]: every agent has a balance sheet, and every flow appears in a transaction-flow matrix whose rows and columns sum to zero. That is the published form of the blueprint's rule that every rupee debited is a rupee credited. It also covers bank credit creation, which the blueprint handles in FAQ Q2.

**Initialising from real data.** Poledna et al. [5] build Austria from national accounts, input-output tables, census and business-demography data, at one agent per real person or firm [17], and forecast as well as VAR and DSGE benchmarks. CANVAS [47] adapts the model to Canada for monetary-policy analysis. Wiese et al. [6] add synthetic populations with income, wealth and consumption heterogeneity, calibrate all 38 OECD countries with approximate Bayesian inference, and apply a scale factor to keep the agent count manageable. Papadopoulos [48] is a data-driven model of household income inequality, consumption, credit and credit risk. Axtell [16] simulates 120 million workers forming 6 million firms.

**Learning agents.** ABIDES-Economist [49] and the AI Economist [50] replace behavioural rules with reinforcement learning.

**Surveys.** Dawid and Delli Gatti [51], Axtell and Farmer [52], and Pangallo and del Rio-Chanona [17] cover the field. Borsos et al. [53] cover its use inside central banks.

**Limits.** These models step monthly or quarterly and track aggregates per agent (wages paid, consumption, loans outstanding). They do not emit individual payments, choose rails, or contain crime.

### 3.4 Dynamic microsimulation of life courses

The blueprint's life-stage machine (its section 4.2) is a dynamic microsimulation, a field that started with Orcutt [7]. Li and O'Donoghue [8] survey the models and their design choices: discrete or continuous time, closed or open populations, and how transition probabilities are estimated from panel data. Two points matter for the blueprint.

1. These models estimate flows (monthly or annual transition rates conditional on age, sex and education) and then use alignment to force simulated totals to match external stocks such as an official unemployment rate. That is the standard way to calibrate against cross-sectional surveys like PLFS.
2. Open frameworks exist: LIAM2 [18], JAS-mine [54] and SimPaths [19], which models education, work, family and health over the life course.

Earnings equations follow Mincer [55]. Saving and drawdown under income risk follow the buffer-stock literature [56, 57], which gives the blueprint's "emergency runway" variable a behavioural basis.

Microsimulation agents rarely transact with each other, so these models have no ledger.

### 3.5 Synthetic populations, including India

Population synthesis fits a joint distribution of person and household attributes to census margins, classically by iterative proportional fitting [58]. Harland et al. [59] compare methods, and SPEW [20] packages the pipeline for many countries.

India has dedicated work:

- SynthPop++ [21] combines surveys with partly overlapping attributes into a full-scale synthetic population.
- BharatSim [9] uses Census, IHDS, NSS and gridded-population data, assigns home and work locations and employment status, and simulates up to 50 million agents on a Scala core.
- The IISc-TIFR simulators [60] did the same at city scale for Bengaluru and Mumbai.

All three were built for COVID-19 and carry no income, account or credit attributes. They do solve the blueprint's first step, and they start from the census population, not the PAN register.

### 3.6 Payment-system simulators

Central banks have simulated payment systems for two decades, mostly at bank level. The Bank of Finland's simulator underlies a large body of liquidity and settlement studies [22]. Arciero et al. [61] and Galbiati and Soramäki [23] model banks as agents choosing when to release payments and how much liquidity to hold.

This is the literature to draw on if the blueprint's "switch traffic and liquidity" use case (its domain 5) is meant to cover settlement positions and queueing. It has no retail customers.

### 3.7 Models of entry into illicit activity

The blueprint's activation rule (its section 7.1) adds financial desperation and peer contagion, subtracts perceived enforcement, and compares the result with a personal threshold. Each term has a source:

- Expected utility and deterrence: Becker [24]; Allingham and Sandmo [62].
- Pressure as a cause: Agnew's strain theory [63]; Cressey's fraud triangle [64].
- Heterogeneous thresholds and contagion: Granovetter [65].

Agent-based tax-compliance models combined these in simulation long ago. Bloomquist [66] compares several, Korobow et al. [25] add social networks, and Hokamp and Pickhardt [67] mix agent types.

On mules, a survey of more than 3,000 Dutch people aged 16 to 25 found that almost one in ten had been approached by a recruiter, mostly through social media or peers, and under 1% admitted acting as a mule [68]. Norris et al. [69] review who falls for online fraud.

None of this supplies calibrated weights. The α coefficients and tier cut-offs in the blueprint's section 7 are modelling assumptions and should be labelled that way. The search found no simulator in which fraud capability grows with experience along a skill tree. The nearest are the co-evolution setup in [39] and the adaptive fraudsters in [4].

### 3.8 Engineering large agent populations

**Synchronisation.** Fujimoto [70] sets out conservative and optimistic synchronisation for parallel discrete-event simulation. The simpler alternative is bulk-synchronous stepping as in Pregel [71]: agents compute on the previous step's state, exchange messages, and the system commits at a barrier. Repast HPC [72] and FLAME GPU 2 [73] implement variants for CPU clusters and GPUs.

**Reproducibility.** Counter-based random number generators [74], which the blueprint already names (Philox, Threefry), make each draw a pure function of seed, agent and step, so results do not depend on how agents are partitioned.

**LLM agents at scale.** Tensorised ABMs reach millions of agents, and "LLM archetypes" let similar agents share language-model queries [75]. With one LLM per agent, AgentSociety reports about ten thousand agents and five million interactions [76]. Generative agents [77], homo silicus [78] and EconAgent [79] are the usual references. LLM agents suit conversation-level fraud (3.2). They are too costly to be the decision engine for a population in the tens of millions.

### 3.9 Learned generative models: the alternative route

The other way to get synthetic financial data is to train a generative model on real records: CTGAN for tables [26], TimeGAN and DoppelGANger for sequences [80, 81], Banksformer and REaLTabFormer for transaction and relational data [27, 82]. J.P. Morgan's overview [83] and the primer by Jordon et al. [84] cover uses and pitfalls. Three caveats apply:

1. These models need the real data the blueprint is trying to do without.
2. They reproduce correlations, so they cannot answer "what if the repo rate rises" questions.
3. Synthetic does not mean private. Stadler et al. [85] show that generative synthetic data either fails to stop inference attacks or loses utility.

The FCA's Synthetic Data Expert Group lists fraud and AML model development among its use cases and notes that validity and governance questions remain open [86]. The usual utility test is to train on synthetic data and test on real data [87].

### 3.10 Calibration, validation and model description

**Calibration.** Economic ABMs are calibrated by simulation: choose target moments, run the model, adjust parameters. Platt [88] compares methods, Lamperti et al. [89] train surrogates to cut the number of runs, Dyer et al. [90] use neural simulation-based inference, and the Bank of Italy's Black-it [91] is an open toolkit.

**Validation.** Fagiolo et al. [92] review practice. Pattern-oriented modelling [93] recommends testing against several independent patterns at different scales and keeping some of them out of calibration. The fraud-simulator papers validate more loosely: AMLworld compares transaction counts and payment mix with Federal Reserve statistics [1], SynthAML tests transfer to real bank data [28], and FraudSociety checks macro totals, micro concentration and intervention effects [4].

**Description.** The ODD protocol [94] is the standard template for describing an agent-based model: purpose, entities and state variables, process overview and scheduling, design concepts, initialisation, inputs and submodels.

### 3.11 India-specific work

The search found three kinds of work for India:

1. Synthetic-population and epidemic simulators (3.5).
2. One economic ABM: Bubna et al. [95] on the outcomes of the 2016 demonetisation, listed here by title only.
3. Scripted UPI fraud datasets on Kaggle, for example [96], which is generated programmatically with banks chosen by market share and a fraud flag set at a 0.2% base rate.

It found no agent-based simulator of the Indian financial system with UPI, NACH or AePS rails, IRACP delinquency or SHG finance, and no India-calibrated macro ABM of the Poledna type.

On the policy side, the RBI's FREE-AI committee report (August 2025) recommends shared financial-sector data infrastructure and an AI innovation sandbox [97]. That is the institutional setting in which a simulator like this would be used.

## 4. How prior work handles the blueprint's hard problems

| Problem in the blueprint | Published approach | Sources | Suggested use |
| :--- | :--- | :--- | :--- |
| Building the population | Fit joint person and household attributes to census margins; India pipelines exist | [58, 21, 9] | Start from a census-based synthetic population and attach PAN, accounts and income as attributes |
| Life-stage transitions | Estimate transition rates from panel data; align simulated totals to official stocks | [8, 19] | Treat PLFS rates as alignment targets, not as transition probabilities |
| Money conservation and credit creation | Balance sheet per agent plus a transaction-flow matrix checked every step | [46, 45] | Adopt the matrix as an automated invariant; add cash and bank ledgers |
| Generating individual transactions | Entity graph of recurring relationships (employer, supplier, merchant) with frequencies and amount distributions | [1, 35] | Same pattern, driven by life-course state in place of fixed draws |
| Illicit behaviour | Typology templates; illicit funds tagged at source; stochastic non-template subgraphs; co-evolving adversaries | [11, 1, 13, 39] | Tag funds at source as AMLworld does; avoid pure templates |
| What an observer can see | Filter the global ledger to one bank; model label noise and missing labels | [1, 12, 42] | Publish per-observer views and a separate truth layer |
| Calibration | Public statistics with feedback tuning; Bayesian optimisation against targets; simulation-based inference | [1, 12, 6, 88] | Keep a registry of targets and fit by simulation |
| Validation | Held-out patterns at several scales; out-of-sample forecasting; transfer to real data | [93, 5, 28] | Hold some benchmarks out of calibration |
| Scale | 1:1 national populations exist for periodic macro models; transaction simulators stop at a few hundred million rows; scale factors are normal | [17, 16, 6, 2] | State a scale factor; do not assume 80 crore agents at transaction level |
| Parallel execution and reproducibility | Bulk-synchronous steps or parallel discrete-event simulation; counter-based RNG | [71, 70, 74] | Daily barrier: intents, settlement, commit |
| Describing the model | ODD protocol | [94] | Restructure the blueprint's model sections along ODD |
| Privacy claims | Synthetic data is not automatically private; rule-based worlds with no real seed avoid most of the problem | [85, 1, 86] | State that no real records are used, and avoid validly formatted real identifiers |

## 5. What is new in the blueprint, and what the literature warns about

New relative to the work above:

1. A life course (education, work, pay, job loss) that drives a transaction ledger. Microsimulation has the first half and AMLworld the second.
2. Credit delinquency under a specific regulatory ladder (IRACP SMA and NPA) inside a transaction simulator.
3. Entry into fraud that follows from modelled stress, with capability that grows with experience.
4. Indian rails, institutions and informal finance.
5. One run that serves credit, wealth, payments and fraud labels together. FINESSE [3] is the only precedent, and it is much narrower.

Warnings from the literature:

1. Template-injected fraud inflates detector scores [13].
2. The search found no published test showing that models trained on a rule-based virtual world transfer to real bank data. SynthAML shows transfer [28], but it was built from real data. The AMLworld authors say performance may not carry over one to one [1]. A transfer test on a partner bank's data belongs early in the plan.
3. Published transaction simulators stop at a few hundred million rows and a few million accounts [1, 2]. One-to-one national runs exist only for models that step monthly or quarterly [17].
4. LLM agents work for scam dialogue and are too costly as the main engine [75, 76].
5. A synthetic dataset is not private by construction [85].

## 6. Search method and limits

- Sources: the arXiv API, OpenAlex, Crossref and general web search, queried on 13 November 2026.
- Checks: every DOI below resolves (Crossref or the DOI handle system) and every arXiv ID was confirmed against the arXiv API. Other links were fetched. One exception: the Axtell (2016) entry points to the ACM Digital Library, which blocks automated checks, so its details come from OpenAlex.
- Depth: descriptions rely on abstracts and on prior familiarity with the older papers. AMLworld was read in full. Two entries are listed by title only and are marked in the text.
- Preprints: FINESSE, FraudSociety and the SEPA Instant study date from August to October 2026 and are not peer reviewed.
- Coverage: the search was in English. It will have missed simulators that banks and vendors keep internal, and Indian working papers that are not indexed.

## References

1. Altman, E., Blanuša, J., von Niederhäusern, L., Egressy, B., Anghel, A., & Atasu, K. (2023). Realistic synthetic financial transactions for anti-money laundering models. *NeurIPS 2023, Datasets and Benchmarks Track*. arXiv:2306.16424. <https://arxiv.org/abs/2306.16424>
2. BIS Innovation Hub London Centre & Bank of England (2025). Project Hertha: Identifying financial crime patterns in real-time retail payment systems. <https://www.bis.org/publications/project-hertha-identifying-financial-crime-patterns-real-time-retail-payment-systems>
3. Farnan, T., Eng, B., Abate, A., Hou, X., et al. (2026). FINESSE: An agent-based simulator and benchmark dataset for multimodal financial event sequences. arXiv:2609.11993. <https://arxiv.org/abs/2609.11993>
4. Chen, K., Jiang, M., Li, Z., Zhao, Y., et al. (2026). FraudSociety: A generative agent-based society for the financial-fraud economy. arXiv:2610.33536. <https://arxiv.org/abs/2610.33536>
5. Poledna, S., Miess, M. G., Hommes, C., & Rabitsch, K. (2023). Economic forecasting with an agent-based model. *European Economic Review*, 151, 104306. <https://doi.org/10.1016/j.euroecorev.2022.104306>
6. Wiese, S., Kaszowska-Mojsa, J., Dyer, J., Moran, J., et al. (2024). Forecasting macroeconomic dynamics using a calibrated data-driven agent-based model. arXiv:2409.18760. <https://arxiv.org/abs/2409.18760>
7. Orcutt, G. H. (1957). A new type of socio-economic system. *The Review of Economics and Statistics*, 39(2), 116–123. <https://doi.org/10.2307/1928528>
8. Li, J., & O'Donoghue, C. (2013). A survey of dynamic microsimulation models: Uses, model structure and methodology. *International Journal of Microsimulation*, 6(2), 3–55. <https://doi.org/10.34196/ijm.00082>
9. Cherian, P., Kshirsagar, J., Neekhra, B., Deshkar, G., et al. (2024). BharatSim: An agent-based modelling framework for India. *PLOS Computational Biology*, 20(12), e1012682. <https://doi.org/10.1371/journal.pcbi.1012682>
10. Lopez-Rojas, E. A., Elmir, A., & Axelsson, S. (2016). PaySim: A financial mobile money simulator for fraud detection. *28th European Modeling and Simulation Symposium (EMSS)*, 249–255. <https://www.msc-les.org/proceedings/emss/2016/EMSS2016_249.pdf>
11. Suzumura, T., & Kanezashi, H. (2021). Anti-Money Laundering Datasets: InPlusLab Anti-Money Laundering Datasets (AMLSim). IBM, GitHub repository. <https://github.com/IBM/AMLSim>
12. Östman, J., Callisen, E., Chen, A., Ausmees, K., et al. (2025). AMLgentex: Mobilizing data-driven research to combat money laundering. arXiv:2506.13989. <https://arxiv.org/abs/2506.13989>
13. Chen, K., Jiang, M., Zhao, Y., Li, Z., et al. (2026). TransXion: A high-fidelity graph benchmark for realistic anti-money laundering. *KDD 2026*. arXiv:2604.17420. <https://doi.org/10.1145/3770855.3817550>
14. Ren, Q., Zheng, Z., Guo, J., Yan, J., Ma, L., & Shao, J. (2026). When AI agents collude online: Financial fraud risks by collaborative LLM agents on social platforms. *ICLR 2026*. arXiv:2511.06448. <https://arxiv.org/abs/2511.06448>
15. Deissenberg, C., van der Hoog, S., & Dawid, H. (2008). EURACE: A massively parallel agent-based model of the European economy. *Applied Mathematics and Computation*, 204(2), 541–552. <https://doi.org/10.1016/j.amc.2008.05.116>
16. Axtell, R. L. (2016). 120 million agents self-organize into 6 million firms: A model of the U.S. private sector. *AAMAS 2016*. <https://dl.acm.org/doi/10.5555/2936924.2937042>
17. Pangallo, M., & del Rio-Chanona, R. M. (2024). Data-driven economic agent-based models. arXiv:2412.16591. <https://arxiv.org/abs/2412.16591>
18. de Menten, G., Dekkers, G., Bryon, G., Liégeois, P., & O'Donoghue, C. (2014). LIAM2: A new open source development tool for discrete-time dynamic microsimulation models. *Journal of Artificial Societies and Social Simulation*, 17(3), 9. <https://doi.org/10.18564/jasss.2574>
19. Richiardi, M. G., Bronka, P., van de Ven, J., Kopasker, D., et al. (2025). SimPaths: An open-source microsimulation model for life course analysis. *International Journal of Microsimulation*, 18(1). <https://doi.org/10.34196/ijm.00318>
20. Gallagher, S., Richardson, L. F., Ventura, S. L., & Eddy, W. F. (2018). SPEW: Synthetic Populations and Ecosystems of the World. *Journal of Computational and Graphical Statistics*, 27(4), 773–784. <https://doi.org/10.1080/10618600.2018.1442342>
21. Neekhra, B., Kapoor, K., & Gupta, D. (2023). SynthPop++: A hybrid framework for generating a country-scale synthetic population. arXiv:2304.12284. <https://arxiv.org/abs/2304.12284>
22. Bank of Finland (2012). *Diagnostics for the financial markets: Computational studies of payment system. Simulator Seminar Proceedings 2009–2011*. Scientific Monographs E:45. <http://hdl.handle.net/10419/212978>
23. Galbiati, M., & Soramäki, K. (2011). An agent-based model of payment systems. *Journal of Economic Dynamics and Control*, 35(6), 859–875. <https://doi.org/10.1016/j.jedc.2010.11.001>
24. Becker, G. S. (1968). Crime and punishment: An economic approach. *Journal of Political Economy*, 76(2), 169–217. <https://doi.org/10.1086/259394>
25. Korobow, A., Johnson, C., & Axtell, R. (2007). An agent-based model of tax compliance with social networks. *National Tax Journal*, 60(3), 589–610. <https://doi.org/10.17310/ntj.2007.3.16>
26. Xu, L., Skoularidou, M., Cuesta-Infante, A., & Veeramachaneni, K. (2019). Modeling tabular data using conditional GAN. *NeurIPS 2019*. arXiv:1907.00503. <https://arxiv.org/abs/1907.00503>
27. Nickerson, K., Tricco, T., Kolokolova, A., Shoeleh, F., et al. (2023). Banksformer: A deep generative model for synthetic transaction sequences. *Lecture Notes in Computer Science*, Springer, 121–136. <https://doi.org/10.1007/978-3-031-26422-1_8>
28. Jensen, R. I. T., Ferwerda, J., Jørgensen, K. S., Jensen, E. R., et al. (2023). A synthetic data set to benchmark anti-money laundering methods. *Scientific Data*, 10(1). <https://doi.org/10.1038/s41597-023-02569-2>
29. Jesus, S., Pombal, J., Alves, D., Cruz, A., et al. (2022). Turning the tables: Biased, imbalanced, dynamic tabular datasets for ML evaluation. *NeurIPS 2022, Datasets and Benchmarks Track*. arXiv:2211.13358. <https://arxiv.org/abs/2211.13358>
30. Lopez-Rojas, E. A., Gorton, D., & Axelsson, S. (2013). RetSim: A shoe store agent-based simulation for fraud detection. *25th European Modeling and Simulation Symposium (EMSS)*, 25–34. <http://www.msc-les.org/proceedings/emss/2013/EMSS2013_25.pdf>
31. Lopez-Rojas, E. A., & Axelsson, S. (2014). BankSim: A bank payments simulator for fraud detection research. *26th European Modeling and Simulation Symposium (EMSS)*, 144–152. <http://www.msc-les.org/proceedings/emss/2014/EMSS2014_144.pdf>
32. Lopez-Rojas, E. A., & Axelsson, S. (2016). A review of computer simulation for fraud detection research in financial datasets. *Future Technologies Conference (FTC)*, 932–935. <https://doi.org/10.1109/FTC.2016.7821715>
33. Azamuke, D., Katarahweire, M., & Bainomugisha, E. (2024). MoMTSim: A multi-agent-based simulation platform calibrated for mobile money transactions. *IEEE Access*, 12, 120226–120238. <https://doi.org/10.1109/ACCESS.2024.3439012>
34. Weber, M., Chen, J., Suzumura, T., Pareja, A., et al. (2018). Scalable graph learning for anti-money laundering: A first look. arXiv:1812.00076. <https://arxiv.org/abs/1812.00076>
35. Altman, E. (2021). Synthesizing credit card transactions. *Proceedings of the 2nd ACM International Conference on AI in Finance (ICAIF)*. <https://doi.org/10.1145/3490354.3494378>
36. Padhi, I., Schiff, Y., Melnyk, I., Rigotti, M., et al. (2021). Tabular transformers for modeling multivariate time series. *ICASSP 2021*. <https://doi.org/10.1109/ICASSP39728.2021.9414142>
37. Oztas, B., Cetinkaya, D., Adedoyin, F., Budka, M., et al. (2023). Enhancing anti-money laundering: Development of a synthetic transaction monitoring dataset. *IEEE International Conference on e-Business Engineering (ICEBE)*. <https://doi.org/10.1109/ICEBE59045.2023.00028>
38. Huda, S., Foo, E., Jadidi, Z., Newton, M. A. H., & Sattar, A. (2025). AMLNet: A knowledge-based multi-agent framework to generate and detect realistic money laundering transactions. arXiv:2509.11595. <https://arxiv.org/abs/2509.11595>
39. Wang, Q., Tsai, W.-T., Shi, T.-Y., Tang, W., & Du, B.-W. (2025). Hide and seek in transaction networks: A multi-agent framework for simulating and detecting money laundering activities. *Complex & Intelligent Systems*, 11(6). <https://doi.org/10.1007/s40747-025-01913-w>
40. Kute, D. V., Xu, Z., Li, Y., & Rabhi, F. (2025). Truman: A large language model-based multi-agent simulator for synthetic money laundering data generation. *AAMAS 2025*. <https://doi.org/10.65109/ugqe9687>
41. Ding, N., Fan, Z., Zhai, Y., Wang, Y., et al. (2025). AML-CFSim: An agent-based simulation model for anti-money laundering from cyber fraud crimes. *Expert Systems with Applications*, 285, 127995. <https://doi.org/10.1016/j.eswa.2025.127995>
42. Abolfadl, A. (2026). KONTOGRAPH: Verified point-in-time feature consistency and amortised explanation for real-time anti-money laundering under a 200 ms decision budget. arXiv:2608.22389. <https://arxiv.org/abs/2608.22389>
43. BIS Innovation Hub Nordic Centre (2023). Project Aurora: The power of data, technology and collaboration to combat money laundering across institutions and borders. <https://www.bis.org/publ/othp66.htm>
44. Dosi, G., Fagiolo, G., & Roventini, A. (2010). Schumpeter meeting Keynes: A policy-friendly model of endogenous growth and business cycles. *Journal of Economic Dynamics and Control*, 34(9), 1748–1767. <https://doi.org/10.1016/j.jedc.2010.06.018>
45. Caiani, A., Godin, A., Caverzasi, E., Gallegati, M., et al. (2016). Agent based-stock flow consistent macroeconomics: Towards a benchmark model. *Journal of Economic Dynamics and Control*, 69, 375–408. <https://doi.org/10.1016/j.jedc.2016.06.001>
46. Godley, W., & Lavoie, M. (2007). *Monetary Economics: An Integrated Approach to Credit, Money, Income, Production and Wealth*. Palgrave Macmillan. <https://doi.org/10.1057/9780230626546>
47. Hommes, C., He, M., Poledna, S., Siqueira, M., et al. (2025). CANVAS: A Canadian behavioral agent-based model for monetary policy. *Journal of Economic Dynamics and Control*, 172, 104986. <https://doi.org/10.1016/j.jedc.2024.104986>
48. Papadopoulos, G. (2019). Income inequality, consumption, credit and credit risk in a data-driven agent-based model. *Journal of Economic Dynamics and Control*, 104, 39–73. <https://doi.org/10.1016/j.jedc.2019.05.002>
49. Dwarakanath, K., Balch, T., & Vyetrenko, S. (2024). ABIDES-Economist: Agent-based simulator of economic systems with learning agents. arXiv:2402.09563. <https://arxiv.org/abs/2402.09563>
50. Zheng, S., Trott, A., Srinivasa, S., Parkes, D. C., & Socher, R. (2022). The AI Economist: Taxation policy design via two-level deep multiagent reinforcement learning. *Science Advances*, 8(18). <https://doi.org/10.1126/sciadv.abk2607>
51. Dawid, H., & Delli Gatti, D. (2018). Agent-based macroeconomics. *Handbook of Computational Economics*, vol. 4, 63–156. <https://doi.org/10.1016/bs.hescom.2018.02.006>
52. Axtell, R. L., & Farmer, J. D. (2025). Agent-based modeling in economics and finance: Past, present, and future. *Journal of Economic Literature*, 63(1), 197–287. <https://doi.org/10.1257/jel.20221319>
53. Borsos, A., Carro, A., Glielmo, A., Hinterschweiger, M., et al. (2025). Agent-based modeling at central banks: Recent developments and new challenges. *Banco de España Occasional Paper*. <https://doi.org/10.53479/39238>
54. Richiardi, M. G., & Richardson, R. E. (2017). JAS-mine: A new platform for microsimulation and agent-based modelling. *International Journal of Microsimulation*, 10(1), 106–134. <https://doi.org/10.34196/ijm.00151>
55. Mincer, J. (1974). *Schooling, Experience, and Earnings*. National Bureau of Economic Research. <https://www.nber.org/books-and-chapters/schooling-experience-and-earnings>
56. Deaton, A. (1991). Saving and liquidity constraints. *Econometrica*, 59(5), 1221–1248. <https://doi.org/10.2307/2938366>
57. Carroll, C. D. (1997). Buffer-stock saving and the life cycle/permanent income hypothesis. *The Quarterly Journal of Economics*, 112(1), 1–55. <https://doi.org/10.1162/003355397555109>
58. Beckman, R. J., Baggerly, K. A., & McKay, M. D. (1996). Creating synthetic baseline populations. *Transportation Research Part A*, 30(6), 415–429. <https://doi.org/10.1016/0965-8564(96)00004-3>
59. Harland, K., Heppenstall, A., Smith, D., & Birkin, M. (2012). Creating realistic synthetic populations at varying spatial scales: A comparative critique of population synthesis techniques. *Journal of Artificial Societies and Social Simulation*, 15(1), 1. <https://doi.org/10.18564/jasss.1909>
60. Agrawal, S., Bhandari, S., Bhattacharjee, A., Deo, A., et al. (2020). City-scale agent-based simulators for the study of non-pharmaceutical interventions in the context of the COVID-19 epidemic. *Journal of the Indian Institute of Science*, 100(4). <https://doi.org/10.1007/s41745-020-00211-3>
61. Arciero, L., Biancotti, C., D'Aurizio, L., & Impenna, C. (2009). Exploring agent-based methods for the analysis of payment systems: A crisis model for StarLogo TNG. *Journal of Artificial Societies and Social Simulation*, 12(1), 2. <https://www.jasss.org/12/1/2.html>
62. Allingham, M. G., & Sandmo, A. (1972). Income tax evasion: A theoretical analysis. *Journal of Public Economics*, 1(3–4), 323–338. <https://doi.org/10.1016/0047-2727(72)90010-2>
63. Agnew, R. (1992). Foundation for a general strain theory of crime and delinquency. *Criminology*, 30(1), 47–88. <https://doi.org/10.1111/j.1745-9125.1992.tb01093.x>
64. Cressey, D. R. (1953). *Other People's Money: A Study in the Social Psychology of Embezzlement*. Free Press.
65. Granovetter, M. (1978). Threshold models of collective behavior. *American Journal of Sociology*, 83(6), 1420–1443. <https://doi.org/10.1086/226707>
66. Bloomquist, K. M. (2006). A comparison of agent-based models of income tax evasion. *Social Science Computer Review*, 24(4), 411–425. <https://doi.org/10.1177/0894439306287021>
67. Hokamp, S., & Pickhardt, M. (2010). Income tax evasion in a society of heterogeneous agents: Evidence from an agent-based model. *International Economic Journal*, 24(4), 541–553. <https://doi.org/10.1080/10168737.2010.525994>
68. Bekkers, L., van Houten, Y., Spithoven, R., & Leukfeldt, E. R. (2023). Money mules and cybercrime involvement mechanisms: Exploring the experiences and perceptions of young people in the Netherlands. *Deviant Behavior*, 44(9), 1368–1385. <https://doi.org/10.1080/01639625.2023.2196365>
69. Norris, G., Brookes, A., & Dowell, D. (2019). The psychology of internet fraud victimisation: A systematic review. *Journal of Police and Criminal Psychology*, 34(3), 231–245. <https://doi.org/10.1007/s11896-019-09334-5>
70. Fujimoto, R. M. (1990). Parallel discrete event simulation. *Communications of the ACM*, 33(10), 30–53. <https://doi.org/10.1145/84537.84545>
71. Malewicz, G., Austern, M. H., Bik, A. J. C., Dehnert, J. C., et al. (2010). Pregel: A system for large-scale graph processing. *SIGMOD 2010*, 135–146. <https://doi.org/10.1145/1807167.1807184>
72. Collier, N., & North, M. (2013). Parallel agent-based simulation with Repast for High Performance Computing. *Simulation*, 89(10), 1215–1235. <https://doi.org/10.1177/0037549712462620>
73. Richmond, P., Chisholm, R., Heywood, P., Chimeh, M. K., et al. (2023). FLAME GPU 2: A framework for flexible and performant agent based simulation on GPUs. *Software: Practice and Experience*, 53(8), 1659–1680. <https://doi.org/10.1002/spe.3207>
74. Salmon, J. K., Moraes, M. A., Dror, R. O., & Shaw, D. E. (2011). Parallel random numbers: As easy as 1, 2, 3. *SC '11*. <https://doi.org/10.1145/2063384.2063405>
75. Chopra, A., Kumar, S., Giray-Kuru, N., Raskar, R., et al. (2024). On the limits of agency in agent-based models. arXiv:2409.10568. <https://arxiv.org/abs/2409.10568>
76. Piao, J., Yan, Y., Zhang, J., Li, N., et al. (2025). AgentSociety: Large-scale simulation of LLM-driven generative agents advances understanding of human behaviors and society. arXiv:2502.08691. <https://arxiv.org/abs/2502.08691>
77. Park, J. S., O'Brien, J. C., Cai, C. J., Morris, M. R., Liang, P., & Bernstein, M. S. (2023). Generative agents: Interactive simulacra of human behavior. *UIST 2023*. <https://doi.org/10.1145/3586183.3606763>
78. Horton, J. J., Filippas, A., & Manning, B. S. (2023). Large language models as simulated economic agents: What can we learn from homo silicus? arXiv:2301.07543. <https://arxiv.org/abs/2301.07543>
79. Li, N., Gao, C., Li, M., Li, Y., & Liao, Q. (2023). EconAgent: Large language model-empowered agents for simulating macroeconomic activities. arXiv:2310.10436. <https://arxiv.org/abs/2310.10436>
80. Yoon, J., Jarrett, D., & van der Schaar, M. (2019). Time-series generative adversarial networks. *NeurIPS 2019*. <https://papers.nips.cc/paper/2019/hash/c9efe5f26cd17ba6216bbe2a7d26d490-Abstract.html>
81. Lin, Z., Jain, A., Wang, C., Fanti, G., & Sekar, V. (2020). Using GANs for sharing networked time series data: Challenges, initial promise, and open questions. *ACM Internet Measurement Conference*, 464–483. <https://doi.org/10.1145/3419394.3423643>
82. Solatorio, A. V., & Dupriez, O. (2023). REaLTabFormer: Generating realistic relational and tabular data using transformers. arXiv:2302.02041. <https://arxiv.org/abs/2302.02041>
83. Assefa, S. A., Dervovic, D., Mahfouz, M., Tillman, R. E., et al. (2020). Generating synthetic data in finance: Opportunities, challenges and pitfalls. *Proceedings of the 1st ACM International Conference on AI in Finance (ICAIF)*. <https://doi.org/10.1145/3383455.3422554>
84. Jordon, J., Szpruch, L., Houssiau, F., Bottarelli, M., et al. (2022). Synthetic data: What, why and how? arXiv:2205.03257. <https://arxiv.org/abs/2205.03257>
85. Stadler, T., Oprisanu, B., & Troncoso, C. (2022). Synthetic data: Anonymisation groundhog day. *USENIX Security 2022*. arXiv:2011.07018. <https://www.usenix.org/conference/usenixsecurity22/presentation/stadler>
86. Financial Conduct Authority, Synthetic Data Expert Group (2024). Report: Using synthetic data in financial services. <https://www.fca.org.uk/publications/corporate-documents/report-using-synthetic-data-financial-services>
87. Esteban, C., Hyland, S. L., & Rätsch, G. (2017). Real-valued (medical) time series generation with recurrent conditional GANs. arXiv:1706.02633. <https://arxiv.org/abs/1706.02633>
88. Platt, D. (2020). A comparison of economic agent-based model calibration methods. *Journal of Economic Dynamics and Control*, 113, 103859. <https://doi.org/10.1016/j.jedc.2020.103859>
89. Lamperti, F., Roventini, A., & Sani, A. (2018). Agent-based model calibration using machine learning surrogates. *Journal of Economic Dynamics and Control*, 90, 366–389. <https://doi.org/10.1016/j.jedc.2018.03.011>
90. Dyer, J., Cannon, P., Farmer, J. D., & Schmon, S. M. (2024). Black-box Bayesian inference for agent-based models. *Journal of Economic Dynamics and Control*, 161, 104827. <https://doi.org/10.1016/j.jedc.2024.104827>
91. Benedetti, M., Catapano, G., De Sclavis, F., Favorito, M., et al. (2022). Black-it: A ready-to-use and easy-to-extend calibration kit for agent-based models. *Journal of Open Source Software*, 7(79), 4622. <https://doi.org/10.21105/joss.04622>
92. Fagiolo, G., Guerini, M., Lamperti, F., Moneta, A., & Roventini, A. (2019). Validation of agent-based models in economics and finance. In *Computer Simulation Validation*, Springer, 763–787. <https://doi.org/10.1007/978-3-319-70766-2_31>
93. Grimm, V., Revilla, E., Berger, U., Jeltsch, F., et al. (2005). Pattern-oriented modeling of agent-based complex systems: Lessons from ecology. *Science*, 310(5750), 987–991. <https://doi.org/10.1126/science.1116681>
94. Grimm, V., Railsback, S. F., Vincenot, C. E., Berger, U., et al. (2020). The ODD protocol for describing agent-based and other simulation models: A second update to improve clarity, replication, and structural realism. *Journal of Artificial Societies and Social Simulation*, 23(2), 7. <https://doi.org/10.18564/jasss.4259>
95. Bubna, R., Raveendran, J., Kumar, S., Duggirala, M., & Malik, M. (2019). A partially grounded agent based model on demonetisation outcomes in India. In *Simulation Foundations, Methods and Applications*, Springer, 247–275. <https://doi.org/10.1007/978-3-030-17164-3_12>
96. UPI Transactions 2024 Dataset: Synthetic dataset of UPI transaction patterns in India. Kaggle (example of a scripted dataset). <https://www.kaggle.com/datasets/skullagos5246/upi-transactions-2024-dataset>
97. Reserve Bank of India (2025). FREE-AI Committee Report: Framework for Responsible and Ethical Enablement of Artificial Intelligence. 13 August 2025. <https://rbi.org.in/scripts/PublicationReportDetails.aspx?ID=1306>
