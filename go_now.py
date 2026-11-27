"""Option C for a student left alone: "Go now, open to share".

The car leaves at once with one student. A later request on the same corridor can be picked up on
the way if its stop is still ahead of the car. Car position comes from a simulated demo clock.

Pricing (fils): the car pays one regulated fare over its whole route. The start fare is split
equally among everyone who rode; each km is split among the riders in the car on that km. Shares
add up to the car fare exactly, and nobody pays more than riding alone from the gate. The price is
final once the car reaches its last stop.
"""
from datetime import datetime, timedelta

from pooling import config
from pooling.matcher import OpenGroup, insert
from pooling.model import Rider, evaluate
from pooling.places import CORRIDORS, DEMO_CAMPUS
from pooling.pricing import car_fare, split_fare


def position_km(departed: datetime, now: datetime, route_km: float) -> float:
    """How far along its corridor the car is (simulated: SPEED_KMH from departure)."""
    driven = max(0.0, (now - departed).total_seconds() / 3600 * config.SPEED_KMH)
    return min(route_km, driven)


def pickup_point(corridor: str, car_km: float) -> tuple[str, float]:
    """The nearest corridor point the car has not passed yet: the gate if it hasn't left, else the next stop."""
    if car_km <= 0:
        return CORRIDORS[corridor]["gate"], 0.0
    ahead = sorted((km, stop) for stop, km in CORRIDORS[corridor]["stops"].items() if km >= car_km)
    return (ahead[0][1], float(ahead[0][0])) if ahead else (None, None)


def split(riders, at: datetime) -> tuple[dict, int, float]:
    """riders: [(id, board_km, drop_km)]. Returns ({id: share}, car fare, route km)."""
    route_km = max(drop for _, _, drop in riders)
    total = car_fare(route_km, at)
    start = car_fare(0, at)
    per_km = (total - start) / route_km if route_km else 0
    marks = sorted({0.0, route_km, *(b for _, b, _ in riders), *(d for _, _, d in riders)})
    raw = {rid: start / len(riders) for rid, _, _ in riders}
    for lo, hi in zip(marks, marks[1:]):
        on_board = [rid for rid, board, drop in riders if board <= lo and drop >= hi]
        for rid in on_board:
            raw[rid] += (hi - lo) * per_km / len(on_board)
    ids = [rid for rid, _, _ in riders]
    return dict(zip(ids, split_fare(total, [raw[i] for i in ids]))), total, route_km


def can_join(members, newcomer, corridor: str, car_km: float, departed: datetime):
    """The pickup (stop name, km) for `newcomer` joining a moving car, or None.

    members/newcomer: app rider dicts (id, name, stop, gender, preference). The seat and ride-option
    rules come from pooling.matcher.insert; the timing is the car's position on the demo clock.
    """
    if newcomer["corridor"] != corridor:
        return None
    stop_name, board_km = pickup_point(corridor, car_km)
    if stop_name is None or newcomer["km"] <= board_km:
        return None  # The car has already passed the student's stop

    def rider(r):
        return Rider(request_id=str(r["id"]), first_name=r["name"], campus_id=DEMO_CAMPUS,
                     meeting_point_id=CORRIDORS[corridor]["gate"], stop_id=r["stop"],
                     leave_after=departed, leave_before=departed + timedelta(minutes=30),
                     gender=r["gender"], preference=r["preference"])

    current = evaluate([rider(m) for m in members], strict=False)
    if current is None or insert([OpenGroup("car", current)], rider(newcomer)).group_id is None:
        return None
    return stop_name, board_km
