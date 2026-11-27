"""Shared-ride rules for the Replit app, backed by the `pooling` engine.

This module keeps the interface store.py, api.py and app.py already use (rider dicts with
id, name, class_end, stop, gender, preference, and optionally friend_group/group_open).
Every rule and price comes from pooling/:
- fares: LTRC smart-app tariff (start + per km over the whole route), one fare per car;
- split: proportional to each rider's own distance, shares add up to the car fare exactly;
- a rider only shares if they save at least 25% and their detour stays within limits;
- ride options: "mixed", "women" or "men" (pooling.model.gender_ok);
- grouping: CP-SAT over every feasible car of up to 4, minimizing total fares plus a penalty per
  student left alone; friends groups ride in one car.
Distances, gates and coordinates are simulated assumptions for the demo.
"""
import math
from datetime import date, datetime, timedelta

from pooling import config
from pooling.model import PREFERENCES, Rider, evaluate
from pooling.places import COORDS, CORRIDORS, DEMO_CAMPUS, GATES
from pooling.pricing import car_fare
from pooling.regroup import regroup

STOPS = {stop: {"corridor": name, "km": km} for name, corridor in CORRIDORS.items() for stop, km in corridor["stops"].items()}

BASE_FARE = config.START_DAY  # Fils, regulated app tariff (day)
PER_KM = config.PER_KM_DAY
MIN_SAVING_PCT = round(config.MIN_SAVING * 100)
SEATS = config.MAX_RIDERS
MAX_GAP = config.MAX_GAP_MIN  # Minutes between the earliest and latest class end in one car
WALK = 15  # Minutes from the last class ending to pickup at the gate

_DAY = date(2026, 11, 28)  # Prices only depend on the clock time; this fixes the date part.


def route_map(gate, stops, width=320, height=170, pad=22):
    """Project the gate and ordered drop-offs into SVG coordinates for a small simulated map."""
    places = [(gate, GATES[gate])] + [(stop, COORDS[stop]) for stop in stops]
    lats = [lat for _, (lat, _) in places]
    lngs = [lng for _, (_, lng) in places]
    squash = math.cos(math.radians(sum(lats) / len(lats)))  # Keep east-west distances in proportion
    span_x = max((max(lngs) - min(lngs)) * squash, 0.01)
    span_y = max(max(lats) - min(lats), 0.01)
    scale = min((width - 2 * pad) / span_x, (height - 2 * pad) / span_y)
    mid_x, mid_y = (max(lngs) + min(lngs)) / 2 * squash, (max(lats) + min(lats)) / 2
    points = [
        {"name": name, "x": round(width / 2 + (lng * squash - mid_x) * scale, 1),
         "y": round(height / 2 - (lat - mid_y) * scale, 1)}
        for name, (lat, lng) in places
    ]
    return {"width": width, "height": height, "points": points,
            "path": " ".join(f"{p['x']},{p['y']}" for p in points)}


def to_minutes(clock):
    hour, minute = map(int, clock.split(":"))
    return hour * 60 + minute


def to_clock(minutes):
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _at(minutes):
    return datetime(_DAY.year, _DAY.month, _DAY.day, tzinfo=config.TZ) + timedelta(minutes=minutes)


