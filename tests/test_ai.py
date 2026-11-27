"""Offline AI layer (simulated data): demand forecast, match chance, captain plan and their endpoints."""
import time

import pytest

import app as campus
from pooling import forecast
from pooling.match_chance import match_chance


@pytest.fixture
def client(tmp_path):
    campus.app.config.update(TESTING=True, DATABASE=tmp_path / "test.sqlite")
    with campus.app.test_client() as client:
        yield client


def test_history_is_deterministic_and_has_no_weekend_teaching_demand():
    a, b = forecast.synthetic_history(), forecast.synthetic_history()
    assert (a.count == b.count).all()
    assert forecast.forecast("2026-12-04", "West", "from_campus", "16:15") == 0  # Friday
    assert forecast.forecast("2026-12-05", "West", "from_campus", "16:15") == 0  # Saturday


def test_peaks_follow_the_timetable():
    day = forecast.DEFAULT_DATE
    assert forecast.forecast(day, "West", "from_campus", "16:15") > forecast.forecast(day, "West", "from_campus", "07:15")
    assert forecast.forecast(day, "West", "to_campus", "07:45") > forecast.forecast(day, "West", "to_campus", "17:45")


def test_model_beats_the_seasonal_average_on_the_held_out_weeks():
    result = forecast.backtest()
    assert result["model"]["mae"] < result["baseline"]["mae"]
    assert all(forecast.forecast(forecast.DEFAULT_DATE, c, d, s) >= 0
               for c in forecast.CORRIDOR_NAMES for d in forecast.DIRECTIONS for s in forecast.SLOTS[::8])


def test_match_chance_is_deterministic_bounded_and_sensible():
    busy = match_chance("Dabouq", "from_campus", "16:00", "man")
    assert busy == match_chance("Dabouq", "from_campus", "16:00", "man")
    quiet = match_chance("Marka", "from_campus", "19:40", "woman")
    assert 0 <= quiet["chance"] <= busy["chance"] <= 1
    assert busy["expected_share_fils"] < busy["solo_fare_fils"]
    for suggestion in quiet["suggestions"]:
        assert suggestion["chance"] >= quiet["chance"] + 0.05


def test_single_gender_option_never_raises_the_chance():
    anyone = match_chance("Khalda", "from_campus", "14:05", "woman", "mixed")
    women = match_chance("Khalda", "from_campus", "14:05", "woman", "women")
    assert women["chance"] <= anyone["chance"]


def test_endpoints_return_simulated_data(client):
    start = time.time()
    r = client.get("/api/v1/ai/match-chance?stop=Dabouq&direction=from_campus&time=16:10&gender=man&preference=men")
    assert r.status_code == 200 and r.get_json()["simulated"] is True
    assert time.time() - start < 3
    assert r.headers["Access-Control-Allow-Origin"] == "*"
    for path in ("/api/v1/ai/forecast?corridor=West", "/api/v1/ai/captain-plan", "/api/v1/ai/model-card"):
        body = client.get(path).get_json()
        assert body["simulated"] is True, path
    plan = client.get("/api/v1/ai/captain-plan").get_json()
    peak = max(plan["rows"], key=lambda row: row["expectedRequests"])
    assert peak["captains"] == plan["peakCaptains"]


@pytest.mark.parametrize("query", [
    "stop=Nowhere&time=16:00&gender=man",
    "stop=Dabouq&time=25:00&gender=man",
    "stop=Dabouq&time=16:00&gender=man&preference=women",
    "stop=Dabouq&time=16:00&gender=other",
    "stop=Dabouq&time=16:00&gender=man&maxGateWaitMinutes=abc",
    "stop=Dabouq&time=16:00&gender=man&date=tomorrow",
])
def test_match_chance_rejects_bad_input(client, query):
    r = client.get(f"/api/v1/ai/match-chance?{query}")
    assert r.status_code == 400 and r.get_json()["error"]["code"] == "invalid_input"
