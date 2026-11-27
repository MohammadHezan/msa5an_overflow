"""Distance and travel-time estimates (no maps API)."""
from math import asin, cos, radians, sin, sqrt

from pooling import config
from pooling.places import Stop

EARTH_KM = 6371.0


def _haversine_km(a: Stop, b: Stop) -> float:
    dlat, dlon = radians(b.lat - a.lat), radians(b.lon - a.lon)
    h = sin(dlat / 2) ** 2 + cos(radians(a.lat)) * cos(radians(b.lat)) * sin(dlon / 2) ** 2
    return 2 * EARTH_KM * asin(sqrt(h))


def road_km(a: Stop, b: Stop) -> float:
    """Estimated road distance. Stops closer than MERGE_KM count as the same stop."""
    km = _haversine_km(a, b) * config.ROAD_FACTOR
    return 0.0 if km < config.MERGE_KM else km


def minutes_for(km: float) -> float:
    return km / config.SPEED_KMH * 60
