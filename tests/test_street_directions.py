from datetime import timedelta

from pooling.model import evaluate
from tests.helpers import at, rider


def street(rid, direction, start_km, end_km, arrive_by=None, ready_at=None, corridor="West",
           start_side=0, end_side=0, gender="woman", preference="mixed"):
    return rider(
        rid, "Dabouq", after="16:00", before="16:30", gender=gender, preference=preference,
    ).__class__(
        request_id=rid, first_name=rid.title(), campus_id="demo", meeting_point_id="Main gate",
        stop_id="Dabouq", leave_after=ready_at or arrive_by or at("16:00"),
        leave_before=(ready_at or arrive_by or at("16:00")) + timedelta(minutes=20),
        direction=direction, corridor=corridor, start_km=start_km, start_side_m=start_side,
        end_km=end_km, end_side_m=end_side, ready_at=ready_at, arrive_by=arrive_by,
        gender=gender, preference=preference,
    )


def test_to_campus_orders_pickups_inward_and_sets_individual_times():
    deadline = at("08:00")
    plan = evaluate([
        street("far", "to_campus", 10, 0, arrive_by=deadline),
        street("near", "to_campus", 5, 0, arrive_by=deadline),
    ])
    assert plan is not None
    assert [r.request_id for r in plan.riders] == ["far", "near"]
    assert plan.route_km == 10
    assert plan.arrival["far"] < plan.arrival["near"] < deadline
    assert plan.car_fare == sum(plan.shares.values())
    assert all(plan.shares[rid] <= plan.solo_fare[rid] for rid in plan.shares)
    assert plan.shares["near"] < plan.shares["far"]


def test_from_campus_dropoff_segments_reduce_early_riders_share():
    ready = at("16:00")
    plan = evaluate([
        street("near", "from_campus", 0, 5, ready_at=ready),
        street("far", "from_campus", 0, 10, ready_at=ready),
    ])
    assert plan is not None
    assert plan.shares["near"] < plan.shares["far"]
    assert sum(plan.shares.values()) == plan.car_fare
    assert all(plan.shares[rid] <= plan.solo_fare[rid] for rid in plan.shares)


def test_one_street_rider_pays_exact_solo_fare_and_walk_is_capped():
    rider = street("single", "from_campus", 0, 8, ready_at=at("16:00"), start_side=350, end_side=150)
    plan = evaluate([rider])
    assert plan is not None
    assert plan.shares["single"] == plan.solo_fare["single"]
    assert plan.route_km == plan.solo_km["single"]
    assert plan.walk_m["single"] == 200


def test_street_walk_threshold_adds_only_excess_distance_to_the_car():
    from dataclasses import replace

    base = street("single", "from_campus", 0, 8, ready_at=at("16:00"),
                  start_side=200, end_side=200)
    at_limit = evaluate([base])
    beyond_limit = evaluate([replace(base, start_side_m=350, end_side_m=400)])
    assert at_limit.route_km == 8
    assert abs(beyond_limit.route_km - 8.7) < 1e-9
    assert at_limit.walk_m["single"] == beyond_limit.walk_m["single"] == 200
    assert beyond_limit.in_car_km["single"] == beyond_limit.solo_km["single"]
    assert beyond_limit.shares["single"] == beyond_limit.car_fare == beyond_limit.solo_fare["single"]


def test_demo_street_locations_are_repeatable_and_near_each_stop():
    from sharing import STOPS
    from store import _street_location

    for stop, info in STOPS.items():
        for direction in ("from_campus", "to_campus"):
            location = _street_location("Demo student", stop, direction)
            assert location == _street_location("Demo student", stop, direction)
            corridor, start, start_side, end, end_side = location
            assert corridor == info["corridor"]
            assert 0 <= start_side <= 400 and 0 <= end_side <= 400
            assert abs((start if direction == "to_campus" else end) - info["km"]) <= 1
            assert (end if direction == "to_campus" else start) == 0


def test_direction_and_corridor_are_hard_matching_rules():
    ready = at("16:00")
    west = street("west", "from_campus", 0, 8, ready_at=ready)
    east = street("east", "from_campus", 0, 8, ready_at=ready, corridor="East")
    morning = street("morning", "to_campus", 8, 0, arrive_by=at("08:00"))
    assert evaluate([west, east]) is None
    assert evaluate([west, morning]) is None


def test_time_gap_uses_ready_at_and_arrive_by():
    assert evaluate([
        street("a", "from_campus", 0, 8, ready_at=at("16:00")),
        street("b", "from_campus", 0, 9, ready_at=at("16:11")),
    ]) is None
    assert evaluate([
        street("a", "to_campus", 8, 0, arrive_by=at("08:00")),
        street("b", "to_campus", 9, 0, arrive_by=at("08:11")),
    ]) is None


def test_other_riders_turn_ins_count_toward_street_detour():
    riders = [
        street("short", "from_campus", 0, 1, ready_at=at("16:00")),
        *(street(str(i), "from_campus", 0, 8, ready_at=at("16:00"), start_side=400)
          for i in range(3)),
    ]
    relaxed = evaluate(riders, strict=False)
    assert relaxed.in_car_km["short"] > relaxed.solo_km["short"] * 1.5
    assert evaluate(riders) is None


def test_street_cars_enforce_preferences_seats_and_individual_savings():
    from dataclasses import replace

    woman = street("woman", "from_campus", 0, 8, ready_at=at("16:00"),
                   gender="woman", preference="women")
    man = replace(woman, request_id="man", gender="man", preference="mixed")
    assert evaluate([woman, man]) is None
    women = [replace(woman, request_id=str(i)) for i in range(4)]
    plan = evaluate(women)
    assert plan is not None
    assert all(plan.shares[rid] <= .75 * plan.solo_fare[rid] for rid in plan.shares)
    assert evaluate([*women, replace(woman, request_id="fifth")]) is None
