# Campus Connect Ride Pooling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the real-time ride-pooling matcher, the fare split, the lock-time CP-SAT regroup and the `/api/v1/rides/` JSON API that the Replit UI consumes.

**Architecture:** A pure-Python `pooling/` package (no Flask imports) holds geography, pricing, group evaluation, live insertion, regroup and ride codes. A Flask blueprint `rides_api.py`, registered in `app.py`, persists requests and groups in the existing SQLite file and translates between JSON and the package's dataclasses. The existing credit demo is untouched.

**Tech Stack:** Python 3.11, Flask 3.1, OR-Tools CP-SAT 9.12+, SQLite, pytest.

**Spec:** `docs/superpowers/specs/2026-11-27-ride-pooling-design.md`

## Global Constraints

- Money is integer **fils** everywhere (1 JOD = 1000 fils). There are no floats in the money fields of the JSON.
- App tariff, day: start 468 fils, 336 fils/km. Night: start 480, 396 fils/km. Night window `22:00–06:00` is a **setting** (the spec leaves it unsourced).
- Car fare = start + per_km × route_km, rounded to the nearest fil. **The shares in a group always add up to that group's car fare** (D6).
- Fare split is proportional to solo km (D4) with largest-remainder rounding.
- Savings: every rider in a group of 2 or more has `share ≤ 0.8 × solo_fare` (D7).
- Max 4 riders per group (D5).
- Detour per rider: in-car km ≤ min(1.5 × solo km, solo km + 4 km).
- Windows: the group window is the intersection of the riders' `[leave_after, leave_before]` and must be ≥ 5 min. Pickup time = window start.
- Women-only: a group is either all women-only requests or has none.
- Stops within 400 m count as one stop (leg distance 0).
- Road km = haversine km × 1.35. Travel time = km ÷ 25 km/h.
- Lock lead time is 15 min. The CP-SAT time limit is 5 s.
- Times are ISO 8601 with `+03:00` (Asia/Amman). Riders see other riders' **first names only**.
- Error body: `{"error": {"code", "message"}}`, with codes `invalid_request` 400, `not_found` 404, `duplicate_request` 409, `group_locked` 409.
- Every commit goes straight to `main` and is pushed (`git push origin main`). Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **A share goes up after confirming.** The spec promises a confirmed share only goes down. The insertion in Task 4 and the regroup in Task 5 must reject any grouping that raises a confirmed rider's quoted share. Pinned by `test_insert_never_raises_confirmed_share` and `test_regroup_respects_confirmed_quotes`.
2. **A decline breaks the remaining group.** Removing a rider can make the rest fail the savings rule (for example 3 riders → 2). The remaining riders must be re-evaluated, and if they're infeasible, re-inserted one at a time. Pinned by `test_decline_reflows_infeasible_group` (Task 7).
3. **The Replit UI is on another origin, or posts JSON.** The existing `check_form` CSRF hook aborts every POST without a form token, which would 400 every API call. `/api/` must be exempt, and the responses need CORS headers. Pinned by `test_api_post_not_blocked_by_csrf` and `test_cors_header_present` (Task 7).
4. **Rounding leaks fils.** Proportional shares like 1616.67 must still add up exactly to the car fare. Pinned by `test_split_sums_exactly` with awkward weights (Task 2).
5. **Lock is pressed twice, or with nothing open.** The second press must return the same groups and codes without new codes or errors. Pinned by `test_lock_is_idempotent` (Task 7).

---

## File Structure

| File | Responsibility |
|---|---|
| `pooling/__init__.py` | Empty package marker |
| `pooling/config.py` | Every tunable constant listed in Global Constraints |
| `pooling/places.py` | Campus, meeting-point and stop data (placeholder coordinates from the research notes) |
| `pooling/geo.py` | `road_km`, `minutes_for` |
| `pooling/pricing.py` | `car_fare`, `split_fare` |
| `pooling/model.py` | `Rider`, `GroupPlan` dataclasses and `evaluate(riders)`, the single feasibility and pricing function |
| `pooling/matcher.py` | `insert(open_groups, rider)` for live insertion |
| `pooling/regroup.py` | `regroup(groups)` for the CP-SAT set partition at lock |
| `pooling/codes.py` | `new_code(existing)` |
| `pooling/seed.py` | The 10-rider demo scenario |
| `rides_api.py` | Flask blueprint: SQLite tables, routes, errors, CORS |
| `app.py` | Modify: register the blueprint and exempt `/api/` from `check_form` |
| `requirements.txt` | Add `pytest>=8,<9` |
| `tests/test_*.py` | One test file per module |
| `README.md` | Add the "Ride pooling API" section for the UI teammate |

