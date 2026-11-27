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


@dataclass(frozen=True)
class Campus:
    id: str
    name: str
    meeting_points: dict[str, Stop] = field(hash=False)


def _stops(*rows):
    return {row[0]: Stop(*row) for row in rows}


CAMPUSES = {
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
