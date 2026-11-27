# Replit brief 02: street pickup, both directions, options, groups, lone riders

Paste everything below the line into Replit Agent.

---

````text
Campus Connect: build the full shared-ride flow. Read this whole message before coding.

THE IDEA IN ONE PARAGRAPH
Students going the same way at about the same time share one Jeeny car, in both directions: home → campus
in the morning, campus → home after class. Nobody gathers at one spot. Each student walks at most 200 m
(about 2 min) to the street the captain is already driving through, and gets out on the street nearest
their destination. Each student pays only for the km they ride. Together they pay exactly one regulated
Jeeny fare for the car.

FIRST
1. Stop auto-sync, run `git pull origin main`, restart auto-sync.
2. Read replit.md, document.md, docs/superpowers/specs/2026-11-27-ride-pooling-design.md and
   reports/Campus ride matching validation.md.
3. Run `python -m pytest`. Everything must pass before and after each phase. Commit after each phase.

PERMISSION: for this brief you may change pooling/ as described below, with tests. Never change:
the tariff (car fare = 468 + 336 × route km, in integer fils); that shares add up to the car fare
exactly; and that nobody pays more than their solo fare.

──────────────── PHASE 0: fix the engine (do first) ────────────────
0.1 Busy-afternoon bug: with ~28 riders at once, regroup() times out in its second solve and everyone
    rides alone. Use ONE objective:
      minimize Σ chosen cars (468 + 336 × route_km) + 1500 × (riders left alone who wanted to share)
    On timeout, keep the best solution found. Never fall back to "everyone alone".
    Test: 15 seeds × 28 riders at the same time → no run with ≥ 20 solo cars, each run < 3 s.
0.2 Pruning bug: only prune sub-groups on monotone rules (seats, time window, gender). Check detour and
    savings on the full group (a pair can fail savings while its trio passes). Add a test for this.
0.3 config: time gap 10 min, MIN_SAVING 0.25, MAX_WALK_M 200, WALK_SPEED 1.4 m/s.

──────────────── PHASE 1: geography for street pickup (simulated, no maps API) ────────────────
- Keep the corridors (West, North, South, East). A corridor is a main road from campus outward, in km.
- Each student has a location: (corridor, km along the road, side_m = metres from the main road).
- Campus has a few entry points on its edge (Main gate, North gate, East gate), each on a corridor at km 0.
  A student on campus has a location near their building: (nearest gate, side_m).
- Street point: if side_m ≤ 200 → the student walks side_m to the main road at their km.
  Walk time = side_m / 1.4 s, shown as "walk 1 min to <street>".
  If side_m > 200 → the captain turns in: extra car km = 2 × (side_m − 200) / 1000, which counts toward
  the detour rule. The student walks the remaining 200 m.
- Same logic at drop-off: the student gets out at their km on the main road (or the turn-in point) and
  walks ≤ 200 m.
- Sample data: generate student locations around the existing stops (random km ± 1 km, side_m 0–400).

──────────────── PHASE 2: both directions ────────────────
- A request has `direction`: "to_campus" or "from_campus".
  from_campus: `ready_at` = class end + time to walk to the street. Riders match if ready_at values
               are within 10 min.
  to_campus:   `arrive_by` = class start − 5 min. Riders match if arrive_by values are within 10 min,
               and the car must reach campus by everyone's arrive_by.
- Only riders with the same direction and corridor share a car.
- Route: the car drives the corridor once, inward or outward. Order the stops by km in the driving direction.
- Each rider gets their OWN time: "Car at your spot 16:12" (from_campus) or
  "Pickup 07:41 at <street>, arrive 08:05" (to_campus). Travel time = km / 25 km/h.

──────────────── PHASE 3: rules for a valid car (pooling/model.evaluate) ────────────────
- ≤ 4 riders, same direction and corridor, time rule above.
- Ride options: preference "mixed" | "women" | "men", plus gender. Valid only if every rider whose
  preference is women/men shares that gender with everyone in the car. Mixed accepts anyone.
  Booking screen: under women/men, "Matching may take longer".
