"""Deterministic, explicitly simulated comparisons for the judge-facing dashboard.

Simulation v2 follows the real product rules. Every student has their own gate-wait and
extra-ride limits, and about 15% of students book as a friends group of 2-3 (about a third of
the groups are closed: no strangers). All three methods see the same scenario:
- alone: everyone rides solo;
- greedy: first-come, a friends group placed as one unit;
- optimizer: pooling.regroup with the friends groups as `together` / `closed`.
"""
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
SOLVE_SECONDS = min(config.SOLVER_SECONDS, 0.15)  # per-solve cap; the constraints stay the same

LIMIT_CHOICES = (5, 10, 15)          # minutes, for both max_gate_wait_min and max_extra_ride_min
LIMIT_WEIGHTS = (0.25, 0.5, 0.25)    # the config default (10) is the most common choice
FRIENDS_SHARE = 0.15                 # share of students who book as part of a friends group
FRIENDS_SIZES = (2, 3)
FRIENDS_CLOSED_SHARE = 1 / 3         # closed groups take no strangers
FRIENDS_TIME_MIN = 5                 # a friend's class time is within this many minutes of the anchor's
FRIEND_DRAWS = 20                    # re-draws of a friend that would fail join validation
SINGLE_GENDER_SHARE = 0.2            # students asking for a women-only or men-only car
SINGLE = {"woman": "women", "man": "men"}


def _clock(hour, minute):
    return datetime(2026, 11, 28, hour, minute, tzinfo=config.TZ)


def _limits(rng):
    return {"gate_wait": rng.choices(LIMIT_CHOICES, LIMIT_WEIGHTS)[0],
            "extra_ride": rng.choices(LIMIT_CHOICES, LIMIT_WEIGHTS)[0]}


def _student(rng):
    """One independent student (same draws, in the same order, as simulation v1)."""
    corridor, info = rng.choice(list(CORRIDORS.items()))
    direction = "to_campus" if rng.random() < 0.5 else "from_campus"
    stop, stop_km = rng.choice(list(info["stops"].items()))
    km = max(1.0, stop_km + rng.uniform(-1.0, 1.0))
    side = rng.randint(0, 400)
    campus_side = rng.randint(0, 400)
    gender = "woman" if rng.random() < 0.5 else "man"
    preference = "mixed"
    if rng.random() < SINGLE_GENDER_SHARE:
        preference = SINGLE[gender]
    minute = rng.choice([0, 5, 10, 15, 20, 25, 30])
    return {"corridor": corridor, "direction": direction, "stop": stop, "km": km, "side": side,
            "campus_side": campus_side, "gender": gender, "preference": preference, "minute": minute}


def _rider(i, s):
    """The engine Rider for one drawn student. `minute` is the class end (15:00 + m) or start (08:00 + m)."""
    if s["direction"] == "from_campus":
        base = _clock(15, 0) + timedelta(minutes=s["minute"])
        ready = base + timedelta(seconds=min(s["campus_side"], config.MAX_WALK_M) / config.WALK_SPEED_MPS)
        start_km, start_side, end_km, end_side = 0.0, s["campus_side"], s["km"], s["side"]
        arrive_by = None
    else:
        base = _clock(8, 0) + timedelta(minutes=s["minute"])
        arrive_by = base - timedelta(minutes=5)
        ready = None
        start_km, start_side, end_km, end_side = s["km"], s["side"], 0.0, s["campus_side"]
    moment = ready or arrive_by
    return Rider(
        request_id=str(i), first_name=f"Student{i}", campus_id=DEMO_CAMPUS,
        meeting_point_id=CORRIDORS[s["corridor"]]["gate"], stop_id=s["stop"].lower().replace(" ", "-"),
        leave_after=moment, leave_before=moment + timedelta(minutes=15),
        gender=s["gender"], preference=s["preference"], direction=s["direction"], corridor=s["corridor"],
        start_km=start_km, start_side_m=start_side, end_km=end_km, end_side_m=end_side,
        ready_at=ready, arrive_by=arrive_by,
        max_gate_wait_min=s["gate_wait"], max_extra_ride_min=s["extra_ride"],
    )