def _rider(r):
    """Map an app rider dict to the engine's Rider.

    The window starts when the student reaches the gate. Its length makes two windows overlap
    by at least MIN_WINDOW_MIN exactly when their class ends are within MAX_GAP minutes.
    """
    direction = r.get("direction", "from_campus")
    if r.get("corridor") is not None and r.get("start_km") is not None and r.get("end_km") is not None:
        def local_time(value):
            if not value:
                return None
            if "T" in value:
                return datetime.fromisoformat(value)
            return _at(to_minutes(value))

        ready_at = local_time(r.get("ready_at"))
        if ready_at is None and direction == "from_campus":
            walk_seconds = min(int(r.get("start_side_m", 0)), config.MAX_WALK_M) / config.WALK_SPEED_MPS
            ready_at = _at(to_minutes(r["class_end"])) + timedelta(seconds=walk_seconds)
        arrive_by = local_time(r.get("arrive_by"))
        if arrive_by is None and direction == "to_campus":
            arrive_by = _at(to_minutes(r["class_start"])) - timedelta(minutes=5)
        # The engine stores a valid legacy window too, for older callers and tests.
        moment = ready_at or arrive_by
        return Rider(
            request_id=str(r["id"]), first_name=r["name"], gender=r["gender"], preference=r["preference"],
            campus_id=DEMO_CAMPUS, meeting_point_id=CORRIDORS[r["corridor"]]["gate"],
            stop_id=r["stop"], leave_after=moment,
            leave_before=moment + timedelta(minutes=MAX_GAP + config.MIN_WINDOW_MIN),
            quoted_share=r.get("quoted_share"),
            direction=direction, corridor=r["corridor"], start_km=float(r["start_km"]),
            start_side_m=int(r.get("start_side_m") or 0), end_km=float(r["end_km"]),
            end_side_m=int(r.get("end_side_m") or 0), ready_at=ready_at, arrive_by=arrive_by,
        )
    ready = to_minutes(r["class_end"]) + WALK
    return Rider(
        request_id=str(r["id"]), first_name=r["name"], gender=r["gender"], preference=r["preference"],
        campus_id=DEMO_CAMPUS, meeting_point_id=CORRIDORS[STOPS[r["stop"]]["corridor"]]["gate"],
        stop_id=r["stop"], leave_after=_at(ready), leave_before=_at(ready + MAX_GAP + config.MIN_WINDOW_MIN),
        quoted_share=r.get("quoted_share"),
    )


def trip_time(clock):
    """A trip-day datetime for an "HH:MM" time (prices depend only on the clock time)."""
    return _at(to_minutes(clock))


def solo_fare(stop, at_minutes=16 * 60):
    return car_fare(STOPS[stop]["km"], _at(at_minutes))


def sample_share(stop, riders=3):
    """Typical share when riding with others going to the same stop."""
    plan = evaluate([_rider({"id": i, "name": "x", "class_end": "16:00", "stop": stop, "gender": "man", "preference": "mixed"})
                     for i in range(riders)])
    return plan.shares["0"] if plan else solo_fare(stop)


def compatible(a, b):
    return evaluate([_rider(a), _rider(b)]) is not None


def group_riders(riders):
    """Split riders into cars (cheapest total fares, fewest students alone). Returns lists of rider ids.

    Riders sharing a `friend_group` always land in one car; if any of them has `group_open` False,
    no one else joins that car.
    """
    if not riders:
        return []
    by_id = {str(r["id"]): r["id"] for r in riders}
    singles = [evaluate([_rider(r)]) for r in riders]
    groups = {}
    for r in riders:
        if r.get("friend_group"):
            groups.setdefault(r["friend_group"], []).append(r)
    together = [frozenset(str(r["id"]) for r in members) for members in groups.values()]
    closed = [frozenset(str(r["id"]) for r in members) for members in groups.values()
              if not all(r.get("group_open", True) for r in members)]
    return [[by_id[x.request_id] for x in plan.riders] for plan in regroup(singles, together=together, closed=closed)]


def group_problem(members):
    """Why these friends cannot share one car (gate, class-end gap, seats or ride option), or None."""
    if len(members) > SEATS:
        return f"A group has at most {SEATS} students."
    if len({m.get("direction", "from_campus") for m in members}) > 1:
        return "Everyone in a friends group must travel in the same direction."
    corridors = {STOPS[m["stop"]]["corridor"] for m in members}
    if len(corridors) > 1:
        return "Everyone in a friends group must be on the same corridor."
    field = "class_start" if members[0].get("direction") == "to_campus" else "class_end"
    values = [to_minutes(m[field]) for m in members]
    if max(values) - min(values) > MAX_GAP:
        return f"Everyone's times must be within {MAX_GAP} minutes of each other."
    if evaluate([_rider(m) for m in members], strict=False) is None:
        return "Someone in the group asked for a women-only or men-only car that the others can't join."
    return None


