# Campus Connect ride pooling: design (draft)

Status: **approved 2026-11-27.** Research behind each decision: [reports/Campus ride pooling research.md](../../../reports/Campus%20ride%20pooling%20research.md).

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
| `pooling/config.py` | Every tunable limit: tariff, night window, detour, savings, window overlap, stop merge radius, lock lead time, speed |

### The API (Flask routes in `app.py`, state in SQLite)

| Endpoint | Returns |
|---|---|
| `POST /api/v1/rides/requests` | A provisional quote: meeting point, pickup time, share, solo fare, % saved, group size |
| `POST /api/v1/rides/requests/{id}/confirm` and `/decline` | Updated status. Declining frees the seat. |
| `GET /api/v1/rides/groups/{id}` | Riders (first names only), drop-off order, shares, status |
| `POST /api/v1/rides/lock` | Demo button: regroup and lock the due groups, then issue ride codes |
| `GET /api/v1/rides/stats` | Pooled vs. everyone solo: cars, total JOD, average saving |
| `POST /api/v1/rides/demo/seed` | Loads the Sara scenario |

## Section 2: matching rules (approved)

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

## Section 3: JSON contract (approved)

General rules:

- Times are ISO 8601 with the Amman offset (`+03:00`).
- Money is **integer fils** (1 JOD = 1000 fils), so the UI never handles floating-point rounding. The UI formats `1620` as `JOD 1.62`.
- IDs are opaque strings.
- Riders see other riders' first names only.

### `GET /api/v1/rides/places`

This endpoint was added so the UI can offer dropdowns rather than free-text addresses.

```json
{
  "campuses": [
    {"id": "ahu", "name": "Al-Ahliyya Amman University",
     "meeting_points": [{"id": "ahu-main-gate", "name": "Main gate", "lat": 32.0430, "lon": 35.7220}]}
  ],
  "stops": [
    {"id": "sweileh", "name": "Sweileh", "lat": 32.0230, "lon": 35.8400}
  ]
}
```

Coordinates are placeholders, to be checked on a map before the demo.

### `POST /api/v1/rides/requests` creates a request and returns a provisional quote

Request:

```json
{
  "student": {"id": "stu-sara", "first_name": "Sara", "gender": "female"},
  "campus_id": "ahu",
  "meeting_point_id": "ahu-main-gate",
  "stop_id": "sweileh",
  "leave_after": "2026-11-28T16:00:00+03:00",
  "leave_before": "2026-11-28T16:30:00+03:00",
  "women_only": true
}
```

Response `201`:

```json
{
  "request_id": "req-12",
  "status": "provisional",
  "group": {"id": "grp-3", "size": 3, "max_size": 4, "women_only": true, "status": "open"},
  "meeting_point": {"id": "ahu-main-gate", "name": "Main gate"},
  "pickup_time": "2026-11-28T16:15:00+03:00",
  "drop_position": 2,
  "estimated_arrival": "2026-11-28T16:42:00+03:00",
  "fare": {"your_share_fils": 1913, "solo_fare_fils": 4500, "saved_pct": 57, "car_fare_fils": 5710},
  "ride_code": null
}
```

A group of 1 returns `"status": "waiting_for_riders"` with `your_share_fils == solo_fare_fils`.

### `POST /api/v1/rides/requests/{id}/confirm` and `/decline`

Both return the same shape as the create response, with `status` set to `confirmed` or `declined`. Confirming does not freeze the share: it can only go **down** as riders join, and the UI should say so.

### `GET /api/v1/rides/groups/{id}`

```json
{
  "id": "grp-3", "status": "open", "women_only": true,
  "meeting_point": {"id": "ahu-main-gate", "name": "Main gate"},
  "pickup_time": "2026-11-28T16:15:00+03:00",
  "car_fare_fils": 5710, "route_km": 15.6,
  "riders": [
    {"first_name": "Lina", "stop": "Tabarbour",  "drop_position": 1, "share_fils": 1429, "status": "confirmed"},
    {"first_name": "Sara", "stop": "Sweileh",    "drop_position": 2, "share_fils": 1913, "status": "provisional"},
    {"first_name": "Noor", "stop": "Al Jubeiha", "drop_position": 3, "share_fils": 2368, "status": "confirmed"}
  ]
}
```

