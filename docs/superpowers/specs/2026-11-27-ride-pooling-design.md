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

## Section 1: architecture and API (approved)

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

## Section 2: matching rules (proposed, awaiting approval)

A new request can join an open group only if **all** of these hold. Every limit is a setting in `pooling/config.py`.

| Rule | Default | Why |
|---|---|---|
| Same campus and meeting point | Exact match | One pickup |
| Departure windows overlap | Each request gives "leave between". The group's window is the intersection and must be ≥ 5 min. | Avoids fixed-slot edges (a 9:14 request and a 9:16 request still match) |
| Seats | ≤ 4 riders | D5 |
| Women-only | A women-only request joins only a women-only group, and vice versa | D8 |
| Detour per rider | In-car km ≤ min(1.5 × solo km, solo km + 4 km), checked for **every** rider after insertion | Nobody's trip gets much longer |
| Savings per rider | Every rider's share ≤ 0.8 × solo fare, checked for **every** rider after insertion | D7 |
| Group is still open | Status `open` and not locked | Locked groups are final |

**Insertion step (`matcher.insert`)**

1. Filter open groups by campus, window, seats and women-only.
2. For each candidate group, try every drop-off order with the new rider (at most 4! = 24) and keep the shortest route.
3. Reject the group if the detour or savings rule fails for anyone.
4. Among the groups that pass, choose the smallest **added km**. On a tie, choose the fuller group.
5. If none passes, open a new group of 1. Its quote shows the solo fare, marked "waiting for riders".

**Nearby stops:** destinations within 400 m of each other count as one stop.

**Pickup time:** the start of the group's shared window. It can only move later as riders join, and never past anyone's window end.

**Lock (`regroup.run`)**, run at departure − 15 min, when a group is full, or on the demo button:

1. Take all open groups for that campus and window.
2. List every feasible group of 1–4 riders under the rules above.
3. CP-SAT puts each rider in exactly one group, minimizing total car-km and then the number of cars.
4. Commit the result, set status `locked` and issue ride codes. A rider left alone is told "no match, solo fare X" and can book solo.

**Travel time:** km ÷ 25 km/h city average, as a setting. It is used only for the pickup and arrival estimates.

## Still to decide

- Request and response JSON field names and the error format
- The demo seed scenario and the numbers it must reproduce
- Testing plan
