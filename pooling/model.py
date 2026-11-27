"""The one place every pooling rule lives. Live insertion, regroup and the API all call `evaluate`."""
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import permutations

from pooling import config
from pooling.geo import minutes_for, road_km
from pooling.places import CAMPUSES, STOPS
from pooling.pricing import car_fare, split_fare


PREFERENCES = {"mixed": None, "women": "woman", "men": "man"}  # ride option -> the gender everyone in the car must have


@dataclass(frozen=True)
class Rider:
    request_id: str
    first_name: str
    campus_id: str
    meeting_point_id: str
    stop_id: str
    leave_after: datetime
    leave_before: datetime
    quoted_share: int | None = None  # set once confirmed; later groupings may never charge more
    gender: str | None = None  # "woman" or "man"
    preference: str = "mixed"  # "mixed" | "women" | "men"
    # Optional street geometry. When provided, `corridor` and `direction` replace the
    # single fixed gate/drop-off model above. Km values are measured outward from campus.
    direction: str = "from_campus"  # "from_campus" | "to_campus"
    corridor: str | None = None
    start_km: float | None = None
    start_side_m: int = 0
    end_km: float | None = None
    end_side_m: int = 0
    ready_at: datetime | None = None  # from_campus; class end plus walk to street
    arrive_by: datetime | None = None  # to_campus; class start minus 5 minutes


@dataclass(frozen=True)
class GroupPlan:
    riders: tuple[Rider, ...]  # in drop-off order
    route_km: float
    car_fare: int
    shares: dict[str, int]
    solo_km: dict[str, float]
    solo_fare: dict[str, int]
    in_car_km: dict[str, float]
    pickup_time: datetime
    arrival: dict[str, datetime]
    board_km: dict[str, float] | None = None
    drop_km: dict[str, float] | None = None
    walk_m: dict[str, int] | None = None
    segments: tuple[tuple[float, tuple[str, ...]], ...] | None = None

    @property
    def ids(self) -> frozenset[str]:
        return frozenset(r.request_id for r in self.riders)


def _shared_window(riders: Sequence[Rider]) -> tuple[datetime, datetime] | None:
    start = max(r.leave_after for r in riders)
    end = min(r.leave_before for r in riders)
    if end - start < timedelta(minutes=config.MIN_WINDOW_MIN):
        return None
    return start, end


def gender_ok(riders: Sequence[Rider]) -> bool:
    """For every rider who asked for "women" or "men", every rider in the car has that gender."""
    wanted = {PREFERENCES[r.preference] for r in riders} - {None}
    return all(all(r.gender == g for r in riders) for g in wanted)


def basic_ok(riders: Sequence[Rider]) -> tuple[datetime, datetime] | None:
    """The rules that also hold for every sub-group (seats, meeting point, gender, window).

    Returns the shared window, or None. regroup prunes on these only: the detour, savings and
    quote checks are re-done on each full group, because a third rider can make a pair pass.
    """
    if not 1 <= len(riders) <= config.MAX_RIDERS:
        return None
    first = riders[0]
    if first.corridor is not None:
        if any(r.direction != first.direction or r.corridor != first.corridor for r in riders):
            return None
        if not gender_ok(riders):
            return None
        if len({r.request_id for r in riders}) != len(riders):
            return None
        if first.direction == "from_campus":
            ready = [r.ready_at for r in riders]
            if any(t is None for t in ready) or max(ready) - min(ready) > timedelta(minutes=config.MAX_GAP_MIN):
                return None
            return min(ready), max(ready)
        deadlines = [r.arrive_by for r in riders]
        if any(t is None for t in deadlines) or max(deadlines) - min(deadlines) > timedelta(minutes=config.MAX_GAP_MIN):
            return None
        return min(deadlines), max(deadlines)
    if any((r.campus_id, r.meeting_point_id) != (first.campus_id, first.meeting_point_id) for r in riders):
        return None
    if not gender_ok(riders):
        return None
    if len({r.request_id for r in riders}) != len(riders):
        return None
    return _shared_window(riders)


