"""Shared-ride rules for the Replit app, backed by the `pooling` engine.

This module keeps the interface store.py, api.py and app.py already use (rider dicts with
id, name, class_end, stop, woman, women_only). Every rule and price comes from pooling/:
- fares: LTRC smart-app tariff (start + per km over the whole route), one fare per car;
- split: proportional to each rider's own distance, shares add up to the car fare exactly;
- a rider only shares if they save at least 20% and their detour stays within limits;
- grouping: CP-SAT over every feasible car of up to 4 (fewest car-km, then fewest cars).
Distances, gates and coordinates are simulated assumptions for the demo.
"""
import math
from datetime import date, datetime, timedelta

from pooling import config
from pooling.model import Rider, evaluate
from pooling.places import COORDS, CORRIDORS, DEMO_CAMPUS, GATES
from pooling.pricing import car_fare
from pooling.regroup import regroup

STOPS = {stop: {"corridor": name, "km": km} for name, corridor in CORRIDORS.items() for stop, km in corridor["stops"].items()}

BASE_FARE = config.START_DAY  # Fils, regulated app tariff (day)
PER_KM = config.PER_KM_DAY
MIN_SAVING_PCT = round(config.MIN_SAVING * 100)
SEATS = config.MAX_RIDERS
MAX_GAP = 20  # Minutes between the earliest and latest class end in one car
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
    ready = to_minutes(r["class_end"]) + WALK
    return Rider(
        request_id=str(r["id"]), first_name=r["name"], women_only=bool(r["women_only"]), woman=bool(r["woman"]),
        campus_id=DEMO_CAMPUS, meeting_point_id=CORRIDORS[STOPS[r["stop"]]["corridor"]]["gate"],
        stop_id=r["stop"], leave_after=_at(ready), leave_before=_at(ready + MAX_GAP + config.MIN_WINDOW_MIN),
    )


def solo_fare(stop, at_minutes=16 * 60):
    return car_fare(STOPS[stop]["km"], _at(at_minutes))


def sample_share(stop, riders=3):
    """Typical share when riding with others going to the same stop."""
    plan = evaluate([_rider({"id": i, "name": "x", "class_end": "16:00", "stop": stop, "woman": False, "women_only": False})
                     for i in range(riders)])
    return plan.shares["0"] if plan else solo_fare(stop)


def compatible(a, b):
    return evaluate([_rider(a), _rider(b)]) is not None


def group_riders(riders):
    """Split riders into cars (fewest car-km, then fewest cars). Returns lists of rider ids."""
    if not riders:
        return []
    by_id = {str(r["id"]): r["id"] for r in riders}
    singles = [evaluate([_rider(r)]) for r in riders]
    return [[by_id[x.request_id] for x in plan.riders] for plan in regroup(singles)]


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
    ready = to_minutes(plan.pickup_time.astimezone(config.TZ).strftime("%H:%M"))
    shared = len(ordered) > 1
    corridor = STOPS[ordered[0]["stop"]]["corridor"]
    return {
        "gate": CORRIDORS[corridor]["gate"], "corridor": corridor,
        "pickup": to_clock(-(-ready // 5) * 5), "members": ordered,
        "car_fare": plan.car_fare, "route_km": plan.route_km,
        "shares": {by_id[rid]["id"]: share for rid, share in plan.shares.items()},
        "shared": shared,
        "women_only": shared and all(m["woman"] for m in ordered) and any(m["women_only"] for m in ordered),
    }
