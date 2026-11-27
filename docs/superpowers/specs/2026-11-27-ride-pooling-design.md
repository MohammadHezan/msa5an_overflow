# Campus Connect ride pooling: design

## Current contract — numbered briefs

Brief 02 supersedes the original single-gate, homebound and proportional-price assumptions in the historical design below.

Requests carry direction, corridor, start/end road km, start/end side offsets, and readiness or arrival deadline. Street walking is capped at 200 m at 1.4 m/s; offsets beyond 200 m add twice the excess to car distance. Inward routes visit pickups by descending km; outward routes visit drops by ascending km, with individual times including turn-ins at 25 km/h.

Cars have at most four riders, one direction/corridor, a ten-minute readiness/deadline gap, compatible mixed/women/men preferences, and in-car km at most min(1.5 × solo km, solo km + 4). Shared riders pay no more than 75% of their individual solo fares.

Street fare is exactly 468 + round(336 × route km) fils. Divide the 468 equally, divide each distance segment among occupants, then largest-remainder round with solo caps. A confirmed quote is a ceiling: any later shortfall is explicit Jeeny cover. Captains get 100 fils per extra rider, separate from student fare.

Regroup uses one CP-SAT objective: total car fares plus 1,500 fils per solo rider. Only hereditary rules prune subsets; savings and detours are evaluated on the full group. Keep a feasible incumbent or the valid greedy partition on timeout. Friends remain together, and closed groups have no strangers.

Use two-minute confirmation holds, ten-minute opt-in waiting, transactional actions, idempotent client request IDs and versioned plan signatures. Go-now pickup eligibility uses the actual street position and driving direction, never an invented downstream pickup.

The simulated judge comparison runs alone/greedy/optimizer on 30 paired seeds at each of 8/16/24/32 students. Per-simulation solver limits must not mutate the shared live-booking configuration.

Status: **approved 2026-11-27, revised the same day to match the app as built.** The Replit app (Flask pages, phone screen, `/api/v1` JSON API) runs on the `pooling/` engine. Research behind each decision: [reports/Campus ride pooling research.md](../../../reports/Campus%20ride%20pooling%20research.md). The API itself is documented in [document.md](../../../document.md), "Proposed API contract" and "As built (B1)".

## Product in one paragraph

Campus Connect is a proposed feature inside Jeeny for university students from middle-income households who don't have a car and rely on buses or taxis after class. A student requests a shared ride. The app matches them with other students leaving the same campus around the same time and heading in the same direction. Before confirming, each student sees the meeting point, pickup time and their share of the fare, based on how far they'll ride. At the meeting point, the driver checks each passenger's unique ride code. The group travels to one destination or to nearby stops along the same route. Women students can choose a women-only group. Scheduled departures on popular routes are a later idea.

## Decisions

| # | Decision | Choice | Why |
|---|---|---|---|
| D1 | Work split | Mohammad owns the matching and pricing engine (`pooling/`). The teammate owns the app, API and UI on Replit. | Parallel work |
| D2 | Interface | **Revised.** The app's existing `/api/v1` API (`api.py`, batches, join codes, bearer tokens). `sharing.py` adapts the engine to it. The planned `/api/v1/rides/` API was not merged; it is kept on the local branch `backup/rides-api`. | The teammate's UI already ran on `/api/v1`; one API, one engine |
| D3 | When matching runs | **Revised.** **Batch.** Students book, then the operator runs matching once for the batch (CP-SAT over every feasible car). Live insertion (`pooling/matcher.py`) is built and tested but not wired into the app. | The app's flow is book, then match, then review and confirm |
| D4 | Fare split | **Proportional to solo distance**: `share_i = car_fare × solo_km_i / Σ solo_km`, largest-remainder rounding to whole fils | Simple to explain. A rider who gets out earlier pays less. |
| D5 | Max group size | **4 riders** | Higher savings. At most 24 drop-off orders to check. |
| D6 | Legal model | One Jeeny booking at the approved app fare, split among riders. `Σ shares == car_fare`. No per-seat price below the approved fare. | No source found banning this. Per-seat pricing would likely need LTRC approval. |
| D7 | Savings guarantee | A rider shares a car only if `share ≤ 0.8 × solo_fare` | "You always pay less than riding alone" |
| D8 | Women-only | **Revised.** If any rider in a car asked for women-only, every rider in it must be a woman. A woman who did not ask can still join. A car is labelled women-only when all riders are women and at least one asked. | The teammate's rule: still a hard filter, and it matches more women |

## Tariff (LTRC smart-app tariff, in effect since 11 May 2026)

| | Start (JOD) | Per km (JOD) | Per waiting minute (JOD) |
|---|---|---|---|
| App ride, day | 0.468 | 0.336 | 0.0576 |
| App ride, night | 0.480 | 0.396 | 0.0679 |

The night window (`22:00–06:00`) is an assumption and a setting. The app's class end times (08:00–21:00) always price at the day rate. Check: 12 km by day costs JOD 4.50. Waiting time is not priced.

## Section 1: architecture

```
templates/ (dashboard, phone)   api.py (/api/v1, tokens)
              \                   /
               app.py --- store.py (batches, riders, SQLite, statuses)
                              |
                          sharing.py   adapter: app rider dicts <-> engine
                              |
   pooling/  config  places  geo  pricing  model.evaluate  regroup  (matcher, codes: built, not wired)
```

