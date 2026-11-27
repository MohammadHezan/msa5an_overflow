# Ride Pooling from a Single Shared Pickup Point: Matching and Fare-Splitting Algorithms (Hackathon Python MVP)

Scope: one shared origin (e.g., a campus gate), 2-4 riders per car, ~10-50 requests per batch. Worked numeric examples marked "(illustration)" are my own arithmetic using the cited formulas, not taken from a source.

## Matching: how are one-to-many (single origin, multiple drop-offs) pooling problems solved?

### Takeaway
The proven recipe is: (1) enumerate every feasible group of up to 4 riders that meets the detour and wait limits, growing groups only from feasible smaller groups (the Alonso-Mora RTV pruning trick), then (2) pick a set of disjoint groups with an integer program (set partitioning). With one shared origin, routing a group is trivial: try every drop-off order, at most 4! = 24. Greedy pairing, Clarke-Wright savings and sweep clustering are faster fallbacks with no optimality guarantee.

### Cited Findings
**Exhaustive group enumeration and ILP (Alonso-Mora et al. 2017, PNAS)**
- Paper: "On-demand high-capacity ride-sharing via dynamic trip-vehicle assignment", Alonso-Mora, Samaranayake, Wallar, Frazzoli, Rus, PNAS 114(3):462-467, DOI 10.1073/pnas.1611675114 — [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC5255617); [ADS abstract](https://ui.adsabs.harvard.edu/abs/2017PNAS..114..462A/abstract)
- Headline result: 3,000 vehicles of capacity 4 (or 2,000 of capacity 10, about 15% of the NYC taxi fleet) serve 98% of demand, with 2.8 min mean wait and 3.5 min mean trip delay, on about 3 million NYC taxi rides — [ADS abstract](https://ui.adsabs.harvard.edu/abs/2017PNAS..114..462A/abstract); [Google Patents US11614751](https://patents.google.com/patent/US11614751)
- RV graph: two requests are linked if one empty virtual vehicle, starting at one request's origin, can serve both within the constraints. A request is linked to a vehicle if that vehicle can serve it — [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC5255617)
- RTV graph: feasible trips are found by exploring cliques of the RV graph and are built up incrementally by size. A trip of size k is tested only if every sub-trip with one request removed is already feasible. Each trip-vehicle edge is weighted by the sum of passenger delays — [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC5255617)
- ILP: binary variable ε(i,j) = 1 if vehicle j takes trip i, and binary χ(k) = 1 if request k is left unassigned. Objective: minimize the sum of trip costs plus a large constant for each unassigned request. Constraints: each vehicle takes at most one trip, and each request is served exactly once or ignored. The model has n + m constraints — [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC5255617)
- Greedy warm start: assign trips in decreasing size, breaking ties by increasing cost, then improve with the ILP. Solution quality improves over time and converges to the optimum — [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC5255617)
- Constraints used: maximum wait Ω, with experiments at 120, 300 and 420 s, and maximum total delay Δ = 2Ω. Requests are batched every 30 s. With Ω ≤ 300 s, each iteration ran in under 30 s on a 24-core 2.5 GHz machine (at NYC scale). The paper does not name the ILP solver. Timeouts on trip generation and the ILP trade optimality for speed — [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC5255617)

**Shareability network plus maximum matching for pairs (Santi et al. 2014, PNAS)**
- Santi, Resta, Szell, Sobolevsky, Strogatz, Ratti, PNAS 111(37):13290-13294. Each trip is a node, and two trips are linked if they can be shared within a maximum delay Δ. Parameter k caps how many trips can be combined. For pairs, classic maximum matching gives the best strategy: unweighted matching maximizes the number of shared trips, and weighted matching minimizes total travel time — [arXiv 1310.2963](https://arxiv.org/pdf/1310.2963); [DSpace@MIT](https://dspace.mit.edu/handle/1721.1/96318)
- The value of Δ has a profound effect on the network's structure. Shareability saturates quickly as trip density grows, so pooling can still work in sparse settings — [arXiv 1310.2963](https://arxiv.org/pdf/1310.2963)
- Reported in a citing patent rather than checked against the paper: more than 95% of NYC trips are shareable at Δ = 5 min, with roughly 30% lower operating cost — [USPTO 11288603](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/11288603); about 30% less cab time per [ScienceDaily](https://www.sciencedaily.com/releases/2014/09/140901211531.htm)

**Clarke-Wright savings (classic single-depot VRP heuristic, a natural fit for one shared origin)**
- Savings formula: s(i,j) = d(D,i) + d(D,j) − d(i,j), where D is the depot (here, the shared pickup). Start with one vehicle per rider. Sort the savings in descending order and merge routes when constraints allow and the endpoints are not interior to a route. Leftover riders go solo — [MIT Urban OR book 6.4.12](https://web.mit.edu/urban_or_book/www/book/chapter6/6.4.12.html)
- Strengths: efficient, simple to program, and complex constraints are easy to check. Weaknesses: no near-optimality guarantee, and pathological cases can go badly — [MIT Urban OR book](https://web.mit.edu/urban_or_book/www/book/chapter6/6.4.12.html); [NEO VRP](https://neo.lcc.uma.es/vrp/?p=185)

**Sweep / angular clustering (cluster first, route second)**
- Work in polar coordinates around the depot. Sweep a ray, adding points in angle order until capacity is hit, then start the next cluster. Solve a TSP within each cluster. Drawbacks: tours can be too long when length limits apply, and it assumes Euclidean distances — [MIT Urban OR book](https://web.mit.edu/urban_or_book/www/book/chapter6/6.4.12.html)

**Industry descriptions**
- Lyft Line pairs riders with overlapping routes automatically, and "the more overlap two routes have, the larger the discount." The engineering series ("Matchmaking in Lyft Line", Parts 1-3) is said to describe a greedy Haversine-based matcher plus a bucketed matching pool that holds riders. Only snippets were available (403 on direct fetch) — [Lyft Eng archive](https://eng.lyft.com/archive); [secondary summary](https://rrojin.tistory.com/21)
- Lyft "Triple Match" let drivers pick up three or more riders on similar routes, and it accounted for 20% of Lyft Line rides per Lyft — [TechCrunch](https://techcrunch.com/?p=1189255)
- Uber batches nearby riders and drivers for a few seconds after a request, then matches the batch to cut average wait for everyone rather than taking the closest pair — [Uber Marketplace: Matching](https://www.uber.com/gb/en/marketplace/matching/)
- UberPOOL kept re-optimizing after a match, and it might hold off matching a rider if a better match was expected soon. The source is an older, undated article that may describe a superseded system — [TechCrunch](https://techcrunch.com/?p=1426531)
- Shared rides have been modeled formally as online hypergraph matching with delays, using a randomized batching algorithm with worst-case guarantees — [arXiv 2107.11318](https://arxiv.org/pdf/2107.11318.pdf)
- One recent paper defines a "detour delay rate" as direct distance divided by actual pooled distance, and matches passengers to minimize detour distance — [arXiv 2503.13200](https://arxiv.org/pdf/2503.13200)

**Detour constraints commonly used**
- Absolute limits: max wait Ω of 2-7 min and max added delay Δ = 2Ω — [Alonso-Mora, PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC5255617). Max delay Δ of about 5 min — [Santi, arXiv](https://arxiv.org/pdf/1310.2963)
- Ratio form: a maximum detour factor γ on pooled versus direct distance. Higher γ raises the share rate — [arXiv 2508.19192](https://arxiv.org/pdf/2508.19192)

### Inferences
- **Recommended MVP pipeline:**
  1. Bucket requests by departure window (see the time-window section).
  2. For each rider, compute the solo distance d(O, i) from the shared origin O.
  3. Enumerate pairs, then triples, then quads, keeping a group only if all its sub-groups were feasible (RTV pruning).
  4. For each group, try every drop-off order (up to 24 permutations). Check each rider's ride ≤ min(γ·solo, solo + X min), for example γ = 1.5 and X = 10 min, plus seat capacity.
  5. Solve set partitioning: each rider covered exactly once, with singletons always allowed so a solution is always feasible. Minimize total vehicle-km (or cost), optionally adding a per-car fixed cost to encourage pooling.
- **Worst-case enumeration with no pruning, n = 50:** C(50,2) = 1,225 pairs, C(50,3) = 19,600 triples, C(50,4) = 230,300 quads. Each group has at most 24 orders, so even unpruned this is a few million cheap evaluations. Feasible groups are usually a small fraction, because detour limits prune most of them.
- **Pairs only (k = 2):** `networkx.max_weight_matching` with edge weight = savings s(i,j) is about 10 lines of code and optimal for pairs. A good "v0" before adding groups of 3-4.
- **With one shared origin**, the Clarke-Wright savings formula is the natural pair score. In the RV graph, the "virtual vehicle at one request's origin" is always the same point, which makes everything simpler.
- **Greedy fallback:** sort feasible groups by savings per rider (or by size, then cost, as in the Alonso-Mora warm start) and take groups whose riders are all still free. Near-instant, usually good, not optimal.

### Gaps
- Could not read the Lyft Line engineering posts directly (403), so the exact thresholds Lyft used (for example detour minutes) are unconfirmed.
- No current, primary Uber engineering post on UberPool / UberX Share matching internals was found.
- Did not verify Santi et al.'s 95% / 30% numbers in the paper itself (the PMC fetch was blocked by a bot check).

## Implementation: can OR-Tools CP-SAT solve set partitioning of groups of size ≤ 3-4 for ~50 riders quickly?

### Takeaway
Yes, almost certainly for an MVP. The model is one Boolean per candidate group, an "exactly one" constraint per rider, and a linear cost objective. OR-Tools documents this pattern, and community CP-SAT set-partition examples exist. I found no published benchmark for exactly 50 riders, so solve time is an inference.

### Cited Findings
- The CP-SAT Python API (`from ortools.sat.python import cp_model`) has Boolean variables, linear constraints and a linear objective — [CP-SAT docs](https://developers.google.com/optimization/cp/cp_solver); [Python reference](https://developers.google.com/optimization/reference/python/sat/python/cp_model)
- The official OR-Tools guide "Assignment with Allowed Groups" covers choosing among predefined allowed groups — [OR-Tools](https://developers.google.com/optimization/assignment/assignment_groups)
- Community CP-SAT set-partitioning models: hakank's `set_partition_sat.py` and `set_covering4_sat.py` — [hakank.org](https://hakank.org/or-tools/set_partition_sat.py); [hakank OR-tools page](https://hakank.org/or_tools); a CSPLib prob049 OR-Tools model — [CSPLib](https://www.csplib.org/Problems/prob049/models/set_partition_ortools.py.html)
- Alonso-Mora's ILP over trips is the same structure, with a penalty for unassigned requests, and it solved at NYC scale in under 30 s per 30-s batch — [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC5255617)

### Inferences
- Sketch (my formulation, following Alonso-Mora):
  ```python
  from ortools.sat.python import cp_model
  m = cp_model.CpModel()
  x = {g: m.NewBoolVar(f"g{gi}") for gi, g in enumerate(groups)}  # groups include all singletons
  for r in riders:
      m.AddExactlyOne(x[g] for g in groups if r in g)
  m.Minimize(sum(int(round(cost[g]*100)) * x[g] for g in groups))  # CP-SAT needs integer coefficients
  s = cp_model.CpSolver(); s.parameters.max_time_in_seconds = 5; s.parameters.num_workers = 8
  s.Solve(m)
  ```
- CP-SAT accepts only integer coefficients, so scale costs (for example, cents or metres).
- Expected size after pruning: likely hundreds to low tens of thousands of columns for 50 riders. Set partitioning at that size typically solves in well under a few seconds. This is an inference with no benchmark found, so set `max_time_in_seconds` as a safety net. CP-SAT returns the best solution found so far.
- Alternatives with the same model: PuLP/CBC, `scipy.optimize.milp`, or OR-Tools `pywraplp`.
- Scaling limit: the risk is the number of quads, not the solver. If feasible quads explode (dense downtown, loose γ), cap each rider's candidate groups (for example, the top 20 by savings). Alonso-Mora caps trips per vehicle the same way.

### Gaps
- No published CP-SAT timing benchmark for ride-pooling set partitioning at n ≈ 50. Verify empirically.

## Fare splitting: which cost-sharing rules are fair, individually rational, and easy to explain?

### Takeaway
For a shared origin, the strongest and simplest-to-justify rules are: (a) the per-leg (segment) split, which is the classic Littlechild-Owen airport-game rule and equals the Shapley value when riders' drop-offs fall along one route; (b) the Shapley value for a fixed drop-off order, which is computable in polynomial time (Levinger et al.); and (c) proportional-to-solo-fare, which is trivially individually rational. Commercial apps (Uber, Lyft) avoid ex-post splitting entirely: each rider gets a guaranteed, discounted upfront fare.

### Cited Findings
**Per-leg / airport-game rule**
- Littlechild & Owen (1973, Management Science 20(3):370-372): each segment's cost is split equally among everyone who needs that segment. The rule equals the Shapley value of the airport game, where a coalition's cost is its largest member's cost. Wikipedia example: costs 8, 11, 13, 18 give increments 8, 3, 2, 5 and charges 2, 3, 4, 9 (total 18) — [Wikipedia: Airport problem](https://en.wikipedia.org/wiki/Airport_problem); [IDEAS/RePEc](https://ideas.repec.org/a/inm/ormnsc/v20y1973i3p370-372.html); [Thomson survey](https://www.iser.osaka-u.ac.jp/collabo/20140524/Airport_Problems.pdf)

**Shapley value for shared rides (Levinger, Hazon, Azaria)**
- Shapley is the only allocation satisfying efficiency, symmetry, null player and additivity — [arXiv 1909.04713](https://arxiv.org/pdf/1909.04713)
- "Prioritized" ride-sharing game: common origin d₀ with a fixed drop-off order. The cost of subset S is the path length visiting S's destinations in that order. Shapley reduces to φ(uᵢ) = (1/n!) Σ_R [δ(dₗ,dᵢ) + δ(dᵢ,dᵣ) − δ(dₗ,dᵣ)], where dₗ and dᵣ are the nearest earlier and later destinations. This gives a closed form in O(n²) pairwise distances, so it is polynomial. The paper calls this a 2D generalization of the airport problem — [ar5iv 1909.04713](https://ar5iv.arxiv.org/html/1909.04713)
- Non-prioritized version (subset cost = shortest path in any order): exact Shapley is NP-hard via path-TSP — [ar5iv](https://ar5iv.arxiv.org/html/1909.04713)
- SHAPO proxy (prioritized Shapley using the shortest-path order). On Toulouse road data with the airport as origin, 3-9 passengers and 100 instances each: 4.60% mean error, MAE $0.19 and max error $0.43, against about a $5 average fare. Alternatives scored worse: "Depot Distance" (proportional to distance from origin) 31.26% error; "Shortcut Distance" 48.42%; "Re-routed Margin" 85.66% — [ar5iv](https://ar5iv.arxiv.org/html/1909.04713)
- Related: AAMAS 2020 version — [IFAAMAS](https://www.ifaamas.org/Proceedings/aamas2020/pdfs/p1895.pdf). Fair ride allocation on a line, using Shapley within groups plus Nash stability and envy-freeness — [arXiv 2007.08045](https://arxiv.org/pdf/2007.08045)

**Core / nucleolus**
- Lu & Quadrifoglio (Transportation Research Part B, 2019) model ridesharing cost allocation as a cooperative game. The nucleolus minimizes maximum dissatisfaction, and computing it is intractable, so they use coalition generation. Their approximation needs about 1.6% of coalition constraints and is exact when the core is non-empty. If riders find the split unfair, they may leave and form their own groups — [arXiv 1902.07266](https://arxiv.org/pdf/1902.07266); [RePEc](https://ideas.repec.org/a/eee/transb/v121y2019icp41-55.html)
- Fair cost-sharing mechanisms and the stable matchings they induce, tested on NYC taxi data — [arXiv 2007.08064](https://arxiv.org/abs/2007.08064)

**How Uber prices pooled riders**
- Uber's upfront price uses expected time, traffic, distance and surge, and it factors in the likelihood of a match, so the shared fare is always cheaper than UberX. The price is fixed unless the trip changes significantly — [Uber POOL FAQ](https://www.uber.com/us/en/blog/uberpoolfaqs); [Uber upfront fares](https://www.uber.com/newsroom/upfront-fares-no-math-and-no-surprises/)
- Advertised savings: up to 40% less than uberX for older POOL marketing; up to about 20% for UberX Share per a third-party guide. Different products and regions, so treat as approximate — [Uber AU POOL](https://www.uber.com/au/en/ride/uberpool/); [Ridester](https://www.ridester.com/?p=618768)
- On the driver side, Uber deducts the service fee from each pickup's upfront fare — [Uber pool service fee](https://www.uber.com/en-AU/blog/pool-service-fee/)
- Lyft ties the discount size to route overlap — [Lyft Eng archive](https://eng.lyft.com/archive)

### Inferences (formulas and worked examples are my illustrations)
Notation: s_i = rider i's solo cost from the origin; C = the group's pooled route cost; savings S = Σ s_i − C.

1. **Proportional to solo:** p_i = C · s_i / Σ s_j. Always individually rational when C ≤ Σ s_j, since p_i ≤ s_i. Easiest to explain. But it ignores who caused the detour.
2. **Equal savings split:** p_i = s_i − S/n. For 2 riders this equals the Shapley value. With 3 or more it can push a short-trip rider's fare to zero or below, so clip at a minimum fare.
3. **Per-leg (segment) split:** split each leg of the actual route equally among riders still on board. Equals Shapley/airport when drop-offs are collinear. With big detours, the last rider can pay more than their solo fare, so cap at min(p_i, s_i·(1−discount)) and renormalize.
4. **Prioritized Shapley (SHAPO):** exact via 2^n subsets for n ≤ 4 (only 16 subsets per group), so just brute-force it. Use the chosen drop-off order as the priority order. Not guaranteed to be in the core with 3+ riders, so add an IR check.
5. **Nucleolus / core:** theoretically the fairest, but it needs an LP over coalitions. Overkill for a demo.
6. **Upfront discounted fare (industry):** quote p_i = (1 − δ)·s_i before matching, with δ around 20-40%. Simplest UX, and the platform absorbs the variance. For a campus MVP, show this to users and use one of the rules above internally to check it covers cost.

**Worked example A (no detour, collinear):** origin O, A at 4 km, B at 7 km along the same road. s_A = 4, s_B = 7, C = 7, S = 4.
- Per-leg: leg O→A (4) split 2/2, leg A→B (3) to B alone, so A = 2, B = 5.
- Shapley (2-player formula, a = 4, b = 3, c = 7): φ_A = a + b/2 − c/2 = 2, φ_B = b/2 + c/2 = 5. Matches per-leg.
- Equal savings: A = 4 − 2 = 2, B = 7 − 2 = 5.
- Proportional: A = 7·4/11 = 2.55, B = 4.45.

**Worked example B (detour):** A at 4 km, B 6 km from O but off-route, with d(A,B) = 4. Route O→A→B gives C = 8. Σs = 10, so S = 2.
- Shapley (a = 4, b = 4, c = 6): A = 4 + 2 − 3 = 3, B = 2 + 3 = 5. Both save 1, so it is IR.
- Proportional: A = 3.2, B = 4.8.
- Per-leg: A = 2, B = 2 + 4 = 6. **B pays its full solo fare (6) and saves nothing.** This shows why per-leg needs an IR cap when detours exist.

**Worked example C (3 riders, prioritized Shapley via subsets; illustration):** collinear drop-offs at 2, 5 and 9 km. The airport rule gives A = 2/3, B = 2/3 + 3/2 = 2.17, C = 2/3 + 3/2 + 4 = 6.17, total 9 km. Multiply by the per-km rate.

### Gaps
- Lu & Quadrifoglio's full-text experiments (instance sizes, comparison of proportional vs nucleolus) were not retrieved.
- Hsieh (2021, Energies), comparing three cost-savings allocation schemes, was not retrieved.
- Lyft's and Via's exact pooled-fare formulas are not public in sources found. Via was not covered.

## Time-window matching: how should requests be grouped by departure time?

### Takeaway
Use short fixed batches (rolling windows) for on-demand requests, as Uber (seconds) and Alonso-Mora (30 s) do. For pre-scheduled campus rides, treat each rider's acceptable departure window [t_i − w, t_i + w] as a hard compatibility constraint during group enumeration, rather than only bucketing by clock slots.

### Cited Findings
- Alonso-Mora collects requests in 30-s batches, with max wait Ω, and Δ = 2Ω — [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC5255617)
- Uber waits "a few seconds" to accumulate a batch before matching — [Uber Matching](https://www.uber.com/gb/en/marketplace/matching/)
- Lyft Line reportedly held riders in a bucketed matching pool (secondary source) — [summary](https://rrojin.tistory.com/21)
- Santi et al. compatibility is time-based: trips are shareable only if all passengers' delays stay ≤ Δ — [arXiv 1310.2963](https://arxiv.org/pdf/1310.2963)
- Timing when to match is itself an optimization problem (deep RL approach) — [arXiv 2503.13200](https://arxiv.org/pdf/2503.13200)
- Randomized batching for online hypergraph matching with delays has provable worst-case guarantees — [arXiv 2107.11318](https://arxiv.org/pdf/2107.11318.pdf)

### Inferences
- **Fixed buckets (e.g., 15-min slots):** trivial to code, but riders at 9:14 and 9:16 never match. Fix this with overlapping buckets, or by assigning each request to its nearest slot and its neighbouring slot, then deduplicating.
- **Flexible windows (recommended):** group G is feasible only if max_i(t_i − w_i) ≤ min_i(t_i + w_i). The car departs at the latest earliest-time, and that departure must fall inside every rider's window. This drops directly into the pruning step of the enumeration.
- **Live demo:** run the solver every 30-60 s on all pending requests. Lock a match once its departure is within a few minutes, and release unmatched riders to a solo ride after their max wait.

### Gaps
- No source found with campus- or scheduled-shuttle-specific bucket sizes.

## Women-only / preference-constrained matching in industry

### Takeaway
Major platforms run gender-preference matching as a hard filter on eligible matches, usually opt-in and driver-side first. All of them warn that it lengthens waits because the eligible supply is smaller. In the MVP this is just another feasibility check during group enumeration: a woman who opted in can only join groups that are all women.

### Cited Findings
- **Uber Women Preferences (US):** riders can request Women Drivers on demand, reserve trips with women drivers, or set a standing preference, though matches are not guaranteed. Women drivers can toggle a Women Rider Preference. Pilots ran in LA, SF and Detroit, and a later FAQ says it is nationwide. Uber says the driver-side feature is in 40 countries with over 100M trips, and warns of longer waits when women drivers are scarce — [Uber Newsroom](https://www.uber.com/us/en/newsroom/women-preferences/)
- **Uber "Ellas" (Mexico):** female drivers can choose to accept only women riders — [Yahoo/Reuters](https://www.yahoo.com/now/didi-launches-mexico-women-select-213952039.html)
- **DiDi Mujer (Mexico, 2020):** female drivers can accept requests only from female passengers. Available in Mexico City, Puebla, Guadalajara and Monterrey. Only 4.3% of DiDi's roughly 100,000 drivers in Mexico were women at the time — [Jakarta Post/Reuters](https://www.thejakartapost.com/life/2020/11/25/didi-launches-service-in-mexico-for-women-to-select-only-female-passengers); a UN partnership profile reports female driver registrations up 28% — [UN SDGs](https://sdgs.un.org/partnerships/didi-women-empowering-women-and-combatting-discrimination-through-technology-and)
- **99 Mulher (Brazil, DiDi subsidiary):** a women-driving-women program in selected cities — [Yahoo/Reuters](https://www.yahoo.com/now/didi-launches-mexico-women-select-213952039.html)
- **DiDi Hitch (China, 2018):** late-night carpool Hitch rides resumed with drivers allowed to pick up only same-sex passengers — [TechCrunch](https://techcrunch.com/2018/06/14/didi-will-resume-late-night-hitch-rides-but-only-allow-drivers-to-pick-up-passengers-of-the-same-sex)
- **Careem Ameera (Dubai):** a women-only service with female captains, where male passengers are allowed only if accompanied by a woman. Approved by Dubai's RTA — [Arabian Business](https://www.arabianbusiness.com/careem-launches-women-only-limo-service-651774.html); [Khaleej Times](https://khaleejtimes.com/uae/ameera-dubais-first-female-chauffeur-service-for-women?amp=1)
- **Careem Pakistan:** female captains serve mixed riders, not women only — [Dawn](https://www.dawn.com/news/1301038). Later, a women-only motorbike service — [ProPakistani](https://propakistani.pk/2020/01/25/careem-announces-a-new-bike-category-for-women/amp/)

### Inferences
- **Implementation:** add `women_only: bool` per request. During enumeration, reject group G if any member has women_only and any member is not a woman. Driver gender can be a further constraint if drivers are modelled. Other preferences (same department, quiet ride, luggage) follow the same pattern.
- **Expected effect:** the women-only pool is smaller, so pooling rates drop and waits grow. Show this in the UI, as Uber does. Consider allowing a women-only group of 2 with a looser detour cap to compensate.
- **Fare rules are unaffected:** the split is computed per formed group.

### Gaps
- Could not confirm whether DiDi Mujer and Careem Ameera are still active today (sources date from 2016-2020).
- No public algorithmic details on how these platforms trade off preference matching against wait time.
