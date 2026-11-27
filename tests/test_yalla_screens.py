"""Brief 04 · Yalla Ride screens, phase 1 (plan, share and ride): each screen renders and is wired to the backend."""
import re

import pytest

import app as campus
from store import database, fare_estimates, get_batch, load_riders


@pytest.fixture
def client(tmp_path):
    campus.app.config.update(TESTING=True, DATABASE=tmp_path / "yalla.sqlite")
    with campus.app.test_client() as client:
        client.get("/")
        yield client


def post(client, path, **data):
    with client.session_transaction() as session:
        csrf = session["csrf"]
    return client.post(path, data={"csrf": csrf, **data})


def text(response):
    return response.get_data(as_text=True)


def my_rider(client):
    with client.session_transaction() as session:
        batch_id, rider_id = session["batch"], session["yalla_rider"]
    with campus.app.app_context():
        db = database()
        riders, _ = load_riders(db, get_batch(db, batch_id))
    return next(r for r in riders if r["id"] == rider_id)


def verify(client, email="lina.k@cedar.edu"):
    post(client, "/yalla/verify", email=email)
    with client.session_transaction() as session:
        code = session["yalla_code"]
        assert email not in str(dict(session))  # Only a masked email is kept
    return post(client, "/yalla/verify/code", **{"digit": list(code)})


def test_home_shows_yalla_ride_entry_points(client):
    page = text(client.get("/yalla"))
    assert "Same campus." in page and "Plan a shared ride" in page and "Leave now &amp; share" in page
    assert "Campus Connect" not in page
    assert client.get("/yalla/help").status_code == 200


def test_verification_code_flow_is_demo_only(client):
    post(client, "/demo/student-verification", action="reset")
    assert client.get("/yalla/plan/destination").location.startswith("/yalla/verify")
    assert post(client, "/yalla/verify", email="not-an-email").location.startswith("/yalla/verify")
    response = post(client, "/yalla/verify", email="lina.k@cedar.edu")
    assert response.location.startswith("/yalla/verify/code")
    page = text(client.get(response.location))
    assert "l***@cedar.edu" in page and "Demo code:" in page
    wrong = post(client, "/yalla/verify/code", digit=list("000000"))
    with client.session_transaction() as session:
        assert session.get("student_verified") is False
    assert wrong.location.startswith("/yalla/verify/code")
    assert verify(client).location.startswith("/yalla/university")
    with client.session_transaction() as session:
        assert session["student_verified"] is True and session["yalla_name"] == "Lina K"


def test_unavailable_university_and_notifications(client):
    assert post(client, "/yalla/university", university="hillcrest").location.startswith("/yalla/not-available")
    assert "next in line" in text(client.get("/yalla/not-available?university=hillcrest"))
    post(client, "/yalla/notify", university="hillcrest")
    assert "Campus notifications on" in text(client.get("/yalla/university"))


def plan(client, stop="Khalda", direction="from_campus", **prefs):
    verify(client)
    post(client, "/yalla/plan/destination", stop=stop, direction=direction, go="next")
    post(client, "/yalla/plan/time", class_end="16:00", class_start="09:00")
    return post(client, "/yalla/plan/preferences", gender="woman", **{"preference": "mixed", **prefs})


def test_review_shows_backend_estimate_and_brief_02_street_pickup(client):
    plan(client, quiet="yes")
    page = text(client.get("/yalla/plan/review"))
    estimate = fare_estimates("Lina K")["Khalda"]
    assert f"JOD {estimate['shared'] / 1000:.2f}–{estimate['solo'] / 1000:.2f}" in page
    assert f"walk {estimate['pickups']['from_campus']['walk_minutes']} min" in page
    assert "Quiet ride" in page and "main gate" not in page.lower()


def test_men_only_is_refused_for_a_woman(client):
    plan(client, preference="men")
    with client.session_transaction() as session:
        assert session["yalla"]["preference"] == "mixed"


def test_full_shared_ride_from_request_to_receipt(client):
    plan(client)
    assert post(client, "/yalla/plan/book").location == "/yalla/ride"
    assert "Finding your campus group" in text(client.get("/yalla/ride"))
    post(client, "/yalla/ride/match")
    rider = my_rider(client)
    assert rider["status"] == "review" and rider["plan"]["shared"]
    group = text(client.get("/yalla/ride"))
    assert f"Confirm my seat · JOD {rider['share'] / 1000:.2f}" in group
    for member in rider["plan"]["members"]:
        assert member["stop"] in group
    fare = text(client.get("/yalla/ride/fare"))
    assert f"JOD {rider['plan']['car_fare'] / 1000:.3f}" in fare
    for member in rider["plan"]["members"]:
        assert f"JOD {rider['plan']['shares'][member['id']] / 1000:.3f}" in fare
    post(client, "/yalla/ride/confirm", plan=rider["signature"])
    rider = my_rider(client)
    assert rider["status"] == "confirmed" and re.fullmatch(r"CC-\d{4}", rider["ride_code"])
    assert "Your seat is confirmed" in text(client.get("/yalla/ride"))
    assert rider["ride_code"] in text(client.get("/yalla/ride?step=code"))
    assert "Your captain is on the way" in text(client.get("/yalla/ride?step=pickup"))
    assert "Your stop" in text(client.get("/yalla/ride?step=trip"))
    receipt = text(client.get("/yalla/ride?step=receipt"))
    assert f"You saved JOD {(rider['solo'] - rider['share']) / 1000:.2f}" in receipt
    assert client.get("/yalla/ride?step=nope").status_code == 404


def test_stale_confirm_is_refused(client):
    plan(client)
    post(client, "/yalla/plan/book")
    post(client, "/yalla/ride/match")
    post(client, "/yalla/ride/confirm", plan="stale")
    assert my_rider(client)["status"] == "review"


def test_ride_without_booking_goes_home(client):
    assert client.get("/yalla/ride").location == "/yalla"
