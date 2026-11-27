"""Planned ride request (screens 05-09): new request fields, gate-wait and extra-ride limits, estimate, checks."""
from dataclasses import replace
from datetime import timedelta

import pytest

import app as campus
from pooling import config
from pooling.matcher import OpenGroup, insert
from pooling.model import evaluate
from pooling.regroup import regroup
from sharing import group_problem, group_riders
from store import database, default_ready_time, get_batch, load_riders
from tests.helpers import at
from tests.test_api import auth, match, new_batch, verified_join
from tests.test_street_directions import street


@pytest.fixture
def client(tmp_path):
    campus.app.config.update(TESTING=True, DATABASE=tmp_path / "planned.sqlite")
    with campus.app.test_client() as client:
        yield client


def home(rid, ready, end_km=8, end_side=0, **limits):
    return replace(street(rid, "from_campus", 0, end_km, ready_at=at(ready), end_side=end_side), **limits)


# ---------- engine rules ----------

def test_pickup_is_never_past_a_riders_gate_wait_limit():
    early, late = home("early", "16:00"), home("late", "16:08")
    plan = evaluate([early, late])
    assert plan is not None and plan.pickup_time == at("16:08")  # Default 10-minute wait: they share
    assert all(plan.pickup_time >= r.ready_at for r in plan.riders)
    impatient = replace(early, max_gate_wait_min=5)
    assert evaluate([impatient, late]) is None
    assert evaluate([impatient, late], strict=False) is None  # Not even for a friends group or a re-priced car
    # Regroup leaves the impatient rider out rather than making them wait 8 minutes
    cars = regroup([evaluate([impatient]), evaluate([late]), evaluate([home("other", "16:07")])])
    for plan in cars:
        for r in plan.riders:
            assert r.ready_at <= plan.pickup_time <= r.ready_at + timedelta(minutes=r.max_gate_wait_min)
    assert next(p for p in cars if "early" in p.ids).ids == {"early"}


def test_extra_ride_time_stays_within_each_riders_limit():
    far = home("far", "16:00", end_km=10)
    near = home("near", "16:00", end_km=6, end_side=600)  # The captain turns in 0.8 km for near's drop-off
    plan = evaluate([far, near])
    assert plan is not None
    extra = (plan.in_car_km["far"] - plan.solo_km["far"]) * 60 / config.SPEED_KMH
    assert 1 < extra <= config.DEFAULT_MAX_EXTRA_RIDE_MIN
    assert evaluate([replace(far, max_extra_ride_min=1), near]) is None
    # A late request is never inserted into a car that would break a member's limit
    # Friends groups (priced without the savings floor) still respect each rider's own limit
    impatient = replace(far, max_extra_ride_min=1)
    assert evaluate([impatient, near], strict=False) is None
    cars = regroup([evaluate([impatient]), evaluate([near])], together=[frozenset({"far", "near"})])
    assert sorted(len(p.riders) for p in cars) == [1, 1]
    placed = insert([OpenGroup("car-1", evaluate([replace(far, max_extra_ride_min=1)]))], near)
    assert placed.group_id is None
    assert insert([OpenGroup("car-1", evaluate([far]))], near).group_id == "car-1"


def test_quiet_ride_never_changes_grouping():
    riders = [
        {"id": i, "name": name, "class_end": end, "stop": stop, "gender": gender, "preference": "mixed"}
        for i, (name, end, stop, gender) in enumerate([
            ("Sara", "16:00", "Dabouq", "woman"), ("Rama", "15:55", "Al Bayader", "woman"),
            ("Kareem", "16:05", "Khalda", "man"), ("Omar", "16:10", "Shafa Badran", "man"),
            ("Lina", "16:00", "Al Jubeiha", "woman"), ("Huda", "16:00", "Wadi As-Seer", "woman"),
        ])
    ]
    plain = group_riders(riders)
    quiet = group_riders([{**r, "quiet_ride": i % 2 == 0} for i, r in enumerate(riders)])
    assert sorted(map(sorted, plain)) == sorted(map(sorted, quiet))


# ---------- API ----------

def book(client, batch, token, name="Sara", **extra):
    body = {"name": name, "classEnd": "16:00", "stop": "Dabouq", "gender": "woman",
            "clientRequestId": f"req-{name.lower()}-0001", **extra}
    return client.post(f"/api/v1/batches/{batch['id']}/riders", headers=auth(token), json=body)


