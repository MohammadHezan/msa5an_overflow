"""Scenario tour: every student button shows a different situation, and each screen renders."""
import re

import pytest

import app as campus
import scenarios
from store import database, get_batch, load_riders

EXPECTED = {
    "Hadi": "review", "Samir": "confirmed", "Salma": "confirmed", "Hala": "changed", "Tala": "declined",
    "Majd": "declined", "Laith": "on_the_way", "Lama": "on_the_way", "Rami": "no_match",
    "Bana": "waiting_match", "Nada": "no_match", "Rawan": "solo_confirmed", "Omar": "arrived", "Jana": "lobby",
}
SCREEN_TEXT = {
    "Hadi": "Your seat is held", "Samir": "Show this to your driver", "Salma": "Women only",
    "Hala": "your plan changed", "Tala": "You left this ride", "Majd": "Your seat was released",
    "Laith": "On the way", "Lama": "Pickup at Tabarbour street", "Rami": "Pick how you want to go",
    "Bana": "Waiting for a match", "Nada": "booked in 10 minutes", "Rawan": "Economy ride",
    "Omar": "Ride ended", "Jana": "Waiting for your friends",
}


@pytest.fixture
def client(tmp_path):
    campus.app.config.update(TESTING=True, DATABASE=tmp_path / "test.sqlite")
    with campus.app.test_client() as client:
        client.get("/")
        with client.session_transaction() as session:
            token = session["csrf"]
        client.post("/reset", data={"csrf": token, "mode": "scenarios"})
        yield client


def riders(client):
    with client.session_transaction() as session:
        batch_id = session["batch"]
    with campus.app.app_context():
        db = database()
        return {r["name"]: r for r in load_riders(db, get_batch(db, batch_id))[0]}


def test_every_student_has_a_labelled_scenario(client):
    found = riders(client)
    assert {name: r["status"] for name, r in found.items()} == EXPECTED
    assert set(scenarios.LABELS) == set(found)
    assert found["Majd"]["released"] and not found["Tala"]["released"]
    assert found["Nada"]["wait_expired"]
    assert found["Salma"]["plan"]["only"] == "women" and found["Salma"]["plan"]["captain"]["gender"] == "woman"
    assert found["Lama"]["plan"]["id"] == found["Laith"]["plan"]["id"]


def test_each_scenario_screen_renders(client):
    page = client.get("/").get_data(as_text=True)
    for label, _ in scenarios.LABELS.values():
        assert label.replace("·", "&middot;") in page or label in page
    for name, rider in riders(client).items():
        html = client.get(f"/?rider={rider['id']}").get_data(as_text=True)
        assert SCREEN_TEXT[name] in html, name
        assert scenarios.LABELS[name][1].split(".")[0].replace("'", "&#39;") in html, name


def test_moving_the_clock_plays_scenarios_forward(client):
    with client.session_transaction() as session:
        token = session["csrf"]
    for _ in range(2):  # 10 minutes: Hadi's hold, Bana's wait and Jana's lobby all run out
        client.post("/clock", data={"csrf": token, "minutes": "5", "back": "/"})
    found = riders(client)
    assert found["Hadi"]["status"] == "declined" and found["Hadi"]["released"]
    assert found["Samir"]["status"] == "changed"
    assert found["Bana"]["status"] == "no_match" and found["Bana"]["wait_expired"]
    assert found["Jana"]["status"] != "lobby"


def test_api_can_create_the_scenario_tour(client):
    response = client.post("/api/v1/batches", json={"mode": "scenarios"})
    assert response.status_code == 201