def evaluate(riders: Sequence[Rider], strict: bool = True) -> GroupPlan | None:
    """Return the shortest feasible plan for exactly these riders, or None if no order works.

    strict=False skips the detour, savings and quote checks (but never the seats, meeting point,
    gender or window rules). It prices an existing car that lost a rider, or a friends group.
    """
    riders = tuple(riders)
    window = basic_ok(riders)
    if window is None:
        return None
    first = riders[0]
    if first.corridor is not None:
        return _evaluate_street(riders, strict, window)
    pickup = window[0]

    origin = CAMPUSES[first.campus_id].meeting_points[first.meeting_point_id]
    solo_km = {r.request_id: road_km(origin, STOPS[r.stop_id]) for r in riders}
    solo_fare = {rid: car_fare(km, pickup) for rid, km in solo_km.items()}

    best = None
    for order in permutations(riders):
        in_car, here, km = {}, origin, 0.0
        for r in order:
            stop = STOPS[r.stop_id]
            km += road_km(here, stop)
            here = stop
            in_car[r.request_id] = km
        if best is not None and km >= best.route_km:
            continue
        if strict and any(
            in_car[rid] > min(solo * config.DETOUR_RATIO, solo + config.DETOUR_EXTRA_KM) + 1e-9
            for rid, solo in solo_km.items()
        ):
            continue
        fare = car_fare(km, pickup)
        shares = dict(zip(
            (r.request_id for r in order),
            split_fare(fare, [solo_km[r.request_id] for r in order]),
        ))
        if strict and len(order) > 1 and any(
            shares[rid] > (1 - config.MIN_SAVING) * solo_fare[rid] for rid in shares
        ):
            continue
        if strict and any(r.quoted_share is not None and shares[r.request_id] > r.quoted_share for r in order):
            continue
        best = GroupPlan(
            riders=order,
            route_km=km,
            car_fare=fare,
            shares=shares,
            solo_km=solo_km,
            solo_fare=solo_fare,
            in_car_km=in_car,
            pickup_time=pickup,
            arrival={rid: pickup + timedelta(minutes=minutes_for(k)) for rid, k in in_car.items()},
        )
    return best


def _walk_distance(side_m: int) -> int:
    return min(max(0, int(side_m)), config.MAX_WALK_M)


def _turn_km(side_m: int) -> float:
    return 2 * max(0, int(side_m) - config.MAX_WALK_M) / 1000


def _street_shares(total: int, rider_ids: list[str], segments: list[tuple[float, tuple[str, ...]]],
                   caps: dict[str, int]) -> dict[str, int]:
    """Split start fare equally and each road segment equally among its occupants.

    Segment lengths include the captain's short turn-ins. A capped largest-remainder pass
    keeps every share at or below the corresponding solo fare while conserving every fils.
    """
    if not rider_ids:
        return {}
    raw = {rid: 0.0 for rid in rider_ids}
    start = min(total, config.START_DAY)
    for rid in rider_ids:
        raw[rid] = start / len(rider_ids)
    km_total = sum(length for length, _ in segments)
    variable = max(0, total - start)
    rate = variable / km_total if km_total else 0
    for length, occupants in segments:
        if not occupants:
            continue
        amount = length * rate / len(occupants)
        for rid in occupants:
            raw[rid] += amount
    # Largest-remainder allocation subject to solo-fare caps.
    exact = {rid: raw[rid] for rid in rider_ids}
    shares = {rid: min(caps[rid], int(exact[rid])) for rid in rider_ids}
    remainder = total - sum(shares.values())
    while remainder > 0:
        eligible = [rid for rid in rider_ids if shares[rid] < caps[rid]]
        if not eligible:
            # Mathematically impossible for valid inputs (car fare <= summed solo fares).
            return {}
        rid = max(eligible, key=lambda item: (exact[item] - shares[item], -rider_ids.index(item)))
        shares[rid] += 1
        remainder -= 1
    return shares