def _group_sizes(n, rng):
    """Friends groups of 2-3 covering about FRIENDS_SHARE of n students (at least one group from n = 4)."""
    left = max(2, round(n * FRIENDS_SHARE)) if n >= 4 else 0
    sizes = []
    while left >= 2:
        size = left if left <= 3 else 2 if left == 4 else rng.choice(FRIENDS_SIZES)  # never leave one over
        sizes.append(size)
        left -= size
    return sizes


def _friend(rng, group):
    """A friend booking with group[0] (the anchor): same corridor, direction and class time
    (within FRIENDS_TIME_MIN minutes), a different stop on the same corridor.

    Friends are gender-compatible: once anyone asked for a single-gender car, every friend has
    that gender, and a friend only asks for one if the whole group already has their gender.
    The app only accepts a join that passes evaluate(strict=False) (sharing.group_problem), so a
    friend failing it is re-drawn; the last resort copies the latest-ready friend's time.
    """
    anchor = group[0]
    stops = CORRIDORS[anchor["corridor"]]["stops"]
    others = [stop for stop in stops if stop != anchor["stop"]]
    fresh = [stop for stop in others if all(stop != m["stop"] for m in group)] or others
    asked = next((m["gender"] for m in group if m["preference"] != "mixed"), None)
    for _ in range(FRIEND_DRAWS):
        stop = rng.choice(fresh)
        gender = asked or ("woman" if rng.random() < 0.5 else "man")
        wants_single = rng.random() < SINGLE_GENDER_SHARE
        friend = {
            "corridor": anchor["corridor"], "direction": anchor["direction"], "stop": stop,
            "km": max(1.0, stops[stop] + rng.uniform(-1.0, 1.0)),
            "side": rng.randint(0, 400), "campus_side": rng.randint(0, 400), "gender": gender,
            "preference": SINGLE[gender] if wants_single and all(m["gender"] == gender for m in group) else "mixed",
            "minute": anchor["minute"] + rng.randint(-FRIENDS_TIME_MIN, FRIENDS_TIME_MIN),
            **_limits(rng),
        }
        if evaluate([_rider(i, s) for i, s in enumerate([*group, friend])], strict=False) is not None:
            return friend
    # Ready when the car already leaves: no one's wait, gap or detour changes (from_campus only fails above).
    latest = max(group, key=lambda m: m["minute"] * 60 + min(m["campus_side"], config.MAX_WALK_M) / config.WALK_SPEED_MPS)
    return {**friend, "minute": latest["minute"], "campus_side": latest["campus_side"]}


def _scenario(n, seed):
    """Exactly n simulated students and their friends groups, deterministic per (n, seed).

    Returns (riders, groups): groups is a list of (frozenset of request ids, closed).
    """
    rng = random.Random(seed * 1009 + n)
    friends_rng = random.Random(seed * 1009 + n + 1_000_003)  # its own stream: students stay as in v1
    sizes = _group_sizes(n, friends_rng)
    specs = [_student(rng) for _ in range(n - sum(sizes) + len(sizes))]
    for spec in specs:
        spec.update(_limits(rng))
    groups = []
    for anchor, size in zip(friends_rng.sample(range(len(specs)), len(sizes)), sizes):
        members = [anchor]
        for _ in range(size - 1):
            specs.append(_friend(friends_rng, [specs[i] for i in members]))
            members.append(len(specs) - 1)
        groups.append((frozenset(str(i) for i in members), friends_rng.random() < FRIENDS_CLOSED_SHARE))
    return [_rider(i, spec) for i, spec in enumerate(specs)], groups


def _first_come(rider):
    return rider.ready_at or rider.arrive_by, rider.corridor, rider.request_id