---

### Task 1: Config, places and geography

**Files:**
- Create: `pooling/__init__.py`, `pooling/config.py`, `pooling/places.py`, `pooling/geo.py`
- Modify: `requirements.txt` (add `pytest>=8,<9`)
- Test: `tests/test_geo.py`

**Interfaces:**
- Produces:
  - `config`: `START_DAY=468, PER_KM_DAY=336, START_NIGHT=480, PER_KM_NIGHT=396, NIGHT_START=time(22), NIGHT_END=time(6), MAX_RIDERS=4, DETOUR_RATIO=1.5, DETOUR_EXTRA_KM=4.0, MIN_SAVING=0.2, MIN_WINDOW_MIN=5, MERGE_KM=0.4, ROAD_FACTOR=1.35, SPEED_KMH=25, LOCK_LEAD_MIN=15, SOLVER_SECONDS=5.0, TZ=ZoneInfo("Asia/Amman")`
  - `places.CAMPUSES: dict[str, Campus]` and `places.STOPS: dict[str, Stop]`, where `Stop(id, name, lat, lon)` and `Campus(id, name, meeting_points: dict[str, Stop])` are frozen dataclasses. Include campus `ahu` with meeting point `ahu-main-gate`, and the stops Sweileh, Al Jubeiha, Khalda, Abdoun, Tabarbour, Marka, Zarqa from the research table. Add 3–5 extra stops along those corridors so the seed (Task 8) has neighbours. Comment that every coordinate is a placeholder.
  - `geo.road_km(a: Stop, b: Stop) -> float` and `geo.minutes_for(km: float) -> float`

- [ ] **Step 1: Write the failing tests**

```python
def test_road_km_is_haversine_times_factor():
    a, b = Stop("a","a",32.0,35.0), Stop("b","b",32.0,35.1)
    assert road_km(a, b) == pytest.approx(9.43 * 1.35, rel=0.01)

def test_stops_within_merge_radius_are_zero():
    a, b = Stop("a","a",32.0,35.0), Stop("b","b",32.0,35.002)  # about 0.19 km
    assert road_km(a, b) == 0.0

def test_minutes_for_uses_25_kmh():
    assert minutes_for(12.5) == pytest.approx(30.0)

def test_seed_stops_exist():
    assert {"sweileh", "zarqa"} <= STOPS.keys() and "ahu-main-gate" in CAMPUSES["ahu"].meeting_points
```

- [ ] **Step 2:** Run `python -m pytest tests/test_geo.py -v`. Expected: FAIL with an import error.
- [ ] **Step 3:** Implement the three modules. `road_km` returns 0.0 when the straight-line km × factor would be < `MERGE_KM`. The 400 m rule is applied to road km.
- [ ] **Step 4:** Run `python -m pytest tests/test_geo.py -v`. Expected: 4 passed.
- [ ] **Step 5:** Commit `Add pooling config, places and geography` and push to main.

---

### Task 2: Pricing

**Files:**
- Create: `pooling/pricing.py`
- Test: `tests/test_pricing.py`

**Interfaces:**
- Consumes: `config` tariff constants
- Produces:
  - `car_fare(km: float, at: datetime) -> int` (fils)
  - `is_night(at: datetime) -> bool`
  - `split_fare(total: int, weights: Sequence[float]) -> list[int]`: proportional, largest remainder. Ties go to the earlier index. All-zero weights split equally.

- [ ] **Step 1: Write the failing tests**

