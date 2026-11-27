# Campus Connect ride pooling: design (draft)

Status: **in progress.** Sections 2 and later are still being agreed. Research behind each decision: [reports/Campus ride pooling research.md](../../../reports/Campus%20ride%20pooling%20research.md).

## Product in one paragraph

Campus Connect is a proposed feature inside Jeeny for university students from middle-income households who don't have a car and rely on buses or taxis after class. A student requests a shared ride. The app matches them with other students leaving the same campus around the same time and heading in the same direction. Before confirming, each student sees the meeting point, pickup time and their share of the fare, based on how far they'll ride. At the meeting point, the driver checks each passenger's unique ride code. The group travels to one destination or to nearby stops along the same route. Women students can choose a women-only group. Scheduled departures on popular routes are a later idea.

## Decisions so far

| # | Decision | Choice | Why |
|---|---|---|---|
| D1 | Work split | Mohammad builds the algorithm in Python. A teammate builds the UI and everything else on Replit. | Parallel work |
| D2 | Interface | JSON API under `/api/v1/rides/` | UI can be built against sample JSON before the matcher is done |
| D3 | When matching runs | **Real time.** Each request is inserted into an open group immediately. A CP-SAT regroup pass runs before groups lock. | Instant answer, near-optimal at lock |
| D4 | Fare split | **Proportional to solo distance**: `share_i = car_fare × solo_km_i / Σ solo_km` | Simple to explain. A rider who gets out earlier pays less. |
| D5 | Max group size | **4 riders** | Higher savings. At most 24 drop-off orders to check. |
| D6 | Legal model | One Jeeny booking at the approved app fare, split among riders. `Σ shares == car_fare`. No per-seat price below the approved fare. | No source found banning this. Per-seat pricing would likely need LTRC approval. |
| D7 | Savings guarantee | A rider joins a group only if `share ≤ 0.8 × solo_fare` | "You always pay less than riding alone" |
| D8 | Women-only | A hard filter: women-only requests match only women-only groups | Industry practice (Uber, DiDi, Careem) |

## Tariff used by the simulator (LTRC, in effect since 11 May 2026)

| | Start (JOD) | Per km (JOD) | Per waiting minute (JOD) |
|---|---|---|---|
| App ride, day | 0.468 | 0.336 | 0.0576 |
| App ride, night | 0.480 | 0.396 | 0.0679 |

The night window is a setting. Check: a 12 km daytime trip costs at least JOD 4.50.

## Section 1: architecture and API (proposed, awaiting approval)

### The algorithm package (no web code)

| File | One job |
|---|---|
| `pooling/geo.py` | Campus and stop coordinates, road-distance estimate (straight line × 1.35), travel minutes |
| `pooling/pricing.py` | Tariff, car fare, proportional split, savings check |
| `pooling/matcher.py` | Real-time insertion into open groups, detour check, women-only filter, max 4 riders |
| `pooling/regroup.py` | CP-SAT regroup of open groups at lock time (same lexicographic pattern as `allocation.py`) |
| `pooling/codes.py` | Unique ride code for each rider when the group locks |

### The API (Flask routes in `app.py`, state in SQLite)

| Endpoint | Returns |
|---|---|
| `POST /api/v1/rides/requests` | A provisional quote: meeting point, pickup time, share, solo fare, % saved, group size |
| `POST /api/v1/rides/requests/{id}/confirm` and `/decline` | Updated status. Declining frees the seat. |
| `GET /api/v1/rides/groups/{id}` | Riders (first names only), drop-off order, shares, status |
| `POST /api/v1/rides/lock` | Demo button: regroup and lock the due groups, then issue ride codes |
| `GET /api/v1/rides/stats` | Pooled vs. everyone solo: cars, total JOD, average saving |
| `POST /api/v1/rides/demo/seed` | Loads the Sara scenario |

## Still to decide

- The detour limit and the departure-time window
- Request and response JSON field names and the error format
- When groups lock (for example 15 minutes before departure)
- The demo seed scenario and the numbers it must reproduce
- Testing plan
