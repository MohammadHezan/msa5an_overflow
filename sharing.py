"""Shared-ride rules: destinations, fares, grouping, and price splits.

Every distance, fare and gate here is a simulated assumption for the demo.
"""
import math

from ortools.sat.python import cp_model

# Directions leaving the demo campus. Each has a meeting gate and ordered drop-offs (km from campus).
CORRIDORS = {
    "West": {"gate": "Main gate", "stops": {"Sweileh": 5, "Khalda": 8, "Dabouq": 12, "Al Bayader": 14, "Wadi As-Seer": 16}},
    "North": {"gate": "North gate", "stops": {"Al Jubeiha": 3, "Shafa Badran": 7, "Abu Nseir": 10}},
    "South": {"gate": "Main gate", "stops": {"Tla' Al Ali": 4, "Um Al Summaq": 7, "Abdoun": 12}},
    "East": {"gate": "East gate", "stops": {"Tabarbour": 9, "Marka": 13}},
}
STOPS = {stop: {"corridor": name, "km": km} for name, corridor in CORRIDORS.items() for stop, km in corridor["stops"].items()}

# Approximate (simulated) map positions as (latitude, longitude). Good enough to sketch a route, not for navigation.
GATES = {"Main gate": (32.0130, 35.8705), "North gate": (32.0215, 35.8730), "East gate": (32.0165, 35.8795)}
COORDS = {
    "Sweileh": (32.0236, 35.8411), "Khalda": (31.9986, 35.8494), "Dabouq": (31.9930, 35.8270),
    "Al Bayader": (31.9620, 35.8420), "Wadi As-Seer": (31.9480, 35.8120),
    "Al Jubeiha": (32.0310, 35.8700), "Shafa Badran": (32.0500, 35.8850), "Abu Nseir": (32.0620, 35.8780),
    "Tla' Al Ali": (31.9960, 35.8600), "Um Al Summaq": (31.9840, 35.8450), "Abdoun": (31.9500, 35.8830),
    "Tabarbour": (32.0120, 35.9350), "Marka": (31.9830, 35.9790),
}

BASE_FARE = 900  # Fils
PER_KM = 300
STOP_FEE = 250  # Each extra drop-off in a shared car
SHARED_RATE = 0.85  # Shared cars are billed at 85% of the car fare
MIN_SHARE = 500
SEATS = 4
MAX_GAP = 20  # Minutes between the earliest and latest class end in one car
WALK = 15  # Minutes from the last class ending to pickup at the gate


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


def solo_fare(stop):
    return BASE_FARE + PER_KM * STOPS[stop]["km"]


def round_fils(value):
    return int(math.floor(value / 50 + 0.5)) * 50


def to_minutes(clock):
    hour, minute = map(int, clock.split(":"))
    return hour * 60 + minute


def to_clock(minutes):
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def sample_share(stop, riders=3):
    """Typical share when riding with others travelling the same distance."""
    km = STOPS[stop]["km"]
    car = (BASE_FARE + PER_KM * km + STOP_FEE * (riders - 1)) * SHARED_RATE
    return max(MIN_SHARE, round_fils(car / riders))


def compatible(a, b):
    if STOPS[a["stop"]]["corridor"] != STOPS[b["stop"]]["corridor"]:
        return False
    if abs(to_minutes(a["class_end"]) - to_minutes(b["class_end"])) > MAX_GAP:
        return False
    if (a["women_only"] and not b["woman"]) or (b["women_only"] and not a["woman"]):
        return False
    return True


def group_riders(riders):
    """Split riders into cars using as few cars as possible. Returns lists of rider ids."""
    n = len(riders)
    if not n:
        return []
    model = cp_model.CpModel()
    # Car g is led by rider g, the lowest-indexed rider in it.
    x = {(i, g): model.new_bool_var(f"x_{i}_{g}") for i in range(n) for g in range(i + 1)}
    for i in range(n):
        model.add_exactly_one(x[i, g] for g in range(i + 1))
    for g in range(n):
        members = [x[i, g] for i in range(g, n)]
        for i in range(g + 1, n):
            model.add_implication(x[i, g], x[g, g])
        model.add(sum(members) <= SEATS)
    for i in range(n):
        for j in range(i + 1, n):
            if not compatible(riders[i], riders[j]):
                for g in range(i + 1):
                    model.add_bool_or([x[i, g].Not(), x[j, g].Not()])
    model.minimize(sum(x[g, g] for g in range(n)))

    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.max_time_in_seconds = 10
    if solver.solve(model) not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError("Matching could not complete for this batch.")
    cars = {}
    for (i, g), var in x.items():
        if solver.value(var):
            cars.setdefault(g, []).append(riders[i]["id"])
    return list(cars.values())


def plan_car(members):
    """Pickup, drop-off order and each rider's share for one car's active riders."""
    members = sorted(members, key=lambda r: (STOPS[r["stop"]]["km"], r["id"]))
    corridor = STOPS[members[0]["stop"]]["corridor"]
    ready = max(to_minutes(r["class_end"]) for r in members) + WALK
    pickup = to_clock(-(-ready // 5) * 5)
    if len(members) == 1:
        only = members[0]
        return {"gate": CORRIDORS[corridor]["gate"], "corridor": corridor, "pickup": pickup, "members": members,
                "car_fare": solo_fare(only["stop"]), "shares": {only["id"]: solo_fare(only["stop"])}, "shared": False}
    longest = max(STOPS[r["stop"]]["km"] for r in members)
    car_fare = (BASE_FARE + PER_KM * longest + STOP_FEE * (len(members) - 1)) * SHARED_RATE
    total_km = sum(STOPS[r["stop"]]["km"] for r in members)
    shares = {
        r["id"]: min(solo_fare(r["stop"]), max(MIN_SHARE, round_fils(car_fare * STOPS[r["stop"]]["km"] / total_km)))
        for r in members
    }
    return {"gate": CORRIDORS[corridor]["gate"], "corridor": corridor, "pickup": pickup, "members": members,
            "car_fare": round_fils(car_fare), "shares": shares, "shared": True,
            "women_only": all(r["woman"] for r in members) and any(r["women_only"] for r in members)}
