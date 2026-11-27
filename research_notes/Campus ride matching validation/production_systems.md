# How production shared-ride and carpool systems match riders, and what they optimize

Context: Campus Connect matches students leaving one campus gate, up to 4 per car. It matches in batches using CP-SAT set partitioning and minimizes car-km first, then the number of cars. These notes describe what real systems do so the project can say where it fits.

Source quality key: [P] = primary (company engineering post, company page, or peer-reviewed paper); [S] = secondary (press, blog summary). All dates fall between 2014 and 2026 unless noted.

## Uber Pool / UberX Share and Lyft Line / Shared: batching windows, matching heuristics, objectives, pricing

### Takeaway
Both companies moved from greedy matching of each new request to batched matching over a time window. Lyft grew its window from about 60 s to "a few minutes"; Uber Pool told riders it could take 90 s and later up to 5 min. Within a window they score each candidate pairing on detour and pickup time and choose the set of pairings that is best for the whole batch. This is the same batch-then-optimize structure Campus Connect uses, but they run it continuously over moving vehicles. Riders were rewarded with an upfront discount: Uber's 2022 UberX Share gives up to 20% off when a co-rider is matched, and allows at most 2 parties per car.

### Cited Findings
**Lyft Line (engineering series "Matchmaking in Lyft Line", Parts 1-3, eng.lyft.com, c. 2016; primary post blocked to fetch, details via summary)**
- Part 1 describes Lyft Line as a product that "automatically pairs riders together with overlapping routes", where more overlap allows a bigger discount [P] — [Lyft Engineering archive](https://eng.lyft.com/archive)
- The first system was greedy and used haversine (straight-line) distance. Riders sat in a matching pool for about 10 minutes [S] — [rrojin summary of Lyft Part 3](https://rrojin.tistory.com/21) (original: [Lyft Part 3](https://eng.lyft.com/matchmaking-in-lyft-line-part-3-d8f9497c0e51))
- Two main constraints: detour time (matched travel time minus solo travel time) and pickup time. Riders preferred short pickup times over short detours. The constraint set later grew past 30 [S] — [rrojin summary](https://rrojin.tistory.com/21)
- Travel-time estimates: A* routing scaled poorly, so Lyft stored average speeds between geohash cells in a hash table and multiplied them by haversine distance. One-way streets and rush-hour traffic remained open problems [S] — [rrojin summary](https://rrojin.tistory.com/21)
- Scaling to 3 or 4 riders blows up the number of stop orderings: 4 permutations for 2 passengers vs 1,776 for 4. Some efficient orderings gave the first rider a poor trip [S] — [rrojin summary](https://rrojin.tistory.com/21)
- Lyft moved from greedy to "less greedy" global matching, framed as a weighted maximum matching problem that also accounts for predicted future demand. Route swapping widened the matching window "from 60 seconds to a few minutes". The system waits to collect enough rides, then optimizes total detour, pickup time and cost [S] — [rrojin summary](https://rrojin.tistory.com/21)
- Triple Matching (July 2015) let a driver carry 3 or more riders on similar routes. It launched in San Francisco, and Lyft said it accounted for 20% of Lyft Line rides [S] — [TechCrunch 2015](https://techcrunch.com/2015/07/29/lyft-line-gets-into-perpetual-ride-territory-with-new-triple-match-service)
- Lyft rolled out a reinforcement-learning revision of its core (non-pool) matching globally in 2021 [P] — [Interfaces / INFORMS paper](https://pubsonline.informs.org/doi/fpi/10.1287/inte.2023.0083); [arXiv 2310.13810](https://arxiv.org/abs/2310.13810v2)

**Uber**
- Uber's general matching waits "a few seconds" after a request so a batch can form, then picks pairings that lower average wait for the whole batch rather than for the single closest pair. It replaced nearest-driver matching because that approach sometimes gave other riders long waits [P] — [Uber Marketplace: Matching](https://www.uber.com/us/en/marketplace/matching/)
- Uber Pool's window as told to riders: an older page said "up to 90 seconds" to match riders going a similar direction. The current page says "up to 5 minutes" [P] — [Uber Pool AU page](https://www.uber.com/au/en/ride/uberpool/); [Uber Pool AU (alt)](https://www.uber.com/en-AU/ride/uberpool)
- Express Pool asked riders to wait "up to a few minutes" for a match and to walk to a nearby pickup spot [P, from search snippet; page returned 404 on fetch] — [Uber blog: Express Pool](https://www.uber.com/blog/express-pool-match-meet-save/)
- An Uber research paper (Yan, Zhu, Korolko, Woodard) models a pooling "waiting window" that "is dynamically determined by market conditions: when supply is constrained, the waiting window increases" [P, from snippet; page 404 on fetch] — [Uber research: Dynamic pricing and matching](https://eng.uber.com/research/dynamic-pricing-and-matching-in-ride-hailing-platforms/)
- UberPool's 2016 update streamlined matchmaking and pickups [S] — [TechCrunch 2016](https://techcrunch.com/2016/12/12/uberpool-streamlines-matchmaking-pickups-and-driver-side-features/)
- UberX Share (June 2022) offers an upfront discount and up to 20% off if a co-rider is matched. It allows only one other passenger at a time and one seat per request, and drivers can opt out [S] — [Mass Transit](https://www.masstransitmag.com/alt-mobility/shared-mobility/article/21272370/uber-brings-back-shared-rides-as-uberx-share); [Fortune 2022](https://fortune.com/2022/06/21/uber-shared-rides-return/)

**Academic basis for the batch-and-assign approach (closest to Campus Connect)**
- Alonso-Mora et al., PNAS 2017 (MIT). The method builds a request-vehicle "shareability" graph and enumerates cliques as feasible trips (an RTV graph). An ILP then gives each vehicle at most one trip and assigns each request to exactly one trip or leaves it unassigned (with a large penalty). The objective is total delay plus that penalty. Constraints are maximum wait Ω, maximum delay Δ (= 2Ω) and capacity. Requests are batched every 30 s, and the ILP is "anytime", warm-started from a greedy assignment [P] — [PMC full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC5255617)
- Results from the paper's NYC taxi simulation (3,000 vehicles, Ω = 7 min): capacity 2 served 94% of demand with a 3.2 min mean wait and 1.5 min mean delay; capacity 4 served 98% with a 2.7 min wait and 2.3 min delay. These are simulations, not field results [P] — [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC5255617); [MIT DSpace](https://dspace.mit.edu/handle/1721.1/111212)

### Inferences
- Campus Connect is a static, single-origin special case of the Alonso-Mora formulation: enumerate feasible groups of 4 or fewer, then solve an exact partition. Because everyone starts at one gate, there is no pickup-time term and no stop-ordering explosion at the origin. Only drop-off ordering matters, which makes exact set partitioning tractable where Lyft needed heuristics.
- Production systems weight rider time (wait, detour) heavily. Campus Connect's car-km-first objective is an operator- and emissions-efficiency objective. It should cap per-rider detour or ride time as a constraint, as Alonso-Mora caps Δ and Lyft caps detour, so that a car-km-optimal plan never gives one rider a bad trip.
- Uber shrank UberX Share to 2 parties per car, while Campus Connect allows 4. The 4-rider case is defensible here because all riders share an origin, but this difference is worth stating.

### Gaps
- The original Lyft posts (eng.lyft.com/Medium) returned 403. Lyft details come from a 2022 secondary summary, and author and date were not confirmed.
- I found no current Uber engineering post describing the Pool or UberX Share matching algorithm in detail. Uber's two pages that would have covered it returned 404.
- No published Pool window for UberX Share (2022 onward) was found.

## Via: virtual stops, corner-to-corner walking, dynamic routing, metrics

### Takeaway
Via asks riders to walk to a nearby corner (a "virtual bus stop") so vehicles avoid detours, then inserts pickups and drop-offs into live vehicle routes in real time. Via publishes design claims and vendor case-study numbers, but I found no independent pooling-rate metrics.

### Cited Findings
- Via's patents describe picking candidate pickup and drop-off virtual stops, favoring "natural" stops on main roads, and setting a walking range (example 50-900 m, including "additional walk" beyond the nearest stop). Vehicles are assigned in real time, with stop tasks inserted into the existing route schedule [P] — [US 10,677,604 (Google Patents)](https://patents.google.com/patent/US10677604); [US 10,197,411 (Justia)](https://patents.justia.com/patent/10197411)
- Academic work on walking-to-stop design: if riders can be asked to walk, a rider can meet the vehicle on the street it is already driving, "inducing zero detour" [P] — [TU Delft / J. Intelligent Transportation Systems](https://research.tudelft.nl/files/126102464/15472450.2021.pdf)
- Via markets its software as routing vehicles "to maximize sharing and minimize detours", which is a design claim, not a measured rate [P, vendor] — [Via: corporate and campus shuttles](https://ridewithvia.com/solutions/corporate-and-campus-shuttles)

### Inferences
- Campus Connect's single fixed gate is the extreme case of Via's idea: every pickup is already consolidated at one virtual stop, so the whole detour cost moves to the drop-off side.

### Gaps
- No independent, published Via pooling or occupancy rate was found. The Google Via2G evaluation PDF (MTI/SJSU) could not be text-extracted, so its numbers are not reported: [MTI Via2G evaluation](https://transweb.sjsu.edu/sites/default/files/2002-Brown-RB-Microtransit-Evaluation.pdf)

## Waze Carpool, BlaBlaCar, DiDi Hitch, Careem: carpool vs ride-pool, scheduled vs on-demand

### Takeaway
True carpooling (a private driver already making the trip, with riders sharing costs) is matched differently from ride-pooling (paid drivers serving pooled requests). BlaBlaCar is pre-booked and deterministic: drivers publish a route and passengers search and book it. Waze Carpool matched commuters and closed in 2022 when commuting fell. DiDi Hitch shows that safety, not the algorithm, can be what decides whether a peer carpool service survives.

### Cited Findings
- BlaBlaCar uses pre-booked, deterministic matching: a known driver is assigned in advance, which suits infrequent, long-distance trips. Drivers publish routes, and passengers searching the same journey are matched to them [P/academic] — [arXiv 2102.06381](https://arxiv.org/pdf/2102.06381)
- BlaBlaCar's machine-learning matching produced 20% of driver-passenger matches in France, and it auto-computes intermediate cities on a ride (2018) [S] — [PhocusWire interview](https://www.phocuswire.com/Big-Chair-Blablacar-Nicolas-Brusson); [TechCrunch 2018](https://techcrunch.com/2018/01/30/blablacar-is-optimizing-its-service-for-small-cities-and-has-a-new-visual-identity/amp/)
- BlaBlaCar's ML matching approach [P] — [BlaBlaCar Medium: ML matching](https://medium.com/blablacar/how-blablacar-matches-passengers-and-drivers-with-machine-learning-1cf151451f)
- BlaBlaLines (commuting) fixed meeting points automatically on the driver's route, as close as possible to the passenger [P] — [BlaBlaCar newsroom](https://newsroom.blablacar.com/news/blablacar-launches-blablalines-a-carpooling-app-for-commuting); guidance on meeting points that avoid detours — [BlaBlaCar blog](https://blog.blablacar.com/blog/blablalife/travel-tips/ridesharing-meeting-points)
- Waze Carpool was retired by 31 Oct 2022 so Google could "focus... on helping drivers on the road today". Press tied the closure to pandemic-driven changes in commuting. It had run in the US, Brazil and Israel [P] — [Google Waze Carpool retirement FAQ](https://support.google.com/waze/carpool); [Engadget](https://www.engadget.com/waze-shuts-down-carpool-app-174825025.html); [TechCrunch](https://techcrunch.com/2022/08/26/googles-waze-shutting-down-its-carpool-service/)
- DiDi Hitch (private car owners and passengers heading the same direction) was suspended in 2018 after two passenger murders. It relaunched in July 2019 as a trial in 7 cities: women could ride only 5am-8pm, trips were capped at 50 km, and social features and ratings were removed. DiDi's separate Express carpool, which pools 2 passengers on paid drivers, was never suspended [S] — [TechCrunch 2018](https://techcrunch.com/2018/05/15/chinas-didi-pares-back-hitchhiking-car-service-following-passenger-murder); [Caixin 2019](https://www.caixinglobal.com/2019-04-16/didis-controversial-hitch-service-proposes-improvement-measures-despite-having-no-timeline-for-relaunch-101404837.html); [The Star / Reuters 2019](https://www.thestar.com.my/tech/tech-news/2019/07/18/chinas-didi-plans-to-relaunch-hitch-service-with-new-safety-features); [SCMP](https://www.scmp.com/tech/article/3036584/didi-resuming-its-controversial-carpool-function-hitch)

### Inferences
- Campus Connect matches riders to cars in batches at a fixed departure point, which is closer to scheduled van or shuttle pooling than to BlaBlaCar's publish-and-book model. Its closed, verified student community addresses the trust problem that sank DiDi Hitch.

### Gaps
- Careem: I found no reliable source on Careem's pooled or carpool matching. Careem's pooled product history was not researched within the tool budget.
- BlaBlaCar's current production matching algorithm is not publicly documented. The available details date from 2017-2018.

## Campus and university carpool or shuttle programs and their results

### Takeaway
Campus programs fall into two types: ride boards for peer carpools (Zimride, now Enterprise, at more than 130 campuses at its peak) and on-demand pooled shuttles (Via at Northwestern, Harvard and Northeastern). Reported results are mostly vendor numbers about ridership, not measured pooling rates.

### Cited Findings
- Zimride, founded by Lyft's founders, was sold to Enterprise Holdings in July 2013. It then had more than 130 university and corporate campus networks and was positioned as a substitute for a college ride board [S] — [TechCrunch](https://techcrunch.com/?p=845475); [Auto Rental News](https://www.autorentalnews.com/112647/enterprise-holdings-acquires-zimride-ride-matching-program)
- Universities joined later, including Rochester (2014), Lehigh (2015) and Penn State (2016). Enterprise later closed the public part of Zimride and kept the university and business accounts [S] — [Penn State News](https://www.psu.edu/news/campus-life/story/penn-state-partners-zimride-enterprise-ride-matching-service); [Skift](https://skift.com/?p=146983)
- Northwestern's Via-powered safe-ride service: Via reports a 65% increase in ridership in year one and 38% more available driver hours (vendor-reported) [P, vendor] — [Via Northwestern coverage, METRO](https://www.metro-magazine.com/news/via-to-provide-on-demand-safe-ride-program-on-northwestern-campus); [Via universities](https://ridewithvia.com/audience/universities)
- Harvard's evening van is free, on-demand and corner-to-corner, and replaced a fixed route. Capacity was cut to 50% during COVID. No ridership numbers were published [P, vendor] — [Via case study: Harvard](https://ridewithvia.com/case-study/harvard-evening-van)
- Northeastern's RedEye operates within 2 miles of Snell Library on Via technology [S] — [METRO Magazine](https://www.metro-magazine.com/news/northeastern-u-taps-via-for-on-demand-safety-shuttle)
- A 2025 study of a university community compared four fixed-route and demand-responsive services over six months. Its results were not retrieved [P] — [Discover Cities 2025 (DOAJ)](https://doaj.org/article/22e0e78a98e849299ec3da1c423a4eaa)

### Inferences
- Campus Connect sits between these two types. It pools peer or shared cars like a ride board but assigns them algorithmically in batches like a shuttle dispatcher. A campus's dense, time-clustered demand at one origin (classes ending) is the condition pooling needs and that city-wide Pool often lacked.

### Gaps
- No measured pooling or occupancy rate for any campus Via or Spare deployment was found. Spare's campus deployments were not researched.

## Why production systems shut down or scaled back pooling: lessons

### Takeaway
Pooling failed in cities mainly because of density: too few compatible requests per window means low match rates, heavy subsidies and detours riders dislike. COVID then gave operators a reason to suspend it (Uber and Lyft, March 2020). Lyft ended Shared in May 2023 because it "took people out of their way", and Uber brought it back in a narrower form (2 parties per car, driver opt-out).

### Cited Findings
- Leaked 2017 documents: UberPool's early match rate was 7.9%, and Uber spent around $1M a week (up to $6M a month by June 2015) subsidizing San Francisco Pool [S] — [TechCrunch 2017](https://techcrunch.com/?p=1497711); [Fortune 2017](https://fortune.com/2017/05/31/uber-uberpool-carpool/); [SFist](https://sfist.com/2017/05/31/uber_pool_loses_much_money.php). Later match-rate figures conflict: one account says roughly 25%, another says 60% after nine months. The source behind each figure was not pinned down, so treat both as unverified.
- Academic analysis: matching needs riders with compatible origins, destinations and timing, which is rare without high demand density. Low prices draw riders but cause losses when matches fail, and TNCs responded by cutting discounts or shutting ride-splitting, leaving a "low-sharing equilibrium" [P] — [NSF PAR paper](https://par.nsf.gov/servlets/purl/10287747); [NSF PAR paper 2](https://par.nsf.gov//servlets/purl/10584875)
- Strict guarantees on detour and wait can lower the match rate and depress participation [P] — [NSF PAR](https://par.nsf.gov/servlets/purl/10313348)
- Uber Pool was suspended in March 2020 (COVID). It was piloted in Miami in late 2021 and relaunched as UberX Share in June 2022 in 9 US cities [S] — [NBC News](https://www.nbcnews.com/tech/tech-news/uber-restarting-shared-rides-us-cities-new-york-san-francisco-rcna34532); [Engadget](https://www.engadget.com/uber-x-share-carpool-nine-cities-120048209.html)
- Lyft paused Shared Rides for COVID and launched Wait & Save, a cheaper fare in exchange for a longer wait for the best-located driver, as a non-pooled substitute [P] — [Lyft blog: Wait & Save](https://www.lyft.com/blog/posts/wait-and-save)
- Lyft discontinued shared rides in May 2023. CEO David Risher said they "took people out of their way" [S] — [Bloomberg](https://www.bloomberg.com/news/articles/2023-05-11/lyft-will-discontinue-pooled-rides-roll-out-new-features); [Fortune](https://fortune.com/2023/05/11/lyft-carpool-ride-eliminated/); commentary: [Human Transit](https://humantransit.org/2023/05/lyft-the-end-of-shared-rides.html)
- In 2025 Lyft revived pooled rides at airports, which are concentrated single-origin locations, piloting them at 8 US airports [S] — [Fortune 2025](https://fortune.com/2025/05/19/lyft-pooled-rides-at-airports-cheaper-trips/)
- TransitCenter called pooling rates in Manhattan "appallingly low" [S] — [TransitCenter](https://transitcenter.org/put-the-pool-in-uber)
- Waze Carpool closed in 2022 after commuting demand collapsed (see above) — [Google FAQ](https://support.google.com/waze/carpool)

### Inferences
- The lessons point toward Campus Connect's setting. Lyft's 2025 return to pooling at airports, a single origin with clustered demand, is the clearest production parallel to a campus gate: the density and detour problems that killed city-wide pooling are much smaller there.
- Remaining risks are demand-side. If too few students request rides in a window, match rates drop, as at Waze and early UberPool. Campus Connect should report its match rate and per-rider detour, and could widen its window dynamically when demand is thin, as in Uber's research model.
- Minimizing car-km first matches pooling's stated public benefit (fewer vehicle-km). Riders judge the service on detour and wait, though, so a detour cap is the safeguard production systems found necessary.

### Gaps
- No primary Uber or Lyft data on pooled match rates after 2017 was found.
- The exact UberX Share pricing formula is not public beyond "up to 20% off if matched".
