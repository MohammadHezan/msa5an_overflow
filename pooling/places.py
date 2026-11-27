"""Campus, meeting-point and stop data.

Every coordinate here is a PLACEHOLDER from the research notes (neighbourhood
centroids, about +/-0.5 km). Check them on a map before the demo.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Stop:
    id: str
    name: str
    lat: float
    lon: float
    # Corridor model (the Replit demo campus): km from campus along a named direction.
    # When both ends have it, road distance follows the corridor instead of the straight line.
    corridor: str | None = None
    km: float | None = None


@dataclass(frozen=True)
class Campus:
    id: str
    name: str
    meeting_points: dict[str, Stop] = field(hash=False)


def _stops(*rows):
    return {row[0]: Stop(*row) for row in rows}


# ---- Demo campus used by the Replit app (sharing.py, store.py, api.py) ----
# Directions leaving the campus. Each has a meeting gate and ordered drop-offs (km from campus).
CORRIDORS = {
    "West": {"gate": "Main gate", "stops": {"Sweileh": 5, "Khalda": 8, "Dabouq": 12, "Al Bayader": 14, "Wadi As-Seer": 16}},
    "North": {"gate": "North gate", "stops": {"Al Jubeiha": 3, "Shafa Badran": 7, "Abu Nseir": 10}},
    "South": {"gate": "Main gate", "stops": {"Tla' Al Ali": 4, "Um Al Summaq": 7, "Abdoun": 12}},
    "East": {"gate": "East gate", "stops": {"Tabarbour": 9, "Marka": 13}},
}
# Approximate (simulated) map positions as (latitude, longitude).
GATES = {"Main gate": (32.0130, 35.8705), "North gate": (32.0215, 35.8730), "East gate": (32.0165, 35.8795)}
COORDS = {
    "Sweileh": (32.0236, 35.8411), "Khalda": (31.9986, 35.8494), "Dabouq": (31.9930, 35.8270),
    "Al Bayader": (31.9620, 35.8420), "Wadi As-Seer": (31.9480, 35.8120),
    "Al Jubeiha": (32.0310, 35.8700), "Shafa Badran": (32.0500, 35.8850), "Abu Nseir": (32.0620, 35.8780),
    "Tla' Al Ali": (31.9960, 35.8600), "Um Al Summaq": (31.9840, 35.8450), "Abdoun": (31.9500, 35.8830),
    "Tabarbour": (32.0120, 35.9350), "Marka": (31.9830, 35.9790),
}
DEMO_CAMPUS = "campus"

CAMPUSES = {
    DEMO_CAMPUS: Campus(
        DEMO_CAMPUS,
        "Demo campus",
        {gate: Stop(gate, gate, *latlon, corridor=None, km=0.0) for gate, latlon in GATES.items()},
    ),
    "ahu": Campus(
        "ahu",
        "Al-Ahliyya Amman University",
        _stops(("ahu-main-gate", "Main gate", 32.0420, 35.7240)),
    ),
}

STOPS = _stops(
    # North-east corridor (Salt road -> Sweileh -> Jubeiha)
    ("sweileh", "Sweileh", 32.0237, 35.8401),
    ("sweileh-circle", "Sweileh circle", 32.0262, 35.8460),
    ("university-street", "University Street", 32.0190, 35.8600),
    ("al-jubeiha", "Al Jubeiha", 32.0275, 35.8710),
    # South corridor (Khalda -> Abdoun)
    ("khalda", "Khalda", 31.9905, 35.8410),
    ("tla-al-ali", "Tla' Al-Ali", 31.9990, 35.8530),
    ("um-uthaina", "Um Uthaina", 31.9700, 35.8700),
    ("abdoun", "Abdoun", 31.9500, 35.8820),
    # East corridor
    ("tabarbour", "Tabarbour", 31.9975, 35.9370),
    ("marka", "Marka", 31.9740, 35.9900),
    # Far away
    ("zarqa", "Zarqa", 32.0728, 36.0880),
)
STOPS.update({
    stop: Stop(stop, stop, *COORDS[stop], corridor=direction, km=float(km))
    for direction, info in CORRIDORS.items()
    for stop, km in info["stops"].items()
})