def only_label(members):
    """"women" or "men" when every rider has that gender and at least one asked for it, else None."""
    if len(members) < 2:
        return None
    for preference, gender in PREFERENCES.items():
        if gender and all(m["gender"] == gender for m in members) and any(m["preference"] == preference for m in members):
            return preference
    return None


def plan_car(members):
    """Pickup, drop-off order and each rider's share for one car's active riders."""
    riders = [_rider(m) for m in members]
    plan = evaluate(riders)
    if plan is None:
        # Can only happen after someone declines and the rest no longer meet every rule.
        # Keep the car together at the regulated fare rather than silently re-matching it.
        plan = evaluate(riders, strict=False)
    by_id = {str(m["id"]): m for m in members}
    ordered = [by_id[r.request_id] for r in plan.riders]
    shares = {by_id[rid]["id"]: share for rid, share in plan.shares.items()}
    jeeny_cover = 0
    for member in members:
        confirmed = member.get("confirmed_plan")
        if confirmed:
            quoted = int(str(confirmed).split("|", 1)[0])
            current = shares[member["id"]]
            if current > quoted:
                jeeny_cover += current - quoted
                shares[member["id"]] = quoted
    ready = to_minutes(plan.pickup_time.astimezone(config.TZ).strftime("%H:%M"))
    shared = len(ordered) > 1
    corridor = STOPS[ordered[0]["stop"]]["corridor"]
    street = plan.board_km is not None
    rider_times = {}
    drop_times = {}
    walk_m = {}
    segment_breakdown = {}
    campus_arrival = None
    if street:
        if plan.riders[0].direction == "to_campus":
            campus_arrival = min(r.arrive_by for r in plan.riders).astimezone(config.TZ).strftime("%H:%M")
        for engine_rider in plan.riders:
            rider_id = engine_rider.request_id
            grouped = {}
            for length, occupants in plan.segments or ():
                if rider_id in occupants:
                    grouped[len(occupants)] = grouped.get(len(occupants), 0.0) + length
            segment_breakdown[by_id[rider_id]["id"]] = [
                {"riders": count, "km": round(length, 2)}
                for count, length in sorted(grouped.items(), reverse=True)
            ]
        for engine_rider in plan.riders:
            rider_id = engine_rider.request_id
            member = by_id[rider_id]
            member["solo"] = plan.solo_fare[rider_id]
            member["km"] = plan.solo_km[rider_id]
            rider_times[member["id"]] = (
                plan.pickup_time if engine_rider.direction == "from_campus"
                else plan.arrival[rider_id]
            ).astimezone(config.TZ).strftime("%H:%M")
            drop_times[member["id"]] = plan.arrival[rider_id].astimezone(config.TZ).strftime("%H:%M")
            walk_m[member["id"]] = min(int(member.get("start_side_m") or 0), config.MAX_WALK_M)
        ordered = [by_id[r.request_id] for r in plan.riders]
        corridor = plan.riders[0].corridor
    return {
        "gate": CORRIDORS[corridor]["gate"], "corridor": corridor,
        "pickup": to_clock(ready) if street else to_clock(-(-ready // 5) * 5), "members": ordered,
        "car_fare": plan.car_fare, "route_km": plan.route_km,
        "shares": shares, "jeeny_cover": jeeny_cover,
        "shared": shared,
        "only": only_label(ordered),
        "women_only": only_label(ordered) == "women",
        "street": street,
        "direction": plan.riders[0].direction if street else "from_campus",
        "rider_times": rider_times, "drop_times": drop_times, "walk_m": walk_m,
        "segment_breakdown": segment_breakdown,
        "campus_arrival": campus_arrival,
    }
