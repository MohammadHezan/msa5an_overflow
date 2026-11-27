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
