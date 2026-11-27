# Rider tolerance for pooled rides: detour, wait, discount, co-riders, women-only (checked against the Campus Connect thresholds)

Thresholds under test: (a) in-car distance ≤ min(1.5 × solo, solo + 4 km); (b) class end times ≤ 20 min apart, so a gate wait of up to about 20 min; (c) every rider saves ≥ 20% vs. solo; (d) at most 4 riders per car; (e) a women-only option.

Labels used below: **SP** = stated preference (survey or choice experiment). **RP** = revealed preference (observed behaviour or market data).

---

## Q1. What detour or extra travel time do riders accept in pooled rides?

### Takeaway
No study gives one universal "acceptable detour". The evidence is consistent on one point: **added time is the main barrier to pooling, more than sharing with strangers**. In SP designs, shared options typically carry +25% to +75% extra time (or +4 to +10 min). In a 2025–26 Chinese SP survey, a 40% detour was treated as "moderate", but even at that level only a minority accepted pooling at discounts of 20–30%. The 1.5× (+50%) cap is at the upper edge of what the literature treats as tolerable. The +4 km absolute cap is the stricter constraint for long trips and is helpful.

### Cited Findings
- **(SP, Dallas–Fort Worth, commuters, n≈1,600, AV ride-hailing context.)** Lavieri & Bhat (2019, *Transportation Research Part A* 124:242–261): "the travel time added to the trip to serve other passengers may be a greater barrier to the use of shared services compared to the presence of a stranger." Choice-experiment levels for the shared option were +4, +8, or +10 min of added travel time on base trips of 10/15/20 min, paired with 20%/40%/60% discounts and 1/2/3 extra passengers. — [Lavieri & Bhat 2019 (author PDF)](https://www.caee.utexas.edu/prof/bhat/ABSTRACTS/WTS_paper.pdf); [EconPapers record](https://econpapers.repec.org/RePEc:eee:transa:v:124:y:2019:i:c:p:242-261)
- **(Joint RP+SP, Austin TX, 2019 survey.)** Kang, Mondal, Bhat & Bhat ("Pooled Versus Private Ride-Hailing"). SP pooled options added **25%, 50%, or 75%** extra travel time (time includes waiting plus pickup/drop-off of others), with discounts of 20%/25%/50% and 1–3 extra passengers. Base private trip was 13 min (±5) at $15 (±$5), taken from RideAustin data. Average presented times were 15.1 min private vs 22.8 min pooled, a 7.7 min difference. — [Kang et al. (author PDF)](https://www.caee.utexas.edu/prof/bhat/ABSTRACTS/PooledRH.pdf)
- **(Same Austin study, policy simulation.)** For commute trips, cutting the pooled time penalty by 5 min (from 7.7 to 2.7 min over private) adds about **4 pooled riders per 100**. Increasing the price gap by $1.00 (from $3.60 to $4.60) adds only about **2 per 100**. One additional passenger loses about **1 per 100**. The authors conclude pooled commute RH needs "minimal detour and pick-up/drop-off delays." — [Kang et al.](https://www.caee.utexas.edu/prof/bhat/ABSTRACTS/PooledRH.pdf)
- **(SP, Shenzhen / Chengdu / Hong Kong, 403 questionnaires, 371 valid after monotonicity screening.)** Respondents gave the minimum discount they would require at detours of **+10%, +20%, +30%, +40%, +50%** of the non-pooled distance, choosing from bins (<5%, 5–10%, 10–15%, 15–20%, 20–30%, 30–40%, >40%, or "never pool"). The authors chose 40% detour as "a moderate yet practically relevant level of service degradation." Their fitted acceptance curve at 40% detour is G(r) = −0.5017r² + 0.9900r − 0.0544 (R² = 0.981). — [Chen, Liu, Zhang, Shi & Ke, arXiv 2608.22440](https://arxiv.org/pdf/2608.22440)
  - Evaluated from that curve (my calculation; the authors fitted it over a bounded discount range and it includes "never pool" respondents): acceptance ≈ **12% at a 20% discount, ≈20% at 30%, ≈26% at 40%, ≈32% at 50%**. Treat this as indicative only.
- **(SP, Ain Shams University engineering faculty commuters, Cairo.)** When drivers were asked the maximum extra detour time they would accept, most chose **5, 10, or 15 minutes**. This is from a search-result summary; I did not read the full text. — [ROSA P / search summary, dot 64290](https://rosap.ntl.bts.gov/view/dot/64290/dot_64290_DS1.pdf)
- **(RP, Chicago.)** Requests authorized for sharing are not always matched; a TNC may drive the rider directly when the detour to pair riders would be too long. — [Scale Effects in Ridesplitting, Chicago (arXiv 2303.03574)](https://ar5iv.labs.arxiv.org/html/2303.03574)
- Lavieri & Bhat note that simulation studies suggest pooling can be done with a per-passenger time penalty of about 2.7 min (Alonso-Mora et al. 2017), as cited in the Austin paper. — [Kang et al.](https://www.caee.utexas.edu/prof/bhat/ABSTRACTS/PooledRH.pdf)

### Inferences
- A 50% distance overrun (the 1.5× cap) matches the top of the Chinese survey grid and the middle of the Austin SP range (25–75% time). It is defensible as a hard **maximum**, but the evidence says acceptance falls steeply as detour rises. The matcher should **minimize** detour, not just stay under the cap. A softer target (e.g. ≤25–30% typical, 50% only in rare cases) would be better supported.
- The +4 km cap binds once solo trips exceed 8 km. Suburban students with 20 km trips are then limited to +20%, which fits the "minutes matter most" finding.
- Riders respond to time. Distance caps should ideally be converted to a time cap (for example, extra in-car minutes), because Amman/Gulf traffic can make +4 km much more than 4 km's worth of minutes. This is an inference, not a measured result.

### Gaps
- No RP study found reports the actual realized detour distribution of Uber Pool or Lyft Shared trips alongside rider acceptance or retention.
- I could not get the full text of the Alonso-González et al. (2021, *Transportation*) WTS paper (PMC served a bot check), so its exact minute and euro trade-offs are not reported here.
- The Ain Shams detour numbers come from a search summary and were not verified in full text.

---

## Q2. What discount do riders require to choose pooled over solo?

### Takeaway
SP studies put the monetary "stranger penalty" small: about **$0.50–$1.70 per extra passenger per trip**, the same for short and long trips. Most of the required discount pays for **added time**. Market discounts historically ranged from about 20–30% (Lyft Shared; UberPool after its 2019 price rises) up to about 50% (UberPool in 2018). A 20% minimum saving matches the low end of what platforms actually offered. Combined with large detours it is likely too small to attract many riders, especially non-commute or less price-sensitive riders.

### Cited Findings
- **(SP, DFW.)** Lavieri & Bhat 2019: willingness to pay to avoid one extra passenger ≈ **$0.49 (commute)** and ≈ **$0.90 (leisure)** per trip. This is a fixed cost, independent of trip length. VTT ≈ **$26.5/h commute**, **$23.2/h leisure** (69% and 60% of the sample's average wage). One fewer passenger is worth the same as **1.10 min (commute)** or **2.33 min (leisure)** of travel time, "low when compared to actual delays caused by an additional passenger." — [Lavieri & Bhat 2019](https://www.caee.utexas.edu/prof/bhat/ABSTRACTS/WTS_paper.pdf)
- **(Joint RP/SP, Austin 2019.)** VTT: **$27.80/h commute, $19.40/h shopping, $10.70/h leisure**. WTS (pay not to pool with one extra passenger): **$0.62 commute, $1.70 shopping, $1.32 leisure**. In time terms, one extra passenger = **1.35 min (commute), 3.7 min (shopping), 2.9 min (leisure)**. — [Kang et al.](https://www.caee.utexas.edu/prof/bhat/ABSTRACTS/PooledRH.pdf)
- **(SP, Netherlands, urban.)** Alonso-González et al. (2020/21): "less than one third of respondents have strong preferences against sharing their rides." Willingness to share "depends mainly on time-cost trade-offs rather than on the disutility of pooling itself." Market segments differ in whether the sharing penalty is per ride or proportional to in-vehicle time. — [TU Delft repository: determinants of WTS](https://repository.tudelft.nl/record/uuid:26c1baaf-726e-48c1-9654-8bb802931793)
- **(SP, Netherlands, n = 1,006.)** In-vehicle VOT for pooled on-demand ≈ **€10.80/h commuting, €7.88–9.94/h leisure**, close to Dutch car VOT. — [Alonso-González et al. 2020, TR Part C 115:102621 (PDF)](https://pure.tudelft.nl/ws/portalfiles/portal/72155146/1_s2.0_S0968090X1931589X_main.pdf)
- **(SP, China/HK.)** At a 40% detour, the fitted acceptance is only about 12% at a 20% discount and about 26% at 40% (calculation from the authors' curve; see Q1). — [arXiv 2608.22440](https://arxiv.org/pdf/2608.22440)
- **(RP prices, Chicago, about 6,358 price observations on about 140 O-D pairs of 4–11 miles, 2018 vs 2019.)** Average prices: UberX $17.57 → $16.34; **UberPool $8.94 → $12.65** (+41.6%); Lyft $17.53 → $16.60; **Lyft Shared $13.92 → $11.79**. Uber Express Pool riders "typically save between $1.5 and $3 per trip" extra by walking 1–2 blocks. — [Schwieterman, "The Changing Price of Ridesharing in Chicago" (DePaul)](https://trforum.org/wp-content/uploads/2020/03/The-Changing-Price-of-Ridesharing-in-Chicago.pdf)
  - Implied discount vs solo (my calculation from those averages): UberPool **≈49% (2018) → ≈23% (2019)**; Lyft Shared **≈21% (2018) → ≈29% (2019)**.
- **(RP, Reuters analysis of >1 million Chicago rides, Jan–Sep 2019.)** Per-mile fares for shared rides rose **13%** while single-rider fares were flat. In the least affluent neighbourhoods, shared rides fell from about half to about one-third of rides between Q1 and Q3. Uber said it had "traditionally lost money" on Pool. — [Reuters via Yahoo Finance](https://uk.finance.yahoo.com/news/uber-carpool-pricing-strategy-revealed-110538792.html)
- **(RP, Chicago.)** Pooled trips fell from about **20% to 9%** of trips over the study year in a 104-million-trip dataset, coinciding with the narrowing discount. — [arXiv 2008.06050](https://arxiv.org/pdf/2008.06050.pdf). In 2019, authorized-shared requests had an average **match rate of ≈71.8%**, and pooled trips were about **18%** of TNC trips. — [NREL report 75682](https://nrel.gov/docs/fy20osti/75682.pdf)
- **(Marketing claims, 2017–2018.)** Uber Express Pool launched at "up to 50% cheaper than UberPool and up to 75% cheaper than UberX". A later report said up to 30% vs UberPool. — [TechCrunch](https://techcrunch.com/2017/11/10/uber-express-pool/amp/); [Fortune](https://fortune.com/2018/02/21/uber-express-pool-ride/)
- **(SP, North Dakota State University students.)** With a **10–20% discount** on a carpool permit vs a normal parking permit, more than 65% of students said they would carpool. About 70% would consider carpooling with guaranteed parking. This is from a search summary. — [ROSA P dot 64290](https://rosap.ntl.bts.gov/view/dot/64290/dot_64290_DS1.pdf)

### Inferences
- Chicago RP data is consistent with SP: when UberPool's discount fell from about 49% to about 23%, pooled share roughly halved. That suggests **~20–25% is near the floor** at which pooling stays attractive in a commercial market. A 20% minimum is therefore a defensible floor but not a comfortable target. In practice, 30–40% savings are likely needed when detours approach the 1.5× cap.
- Because the stranger penalty is a small fixed amount (about $0.5–1.7 per trip) while the time penalty scales with minutes, the saving guarantee would be better tied to detour size (e.g. a larger saving for more detour) than flat. This is an inference.
- For a student fare split among 2–4 riders, savings well above 20% are natural (e.g. a 3-way split with a 30% longer route still saves ~55%). In practice the 20% floor will rarely bind except for 2-rider cars with long detours. This is my arithmetic, not a cited finding.

### Gaps
- No published Uber or Lyft official figure states their average pooled discount. The ~20–40% range rests on third-party price sampling and press reports.
- No MENA-specific SP estimate of the discount needed to pool was found.

---

## Q3. Wait time and walking-to-pickup tolerance

### Takeaway
Commercial pooled products tolerated only **~1–2 min of extra wait** and up to about a **5-min walk**. In the Dutch SP study, waiting is valued at **1–1.5× in-vehicle time**, and per-minute disutility **rises with longer waits**. A wait of up to 20 min at the gate is far beyond anything commercial pooled products imposed. It is defensible only because campus waiting is a different context (riders are not standing at the curb with no alternative and can use the time). It should be treated as a key risk to test.

### Cited Findings
- **(SP, Netherlands, n = 1,006.)** Waiting-stage VOT **€9.27–16.50/h**, increasing with total waiting time (a squared waiting term improved fit: "individuals associate a higher per-minute waiting disutility to longer waiting times"). The waiting-to-in-vehicle ratio is **1–1.5**, below the traditional ≥2 attributed to real-time information. The service tested assumed about **1 min walk** to the pickup point. — [Alonso-González et al. 2020 (PDF)](https://pure.tudelft.nl/ws/portalfiles/portal/72155146/1_s2.0_S0968090X1931589X_main.pdf)
- **(Product design.)** Uber Express Pool asked riders to walk to a nearby pickup point and accept a wait "up to two minutes" longer. — [TechCrunch](https://techcrunch.com/2017/11/10/uber-express-pool/amp/). Lyft Shared Saver: pickup locations "never more than a five-minute walk", and drivers wait only **one minute**. — [Autoblog](https://www.autoblog.com/2019/03/02/lyft-shared-saver-uber-express-pool-ridesharing/)
- **(SP, Austin.)** Pooled travel times shown to respondents explicitly included waiting plus detour. The total pooled penalty averaged 7.7 min, and cutting 5 min of it had about twice the uptake effect of a $1 discount (commute). — [Kang et al.](https://www.caee.utexas.edu/prof/bhat/ABSTRACTS/PooledRH.pdf)
- **(News, Malaysia, Nov 2026, anecdotal.)** Some women passengers say they are willing to wait an extra **20–30 minutes** for a female driver for safety. — [The Star](https://www.thestar.com.my/news/nation/2026/11/09/women-only-rides-grant-a-priceless-sense-of-security)

### Inferences
- Valuing a 20-min wait at Dutch waiting VOT gives roughly **€3.1–5.5** of time cost (my arithmetic). Student VOTs are likely lower, but for short campus trips this could exceed the money saved. The **worst case** (first rider waits a full 20 min) is the binding risk. If class end times are spread uniformly within the window, the average wait for the earliest rider is closer to 10 min (inference).
- Mitigations consistent with the evidence: show the exact expected wait up front (the Dutch study credits real-time information with lowering waiting disutility); give longer-waiting riders a larger share of the savings; consider a tighter default (e.g. 10–15 min), with 20 min only as an opt-in.
- Safety-motivated riders (women-only) appear willing to tolerate much longer waits (Malaysia anecdote), so a longer window may be acceptable in the women-only pool specifically.

### Gaps
- No peer-reviewed study found on wait tolerance for **scheduled** pooled rides with a known departure time (like a campus gate pickup), as opposed to on-demand. This is the closest analogue to Campus Connect and is a real evidence gap.
- No minutes-based walking tolerance from a SP study was found; the 1–5 min figures are product parameters, not measured tolerance.

---

## Q4. Evidence specific to students / university carpooling, and to MENA / women's safety

### Takeaway
Student evidence is thin but suggests modest incentives (10–20% savings, parking perks) motivate carpooling, and safety and trust are main concerns. In Jordan and Saudi Arabia, **women are less willing to carpool with strangers**, citing privacy, trust, and safety. Demand for women-only options is documented in global and Saudi data. This supports offering a women-only option.

### Cited Findings
- **(SP/survey, Jordan, n = 630 valid.)** A 2022 study of carpooling intentions found **females were less interested in adopting carpooling** because they attach more importance to convenience, privacy, and trust. Postgraduate students were less likely to adopt. This is from a search summary of the abstract. — [Modeling Determinants of Carpooling Intentions in Jordan (catalog record)](https://katalog.lib.cas.cz/KNAV/EdsRecord/edsair,edsair.doi...........2cee26c08bfa9c1a59443f8f79b36efe)
- **(Survey, Amman residents, 2024.)** Initial willingness-to-adopt shared mobility ≈ **25.4%**. — [MDPI Sustainability 16(2):732 via IDEAS](https://ideas.repec.org/a/gam/jsusta/v16y2024i2p732-d1319144.html)
- **(Survey, Jeddah women.)** Women's carpooling participation is constrained by safety, trust, and social norms; **22.2%** expressed negative sentiment. The authors recommend women-only carpool initiatives. — [UWS research portal: attitudes of women towards carpooling in Jeddah](https://research-portal.uws.ac.uk/en/publications/investigating-attitudes-of-women-towards-carpooling-in-jeddah/)
- **(IFC six-country ride-hailing study.)** **20%** of women riders said the lack of women drivers limits their trips. **44%** would be more likely to use ride-hailing with an option to select a woman driver. Demand for gender-segregated transport "peak[s] at night or when passengers are traveling alone." GST models face a supply problem and potentially longer wait times. — [IFC, Gender-Segregated Transportation in Ride-Hailing, Executive Summary (2020)](https://www.ifc.org/content/dam/ifc/doc/mgrt/executive-summary-ifc-gender-segregated-transportation-in-ride-hailing.pdf)
- **(Saudi Arabia, Uber pre-launch survey.)** **74%** of prospective women drivers were interested only in driving women. Over time, women in the "Women Rider Preference" program used it less and served all riders. — [IFC Executive Summary](https://www.ifc.org/content/dam/ifc/doc/mgrt/executive-summary-ifc-gender-segregated-transportation-in-ride-hailing.pdf)
- **(Model taxonomy.)** IFC identifies "algorithmic prioritization" (DiDi, 99): women drivers and riders are matched automatically when doing so does not increase pickup waits. This is an alternative to hard women-only pools. — [IFC Executive Summary](https://www.ifc.org/content/dam/ifc/doc/mgrt/executive-summary-ifc-gender-segregated-transportation-in-ride-hailing.pdf)
- **(Austin RP/SP.)** Women have a lower propensity to choose pooled ride-hailing. — [Kang et al.](https://www.caee.utexas.edu/prof/bhat/ABSTRACTS/PooledRH.pdf)
- **(Students, other countries; search summaries.)** Sohar University, Oman (n = 250): over 60% willing to carpool under the incentives studied. Shenzhen University (n = 514): safety concerns and cost made students "neutral" toward carpooling. Istanbul Technical University: **women and frequent campus travellers more likely to prefer being carpool passengers**. — [search summary sources incl. ITU record](https://research.itu.edu.tr/en/publications/potential-of-carpooling-among-unfamiliar-users-case-of-undergradu/); [Shenzhen/Oman via tots.upol.cz](https://www.tots.upol.cz/pdfs/tot/2025/02/03.pdf)
- **(Jordan context.)** Women are 51.8% of Jordanian university students (FES). About 8,000 Hashemite University students commute from Amman (Al-Fanar, 2015). — [FES Gender in Public Transportation (Amman)](https://library.fes.de/pdf-files/bueros/amman/15221.pdf); [Al-Fanar Media](https://al-fanarmedia.org/2015/09/in-jordan-poor-transportation-is-a-drag-on-education/)

### Inferences
- With women the majority of Jordanian students and less willing to pool with strangers, a women-only option is strongly justified and may be **necessary for adoption**, not just a feature.
- A women-only pool shrinks the matching pool, so it will produce longer waits and larger detours (IFC notes the wait-time trade-off). Consider relaxing the time window for women-only matches only when the rider opts in, or using DiDi-style soft prioritization.
- University-verified identity (same-campus students) likely reduces the "stranger" disutility, which is already small in US SP data. This is an inference; no study measured it directly.

### Gaps
- No Jordan/Gulf SP study found with numeric detour, wait, or discount trade-offs for women or students.
- Several student-study numbers come from search summaries, not verified full text (Jordan 630-response study, Sohar, Shenzhen, Ain Shams, NDSU).

---

## Q5. Discomfort with strangers / number of co-riders

### Takeaway
Each additional co-rider has a small, fixed disutility, roughly equivalent to **1–4 minutes** of travel time. It is smallest for commutes and larger for leisure and shopping. Comfort with strangers is far lower than with known people. Capping at 4 riders (3 co-riders) matches the vehicle capacity used in all SP designs. The bigger cost of more riders is the extra stops and time they create.

### Cited Findings
- **(SP, DFW.)** Extra passenger ≈ $0.49 (commute) / $0.90 (leisure), which equals 1.10 / 2.33 min. People pay 84% more to avoid an extra passenger on leisure vs commute trips. — [Lavieri & Bhat 2019](https://www.caee.utexas.edu/prof/bhat/ABSTRACTS/WTS_paper.pdf)
- **(RP/SP, Austin.)** Extra passenger ≈ $0.62 / $1.70 / $1.32 (commute/shopping/leisure), which equals 1.35 / 3.7 / 2.9 min. Commute: +1 passenger reduces uptake by about 1 per 100. For shopping and leisure, the passenger effect exceeds the time and cost effects. — [Kang et al.](https://www.caee.utexas.edu/prof/bhat/ABSTRACTS/PooledRH.pdf)
- **(Survey, Austin, n = 347; Bansal et al. 2016, as cited in Lavieri & Bhat.)** Only about **half** would feel comfortable sharing a ride with a stranger during the day, vs **90%** with friends or family. — [Lavieri & Bhat 2019 lit. review](https://www.caee.utexas.edu/prof/bhat/ABSTRACTS/WTS_paper.pdf)
- Both Bhat-group SP designs capped extra passengers at **3** ("standard autonomous cars would accommodate comfortably up to four passengers"; "limited to three or fewer additional passengers" for a sedan). — [Lavieri & Bhat](https://www.caee.utexas.edu/prof/bhat/ABSTRACTS/WTS_paper.pdf); [Kang et al.](https://www.caee.utexas.edu/prof/bhat/ABSTRACTS/PooledRH.pdf)
- **(SP, Netherlands.)** Fewer than one third strongly object to sharing at all. — [TU Delft](https://repository.tudelft.nl/record/uuid:26c1baaf-726e-48c1-9654-8bb802931793)

### Inferences
- Class-to-home trips are commute-like, the purpose where sensitivity to co-riders is lowest, so a 4-rider cap is well supported. Each extra rider's added stop (detour) matters more than their presence.
- The "half comfortable with a stranger" figure, together with Jordan/Jeddah evidence on women, means safety cues (verified student IDs, the women-only option, trip sharing) are likely to matter more than the co-rider count.

### Gaps
- No study found that separately measures discomfort for 2 vs 3 co-riders in a cramped back seat (comfort or physical crowding), as distinct from the time each one adds.
- No MENA-specific estimate of the per-co-rider penalty was found.
