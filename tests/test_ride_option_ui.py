"""Backend contracts for the Jeeny chooser and demo-only student verification."""
import math
import re

import pytest

import app as campus
from pooling import config
from sharing import STOPS, sample_share, solo_fare
from store import _street_location, fare_estimates


@pytest.fixture
def client(tmp_path):
    campus.app.config.update(TESTING=True, DATABASE=tmp_path / "chooser.sqlite")
    with campus.app.test_client() as client:
        client.get("/")
        yield client


def post(client, path, **data):
    with client.session_transaction() as session:
        csrf = session["csrf"]
    return client.post(path, data={"csrf": csrf, **data})


def test_comparison_estimates_are_backend_values_for_every_destination():
    for stop, estimate in fare_estimates().items():
        assert estimate["solo"] == solo_fare(stop)
        assert estimate["shared"] == sample_share(stop)
        assert estimate["taxi"] == 390 + round(280 * STOPS[stop]["km"])
        assert estimate["comfort"] == round(estimate["solo"] * 1.3)
        assert estimate["box"] == estimate["solo"]
        assert estimate["save_percent"] == round(
            100 * (estimate["solo"] - estimate["shared"]) / estimate["solo"])
        for direction in ("from_campus", "to_campus"):
            _, _, side, _, _ = _street_location("Sara", stop, direction)
            pickup = estimate["pickups"][direction]
            assert pickup["walk_meters"] == min(side, config.MAX_WALK_M)
            assert pickup["walk_minutes"] == math.ceil(pickup["walk_meters"] / config.WALK_SPEED / 60)


def test_demo_verification_is_session_only_and_never_sends_or_keeps_email(client):
    assert post(client, "/demo/student-verification", action="reset").get_json() == {"verified": False}
    assert post(client, "/demo/student-verification", email="invalid").status_code == 400
    assert post(client, "/demo/student-verification", email="demo@cedar.example").get_json() == {"verified": True}
    with client.session_transaction() as session:
        assert session["student_verified"] is True
        assert "demo@cedar.example" not in str(dict(session))


def test_unverified_session_cannot_book_campus_even_with_direct_post(client):
    post(client, "/demo/student-verification", action="reset")
    response = post(client, "/requests", ride="campus", name="Unverified demo",
                    stop="Dabouq", class_end="16:00", gender="woman", preference="mixed")
    assert response.status_code == 302
    with campus.app.app_context():
        assert campus.database().execute(
            "SELECT COUNT(*) FROM riders WHERE name = 'Unverified demo'").fetchone()[0] == 0


def test_non_campus_choices_cannot_create_a_real_request(client):
    for ride in ("economy", "taxi", "comfort", "box"):
        response = post(client, "/requests", ride=ride, name="Demo comparison",
                        stop="Dabouq", class_end="16:00", gender="woman", preference="mixed")
        assert response.status_code == 302
    with campus.app.app_context():
        assert campus.database().execute(
            "SELECT COUNT(*) FROM riders WHERE name = 'Demo comparison'").fetchone()[0] == 0


def test_verification_requires_the_existing_csrf_token(client):
    assert client.post("/demo/student-verification", data={"email": "demo@cedar.example"}).status_code == 400


def test_yalla_is_a_peer_in_the_existing_ride_options(client):
    html = client.get("/?screen=book").get_data(as_text=True)
    rows = re.findall(r'<label class="ride[^"]*"[^>]*>(.*?)</label>', html, re.S)
    assert len(rows) == 5
    assert [re.search(r'name="ride" value="([^"]+)"', row)[1] for row in rows] == [
        "economy", "taxi", "comfort", "campus", "box"]
    for row, name in zip(rows, ["Economy", "Taxi", "Jeeny Comfort", "Yalla Ride", "Box"]):
        assert name in row
    assert 'value="economy" checked' in rows[0]
    assert "Students" in rows[3]
    assert 'id="shared"' in rows[3]
    assert 'id="campus-saving"' in rows[3]
    assert "Campus Connect" not in html


def test_yalla_does_not_have_a_separate_home_or_menu_section(client):
    for screen in ("home", "menu"):
        html = client.get(f"/?screen={screen}").get_data(as_text=True)
        assert 'class="campus-home-entry"' not in html
        assert 'class="campus-menu-card"' not in html
        assert "Campus Connect" not in html


def test_yalla_preserves_selected_and_verification_states(client):
    html = client.get("/?screen=book&ride=campus").get_data(as_text=True)
    assert 'id="ride-campus" checked' in html
    assert '<h2 id="details-title">Yalla Ride</h2>' in html
    post(client, "/demo/student-verification", action="reset")
    html = client.get("/?screen=book&ride=campus").get_data(as_text=True)
    assert 'aria-label="Verify your university email to unlock Yalla Ride"' in html
    assert 'id="ride-campus"' not in html
    assert 'value="economy" checked' in html


def test_yalla_uses_the_existing_shared_booking_handler(client):
    post(client, "/reset", mode="empty")
    response = post(client, "/requests", ride="campus", name="Yalla tester",
                    stop="Dabouq", class_end="16:00", gender="woman",
                    preference="mixed", direction="from_campus")
    assert response.status_code == 302
    assert "rider=" in response.location
    with campus.app.app_context():
        rider = campus.database().execute(
            "SELECT * FROM riders WHERE name = 'Yalla tester'").fetchone()
        assert rider is not None
        assert rider["stop"] == "Dabouq"