```python
DAY = datetime(2026, 11, 28, 16, 0, tzinfo=TZ)
NIGHT = datetime(2026, 11, 28, 23, 0, tzinfo=TZ)

def test_12km_day_is_4500():           assert car_fare(12, DAY) == 4500
def test_night_tariff():               assert car_fare(12, NIGHT) == 480 + round(396 * 12)
def test_night_window_wraps_midnight(): assert is_night(datetime(2026,11,28,5,59,tzinfo=TZ)) and not is_night(DAY)
def test_split_sums_exactly():
    shares = split_fare(4850, [1, 1, 1])
    assert sum(shares) == 4850 and sorted(shares) == [1616, 1617, 1617]
def test_split_spec_example():          assert split_fare(5710, [8.96, 12.0, 14.85]) == [1429, 1913, 2368]
def test_earlier_dropoff_never_pays_more():
    s = split_fare(5000, [5, 9, 9.0001]); assert s[0] < s[1] <= s[2]
```

- [ ] **Step 2:** Run `python -m pytest tests/test_pricing.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement `car_fare` and `is_night`. **`split_fare` is the human contribution:** leave a `TODO(human)` body for Mohammad, as a Learn by Doing request. Rounding is a design choice with several valid answers.
- [ ] **Step 4:** Run `python -m pytest tests/test_pricing.py -v`. Expected: 6 passed.
- [ ] **Step 5:** Commit `Add tariff and proportional fare split` and push to main.

---

### Task 3: Group evaluation (one feasibility function)

**Files:**
- Create: `pooling/model.py`
- Test: `tests/test_model.py`

**Interfaces:**
- Consumes: `geo.road_km`, `geo.minutes_for`, `pricing.car_fare`, `pricing.split_fare`, `places`
- Produces:

```python
@dataclass(frozen=True)
class Rider:
    request_id: str; first_name: str; women_only: bool
    campus_id: str; meeting_point_id: str; stop_id: str
    leave_after: datetime; leave_before: datetime
    quoted_share: int | None = None   # set once confirmed; a cap for later regrouping

@dataclass(frozen=True)
class GroupPlan:
    riders: tuple[Rider, ...]          # in drop-off order
    route_km: float
    car_fare: int
    shares: dict[str, int]             # request_id -> fils
    solo_km: dict[str, float]
    solo_fare: dict[str, int]
    in_car_km: dict[str, float]
    pickup_time: datetime
    arrival: dict[str, datetime]

def evaluate(riders: Sequence[Rider]) -> GroupPlan | None
```

`evaluate` returns the best (shortest-route) feasible plan or `None`. It checks: 1 ≤ size ≤ 4; same campus and meeting point; all-or-none women-only; window intersection ≥ 5 min; then over every permutation of drop-off order: the detour rule for every rider, the savings rule for every rider when the group has 2 or more, and `share ≤ quoted_share` for every rider with a quote. Fares are priced at `pickup_time`.

- [ ] **Step 1: Write the failing tests.** Build riders with a small helper `rider(id, stop, after="16:00", before="16:30", women_only=False, quote=None)`.

```python
def test_single_rider_pays_solo():          p = evaluate([rider("a","sweileh")]); assert p.shares["a"] == p.solo_fare["a"]
def test_shares_sum_to_car_fare():          p = evaluate([rider("a","sweileh"), rider("b","jubeiha")]); assert sum(p.shares.values()) == p.car_fare
def test_fifth_rider_refused():             assert evaluate([rider(str(i),"sweileh") for i in range(5)]) is None
def test_women_only_must_not_mix():         assert evaluate([rider("a","sweileh",women_only=True), rider("b","sweileh")]) is None
def test_disjoint_windows_refused():        assert evaluate([rider("a","sweileh"), rider("b","sweileh",after="16:40",before="17:00")]) is None
def test_window_overlap_under_5_min_refused(): assert evaluate([rider("a","sweileh",before="16:10"), rider("b","sweileh",after="16:06")]) is None
def test_far_rider_breaks_detour():         assert evaluate([rider("a","sweileh"), rider("b","zarqa")]) is None
def test_picks_shortest_drop_order():       p = evaluate([rider("far","abdoun"), rider("near","sweileh")]); assert [r.request_id for r in p.riders] == ["near","far"]
def test_pickup_is_window_start():          p = evaluate([rider("a","sweileh",after="16:00"), rider("b","sweileh",after="16:10")]); assert p.pickup_time.strftime("%H:%M") == "16:10"
def test_quote_cap_blocks_higher_share():   assert evaluate([rider("a","sweileh",quote=1), rider("b","sweileh")]) is None
```

- [ ] **Step 2:** Run `python -m pytest tests/test_model.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement `Rider`, `GroupPlan` and `evaluate` in `pooling/model.py`. Use `itertools.permutations` for drop-off order.
- [ ] **Step 4:** Run `python -m pytest tests/test_model.py -v`. Expected: 10 passed. If `test_far_rider_breaks_detour` or `test_picks_shortest_drop_order` fails only because of placeholder coordinates, adjust the **stop choice in the test**, not the rule.
- [ ] **Step 5:** Commit `Add group evaluation with detour, savings and window rules` and push to main.

