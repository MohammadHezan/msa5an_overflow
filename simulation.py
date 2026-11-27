"""Deterministic, explicitly simulated comparisons for the judge-facing dashboard."""
from datetime import datetime, timedelta
from functools import lru_cache
import random

from pooling import config
from pooling.model import Rider, evaluate
from pooling.places import CORRIDORS, DEMO_CAMPUS
from pooling.regroup import regroup

METHODS = ("alone", "greedy", "optimizer")
COUNTS = (8, 16, 24, 32)
SEEDS = tuple(range(30))


def _clock(hour, minute):
    return datetime(2026, 11, 28, hour, minute, tzinfo=config.TZ)


def _scenario(n, seed):
    rng = random.Random(seed * 1009 + n)
    result = []
    corridors = list(CORRIDORS.items())
    for i in range(n):
        corridor, info = rng.choice(corridors)
        direction = "to_campus" if rng.random() < 0.5 else "from_campus"
        stop, stop_km = rng.choice(list(info["stops"].items()))
        km = max(1.0, stop_km + rng.uniform(-1.0, 1.0))
        side = rng.randint(0, 400)
        campus_side = rng.randint(0, 400)
        gender = "woman" if rng.random() < 0.5 else "man"
        preference = "mixed"
        if rng.random() < 0.2:
            preference = "women" if gender == "woman" else "men"
        minute = rng.choice([0, 5, 10, 15, 20, 25, 30])
        if direction == "from_campus":
            base = _clock(15, minute)
            ready = base + timedelta(seconds=min(campus_side, config.MAX_WALK_M) / config.WALK_SPEED_MPS)
            start_km, start_side, end_km, end_side = 0.0, campus_side, km, side
            arrive_by = None
        else:
            base = _clock(8, minute)
            arrive_by = base - timedelta(minutes=5)
            ready = None
            start_km, start_side, end_km, end_side = km, side, 0.0, campus_side
        result.append(Rider(
            request_id=str(i), first_name=f"Student{i}", campus_id=DEMO_CAMPUS,
            meeting_point_id=info["gate"], stop_id=stop.lower().replace(" ", "-"),
            leave_after=ready or arrive_by, leave_before=(ready or arrive_by) + timedelta(minutes=15),
            gender=gender, preference=preference, direction=direction, corridor=corridor,
            start_km=start_km, start_side_m=start_side, end_km=end_km, end_side_m=end_side,
            ready_at=ready, arrive_by=arrive_by,
        ))
    return result


def _greedy(riders):
    """First-come incremental grouping, using exactly the same feasibility test as the optimizer."""
    ordered = sorted(riders, key=lambda r: (
        r.ready_at or r.arrive_by, r.corridor, r.request_id
    ))
    groups = []
    for rider in ordered:
        candidates = []
        for index, group in enumerate(groups):
            if len(group.riders) >= config.MAX_RIDERS:
                continue
            plan = evaluate([*group.riders, rider])
            if plan:
                candidates.append((plan.car_fare - group.car_fare, index, plan))
        if candidates:
            _, index, plan = min(candidates, key=lambda row: (row[0], row[1]))
            groups[index] = plan
        else:
            groups.append(evaluate([rider]))
    return groups


def _metrics(groups, singles):
    riders = [r for group in groups for r in group.riders]
    solo_distance = sum(plan.route_km for plan in singles)
    trip_distance = sum(plan.route_km for plan in groups)
    solo_fares = sum(plan.car_fare for plan in singles)
    paid = sum(sum(plan.shares.values()) for plan in groups)
    matched = sum(len(plan.riders) for plan in groups if len(plan.riders) > 1)
    walks = []
    extra_minutes = []
    for plan in groups:
        for rider in plan.riders:
            walks.extend((min(rider.start_side_m, config.MAX_WALK_M), min(rider.end_side_m, config.MAX_WALK_M)))
            extra_minutes.append(max(0, plan.in_car_km[rider.request_id] - plan.solo_km[rider.request_id])
                                 * 60 / config.SPEED_KMH)
    return {
        "cars": len(groups),
        "car_km": trip_distance,
        "km_saved_pct": (solo_distance - trip_distance) * 100 / solo_distance if solo_distance else 0,
        "matched_pct": matched * 100 / len(riders) if riders else 0,
        "saving_fils_per_rider": (solo_fares - paid) / len(riders) if riders else 0,
        "walk_m": sum(walks) / len(walks) if walks else 0,
        "extra_minutes": sum(extra_minutes) / len(extra_minutes) if extra_minutes else 0,
    }


@lru_cache(maxsize=1)
def run_simulation():
    """Run 30 paired seeds per wave size; shorten per-solve time without changing constraints."""
    result = {n: {method: [] for method in METHODS} for n in COUNTS}
    old_seconds = config.SOLVER_SECONDS
    config.SOLVER_SECONDS = min(old_seconds, 0.15)
    try:
        for n in COUNTS:
            for seed in SEEDS:
                riders = _scenario(n, seed)
                singles = [evaluate([r]) for r in riders]
                plans_by_method = {
                    "alone": singles,
                    "greedy": _greedy(riders),
                    "optimizer": regroup(singles),
                }
                for method, plans in plans_by_method.items():
                    result[n][method].append(_metrics(plans, singles))
    finally:
        config.SOLVER_SECONDS = old_seconds
    summary = {}
    for n in COUNTS:
        summary[n] = {}
        for method in METHODS:
            metrics = result[n][method]
            summary[n][method] = {}
            for key in metrics[0]:
                values = [float(item[key]) for item in metrics]
                summary[n][method][key] = {
                    "mean": sum(values) / len(values), "min": min(values), "max": max(values),
                }
    return {"counts": COUNTS, "seeds": len(SEEDS), "summary": summary}
