import pytest

from pooling.geo import minutes_for, road_km
from pooling.places import CAMPUSES, STOPS, Stop


def test_road_km_is_haversine_times_factor():
    a, b = Stop("a", "a", 32.0, 35.0), Stop("b", "b", 32.0, 35.1)
    assert road_km(a, b) == pytest.approx(9.43 * 1.35, rel=0.01)


def test_stops_within_merge_radius_are_zero():
    a, b = Stop("a", "a", 32.0, 35.0), Stop("b", "b", 32.0, 35.002)  # about 0.19 km
    assert road_km(a, b) == 0.0


def test_minutes_for_uses_25_kmh():
    assert minutes_for(12.5) == pytest.approx(30.0)


def test_seed_stops_exist():
    assert {"sweileh", "zarqa"} <= STOPS.keys()
    assert "ahu-main-gate" in CAMPUSES["ahu"].meeting_points
