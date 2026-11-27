""""Your chance of sharing": Monte Carlo over forecast demand, decided by the real matching rules.

For one request, each draw samples the other students who might book on the same corridor and direction
around that time (Poisson counts from pooling.forecast), gives them random stops, genders, ride options
and limits like simulation.py, and asks the engine (pooling.model.evaluate, every rule: gender, gate wait,
extra ride time, savings) for the best car of up to four that contains the student. Greedy insertion is
used per draw instead of CP-SAT so one answer takes well under a second.

Everything here is simulated: the demand comes from the synthetic history in pooling.forecast.
"""
import random
import zlib
from datetime import datetime, timedelta
from functools import lru_cache

from pooling import config, forecast
from pooling.model import Rider, evaluate
from pooling.places import CORRIDORS, DEMO_CAMPUS

SAMPLES = 40
SHIFTS_MIN = (-10, -5, 5, 10, 15)
MIN_GAIN = 0.05            # a suggestion must raise the chance by at least 5 points
WINDOW_MIN = config.MAX_GAP_MIN
LIMIT_CHOICES = ((5, 10, 15), (0.25, 0.5, 0.25))
SINGLE_GENDER_SHARE = 0.2


def _clock(day, minute):
    return datetime(day.year, day.month, day.day, tzinfo=config.TZ) + timedelta(minutes=minute)


def _rider(rid, day, corridor, direction, stop, minute, gender, preference, gate_wait, extra_ride, side=60, campus_side=60):
    km = float(CORRIDORS[corridor]["stops"][stop])
    if direction == "from_campus":
        ready = _clock(day, minute) + timedelta(seconds=min(campus_side, config.MAX_WALK_M) / config.WALK_SPEED_MPS)
        arrive_by, start_km, start_side, end_km, end_side = None, 0.0, campus_side, km, side
    else:
        ready, arrive_by = None, _clock(day, minute) - timedelta(minutes=5)
        start_km, start_side, end_km, end_side = km, side, 0.0, campus_side
    moment = ready or arrive_by
    return Rider(
        request_id=rid, first_name=rid, campus_id=DEMO_CAMPUS, meeting_point_id=CORRIDORS[corridor]["gate"],
        stop_id=stop.lower().replace(" ", "-"), leave_after=moment, leave_before=moment + timedelta(minutes=15),
        gender=gender, preference=preference, direction=direction, corridor=corridor,
        start_km=start_km, start_side_m=start_side, end_km=end_km, end_side_m=end_side,
        ready_at=ready, arrive_by=arrive_by, max_gate_wait_min=gate_wait, max_extra_ride_min=extra_ride,
    )


def corridor_of(stop):
    return next((name for name, info in CORRIDORS.items() if stop in info["stops"]), None)


def _best_share(me, others):
    """Greedy: keep adding the student who lowers my share most while every rule passes. Returns my share or None."""
    group, best = [me], None
    pool = list(others)
    while len(group) < config.MAX_RIDERS and pool:
        choice = None
        for other in pool:
            plan = evaluate([*group, other])
            if plan and (choice is None or plan.shares[me.request_id] < choice[0]):
                choice = (plan.shares[me.request_id], other)
        if choice is None:
            break
        best = choice[0]
        group.append(choice[1])
        pool.remove(choice[1])
    return best


def _chance(day, stop, direction, minute, gender, preference, gate_wait, extra_ride):
    corridor = corridor_of(stop)
    me = _rider("me", day, corridor, direction, stop, minute, gender, preference, gate_wait, extra_ride)
    solo = evaluate([me]).car_fare
    stops = list(CORRIDORS[corridor]["stops"])
    expected = sum(forecast.rate_per_minute(day, corridor, direction, m)
                   for m in range(minute - WINDOW_MIN, minute + WINDOW_MIN + 1))
    seed = zlib.crc32(f"{day}|{stop}|{direction}|{minute}|{gender}|{preference}|{gate_wait}|{extra_ride}".encode())
    rng = random.Random(seed)
    shared, shares = 0, []
    for _ in range(SAMPLES):
        count = _poisson(rng, expected)
        others = []
        for i in range(count):
            g = "woman" if rng.random() < 0.5 else "man"
            pref = ("women" if g == "woman" else "men") if rng.random() < SINGLE_GENDER_SHARE else "mixed"
            others.append(_rider(
                f"o{i}", day, corridor, direction, rng.choice(stops), minute + rng.randint(-WINDOW_MIN, WINDOW_MIN),
                g, pref, rng.choices(*LIMIT_CHOICES)[0], rng.choices(*LIMIT_CHOICES)[0],
                side=rng.randint(0, 300), campus_side=rng.randint(0, 300)))
        share = _best_share(me, others)
        if share is not None:
            shared += 1
            shares.append(share)
    return {"chance": shared / SAMPLES, "expected_share_fils": round(sum(shares) / len(shares)) if shares else None,
            "solo_fare_fils": solo, "expected_requests_nearby": round(expected, 2)}


def _poisson(rng, lam):
    """Knuth's method; lam is small (a handful of students around one time)."""
    if lam <= 0:
        return 0
    limit, k, p = pow(2.718281828459045, -lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


@lru_cache(maxsize=512)
def match_chance(stop, direction, time, gender, preference="mixed", gate_wait=config.DEFAULT_MAX_GATE_WAIT_MIN,
                 extra_ride=config.DEFAULT_MAX_EXTRA_RIDE_MIN, day=None):
    """Chance of a shared car for this request, expected share, and up to two better times."""
    day = forecast.as_date(day or forecast.DEFAULT_DATE)
    hour, minute = map(int, time.split(":"))
    at = hour * 60 + minute
    base = _chance(day, stop, direction, at, gender, preference, gate_wait, extra_ride)
    better = []
    for shift in SHIFTS_MIN:
        if not forecast.SERVICE_START <= at + shift < forecast.SERVICE_END:
            continue
        other = _chance(day, stop, direction, at + shift, gender, preference, gate_wait, extra_ride)
        if other["chance"] >= base["chance"] + MIN_GAIN:
            better.append({"shiftMinutes": shift, "time": forecast.slot_label(at + shift), **other})
    better.sort(key=lambda s: (-s["chance"], abs(s["shiftMinutes"])))
    return {**base, "samples": SAMPLES, "day": day.isoformat(), "suggestions": better[:2]}
