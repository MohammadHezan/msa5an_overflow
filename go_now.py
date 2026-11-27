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


def position_km(departed: datetime, now: datetime, route_km: float, direction="from_campus", start_km=0.0) -> float:
    """Current corridor position, using the simulated speed and the trip direction."""
    driven = max(0.0, (now - departed).total_seconds() / 3600 * config.SPEED_KMH)
    if direction == "to_campus":
        return max(0.0, start_km - driven)
    return min(route_km, start_km + driven)


def pickup_point(corridor: str, car_km: float, direction="from_campus") -> tuple[str, float]:
    """The nearest corridor point the car has not passed yet: the gate if it hasn't left, else the next stop."""
    if car_km <= 0:
        return CORRIDORS[corridor]["gate"], 0.0
    if direction == "to_campus":
        ahead = sorted(((km, stop) for stop, km in CORRIDORS[corridor]["stops"].items() if km <= car_km), reverse=True)
    else:
        ahead = sorted((km, stop) for stop, km in CORRIDORS[corridor]["stops"].items() if km >= car_km)
    return (ahead[0][1], float(ahead[0][0])) if ahead else (None, None)


def split(riders, at: datetime, direction="from_campus", extras=None, caps=None) -> tuple[dict, int, float]:
    """Split start fare equally and route segments among occupants; apply solo-fare caps.

    `riders`: `(id, board_km, drop_km)` with km measured outward from campus.
    `extras`: `(position_km, extra_km, kind)` turn-ins, apportioned only to riders aboard.
    """
    extras = extras or {}
    caps = caps or {}
    road_extent = max((drop if direction == "from_campus" else board
                       for _, board, drop in riders), default=0.0)
    route_km = road_extent + sum(distance for entries in extras.values() for _, distance, _ in entries)
    # This street-pickup demo uses the brief's fixed approved tariff in every mode.
    start = config.START_DAY
    total = start + round(config.PER_KM_DAY * route_km)
    per_km = (total - start) / route_km if route_km else 0
    marks = sorted({0.0, road_extent, *(b for _, b, _ in riders), *(d for _, _, d in riders)})
    raw = {rid: start / len(riders) for rid, _, _ in riders}
    for lo, hi in zip(marks, marks[1:]):
        if direction == "to_campus":
            on_board = [rid for rid, board, drop in riders if board >= hi and drop <= lo]
        else:
            on_board = [rid for rid, board, drop in riders if board <= lo and drop >= hi]
        for rid in on_board:
            raw[rid] += (hi - lo) * per_km / len(on_board)
    for rid, entries in extras.items():
        for position, distance, kind in entries:
            if direction == "to_campus":
                on_board = [who for who, board, _ in riders if board >= position] if kind == "pickup" else [who for who, _, _ in riders]
            else:
                on_board = [who for who, _, drop in riders if drop >= position] if kind == "dropoff" else [who for who, _, _ in riders]
            if on_board and distance:
                for who in on_board:
                    raw[who] += distance * per_km / len(on_board)
    ids = [rid for rid, _, _ in riders]
    if not caps:
        return dict(zip(ids, split_fare(total, [raw[i] for i in ids]))), total, route_km
    shares = {rid: min(caps.get(rid, total), int(raw[rid])) for rid in ids}
    remainder = total - sum(shares.values())
    while remainder:
        eligible = [rid for rid in ids if shares[rid] < caps.get(rid, total)]
        if not eligible:
            break
        rid = max(eligible, key=lambda item: (raw[item] - shares[item], -ids.index(item)))
        shares[rid] += 1
        remainder -= 1
    return shares, total, route_km


def can_join(members, newcomer, corridor: str, car_km: float, departed: datetime):
    """The pickup (stop name, km) for `newcomer` joining a moving car, or None.

    members/newcomer: app rider dicts (id, name, stop, gender, preference). The seat and ride-option
    rules come from pooling.matcher.insert; the timing is the car's position on the demo clock.
    """
    direction = members[0].get("direction", "from_campus") if members else "from_campus"
    if newcomer["corridor"] != corridor or newcomer.get("direction", "from_campus") != direction:
        return None
    if direction == "to_campus":
        board_km = float(newcomer.get("start_km", newcomer["km"]))
        if board_km >= car_km:
            return None
        stop_name = newcomer["stop"] + " street"
    else:
        stop_name, board_km = pickup_point(corridor, car_km)
        if stop_name is None or newcomer["km"] <= board_km:
            return None

    def rider(r):
        return Rider(request_id=str(r["id"]), first_name=r["name"], campus_id=DEMO_CAMPUS,
                     meeting_point_id=CORRIDORS[corridor]["gate"], stop_id=r["stop"],
                     leave_after=departed, leave_before=departed + timedelta(minutes=30),
                     gender=r["gender"], preference=r["preference"])

    current = evaluate([rider(m) for m in members], strict=False)
    if current is None or insert([OpenGroup("car", current)], rider(newcomer)).group_id is None:
        return None
    return stop_name, board_km