---

### Task 4: Live insertion

**Files:**
- Create: `pooling/matcher.py`
- Test: `tests/test_matcher.py`

**Interfaces:**
- Consumes: `model.evaluate`, `model.Rider`, `model.GroupPlan`
- Produces:

```python
@dataclass(frozen=True)
class OpenGroup:
    group_id: str
    plan: GroupPlan

@dataclass(frozen=True)
class Insertion:
    group_id: str | None   # None = open a new group
    plan: GroupPlan

def insert(open_groups: Sequence[OpenGroup], rider: Rider) -> Insertion
```

Rule: for each open group, `evaluate(group.plan.riders + (rider,))`. Among the feasible groups, choose the smallest `plan.route_km - group.plan.route_km`. Break ties by the larger existing group, then the earlier `group_id`. If none is feasible, return `Insertion(None, evaluate([rider]))`. The quote cap lives in `evaluate`, so confirmed shares can never rise here.

- [ ] **Step 1: Write the failing tests**

```python
def test_joins_compatible_group()
def test_opens_new_group_when_none_fit()            # Zarqa rider -> group_id None, size 1
def test_prefers_least_added_km()                   # two open groups; rider joins the nearer corridor
def test_tie_prefers_fuller_group()
def test_rejects_when_existing_rider_would_lose_savings()
def test_insert_never_raises_confirmed_share()      # confirmed rider with quote; insertion that would raise it goes elsewhere
def test_women_only_rider_skips_mixed_group()
```

Each test asserts `result.group_id` and, where it joins, `len(result.plan.riders)`.

- [ ] **Step 2:** Run `python -m pytest tests/test_matcher.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement `insert` in `pooling/matcher.py`.
- [ ] **Step 4:** Run `python -m pytest tests/test_matcher.py -v`. Expected: 7 passed.
- [ ] **Step 5:** Commit `Add real-time insertion matcher` and push to main.

---

### Task 5: Lock-time regroup (CP-SAT)

**Files:**
- Create: `pooling/regroup.py`
- Test: `tests/test_regroup.py`

**Interfaces:**
- Consumes: `model.evaluate`, `model.GroupPlan`, `config.MAX_RIDERS`, `config.SOLVER_SECONDS`
- Produces: `regroup(current: Sequence[GroupPlan]) -> list[GroupPlan]`

Algorithm, which the signature doesn't determine:

```
riders = all riders in current
feasible = {}                              # frozenset(ids) -> GroupPlan
for k in 1..MAX_RIDERS:
    for combo of size k:
        if k > 1 and any(combo - {x} not in feasible for x in combo): continue   # subset pruning
        plan = evaluate(combo); if plan: feasible[combo] = plan