def _greedy(riders, groups=()):
    """First-come incremental grouping, using exactly the same feasibility test as the optimizer.

    A friends group is one unit, placed at its earliest member's time: it is never split, and a
    closed group neither takes nor joins strangers. Like regroup, a friends group that fails the
    strict rules together still rides together, priced with evaluate(strict=False); anyone joining
    it later must pass the strict rules with the whole car.
    """
    unit_of = {rid: ids for ids, _ in groups for rid in ids}
    closed = {ids for ids, is_closed in groups if is_closed}
    units = {}
    for rider in riders:
        units.setdefault(unit_of.get(rider.request_id, frozenset([rider.request_id])), []).append(rider)
    ordered = sorted(units.items(), key=lambda item: min(map(_first_come, item[1])))
    cars = []  # [plan, locked]: a car with a closed group takes no one else
    for key, members in ordered:
        members = sorted(members, key=_first_come)
        candidates = []
        if key not in closed:
            for index, (plan, locked) in enumerate(cars):
                if locked or len(plan.riders) + len(members) > config.MAX_RIDERS:
                    continue
                joined = evaluate([*plan.riders, *members])
                if joined:
                    candidates.append((joined.car_fare - plan.car_fare, index, joined))
        if candidates:
            _, index, joined = min(candidates, key=lambda row: (row[0], row[1]))
            cars[index][0] = joined
            continue
        plan = evaluate(members) or evaluate(members, strict=False)
        if plan is None:  # Impossible together (the app rejects such a join); regroup does not force it either
            cars.extend([evaluate([r]), False] for r in members)
        else:
            cars.append([plan, key in closed])
    return [plan for plan, _ in cars]


def _optimizer(singles, groups=(), solver_seconds=SOLVE_SECONDS):
    return regroup(singles, together=[ids for ids, _ in groups],
                   closed=[ids for ids, is_closed in groups if is_closed], solver_seconds=solver_seconds)


def _metrics(groups, singles, friends=()):
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
    car_of = {r.request_id: plan.ids for plan in groups for r in plan.riders}
    together = sum(1 for ids, _ in friends if len({car_of[rid] for rid in ids}) == 1)
    return {
        "cars": len(groups),
        "car_km": trip_distance,
        "km_saved_pct": (solo_distance - trip_distance) * 100 / solo_distance if solo_distance else 0,
        "matched_pct": matched * 100 / len(riders) if riders else 0,
        "saving_fils_per_rider": (solo_fares - paid) / len(riders) if riders else 0,
        "walk_m": sum(walks) / len(walks) if walks else 0,
        "extra_minutes": sum(extra_minutes) / len(extra_minutes) if extra_minutes else 0,
        # Friends groups whose members all ride in one car (100 when a wave has no groups).
        "friends_together_pct": together * 100 / len(friends) if friends else 100,
        "alone_pct": (len(riders) - matched) * 100 / len(riders) if riders else 0,
        # Shared cars where someone asked for women-only or men-only (gender_ok: everyone has that gender).
        "single_gender_cars": sum(1 for plan in groups
                                  if len(plan.riders) > 1 and any(r.preference != "mixed" for r in plan.riders)),
    }


def simulate(counts=COUNTS, seeds=SEEDS, solver_seconds=SOLVE_SECONDS):
    """Paired comparison: every method gets the same scenario per (n, seed). Not cached."""
    result = {n: {method: [] for method in METHODS} for n in counts}
    for n in counts:
        for seed in seeds:
            riders, friends = _scenario(n, seed)
            singles = [evaluate([r]) for r in riders]
            plans_by_method = {
                "alone": singles,
                "greedy": _greedy(riders, friends),
                "optimizer": _optimizer(singles, friends, solver_seconds),
            }
            for method, plans in plans_by_method.items():
                result[n][method].append(_metrics(plans, singles, friends))
    summary = {}
    for n in counts:
        summary[n] = {}
        for method in METHODS:
            metrics = result[n][method]
            summary[n][method] = {}
            for key in metrics[0]:
                values = [float(item[key]) for item in metrics]
                summary[n][method][key] = {
                    "mean": sum(values) / len(values), "min": min(values), "max": max(values),
                }
    return {"counts": tuple(counts), "seeds": len(seeds), "methods": METHODS, "simulated": True, "summary": summary}


@lru_cache(maxsize=1)
def run_simulation():
    """Run 30 paired seeds per wave size; shorten per-solve time without changing constraints."""
    return simulate(COUNTS, SEEDS)