def _evaluate_street(riders: tuple[Rider, ...], strict: bool, window) -> GroupPlan | None:
    """Evaluate one direction along a simulated corridor with street pickups and drop-offs."""
    from_campus = riders[0].direction == "from_campus"
    if riders[0].direction not in ("from_campus", "to_campus"):
        return None
    first = riders[0]
    if from_campus:
        board = {r.request_id: 0.0 for r in riders}
        drop = {r.request_id: float(r.end_km) for r in riders}
        solo = {r.request_id: abs(drop[r.request_id]) + _turn_km(r.start_side_m) + _turn_km(r.end_side_m)
                for r in riders}
        # A single car starts from the campus edge and reaches each destination once.
        ordered = tuple(sorted(riders, key=lambda r: (drop[r.request_id], r.request_id)))
        route_events = [(r.request_id, drop[r.request_id], _turn_km(r.end_side_m)) for r in ordered]
        route_km = max((drop[r.request_id] for r in riders), default=0.0) + sum(
            _turn_km(r.start_side_m) + _turn_km(r.end_side_m) for r in riders
        )
        end_time = max(r.ready_at for r in riders)
        start_time = end_time
        # All passengers board at campus; each segment is shared by riders not yet dropped.
        marks = sorted({0.0, *(drop[r.request_id] for r in riders)})
        segments = []
        for lo, hi in zip(marks, marks[1:]):
            onboard = tuple(r.request_id for r in riders if drop[r.request_id] >= hi)
            if hi > lo and onboard:
                segments.append((hi - lo, onboard))
        for rid, km, turn in route_events:
            if turn:
                segments.append((turn, tuple(r.request_id for r in riders if drop[r.request_id] >= km)))
        # Campus side turn-in is a shared first segment.
        campus_turn = sum(_turn_km(r.start_side_m) for r in riders)
        if campus_turn:
            segments.insert(0, (campus_turn, tuple(r.request_id for r in riders)))
    else:
        board = {r.request_id: float(r.start_km) for r in riders}
        drop = {r.request_id: 0.0 for r in riders}
        solo = {r.request_id: abs(board[r.request_id]) + _turn_km(r.start_side_m) + _turn_km(r.end_side_m)
                for r in riders}
        ordered = tuple(sorted(riders, key=lambda r: (-board[r.request_id], r.request_id)))
        route_km = max(board.values(), default=0.0) + sum(
            _turn_km(r.start_side_m) + _turn_km(r.end_side_m) for r in riders
        )
        marks = sorted({0.0, *board.values()}, reverse=True)
        segments = []
        for hi, lo in zip(marks, marks[1:]):
            onboard = tuple(r.request_id for r in riders if board[r.request_id] >= hi)
            if hi > lo and onboard:
                segments.append((hi - lo, onboard))
        for r in ordered:
            turn = _turn_km(r.start_side_m)
            if turn:
                segments.append((turn, tuple(x.request_id for x in ordered if board[x.request_id] >= board[r.request_id])))
        campus_turn = sum(_turn_km(r.end_side_m) for r in riders)
        if campus_turn:
            segments.append((campus_turn, tuple(r.request_id for r in riders)))
        deadline = min(r.arrive_by for r in riders)
        start_time = deadline - timedelta(hours=route_km / config.SPEED_KMH)
        end_time = start_time + timedelta(hours=route_km / config.SPEED_KMH)

    # The tariff is fixed to the approved day rate for this demo.
    fare = config.START_DAY + round(config.PER_KM_DAY * route_km)
    solo_fares = {r.request_id: config.START_DAY + round(config.PER_KM_DAY * solo[r.request_id]) for r in riders}
    rider_ids = [r.request_id for r in riders]
    shares = _street_shares(fare, rider_ids, segments, solo_fares)
    if not shares:
        return None
    if from_campus:
        campus_detour = sum(_turn_km(r.start_side_m) for r in riders)
        in_car = {
            r.request_id: drop[r.request_id] + campus_detour + sum(
                _turn_km(other.end_side_m) for other in riders
                if drop[other.request_id] <= drop[r.request_id]
            )
            for r in riders
        }
    else:
        campus_detour = sum(_turn_km(r.end_side_m) for r in riders)
        in_car = {
            r.request_id: board[r.request_id] + campus_detour + _turn_km(r.start_side_m) + sum(
                _turn_km(other.start_side_m) for other in riders
                if board[other.request_id] < board[r.request_id]
            )
            for r in riders
        }
    if strict:
        if any(in_car[r.request_id] > min(solo[r.request_id] * config.DETOUR_RATIO,
                                         solo[r.request_id] + config.DETOUR_EXTRA_KM) + 1e-9 for r in riders):
            return None
        if len(riders) > 1 and any(shares[rid] > (1 - config.MIN_SAVING) * solo_fares[rid] for rid in shares):
            return None
        if any(r.quoted_share is not None and shares[r.request_id] > r.quoted_share for r in riders):
            return None
    arrivals = {}
    if from_campus:
        for r in riders:
            arrivals[r.request_id] = start_time + timedelta(hours=in_car[r.request_id] / config.SPEED_KMH)
    else:
        for r in riders:
            arrivals[r.request_id] = start_time + timedelta(
                hours=(route_km - in_car[r.request_id]) / config.SPEED_KMH
            )
    return GroupPlan(
        riders=ordered, route_km=route_km, car_fare=fare, shares=shares, solo_km=solo,
        solo_fare=solo_fares, in_car_km=in_car, pickup_time=start_time, arrival=arrivals,
        board_km=board, drop_km=drop,
        walk_m={r.request_id: _walk_distance(r.start_side_m) for r in riders},
        segments=tuple(segments),
    )