- Detour: each rider's in-car km ≤ min(1.5 × their solo km, solo km + 4 km).
- Savings: each rider in a shared car pays ≤ 75% of their solo fare.
- Solo km/fare = that rider's own street point → destination street point, alone.

──────────────── PHASE 4: pricing (one rule for every car) ────────────────
- Car fare = 468 + 336 × total route km (fils).
- Split the 468 start fare equally among all riders in the car.
- Split each km segment equally among the riders on board for that segment.
- Round with largest remainder so the shares add up to the car fare exactly.
- Cap: a share never exceeds that rider's solo fare.
- Show: "Your share JOD 1.62 · alone JOD 4.50 · you save 64%" and a breakdown
  ("You rode 9 km: 5 km shared by 3, 4 km shared by 2").
- Tests: a rider picked up later pays less; shares add up to the car fare; nobody exceeds solo;
  a single rider pays exactly the solo fare.

──────────────── PHASE 5: friends booking together ────────────────
- "Book with friends": the creator gets a code like "GR-48", and others join with it (max 4).
  Same direction and corridor, times within the gap.
- Toggle "Let others fill empty seats" (default on).
- Matching: all of a group's members ride in one car or none do. A closed group gets no strangers.
  Each friend pays by their own km.

──────────────── PHASE 6: captains (simulated) ────────────────
- Seed `captains` (name, gender, available).
- Women-only car → a free woman captain if any, otherwise any free captain.
- Captain view: ordered list of street pickups and drop-offs with times, rider first names, ride codes
  to check, car fare, and a Jeeny-paid extra-rider bonus = 100 fils × (riders − 1).
  The bonus is not charged to students.

──────────────── PHASE 7: confirmations and race conditions ────────────────
- After matching, each rider has 2 min to confirm. If the hold expires → treat as declined, re-plan the
  car, and mark the others "changed".
- Keep BEGIN IMMEDIATE transactions, plan signatures (409 plan_changed) and clientRequestId retries.
- A confirmed share never goes up. If a decline would raise it, keep the confirmed share and record the
  gap as "Jeeny covers X fils" (shown on the dashboard).
- Ride code (CC-####) on confirm; the captain checks it at each pickup.
- Tests: two simultaneous confirms of one seat → exactly one wins; an expired hold frees the seat;
  a confirmed share never rises after a decline.

──────────────── PHASE 8: a rider left alone gets three choices ────────────────
 A. Ride alone now: standard solo fare.
 B. Wait for a match: up to 10 min. Matching re-runs as requests arrive; if none comes, show A again.
 C. Go now, open to share: the car leaves. A new request on the same corridor and direction whose street
    point is still ahead of the car (simulated demo clock) can join on the way (use pooling/matcher.py
    insert). Price with the Phase 4 rule, settled when the ride ends.
    Upfront: "You pay at most JOD X. Less if someone joins."

──────────────── PHASE 9: simulation tab for judges ────────────────
- "Simulation" tab: N students (8, 16, 24, 32), both directions, 30 random seeds each, same seeds for
  every method.
- Methods: everyone alone · first-come grouping (greedy) · our optimizer.
- Show mean and range for: cars used, car-km, % km saved vs alone, % riders matched,
  average saving per rider, average walk, average extra ride time.
- Charts: km saved vs N, and match rate vs N, for greedy vs optimizer.
- Label everything "simulated".

DONE WHEN (check in Preview)
- Both directions bookable. Each student sees their own street, walk time and pickup time.
- Sample afternoon and a morning sample both form shared cars; 28 riders at once never give 28 solo cars.
- Women-only car gets a woman captain when one is free. A friends group rides together.
- A lone rider can choose A, B or C; with C, the final price drops when someone joins on the way.
- Shares add up to the car fare in every car, and nobody pays more than alone.
- Simulation tab shows optimizer vs greedy vs alone over 30 seeds.
- `python -m pytest` passes. Update replit.md, document.md and the spec. Put open questions in agent.md.
````