def test_booking_stores_the_planned_fields_and_returns_the_screen_09_checks(client):
    batch = new_batch(client)
    token = verified_join(client, batch["joinCode"], "Sara")
    body = {"rideDate": batch["tripDate"], "readyAt": "16:06", "preferredPickup": "16:11", "womenOnly": True,
            "quietRide": True, "maxGateWaitMin": 15, "maxExtraRideMin": 8, "paymentMethod": "cash"}
    response = book(client, batch, token, **body)
    assert response.status_code == 201, response.get_json()
    rider = response.get_json()
    assert rider["requestStatus"] == "matching" and rider["plan"] is None
    assert rider["request"]["preference"] == "women" and rider["request"]["quietRide"] is True
    assert (rider["request"]["readyAt"], rider["request"]["preferredPickup"]) == ("16:06", "16:11")
    assert (rider["request"]["maxGateWaitMin"], rider["request"]["maxExtraRideMin"]) == (15, 8)
    assert rider["request"]["paymentMethod"] == "cash"
    assert rider["sameCampusDirection"] == {"corridor": "West", "direction": "from_campus", "gate": "Main gate"}
    window = rider["timeWindow"]
    assert window["readyTime"] == "16:06" and window["pickupAroundTime"] == "16:11"
    assert window["readyAt"] == f"{batch['tripDate']}T16:06:00+03:00" and window["maxGateWaitMin"] == 15
    assert rider["preferences"] == {"preference": "women", "womenOnly": True, "quietRide": True,
                                    "maxExtraRideMin": 8, "paymentMethod": "cash"}
    # The same request again is an idempotent retry; changed limits are a conflict
    assert book(client, batch, token, **body).status_code == 200
    assert book(client, batch, token, **{**body, "maxGateWaitMin": 5}).get_json()["error"]["code"] == "request_conflict"
    # The captain sees the quiet ride; the operator view lists it too
    detail = client.get(f"/api/v1/batches/{batch['id']}", headers=auth(batch["operatorToken"])).get_json()
    assert detail["riders"][0]["quietRide"] is True
    assert match(client, batch).status_code == 200
    with campus.app.app_context():
        db = database()
        riders, _ = load_riders(db, get_batch(db, batch["id"]))
    stored = riders[0]
    assert stored["ready_at"] == f"{batch['tripDate']}T16:06:00+03:00"
    assert stored["plan"]["pickup"] == "16:06"  # Never before readyAt


def test_old_clients_get_the_defaults(client):
    batch = new_batch(client)
    token = verified_join(client, batch["joinCode"], "Sara")
    response = client.post(f"/api/v1/batches/{batch['id']}/riders", headers=auth(token), json={
        "name": "Sara", "classEnd": "16:00", "stop": "Dabouq", "woman": True, "womenOnly": False,
        "clientRequestId": "req-sara-0001"})
    assert response.status_code == 201
    rider = response.get_json()
    assert rider["status"] == "waiting" and rider["requestStatus"] == "matching"
    request = rider["request"]
    assert request["readyAt"] is None and request["preferredPickup"] is None and request["quietRide"] is False
    assert request["maxGateWaitMin"] == config.DEFAULT_MAX_GATE_WAIT_MIN == 10
    assert request["maxExtraRideMin"] == config.DEFAULT_MAX_EXTRA_RIDE_MIN == 10
    assert request["paymentMethod"] == "cash" and request["rideDate"] == batch["tripDate"]
    assert rider["timeWindow"]["readyTime"] == default_ready_time("Sara", "Dabouq", "16:00")


@pytest.mark.parametrize("extra, message", [
    ({"preferredPickup": "16:07"}, "preferredPickup"),
    ({"readyAt": "16:00", "preferredPickup": "16:20"}, "preferredPickup"),
    ({"readyAt": "15:50"}, "readyAt"),
    ({"paymentMethod": "card"}, "paymentMethod"),
    ({"maxGateWaitMin": 0}, "maxGateWaitMin"),
    ({"maxGateWaitMin": config.MAX_GATE_WAIT_CAP_MIN + 1}, "maxGateWaitMin"),
    ({"maxExtraRideMin": 99}, "maxExtraRideMin"),
    ({"maxExtraRideMin": "10"}, "maxExtraRideMin"),
    ({"quietRide": "yes"}, "quietRide"),
    ({"rideDate": "2020-01-01"}, "rideDate"),
    ({"womenOnly": True, "preference": "mixed"}, "womenOnly"),
])
def test_invalid_planned_fields_are_rejected_with_the_standard_error(client, extra, message):
    batch = new_batch(client)
    token = verified_join(client, batch["joinCode"], "Sara")
    response = book(client, batch, token, **extra)
    assert response.status_code == 400
    body = response.get_json()
    assert body["error"]["code"] == "invalid_input" and message in body["error"]["message"]
    assert client.get(f"/api/v1/batches/{batch['id']}", headers=auth(batch["operatorToken"])).get_json()["riders"] == []


