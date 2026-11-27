# Ride-Pooling Evaluation Metrics and Failure Modes (for the Campus Connect simulation demo)

Context: Campus Connect simulates students leaving one campus in shared cars of up to 4 people. Most published benchmarks come from dense urban ride-hailing (NYC, Chicago, Toronto, Lisbon). They are useful as reference ranges, but a one-origin campus outbound trip pattern differs from them (see Inferences).

## Standard metrics: definitions and typical reported values

### Takeaway
A credible set covers six things: VKT saved against a solo baseline, average occupancy, share of requests that get pooled (match rate), added detour or delay per rider, cars used, and CO2 saved, with cost per rider derived from VKT. Published simulations give upper-bound results (98% of demand served, 37% fewer peak vehicle-km). Real-world pooled services report far less: roughly 50-72% of pooling-authorized trips get matched, and about 3.6 extra minutes for a matched trip.

### Cited Findings
**Vehicle-km traveled (VKT) saved / fleet size (simulation benchmarks)**
- ITF/OECD Lisbon agent-based model, which replaced car, bus and taxi trips with shared taxis and taxi-buses plus metro: peak vehicle-km came out 37% below current levels and emissions 34% below in the short term, with no congestion even at peak. Shared taxis had a combined detour-plus-wait limit of 7 min for trips of 3 km or less, rising to 15 min for trips of 12 km or more. Modal split was 67% shared taxi and 33% taxi-bus. — [ITF/TRB 2016, Martinez & Viegas](https://www.itf-oecd.org/sites/default/files/docs/martinezviegas_trb2016.pdf); [ITF Shared Mobility report](https://www.oecd.org/en/publications/shared-mobility_5jlwvz8bd4mx-en.html)
- ITF summary: the "ridesharing plus taxi-bus" scenario cut CO2 to 71.9% of Lisbon's current daily transport emissions, and high occupancy drives both the vehicle-km and the CO2 reductions. — [ITF Transition to Shared Mobility (2017)](https://www.itf-oecd.org/sites/default/files/docs/transition-shared-mobility.pdf)
- Alonso-Mora et al. (PNAS 2017), using about 3 million NYC taxi rides: 3,000 four-passenger vehicles, or 2,000 ten-passenger vehicles (about 15% of the taxi fleet), served 98% of demand. Mean wait was 2.8 min and mean added trip delay 3.5 min. With 3,000 vehicles, capacity 2 served 94% of demand and capacity 4 served 98%. — [PNAS via PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC5255617). MIT's 2016 press release gives 95% for the 2,000 ten-seat case, so the two sources disagree. — [MIT News](https://news.mit.edu/2016/how-ride-sharing-can-improve-traffic-save-money-and-help-environment-0104)

**Shareability / match rate**
- Tachet et al. (Sci. Reports 2017) define "shareability" S as the fraction of trips that can be paired with at most Δ minutes of added delay. NYC taxi shareability exceeded 95% at Δ = 5 min. Curves for NYC, SF, Singapore and Vienna collapse onto one curve under a single dimensionless parameter L = λv²Δ³/|Ω| (λ = trip density, v = speed, Ω = area), and S rises fast and then saturates. This measures the theoretical possibility of sharing, not realized matches. — [Tachet et al. 2017 (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC5337932)
- Toronto, 12 million ride-hailing records from Sept 2016 to Mar 2017: 15% of trips were requested as pooled, but only 52% of those were actually matched. Matched shared trips took about 3.6 min longer than comparable solo trips. — [TRID: True Cost of Sharing (Toronto)](https://trid.trb.org/View/1759884)
- Chicago 2019: an average match rate of 71.8% among trips authorized for sharing, with 18.5% of all trips pooled. This comes from an older slide deck. — via search summary of [NSF PAR paper](https://par.nsf.gov/servlets/purl/10499934). A separate machine-learning study of 96 million Chicago 2019 trips found 19.61% requested to share and 13.85% actually shared, which works out to about 71% of requests matched. — [arXiv 2201.12696](https://www.arxiv.org/pdf/2201.12696)
- Chicago Jan-Sep 2019, scale effects: pooling authorization was 17.3% on weekdays on the North side and 39.8% on the South side. Matched share and detour both improve with volume. At one matched trip per hour, a 1% rise in matched trips goes with a 0.50-0.75% cut in detour distance. Detour can halve or better as volume grows. — [Scale Effects in Ridesplitting, Chicago (arXiv 2303.03574)](https://ar5iv.labs.arxiv.org/html/2303.03574)
- Lyft-reported share of rides booked as Lyft Line: more than 50% in SF and more than 30% in NYC (2015), about 40% in its markets (2016), and about 35% across 19 metros (2017). Streetsblog noted Lyft could not say how many of these were actually shared, so this is opt-in share, not match rate. — [GeekWire 2015](https://www.geekwire.com/2015/lyfts-carpooling-service-now-makes-up-50-of-rides-in-san-francisco-30-in-nyc/); [Fortune 2016](https://fortune.com/2016/04/05/lyft-line-expansion/); [Streetsblog SF 2015](https://sf.streetsblog.org/2015/03/17/most-lyft-customers-in-sf-sign-up-to-share-their-trips)
- Uber's publicized match rate at the UberPool launch was 20-30%. This is a company figure. — via [DePaul Chaddick report (rosap)](https://rosap.ntl.bts.gov/view/dot/64556/dot_64556_DS1.pdf)

**Average occupancy (baseline)**
- 2017 NHTS: average light-vehicle occupancy was 1.67 across all trips, unchanged since 2009. — [DOE Fact of the Week #1040](https://www.energy.gov/eere/vehicles/articles/fotw-1040-july-30-2018-average-vehicle-occupancy-remains-unchanged-2009-2017)
- FHWA mileage-weighted occupancy factor: car 1.40, all vehicles 1.52. — [FHWA AVO factors](https://www.fhwa.dot.gov/tpm/guidance/avo_factors.pdf)
- Fehr & Peers 2019 (Sept 2018 data, six metros): TNCs were about 2.9% of regional VMT. About 54-62% of TNC miles carried a passenger, so roughly 40% were deadhead. A peer-reviewed review cites deadhead shares of 36-45%. — [Urbanism Next summary](https://urbanismnext.org/resources/how-much-traffic-do-uber-and-lyft-cause); [eScholarship review](https://escholarship.org/content/qt5hm5h0g9/qt5hm5h0g9.pdf). These figures come from secondary coverage, and the original memo was not verified.

**Detour / delay**
- Matched pooled trips in Toronto: +3.6 min on average. — [TRID](https://trid.trb.org/View/1759884)
- Waze Carpool drivers went 3-4 min out of their way on average to pick up a rider. — [Axios 2019](https://www.axios.com/2019/10/11/catching-up-with-wazes-carpool-app)
- Simulation: mean delay 3.5 min and mean wait 2.8 min. — [Alonso-Mora 2017](https://pmc.ncbi.nlm.nih.gov/articles/PMC5255617)

**Emissions**
- EPA: a typical passenger vehicle emits about 400 g CO2 per mile (about 250 g/km). This is derived from 8,887 g CO2 per gallon divided by fleet fuel economy. Older EPA pages give 404 g and 423 g. — [EPA Green Vehicle Guide](https://www.epa.gov/greenvehicles/greenhouse-gas-emissions-typical-passenger-vehicle)
- UCS 2020: a non-pooled ride-hailing trip is 47% more polluting than a private car trip. A pooled trip is roughly equal to a private car trip. An electric pooled trip is about 68% cleaner. On average, ride-hailing trips produce about 69% more emissions than the trips they displace, mainly because of deadheading. — [UCS Ride-Hailing's Climate Risks](https://www.ucsusa.org/sites/default/files/2020-02/Ride-Hailing's-Climate-Risks.pdf)

**Cost**
- ITF Lisbon: shared-taxi fares for cost recovery came to 31% of current taxi fares. — [ITF/TRB 2016](https://www.itf-oecd.org/sites/default/files/docs/martinezviegas_trb2016.pdf)
- Uber said drivers earn a minimum of $4.75 per POOL trip (2016). — via [Vice](https://www.vice.com/en/article/why-drivers-and-riders-hate-uberpool-and-lyft-line)

### Inferences
- Suggested formulas for the demo, all computed against an "everyone drives or rides solo" baseline:
  - VKT saved % = 1 − (Σ km of pooled routes, detours included) / (Σ km of the same requests made solo).
  - Avg occupancy = passenger-km / vehicle-km. Report this alongside the simple riders-per-car figure.
  - Match rate = riders placed in a car of 2 or more / all requests. Also report the share left solo or unmatched.
  - Detour = per-rider (pooled travel time − direct travel time), reported as the mean and the 90th or 95th percentile.
  - Cars used = number of vehicles dispatched compared with the number of requests.
  - CO2 saved = VKT saved × about 0.25 kg/km. State the factor on screen.
  - Cost per rider = (vehicle-km × cost per km) / riders.
- With 4 seats and a single origin, Campus Connect's ceiling is occupancy 4.0 and about 75% VKT saved, and only if everyone shares the same destination. Any result above roughly 50-60% VKT saved needs a stated explanation, such as clustered destinations.
- A one-origin campus trip should pool more easily than city-wide trips with scattered origins, because pickup detours disappear. It is fair to say "better than the urban 52-72% match rates" only if the destination clustering is shown.
- The demo should show detour caps the way ITF does, for example 7-15 min depending on trip length, so that judges see the trade-off between match rate and detour.

### Gaps
- I found no verified commute-specific occupancy figure. The often-quoted 1.1-1.2 for commutes was not confirmed (see NHTS Table 16).
- I found no published match rates or VKT savings for any campus carpool program. Campus reports (Zimride at Cornell and UCSD, the UCF thesis) give only registration counts. — [AASHE Cornell](https://reports.aashe.org/institutions/cornell-university-ny/report/2014-03-07/OP/transportation/OP-T2-32); [UCF thesis](https://core.ac.uk/download/236293598.pdf)
- The four-city percentages in the ITF 2017 table (-54%, -31%, -34%, -62%) were not confirmed as VKT reductions.

## Failure modes and typical numbers

### Takeaway
The main failure modes are: low demand density, so too few overlapping trips (cold start); requests that opt in but never get matched (about 30-50% in practice); cancellations and no-shows (about 3% combined in paratransit data, higher for on-demand); driver reluctance to take pooled trips; and safety-driven opt-outs, especially among women. Pooling can also raise total VMT when it pulls riders away from transit or walking.

### Cited Findings
**Low density / cold start**
- Shareability and detour both depend strongly on trip density: S rises with λ and then saturates. — [Tachet 2017](https://pmc.ncbi.nlm.nih.gov/articles/PMC5337932); [Chicago scale effects](https://ar5iv.labs.arxiv.org/html/2303.03574)
- Waze Carpool's "biggest challenge" was described as density. Susan Shaheen (UC Berkeley) called critical mass "a big reason carpooling hasn't been able to be as successful as it could be." Waze's internal retention "magic number" was 4 rides per user. In Sept 2019 it reported more than 550k rides per month globally. — [Axios 2019](https://www.axios.com/2019/10/11/catching-up-with-wazes-carpool-app); [Marketplace 2019](https://www.marketplace.org/episode/2019/10/21/waze-wants-to-make-carpooling-a-thing)
- Scoop, Carma and Waze Carpool were not "a game-changer" for commuters combining their drives. — via [Digital Trends](https://digitaltrends.com/mobile/waze-carpool-expansion). Lyft paused its carpool experiment for lack of driver interest. — [GovTech](https://govtech.com/fs/facing-lack-of-driver-interest-lyft-hits-pause-on-carpooling-experiment.html)
- Pooled demand in Chicago collapsed with COVID. Authorized shared trips recovered from 21,484 per month (June 2022) to 214,689 per month (April 2023), still well below pre-pandemic levels. — via [NSF PAR](https://par.nsf.gov//servlets/purl/10584875)

**Opt-in but not matched (churn)**
- In Toronto, 48% of pooled requests went unmatched. The authors warn that tightening detours to attract riders can raise the unmatched rate. — [TRID](https://trid.trb.org/View/1759884)
- In Chicago, unmatched authorized trips are simply driven direct, as if solo. About 28% were unmatched in 2019. — [Chicago scale effects](https://ar5iv.labs.arxiv.org/html/2303.03574)
- One Philadelphia driver estimated that only about a third of his POOL rides were actually matched. This is a single anecdote. — [Billy Penn 2016](https://billypenn.com/2016/06/07/uber-pool-in-philly-the-more-devoted-the-driver-the-less-they-like-the-service/)

**No-shows and late cancellations**
- TCRP paratransit synthesis: no-show rate about 1.3%, combined no-show plus late-cancellation about 3.0% in one agency's data, with no consensus on what counts as "excessive." — [TCRP via National Academies](https://nap.nationalacademies.org/read/13856/chapter/6)
- A vendor blog cites a Pioneer Valley paratransit analysis that flagged cancellation rates above about 15% as needing attention. This is secondhand. — [TransLoc blog](https://transloc.com/blog/the-ride-capacity-you-never-actually-had/)
- MARTA Reach on-demand pilot (Atlanta): 78.93% of cancellations happened while the rider was waiting for the vehicle, and about 30% of cancellers took a ride within an hour. — [arXiv 2308.02681](https://arxiv.org/pdf/2308.02681)
- Medical ride programs: a clinic's no-show rate fell from 31% to 22.5% with Lyft/Hitch (company-reported). UMN found an effect of about 10 percentage points that faded over time. — [MobiHealthNews](https://www.mobihealthnews.com/news/lyft-hitch-health-roundtrip-deals-bearing-fruit-systems-seeking-non-emergency-medical); [UMN](https://cse.umn.edu/node/107966)

**Driver acceptance of pooled trips**
- In a survey of 309 TNC drivers, more of them saw pooled-trip pay as unfair and found shared trips stressful. Drivers were considerably less satisfied with shared trips than with solo ones. — [Clemson C2M2 UberPool report](https://cecas.clemson.edu/C2M2/wp-content/uploads/2019/06/Revised_FinalCopy_UberPool-report-1.pdf); [Transport Policy 94 (2020)](https://econpapers.repec.org/RePEc:eee:trapol:v:94:y:2020:i:c:p:123-138)
- A UW dissertation found drivers typically needed a subsidy of at least $10 to accept shared rides. — [UW ResearchWorks](https://digital.lib.washington.edu/researchworks/bitstreams/ce52d31b-ee23-43a6-b75e-a08e0c852085/download)

**Gender / safety opt-outs**
- A 2026 US poll of 1,000 women found 59.3% had felt unsafe in a rideshare at least once. It covers rideshare generally, not pooling. — [Stacker](https://stacker.com/stories/social-issues/survey-finds-3-5-women-have-felt-unsafe-rideshare-most-using-fake-phone-calls)
- Thomson Reuters Foundation: safety was women's top transport concern, and 56% said ride-hailing apps improved their mobility. — [WEF](https://weforum.org/stories/2018/11/ten-findings-about-the-biggest-transport-challenges-facing-women)
- Togopool, an Indian company survey of more than 250 respondents: 88% of women would switch to carpooling if safety features improved. This is a promotional source with a weak method. — [Autocar Pro](https://www.autocarpro.in/news/82-of-women-prefer-carpooling-over-other-commuting-modes-reveals-togopools-survey-report-120881)
- A study of 293 women in India modeled safety and comfort perceptions in ridesharing; I did not retrieve a headline percentage. — [Springer HSSC 2024](https://link.springer.com/10.1057/s41599-024-02740-z)

**Mode shift / induced VMT (system-level failure)**
- Schaller 2018: pooled services (UberPOOL, Lyft Shared) still add 2.6 new vehicle miles for each mile of personal driving removed, because most users came from transit, walking or biking, and because of deadheading. TNCs added 5.7 billion miles across nine large metros. — [Schaller Consulting](https://schallerconsult.com/rideservices/automobility.htm)

### Inferences
- Suggested stochastic failure parameters for the simulation, each stated as an assumption: no-show or late cancellation at 3% (paratransit-like, scheduled rides) up to about 10-15% (on-demand stress test); a pooled-offer decline rate of 10-30%; and a "same-gender only" or "no pooling" preference flag for a configurable share of riders, with the cost in match rate shown.
- Each failure mode maps directly to a metric: no-shows cause a stranded or empty seat, which lowers occupancy, and a re-match can add detour. Showing a "robustness" panel (metric with and without failures) is more credible than reporting only the ideal case.
- Cold start can be shown by sweeping the number of riders per departure window, for example 5, 10, 20 and 50 students per 15 minutes, and plotting match rate. The literature predicts a rise followed by saturation.

### Gaps
- I found no reliable overall rider-cancellation rate for Uber or Lyft. Published cancellation studies measure racial disparities, for example a Black rider being about 4% more likely to be cancelled in an LA audit of about 1,700 rides, not baseline rates. — [METRO Magazine](https://www.metro-magazine.com/10032537/research-examines-discrimination-travel-patterns-for-lyft-uber-taxis)
- I found no independent survey giving the share of women who opt out of pooled rides specifically.
- I found no published Scoop no-show or match statistics.

## How simulation studies model demand, and runs/seeds

### Takeaway
Ride-pooling simulations either replay historical trip records (NYC taxi data, Chicago TNC data) or generate requests as Poisson arrivals, often with zone-specific rates calibrated from history, and they usually discard a warm-up period. I found little explicit reporting of multiple seeds or confidence intervals, so a demo that does report them stands out.

### Cited Findings
- Alonso-Mora 2017 replayed about 3 million real NYC taxi requests, a historical-replay demand model. — [PNAS/PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC5255617)
- ITF Lisbon used an agent-based model with a synthetic population built from travel-survey data. — [ITF/TRB 2016](https://www.itf-oecd.org/sites/default/files/docs/martinezviegas_trb2016.pdf)
- A general ridesharing model used steady-state Poisson demand in an agent-based simulation. It discarded a warm-up batch and then measured 10,000 passengers, and noted that stochastic fluctuations matter more when few vehicles are idle. — [arXiv 1807.01140](https://arxiv.org/pdf/1807.01140)
- A deep-RL ride-pooling study used a Poisson rate per zone and time period, calibrated as the historical mean number of requests. — [arXiv 2503.13200](https://arxiv.org/pdf/2503.13200)
- Open-source platforms: MaaSSim (Python, within-day and day-to-day dynamics of travellers, drivers and platform) and HRSim (high-capacity pooling on real road networks). — [arXiv 2505.17758 (HRSim)](https://arxiv.org/pdf/2505.17758); MaaSSim referenced in the same results
- Agent-based testing of demand-responsive shared transport. — [arXiv 1803.08867](https://arxiv.org/pdf/1803.08867)

### Inferences
- For a campus, a non-homogeneous Poisson process tied to the class timetable is the most defensible choice: departure-request spikes in the 10-20 minutes after class blocks end, with a low background rate. Destinations should be sampled from a realistic distribution (dorm clusters, transit hubs, neighborhoods) rather than uniformly, since destination clustering drives match rate.
- Recommended practice, from standard simulation output analysis rather than from a specific source found here: run 20-30 or more seeds per scenario, report mean ± 95% CI (or median and IQR), and fix the seed list so all algorithms see identical demand (common random numbers).

### Gaps
- I found no source documenting typical seed counts or CI reporting in ride-pooling papers. The 20-30 seed recommendation is general simulation practice, not a sourced benchmark.
- I found no published campus-specific demand model for ride pooling.

## Evaluation pitfalls: baselines, ties and over-claiming

### Takeaway
The biggest credibility risks are: comparing only against "everyone drives solo" while ignoring transit or walking and naive grouping; reporting theoretical shareability as if it were achieved matching; omitting deadhead or empty driver legs; and claiming emissions savings that real-world data show can vanish or reverse.

### Cited Findings
- Real-world pooled service can raise total VMT (2.6 new miles per personal mile removed) because the right baseline includes riders who would otherwise take transit or walk. — [Schaller](https://schallerconsult.com/rideservices/automobility.htm)
- Pooled ride-hailing was roughly equal to private-car emissions, not below them, once deadheading is counted. — [UCS 2020](https://www.ucsusa.org/sites/default/files/2020-02/Ride-Hailing's-Climate-Risks.pdf)
- Deadhead makes up about 36-45% of ridesourcing VMT, and no study captures all empty miles. — [eScholarship review](https://escholarship.org/content/qt5hm5h0g9/qt5hm5h0g9.pdf)
- Opt-in share is not match rate: Lyft "Line share of rides" was reported without the share actually shared. — [Streetsblog SF](https://sf.streetsblog.org/2015/03/17/most-lyft-customers-in-sf-sign-up-to-share-their-trips)
- Shareability is a potential measure: more than 95% of NYC trips were shareable, yet real matched rates are 52-72%. — [Tachet](https://pmc.ncbi.nlm.nih.gov/articles/PMC5337932); [Toronto](https://trid.trb.org/View/1759884)
- The same fleet result is reported differently across sources (95% vs 98% of demand), which shows the value of quoting the exact configuration. — [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC5255617) vs [MIT News](https://news.mit.edu/2016/how-ride-sharing-can-improve-traffic-save-money-and-help-environment-0104)
- Simulated ITF reductions assumed a full system redesign (shared taxis, taxi-buses and metro) and replacement of all car and bus trips, so the result depends on its scenario. — [ITF 2016](https://www.itf-oecd.org/sites/default/files/docs/martinezviegas_trb2016.pdf)

### Inferences
- Show at least three baselines side by side: (a) everyone solo; (b) naive grouping, such as first-come-first-served or grouping by departure time only, with no route optimization; (c) a bus or shuttle reference. The optimizer's value is the gap between (b) and the optimized result, not the gap between solo and optimized.
- Ties: when the optimizer and naive grouping give the same number of cars, say so and break the tie on a secondary metric (total detour, 95th-percentile detour). Report results as distributions across seeds; a 1-car difference within the CI is not a win.
- Language to avoid: "eliminates X tons of CO2" (use "estimated, assuming each pooled rider would otherwise drive solo, at 250 g/km"); "98% match rate" without the detour cap and demand level; and any real-world claim derived only from simulation.
- Include the return trip or empty legs if drivers are students who drive back, or state explicitly that the drivers are travelling anyway (true carpool, no deadhead). This distinction drives whether the UCS and Schaller critiques apply.

### Gaps
- I found no source that formally benchmarks "naive grouping" against optimized pooling in a campus setting. The three-baseline recommendation is an inference.
