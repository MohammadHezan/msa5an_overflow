# Greedy/insertion vs exact/batch-optimal ride-pooling matching: quantitative quality gap

Scope note: 15 tool calls. The PNAS publisher pages returned 403, so the Alonso-Mora and Santi figures come from the PMC open-access copies. The Prague head-to-head study (arXiv 2305.02209) is the cleanest direct "optimal vs insertion heuristic" comparison found. Its main text was read only up to roughly 100k of 138k characters, so the Manhattan appendix was not read.

## 1. Alonso-Mora et al. 2017 (PNAS) and follow-ups: optimal assignment vs greedy; fleet size and occupancy

### Takeaway
Alonso-Mora et al. show that a batch ILP over the RTV graph (30 s batches) lets 2,000 vehicles of capacity 10, or 3,000 of capacity 4, serve about 98% of Manhattan taxi demand. That is roughly 15–22% of the taxi fleet. The paper does not publish a numeric greedy-vs-optimal gap. A 2023 follow-up that re-implements the method (Prague, 30 s batches) finds that optimal assignment beats an insertion heuristic by about 20% vehicle-km, about 12% vehicles used and about 5% passenger delay at peak. The gains shrink off-peak, where the fleet advantage flips to about 2% worse.

### Cited Findings
**Alonso-Mora, Samaranayake, Wallar, Frazzoli, Rus (PNAS 114:462, 2017). Setting: NYC Manhattan taxi data, about 3M rides, 13,586 active taxis, 382,779–460,700 requests/day, max wait Ω = 420 s unless noted, 30 s batch.**
- The method starts from a greedy assignment and improves it through constrained optimization (ILP), "converging to the optimal assignment over time". No numeric greedy-vs-optimal cost gap is reported in the main text. — [PMC copy](https://pmc.ncbi.nlm.nih.gov/articles/PMC5255617); [ADS abstract](https://ui.adsabs.harvard.edu/abs/2017PNAS..114..462A/abstract)
- Service rate, waiting and delay by fleet and capacity (all at Ω = 420 s):
  - 3,000 vehicles, capacity 2: 94% served, mean wait 3.2 min, mean delay 1.5 min.
  - 3,000 vehicles, capacity 4: 98% served, wait 2.7 min, delay 2.3 min.
  - 3,000 vehicles, capacity 10: 99% served.
  - 2,000 vehicles, capacity 10: 98% served, wait 2.8 min, delay 3.5 min.

  — [PMC copy](https://pmc.ncbi.nlm.nih.gov/articles/PMC5255617)
- 1,000 vehicles, capacity 10: almost 80% of requests served, versus below 30% for single-rider taxis of the same fleet size. — [PMC copy](https://pmc.ncbi.nlm.nih.gov/articles/PMC5255617)
- With a tight Ω = 120 s and 3,000 vehicles, the benefit of high capacity is only about 15%. Tight wait limits sharply cut pooling gains. — [PMC copy](https://pmc.ncbi.nlm.nih.gov/articles/PMC5255617)
- About 90% of rides were shared. At 1,000 vehicles, capacity 10, Friday 18:00: 10% of vehicles carry 8 or more passengers, 40% carry 6 or more, 80% carry 3 or more. At 2,000 vehicles, capacity 4: over 70% of vehicles carry at least 3 passengers. — [PMC copy](https://pmc.ncbi.nlm.nih.gov/articles/PMC5255617)
- Rebalancing idle vehicles raised the service rate by about 20%. — [PMC copy](https://pmc.ncbi.nlm.nih.gov/articles/PMC5255617)
- Computation: for Ω ≤ 300 s, one 30 s iteration solves in under 30 s on a 24-core 2.5 GHz machine. Robustness tests covered batch windows of 10–50 s and demand of about 220k and 880k requests/day. Numeric results for these tests are in the supplement, which was not machine-readable. — [PMC copy](https://pmc.ncbi.nlm.nih.gov/articles/PMC5255617)

**Fiedler/Čáp et al. style follow-up, "Large-scale Online Ridesharing: The Effect of Assignment Optimality on System Performance" (arXiv 2305.02209). Setting: Prague, about 122k peak-hour requests (07:00–08:00) and about 43k off-peak (11:00–12:00), capacity 5, max delay 4 min, 30 s batch, 100% service (fleet not limiting). "VGA optimal" is an exact ILP with a 0.02% Gurobi gap. "IH" is the insertion heuristic.**
- Peak hour:

  | Method | Vehicle-km | Average delay | Vehicles used | Computation time per batch |
  |---|---|---|---|---|
  | IH | 539,793 | 190 s | 15,685 | 18 ms |
  | VGA optimal | 429,172 | 180 s | 13,787 | about 193 s |
  | VGA limited (0.5% gap, 60 ms/vehicle group cap) | 451,978 | 178 s | 14,449 | 27.7 s |
  | "VGA PNAS" (Alonso-Mora-style) | 475,378 | 161 s | 14,607 | 15.6 s |

  — [arXiv 2305.02209](https://arxiv.org/html/2305.02209)
- Headline at peak: optimal cuts vehicle distance by "more than 20%" vs insertion (about 110,000 km per hour), passenger delay by about 5%, and fleet by about 12% (1,898 fewer vehicles). — [arXiv 2305.02209](https://arxiv.org/html/2305.02209)
- Off-peak:

  | Method | Vehicle-km | Average delay | Vehicles used |
  |---|---|---|---|
  | IH | 211,285 | 191 s | 4,646 |
  | VGA optimal | 175,865 (about 17% less) | 179 s | 4,746 (about 2% more than IH) |

  — [arXiv 2305.02209](https://arxiv.org/html/2305.02209)
- The time-limited near-optimal VGA still beats insertion by about 16% vehicle-km at peak, at about 86% less computation than the full optimum. — [arXiv 2305.02209](https://arxiv.org/html/2305.02209)
- Pooling of any kind versus no ridesharing at peak: 57% less vehicle-km (optimal). Off-peak: about 48% less. — [arXiv 2305.02209](https://arxiv.org/html/2305.02209)
- Scalability limit: the exact optimum was tractable at peak only for 30 s batches with 3–4 min max delay and capacity 2–5. Capacity 10 failed. Off-peak, a 7 min max delay did not finish in 24 h. Batches reached more than 3,000 waiting requests and 11,000 vehicles. — [arXiv 2305.02209](https://arxiv.org/html/2305.02209)
- Some ratios quoted in the paper's text, such as "about one-third" of the no-sharing fleet, do not match its own tables (13,787/33,066 ≈ 42%). Use the table values. — [arXiv 2305.02209](https://arxiv.org/html/2305.02209)

**Simonetto, Monteil, Gambella (IBM, arXiv 1902.10676): linear-assignment simplification of the batch approach**
- Casts ridesharing as a linear assignment between new requests and vehicles (NYC and Melbourne data). A companion paper states that linear assignments "can perform as good as more elaborated assignments, when run at a high enough sampling rate". This suggests a simpler matcher run often can close much of the gap to the RTV ILP. — [arXiv 1902.10676](https://ar5iv.arxiv.org/html/1902.10676); [companion arXiv 1906.07567](https://ar5iv.labs.arxiv.org/html/1906.07567)

**Customer-focused heuristics (arXiv 2107.11318). Setting: Manhattan, 500 vehicles, 10% and 12% of AM-peak demand, groups of 2 or fewer people.**
- A 1-min-batch bipartite (near-optimal) matcher beat the other heuristics on throughput by about 10% (about 200 requests/hour) at 10% demand. A 5 s "restricted subgraph" greedy came within about 10% of bipartite throughput in under-supply. — [arXiv 2107.11318](https://arxiv.org/html/2107.11318)
- Customer trade-off at 10% demand:

  | Method | Pickup | Total wait | In-vehicle delay |
  |---|---|---|---|
  | Bipartite, 1 min batch | 3.74 min | 4.64 min | 3.16 min |
  | Greedy, 5 s batch | 7.51 min | 8.09 min | 1.34 min |

  The batch optimizer roughly halves wait but more than doubles detour delay. — [arXiv 2107.11318](https://arxiv.org/html/2107.11318)

### Inferences
- A defensible, sourced claim is "batch-optimal assignment typically saves about 15–20% vehicle-km and about 10% fleet over an insertion heuristic at peak demand". The basis is the Prague 30 s batch study with capacity 5 and 4 min max delay. Off-peak the fleet gain can vanish.
- Most of the gain is captured by a time-limited near-optimal solve (16% vs 20%). This supports CP-SAT with a time limit as a reasonable design.
- The objective matters. Optimizers can trade lower wait for more detour (2107.11318), so Campus Connect should report wait and detour separately, not only vehicle-km.

### Gaps
- A numeric "greedy initial solution vs ILP" gap inside Alonso-Mora 2017 could not be extracted. The supplementary PDF was not machine-readable.
- The Manhattan appendix of 2305.02209 was not read, so the numbers above are Prague only.

## 2. Santi et al. 2014 (PNAS shareability networks): % shareable, km saved, delay tolerance and density

### Takeaway
In NYC, nearly all taxi trips are pairwise shareable with small delay tolerances when the system knows all trips in advance ("oracle"). An online system with a 1 min look-ahead window captures far less at tight tolerances but catches up by Δ = 5 min. At Δ = 5 min, shared travel time savings are 32% online and 40% oracle. Shareability saturates at about 25% of NYC's normal daily trip volume.

### Cited Findings
**Santi, Resta, Szell, Sobolevsky, Strogatz, Ratti (PNAS 111:13290, 2014). Setting: about 150M NYC taxi trips (2011), 13,586 taxis, about 400k trips/day, Manhattan network of 4,091 nodes, k = 2 (pairs) unless stated.**
- At Δ = 1 min, 94.5% of trips are shareable in the oracle model (full-day foreknowledge) vs under 30% in the online model (δ = 1 min window). At Δ = 2 min the oracle model is close to 100%. — [PMC copy](https://pmc.ncbi.nlm.nih.gov/articles/PMC4169909)
- At Δ = 5 min the online model exploits nearly all sharing opportunities. Total travel time saved is 32% online vs 40% oracle, or 24% vs 30% excluding empty trips. — [PMC copy](https://pmc.ncbi.nlm.nih.gov/articles/PMC4169909)
- The abstract claims cumulative trip length can be cut by "40% or more". MIT News: at 5 min delay tolerance almost 95% of trips could be shared, and the trip count could fall 40% with about 30% lower operating cost and pollution. — [arXiv 1310.2963](https://arxiv.org/pdf/1310.2963.pdf); [MIT News](https://news.mit.edu/2014/rideshare-data-cut-taxi-time-0901)
- Saved trips at Δ = 300 s: about 50% for k = 2 (theoretical maximum 50%) and about 60% for k = 3 (maximum 66.7%). Triples add value only above Δcrit ≈ 150 s. Below that the gain is negligible. — [PMC copy](https://pmc.ncbi.nlm.nih.gov/articles/PMC4169909)
- Density: shareability saturates at about 100,000 trips/day, about 25% of the NYC average, with near-maximum shareability. The lowest density tested was 1,962 trips/day. The fitted curve is f(x) = Kx^n/(1+Kx^n). — [PMC copy](https://pmc.ncbi.nlm.nih.gov/articles/PMC4169909)
- Method note: the paper solves maximum matching (k = 2) exactly on the shareability graph and uses a heuristic for k = 3. — [PMC copy](https://pmc.ncbi.nlm.nih.gov/articles/PMC4169909)

### Inferences
- The oracle vs online gap at small Δ (94.5% vs under 30% at Δ = 1 min) is the closest published proxy for the value of a longer look-ahead or batching window. Waiting to see more requests matters most when delay tolerance is tight. This bears on whether to batch requests before a campus departure.
- Shareability potential is not the same as realized savings. The 40% figure is a shareability-graph upper bound under NYC density.

### Gaps
- The full PDF figures (shareability vs Δ curves) could not be read. The arXiv PDF was binary-only.

## 3. Batching window length (seconds vs minutes) and match quality; batch vs immediate

### Takeaway
Longer batch windows raise pairing ratio and distance saving but add matching wait and detour. Total customer wait is U-shaped in the window length. Optimal fixed windows in NYC simulations are about 15–20 s, and an adaptive window does better. In the Prague study, only the exact optimizer clearly converted longer batches into efficiency gains, and larger windows quickly made the exact solve intractable.

### Cited Findings
- Bao et al., "Timing the Match" (arXiv 2503.13200, NYC-calibrated simulator):
  - Ride-hailing total wait was about 284 s at a 5 s interval, about 269 s at 15 s (best fixed), about 277 s at 30 s, and about 298 s at 60 s. Matching time rose from about 7 s to about 63 s across that range.
  - For pooling, a 20 s fixed interval was best among 10–80 s, and an adaptive RL policy reached about 338 s total wait.
  - The journal version reports 3.1% (ride-hailing) and 20.1% (pooling) waiting-time reductions from adaptive timing. These headline numbers differ between the versions.

  — [arXiv 2503.13200](https://arxiv.org/html/2503.13200v1); [TRC paper PDF](https://www.fransoliehoek.net/docs/Bao26TRC.pdf)
- A prediction-based dispatch study found that as the matching interval Δt increases, total distance saving and pairing ratio improve for all strategies, but response time and passenger detour also increase. — [arXiv 2403.06463](https://arxiv.org/pdf/2403.06463)
- Peer-to-peer ridesharing work notes that an overly long batching interval causes dissatisfaction and abandoned requests. It says the interval should be chosen by trading vehicle-km against matching success and wait. — [arXiv 2105.13078](https://arxiv.org/pdf/2105.13078)
- An intercity pooling paper states that practical matching intervals are about 0.5–2 min. — [arXiv 2307.06742](https://arxiv.org/html/2307.06742)
- Prague study: longer batches increase passenger delay, and "optimal VGA is the only method where longer batches clearly improve efficiency". The exact solve at peak was feasible only at 30 s batches. — [arXiv 2305.02209](https://arxiv.org/html/2305.02209)
- Alonso-Mora 2017 tested 10–50 s windows for robustness and used 30 s as the baseline. — [PMC copy](https://pmc.ncbi.nlm.nih.gov/articles/PMC5255617)

### Inferences
- An optimizer's advantage over greedy grows with the batch size, meaning the number of simultaneous requests it sees. Running CP-SAT on a 5 s or near-immediate trickle of requests would likely give results close to greedy. Its value shows up when it batches a departure wave, for example all requests for a given shuttle slot.
- For scheduled campus departures, "batch until departure cutoff" approximates Santi's oracle model. Literature suggests this is where optimization beats immediate first-come matching most, especially at tight detour limits.

### Gaps
- No study found reported vehicle-km for greedy vs optimal at several different batch lengths in one table. The Prague sensitivity figures (Fig. 13–14) have no numeric values in the text.
- No 2 s vs 30 s pooling result was found.

## 4. One-to-many (single origin, many destinations), airport and campus pooling

### Takeaway
Little quantitative greedy-vs-optimal evidence exists specifically for one-to-many or campus settings. The literature is mostly small case studies. One airport-shuttle study reports that heuristics approximate the exact solution well, and a campus case study found no single dominant mode. For a campus claim, Campus Connect would need its own benchmark on its own demand.

### Cited Findings
- Airport-access shared shuttle routing and scheduling, tested on one day of Dulles airport records (Transportation Research Record 2467, 2014). It reports that heuristics "provide good approximations to the exact solution". Numbers were paywalled. — [TRR 2467-17](https://journals.sagepub.com/doi/10.3141/2467-17)
- NYC ridesharing-adoption analysis: average cost savings of shared airport rides about 50%. Airport trip about $42 vs a Manhattan trip at $12.50. — [arXiv 2309.07257](https://arxiv.org/pdf/2309.07257)
- Santi et al. note that earlier taxi-sharing work was done on small scales "such as within airport perimeters". — [arXiv 1310.2963](https://arxiv.org/pdf/1310.2963.pdf)
- Würzburg "Mobility to Campus" framework (2025) compared ride-sharing, ride-pooling and solo driving and found no definitive best mode for campus mobility. — [arXiv 2506.13574](https://arxiv.org/pdf/2506.13574)
- A Texas A&M ridesharing study found that raising the maximum number of passengers matched per vehicle is the most effective lever for mileage savings. — [TAMU paper](https://lquadrifoglio.engr.tamu.edu/wp-content/uploads/sites/221/2025/02/WMCCAU2004_Ridesharing.pdf)
- A 2024 University of Michigan dissertation reports that scalable heuristics can substitute for centralized optimization in many scenarios with only minor performance sacrifice. — [UMich Deep Blue](https://deepblue.lib.umich.edu/handle/2027.42/193282)

### Inferences
- With a single shared origin, pickup-side detour disappears. The problem reduces to partitioning destinations into vehicle groups and sequencing drop-offs, a set partitioning or capacitated VRP. Greedy matchers here typically fail by committing early riders to poor groupings. That is the failure batch set partitioning fixes. The 20% (Prague) and about 10% throughput (Manhattan) gaps are therefore plausible but unverified upper or lower references, not campus-specific evidence.
- Because the problem is small (tens of riders per departure), CP-SAT can likely solve to proven optimality. The tractability limits seen at city scale (Prague) do not apply.

### Gaps
- No peer-reviewed study was found reporting greedy vs optimal vehicle-km or match rate for a one-origin, many-destination campus or airport pooling problem.

## 5. Minimum demand density / critical mass for pooling

### Takeaway
Tachet et al. (2017) give a universal scaling law. Shareability depends on L = λv²Δ³/|Ω|, where λ is trips per hour, v is speed, Δ is delay tolerance and |Ω| is area. Shareability saturates quickly. At Δ = 5 min, about 2.5 trips/h/km² already gives 60–97% pairwise shareability across eight cities, and 0.5 trips/h/km² gives only 17–59%.

### Cited Findings
- Tachet, Sagarra, Santi, Resta, Szell, Strogatz, Ratti, "Scaling Law of Urban Ride Sharing", Sci. Rep. 7:42868 (2017):
  - Shareability curves for NYC, SF, Singapore and Vienna collapse onto one universal curve in L, with no adjustable parameters. Model fit R² is 0.91–0.98.
  - L = λv²Δ³/|Ω|, so shareability scales with the cube of delay tolerance.

  — [PMC5337932](https://pmc.ncbi.nlm.nih.gov/articles/PMC5337932); [arXiv 1610.09921](https://www.arxiv.org/abs/1610.09921)
- Taxi densities and resulting shareability: NYC 344 trips/h/km², Singapore 24.5, San Francisco 12.6 (all "almost 100%" shareable), Vienna 0.95 (83%). — [PMC5337932](https://pmc.ncbi.nlm.nih.gov/articles/PMC5337932)
- Predicted shareability at Δ = 5 min by density (trips/h/km²):

  | City | 0.5 | 2.5 | 4.5 | 8.5 |
  |---|---|---|---|---|
  | Amsterdam | 45% | 92% | 98% | 100% |
  | Berlin | 17% | 60% | 80% | 94% |
  | London | 17% | 60% | 80% | 94% |
  | Newcastle | 59% | 97% | 99% | 100% |
  | Paris | 39% | 89% | 97% | 100% |
  | Prague | 51% | 95% | 99% | 100% |
  | Rome | 37% | 88% | 97% | 99% |
  | Santiago | 39% | 89% | 97% | 100% |

  Berlin and London show identical rows in the source, which may be a transcription error. — [PMC5337932](https://pmc.ncbi.nlm.nih.gov/articles/PMC5337932)
- The paper gives no explicit critical-mass threshold. It stresses that potential is large even at low density and "saturates rapidly". — [PMC5337932](https://pmc.ncbi.nlm.nih.gov/articles/PMC5337932)
- Santi 2014: NYC saturates at about 100k trips/day, about 25% of normal volume. — [PMC4169909](https://pmc.ncbi.nlm.nih.gov/articles/PMC4169909)

### Inferences
- Shareability means a pairable trip exists. It is not realized pooling with fleets, waits and capacities. Real systems realize less.
- For a campus, the relevant λ is requests per departure window per destination area. Because L scales with Δ³, a generous detour tolerance (for example 5 vs 2 min) matters more than modest demand growth.
- At low density, few combinatorial alternatives exist, so greedy approaches the optimum. The optimizer's measurable advantage is likely largest at peak departure waves. This is consistent with Prague: peak fleet gain of 12% vs about −2% off-peak.

### Gaps
- No source gave a hard minimum density (trips/h/km²) below which pooling "fails". Tachet's Table 2 is the best quantitative proxy.