model: bool x[g] per feasible group; for each rider: sum(x[g] for g containing rider) == 1
objective 1: minimize sum(round(plan.route_km * 1000) * x[g]); fix it; objective 2: minimize sum(x[g])
(same solve / fix / re-solve pattern as allocation.optimize, time limit SOLVER_SECONDS)
if the solver result's total km > sum(p.route_km for p in current): return list(current)   # never worse than greedy
```

Singletons are always feasible, so a solution always exists.

- [ ] **Step 1: Write the failing tests**

```python
def test_every_rider_exactly_once()
def test_never_worse_than_input()               # total route_km(result) <= total route_km(current)
def test_fixes_greedy_order_trap()              # hand-built bad pairing -> strictly fewer km
def test_regroup_respects_confirmed_quotes()    # quoted rider never placed where share > quote
def test_empty_input_returns_empty()
```

- [ ] **Step 2:** Run `python -m pytest tests/test_regroup.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement `regroup` in `pooling/regroup.py`.
- [ ] **Step 4:** Run `python -m pytest tests/test_regroup.py -v`. Expected: 5 passed.
- [ ] **Step 5:** Commit `Add CP-SAT regroup at lock` and push to main.

---

### Task 6: Ride codes

**Files:**
- Create: `pooling/codes.py`
- Test: `tests/test_codes.py`

**Interfaces:**
- Produces: `new_code(existing: set[str], rng: random.Random | None = None) -> str`, in the format `CC-` followed by 4 digits, not in `existing`. It uses `secrets` when `rng` is None.