| File | One job |
|---|---|
| `pooling/config.py` | Every tunable limit: tariff, night window, detour, savings, window overlap, stop merge radius, speed, solver time limit |
| `pooling/places.py` | Single source of map data: the demo campus's corridors, gates and coordinates (used by the app), plus the Al-Ahliyya placeholder stops used in engine tests |
| `pooling/geo.py` | Road distance. Corridor stops: gate to stop = stop km; same corridor = km difference; different corridors = via campus. Otherwise straight line × 1.35. Stops under 400 m apart are one stop. |
| `pooling/pricing.py` | Tariff, car fare, proportional split |
| `pooling/model.py` | `evaluate(riders)`: the one function that applies every rule and prices a car |
| `pooling/regroup.py` | CP-SAT set partition over all feasible cars |
| `pooling/matcher.py` | Live insertion into open groups (not used by the app yet) |
| `pooling/codes.py` | Ride codes `CC-1234` (not used by the app yet) |
| `sharing.py` | Keeps the app's interface (`group_riders`, `plan_car`, `solo_fare`, `sample_share`, `compatible`, `route_map`) and calls the engine |

**How the adapter maps the app's riders:** the meeting point is the corridor's gate. The window starts at class end + 15 min walk and lasts 25 min. Two windows then overlap by at least 5 min exactly when class ends are within 20 min of each other, which is the app's own rule. Pickup is the window start rounded up to the next 5 minutes.

## Section 2: matching rules

A car is valid only if **all** of these hold, checked for every rider (`model.evaluate`):

| Rule | Default |
|---|---|
| Same campus and meeting point | Exact match |
| Departure windows overlap | The shared window is ≥ 5 min |
| Seats | ≤ 4 riders |
| Women-only | D8 |
| Detour | In-car km ≤ min(1.5 × solo km, solo km + 4 km) |
| Savings | Share ≤ 0.8 × solo fare (cars of 2 or more) |
| Confirmed quote | A rider with a confirmed share is never charged more (engine rule; the app instead marks the rider `changed` and asks again) |

`evaluate` tries every drop-off order and keeps the shortest route that passes.

**Matching (`regroup`, run by the operator's "Run matching"):** list every valid car of 1–4 riders, testing a car only if all its smaller sub-cars are valid. CP-SAT puts each rider in exactly one car, minimizing total car-km and then the number of cars. A rider alone is offered a solo ride.

**After a decline:** the remaining riders are re-priced. If they no longer pass every rule, the car is still priced at the regulated fare over its route (`evaluate(strict=False)`), so shares still add up to the car fare. The app marks earlier confirmations `changed`.

**Live insertion (built, not wired):** a new request joins the valid open group that adds the fewest km (ties: fuller group). Otherwise it opens a new group. This is the path to the real-time flow in the original D3.

## Section 3: API

The app's `/api/v1` contract is documented in [document.md](../../../document.md) and implemented in `api.py`. Engine-related changes:

- `GET /api/v1/stops` → `rules` now has `baseFare` (468 fils), `perKm` (336 fils) and `minSavingPercent` (20). `extraStopFee`, `sharedRatePercent` and `minShare` were removed.
- `soloFare`, `share`, `carFare` and `sampleShare` come from the regulated tariff and the proportional split, in exact fils, no longer rounded to 50.

## Section 4: demo scenario and testing

**Sample afternoon** (`store.FIXTURE`, 10 students) still forms the same 5 cars:

| Car | Riders and share (solo fare), JOD |
|---|---|
| West · Main gate · 16:15 · women-only, car fare 5.84 | Sara 1.67 (4.50), Rama 1.95 (5.17), Huda 2.23 (5.84) |
| West · Main gate · 16:20 | Kareem 3.16 alone (the West car is women-only) |
| North · North gate · 16:35 | Lina 0.57 (1.48), Omar 1.34 (2.82), Yazan 1.91 (3.83) |
| South · Main gate · 13:25 | Leen 1.66 (2.82), Dana 2.84 (4.50) |
| East · East gate · 18:15 | Zaid 4.84 alone |

**Pitch number:** Sara pays **JOD 1.67 instead of JOD 4.50**, which is 63% off. The car pays the full regulated fare of 468 + 336 × 16 = 5,844 fils.

**Tests** (`python -m pytest`, 85 at revision):

| File | What it proves |
|---|---|
| `test_geo`, `test_pricing` | Distances, tariff (12 km by day = 4500), exact-sum split |
| `test_model` | Every rule in section 2, corridor distances, women-only (D8) |
| `test_matcher`, `test_regroup`, `test_codes` | Live insertion, CP-SAT regroup (never worse than input, fixes a greedy trap), ride codes |
| `test_sharing` | The app adapter: sample afternoon cars, Sara's share, shares add up to the car fare |
| `test_app`, `test_api`, `test_open_batch` | The teammate's pages and API on the new numbers |

## Open items

- Wire ride codes (`pooling/codes.py`) into the app's confirmed plans for the driver check.
- Decide whether to move the app to live insertion (original D3) or keep batch matching for the demo.
- Check the demo coordinates on a map. The research's Gazette and fare checks are still unverified.