The shares always add up to `car_fare_fils`. In this example the solo distances are 8.96, 12.0 and 14.85 km (Sara's 12 km gives her JOD 4.50 solo fare). The route is 15.6 km, so the car fare is 468 + 336 × 15.6 = 5710 fils, and each rider saves about 57%.

### `POST /api/v1/rides/lock`

Body: `{"campus_id": "ahu"}`. With no `window`, it locks all of that campus's open groups (the demo button).

```json
{
  "locked_groups": [
    {"id": "grp-3", "riders": [{"first_name": "Sara", "ride_code": "CC-4821", "share_fils": 1913}]}
  ],
  "unmatched": [{"request_id": "req-15", "first_name": "Omar", "solo_fare_fils": 3900}]
}
```

### `GET /api/v1/rides/stats`

```json
{
  "requests": 9, "matched": 8, "unmatched": 1,
  "pooled": {"cars": 3, "total_fils": 14600},
  "solo":   {"cars": 9, "total_fils": 32400},
  "avg_saved_pct": 55
}
```

### `POST /api/v1/rides/demo/seed`

Clears the demo data and loads the Sara scenario (section 4). It returns the stats object.

### Errors

Every error uses one shape, so the UI needs one error handler:

```json
{"error": {"code": "group_locked", "message": "This group is already locked."}}
```

| HTTP | `code` | When |
|---|---|---|
| 400 | `invalid_request` | Missing or invalid field, or `leave_before` ≤ `leave_after` |
| 404 | `not_found` | Unknown request, group, campus or stop |
| 409 | `duplicate_request` | Student already has an active request in an overlapping window |
| 409 | `group_locked` | Confirm or decline after lock |

## Section 4: demo scenario and testing (approved)

### Demo seed: "4 p.m. at the main gate"

`POST /api/v1/rides/demo/seed` loads 10 students at one campus, all wanting to leave between 16:00 and 16:30. The requests arrive in a fixed order, through the same insertion code a live request uses.

| Riders | Who | Expected outcome |
|---|---|---|
| 3 | Sara and two other women, women-only, stops along one corridor | One women-only group of 3, which is Sara's story |
| 4 | Mixed riders along a second corridor | One full group of 4 |
| 2 | Riders along a third corridor | One group of 2 |
| 1 | Omar, far off every corridor (for example Zarqa) | Unmatched: "no match, solo fare X" |

**Order trap:** the arrival order is chosen so that greedy insertion builds at least one worse group. The lock regroup must then fix it. This is the judge moment: "live answer, then the optimizer improves it."

**Expected checks (exact JOD figures are recorded once the matcher runs):**

- 4 cars instead of 10. Of the 10 requests, 9 are matched.
- Every matched rider saves at least 20%. Sara pays well under her solo fare.
- Car-km after regroup < car-km after greedy insertion alone.
- Every group's shares add up exactly to its car fare.

Stops and coordinates are placeholders until they are checked on a map. The numbers come from the code, never from a slide.

### Tests (pytest, no network)

| Area | What the tests prove |
|---|---|
| `pricing` | 12 km by day = 4500 fils. The night tariff applies inside the night window. Shares add up to the car fare after largest-remainder rounding. A rider who gets out earlier never pays more. |
| `matcher` | Women-only works in both directions. Windows that don't overlap never match. A 5th rider is refused. A detour or savings violation for an **existing** rider blocks the insertion. Stops within 400 m merge. |
| `regroup` | Each rider ends up in exactly one group. The result is never worse than greedy. The seed shows a strict improvement. A time limit always returns an answer. |
| API (Flask test client) | Response shapes match section 3. All four error codes. Locking twice returns the same codes and groups. A duplicate request is refused. |
| Seed | `/demo/seed` then `/lock` reproduces the expected checks above. |

### Existing app

The current credit-allocation demo (`allocation.py`, the existing routes and templates) stays as it is. The new `/api/v1/rides/` routes and the `pooling/` package sit beside it. Retiring the old demo is a separate decision for later.