- [ ] **Step 1:** Write `test_format` (regex `^CC-\d{4}$`) and `test_avoids_existing` (seeded rng, with the first draw put in `existing`).
- [ ] **Step 2:** Run `python -m pytest tests/test_codes.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement `new_code`.
- [ ] **Step 4:** Run `python -m pytest tests/test_codes.py -v`. Expected: 2 passed.
- [ ] **Step 5:** Commit `Add ride codes` and push to main.

---

### Task 7: JSON API blueprint

**Files:**
- Create: `rides_api.py`
- Modify: `app.py`, to register `rides_api.bp` and make `check_form` return early when `request.path.startswith("/api/")`
- Test: `tests/test_api.py`, with a fixture app using a `tmp_path` database

**Interfaces:**
- Consumes: all of `pooling/*` and `app.database()`
- Produces: `bp = Blueprint("rides", __name__, url_prefix="/api/v1/rides")`, the routes in spec section 3, and `serialize_group(...)` for the seed in Task 8.

**SQLite tables** (created in `rides_api.ensure_tables(db)`, called on first request):

- `pool_groups(id TEXT PK, campus_id, meeting_point_id, women_only INT, status TEXT CHECK(status IN ('open','locked')), created_at)`
- `pool_requests(id TEXT PK, student_id, first_name, gender, women_only INT, campus_id, meeting_point_id, stop_id, leave_after, leave_before, status TEXT CHECK(status IN ('provisional','waiting_for_riders','confirmed','declined','unmatched')), group_id REFERENCES pool_groups(id), quoted_share INT, share INT, ride_code TEXT UNIQUE, created_at)`

Plans are re-derived with `evaluate` whenever needed, never stored as JSON. A stored share is a cache that is refreshed after each change.

**Behaviour that is not obvious from the spec:**

- **Create:** validate fields. `women_only: true` with `gender != "female"` is `invalid_request`. A `duplicate_request` is the same `student.id` with a non-declined request whose window overlaps. Build open groups for the campus, call `insert`, and write the group and every member's refreshed `share`. Status is `waiting_for_riders` for a group of 1, otherwise `provisional`.
- **Confirm:** set `quoted_share = share` and status `confirmed`. If the group is locked, return `group_locked`.
- **Decline:** set status `declined` and remove the rider from the group. Re-evaluate the rest. If that returns `None`, dissolve the group and re-`insert` each remaining rider in `created_at` order.
- **Lock** `{"campus_id"}`: run `regroup` on the open groups' plans, rewrite membership, set `locked`, and give each rider a `new_code`. Singletons become `unmatched` with no code. The response lists **all** locked groups for the campus, so a second call returns the same groups and codes.
- **Stats:** count non-declined requests. `matched` = riders in locked or open groups of 2 or more. `pooled.cars` = number of non-empty groups. `solo` = one car per request at its solo fare. `avg_saved_pct` = the mean over matched riders of `round(100 × (1 − share / solo_fare))`.
- **Errors:** handled by one helper `api_error(status, code, message)`. 404 and 405 inside the blueprint also return the JSON shape.
- **CORS:** an `after_request` on the blueprint sets `Access-Control-Allow-Origin: *`, plus `Allow-Headers: Content-Type` and `Allow-Methods: GET, POST, OPTIONS`. `OPTIONS` returns 204.

- [ ] **Step 1: Write the failing tests**

```python
def test_places_lists_campus_and_stops()
def test_create_returns_quote_shape()            # keys exactly as spec section 3 create response
def test_second_rider_joins_and_shares_drop()
def test_women_only_male_is_invalid_request()
def test_duplicate_request_409()
def test_confirm_then_lock_issues_codes()
def test_confirm_after_lock_409_group_locked()
def test_decline_reflows_infeasible_group()
def test_lock_is_idempotent()                    # same group ids and ride codes on second call
def test_group_view_first_names_only()           # no student_id or gender in the response
def test_stats_shape()
def test_unknown_stop_404()
def test_api_post_not_blocked_by_csrf()          # JSON POST without a form token -> not 400
def test_cors_header_present()
def test_old_credit_demo_still_renders()         # GET / -> 200
```

- [ ] **Step 2:** Run `python -m pytest tests/test_api.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement `rides_api.py` and the two-line change in `app.py`.
- [ ] **Step 4:** Run `python -m pytest -v`. Expected: all tests pass, including Tasks 1–6.
- [ ] **Step 5:** Commit `Add /api/v1/rides JSON API` and push to main.

---

### Task 8: Demo seed and the judge numbers

**Files:**
- Create: `pooling/seed.py`
- Modify: `rides_api.py` (`POST /demo/seed`), `docs/superpowers/specs/2026-11-27-ride-pooling-design.md` (record the numbers)
- Test: `tests/test_seed.py`

**Interfaces:**
- Produces: `SEED: list[dict]`, which is request bodies in arrival order (the same shape as `POST /requests`), and `seed(db)`, which clears the pool tables and posts each body through the same create logic.

The scenario from spec section 4: 10 riders, campus `ahu`, all `16:00–16:30` on the next day. There are 3 women-only women including Sara along one corridor, 4 mixed riders along a second, 2 along a third, and Omar to Zarqa. **Choose the arrival order so that greedy insertion builds a worse grouping than the regroup.** A known pattern is that an early rider to an in-between stop grabs a group that two later riders would fill better. Tune the stops and order until `test_regroup_strictly_improves` passes.

- [ ] **Step 1: Write the failing tests**

```python
def test_seed_then_lock_gives_4_cars_9_matched(client)   # stats: requests 10, matched 9, pooled.cars 4, solo.cars 10
def test_every_matched_rider_saves_20pct(client)
def test_sara_in_womens_group_of_3(client)
def test_regroup_strictly_improves(client)                # car-km after lock < car-km before lock
def test_all_shares_sum_to_car_fare(client)
def test_omar_unmatched(client)
```

- [ ] **Step 2:** Run `python -m pytest tests/test_seed.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement `seed.py` and the route, then tune the stops and order until the tests pass.
- [ ] **Step 4:** Run `python -m pytest -v`. Expected: all pass. Then run the seed once and record the real figures (pooled vs. solo JOD, Sara's share, average saved %) in the spec's section 4, replacing "recorded once the matcher runs".
- [ ] **Step 5:** Commit `Add demo seed and record judge numbers` and push to main.

---

### Task 9: Hand-off docs for the UI teammate

**Files:**
- Modify: `README.md`

- [ ] **Step 1:** Add a "Ride pooling API" section: the base URL on Replit, a link to spec section 3 for the shapes, a `curl` example for `seed → lock → stats`, the note "money is in fils; format as JOD x.xx", and the note "the share shown can only go down after confirming".
- [ ] **Step 2:** Run `python app.py`, then `curl -s -X POST localhost:5000/api/v1/rides/demo/seed` and `curl -s -X POST -H "Content-Type: application/json" -d '{"campus_id":"ahu"}' localhost:5000/api/v1/rides/lock`. Expected: JSON matching spec section 3, with no HTML error pages.
- [ ] **Step 3:** Commit `Document ride pooling API for the UI` and push to main.