def test_ready_time_is_only_for_rides_from_campus(client):
    batch = new_batch(client)
    token = verified_join(client, batch["joinCode"], "Sara")
    response = book(client, batch, token, direction="to_campus", classStart="09:00", classEnd="", readyAt="08:00")
    assert response.status_code == 400 and response.get_json()["error"]["code"] == "invalid_input"


def test_late_request_respects_the_gate_wait_limit(client):
    batch = new_batch(client)
    first = verified_join(client, batch["joinCode"], "Sara")
    assert book(client, batch, first, "Sara", readyAt="16:00", maxGateWaitMin=5).status_code == 201
    assert match(client, batch).status_code == 200
    with campus.app.app_context():  # Sara waits for a match
        db = database()
        with db:
            db.execute("UPDATE riders SET choice = 'wait', wait_until = ? WHERE batch = ?",
                       ("2099-01-01T00:00:00+03:00", batch["id"]))
    late = verified_join(client, batch["joinCode"], "Rama")
    response = book(client, batch, late, "Rama", readyAt="16:08", stop="Al Bayader")
    assert response.status_code == 201
    assert response.get_json()["plan"]["shared"] is False  # 8 minutes is past Sara's 5-minute limit
    ok = verified_join(client, batch["joinCode"], "Huda")
    response = book(client, batch, ok, "Huda", readyAt="16:04", stop="Al Bayader")
    assert response.get_json()["plan"]["shared"] is True and response.get_json()["plan"]["riders"] == ["Sara"]


def test_estimate_returns_a_range_and_an_amman_drop_off_time(client):
    for stop in ("Dabouq", "Khalda", "Marka", "Abu Nseir"):
        response = client.get(f"/api/v1/estimate?stop={stop}&preferredPickup=16:30&rideDate=2026-11-28")
        assert response.status_code == 200
        body = response.get_json()
        low, high = body["estimatedShare"]["low"], body["estimatedShare"]["high"]
        assert low["currency"] == high["currency"] == "JOD"
        assert 0 < low["fils"] <= high["fils"] < body["soloFare"]["fils"]
        assert body["dropOffEta"].startswith("2026-11-28T") and body["dropOffEta"].endswith("+03:00")
        assert body["dropOffEta"] > "2026-11-28T16:30" and body["paymentTakenNow"] is False
    dabouq = client.get("/api/v1/estimate?stop=Dabouq&preferredPickup=16:30&rideDate=2026-11-28").get_json()
    fare = dabouq["soloFare"]["fils"]  # 12 km at the day tariff
    assert dabouq["estimatedShare"]["low"]["fils"] == -(-fare // 4) and dabouq["estimatedShare"]["high"]["fils"] == -(-fare // 2)
    assert dabouq["dropOffTime"] == "16:58"  # 12 km at 25 km/h
    for bad in ("stop=Nowhere&preferredPickup=16:30", "stop=Dabouq&preferredPickup=4pm", "stop=Dabouq"):
        response = client.get(f"/api/v1/estimate?{bad}")
        assert response.status_code == 400 and response.get_json()["error"]["code"] == "invalid_input"


def test_joining_a_friends_group_checks_the_extra_ride_limit():
    sara = {"id": 1, "name": "Sara", "class_end": "16:00", "stop": "Dabouq", "gender": "woman", "preference": "mixed",
            "direction": "from_campus", "corridor": "West", "start_km": 0.0, "start_side_m": 0,
            "end_km": 9.0, "end_side_m": 900}  # Sara's drop-off needs a 1.4 km turn-in before Rama's
    rama = {**sara, "id": 2, "name": "Rama", "end_km": 12.0, "end_side_m": 0, "max_extra_ride_min": 1}
    assert group_problem([sara, rama]) == "Riding together would take someone longer than their maximum extra ride time."
    assert group_problem([sara, {**rama, "max_extra_ride_min": 10}]) is None
