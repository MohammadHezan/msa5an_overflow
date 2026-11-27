"""JSON API: batches, join codes, booking retries, matching, and confirm/decline on the same batch as the dashboard."""

import pytest

import app as campus


@pytest.fixture
def client(tmp_path):
    campus.app.config.update(TESTING=True, DATABASE=tmp_path / "test.sqlite")
    with campus.app.test_client() as client:
        yield client


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def new_batch(client, mode="empty"):
    response = client.post("/api/v1/batches", json={"mode": mode})
    assert response.status_code == 201
    return response.get_json()


def join(client, code):
    response = client.post("/api/v1/demo-sessions/join", json={"joinCode": code})
    assert response.status_code == 201
    return response.get_json()["token"]


def book(client, batch, token, name, stop="Dabouq", class_end="16:00", woman=True, women_only=False, request_id=None):
    return client.post(
        f"/api/v1/batches/{batch['id']}/riders", headers=auth(token),
        json={"name": name, "classEnd": class_end, "stop": stop, "woman": woman, "womenOnly": women_only,
              "clientRequestId": request_id or f"req-{name.lower()}-0001"},
    )


def student(client, batch, name, **kwargs):
    token = join(client, batch["joinCode"])
    response = book(client, batch, token, name, **kwargs)
    assert response.status_code == 201, response.get_json()
    return token, response.get_json()["id"]


def match(client, batch):
    return client.post(f"/api/v1/batches/{batch['id']}/matching", headers=auth(batch["operatorToken"]))


@pytest.fixture
def west_car(client):
    """Sara, Rama and Huda booked from three phones and matched into one women-only car."""
    batch = new_batch(client)
    riders = {
        "Sara": student(client, batch, "Sara", stop="Dabouq", class_end="16:00", women_only=True),
        "Rama": student(client, batch, "Rama", stop="Al Bayader", class_end="15:55", women_only=True),
        "Huda": student(client, batch, "Huda", stop="Wadi As-Seer", class_end="16:00", women_only=True),
    }
    assert match(client, batch).status_code == 200
    return batch, riders


def test_health_and_stops(client):
    assert client.get("/api/v1/health").get_json()["status"] == "ok"
    body = client.get("/api/v1/stops").get_json()
    west = next(c for c in body["corridors"] if c["name"] == "West")
    dabouq = next(s for s in west["stops"] if s["name"] == "Dabouq")
    assert west["gate"] == "Main gate"
    assert dabouq == {"name": "Dabouq", "km": 12, "soloFare": {"fils": 4500, "currency": "JOD"},
                      "sampleShare": {"fils": 1500, "currency": "JOD"}}
    assert body["rules"]["seatsPerCar"] == 4 and body["rules"]["maxClassEndGapMinutes"] == 20
    assert body["rules"]["baseFare"]["fils"] == 468 and body["rules"]["minSavingPercent"] == 20


def test_booking_returns_waiting_and_retry_returns_same_rider(client):
    batch = new_batch(client)
    token = join(client, batch["joinCode"])
    first = book(client, batch, token, "Sara", women_only=True)
    assert first.status_code == 201
    assert first.get_json()["status"] == "waiting" and first.get_json()["plan"] is None
    retry = book(client, batch, token, "Sara", women_only=True)
    assert retry.status_code == 200
    assert retry.get_json()["id"] == first.get_json()["id"]
    detail = client.get(f"/api/v1/batches/{batch['id']}", headers=auth(batch["operatorToken"])).get_json()
    assert [r["name"] for r in detail["riders"]] == ["Sara"]


def test_booking_conflicts(client):
    batch = new_batch(client)
    token = join(client, batch["joinCode"])
    book(client, batch, token, "Sara")
    changed = book(client, batch, token, "Sara", stop="Khalda")
    assert changed.status_code == 409 and changed.get_json()["error"]["code"] == "request_conflict"
    second = book(client, batch, token, "Rama", request_id="another-request")
    assert second.status_code == 409 and second.get_json()["error"]["code"] == "already_booked"
    duplicate = book(client, batch, join(client, batch["joinCode"]), "sara", request_id="other-phone-01")
    assert duplicate.status_code == 409 and duplicate.get_json()["error"]["code"] == "duplicate_name"


def test_invalid_input(client):
    batch = new_batch(client)
    token = join(client, batch["joinCode"])
    man = book(client, batch, token, "Ali", woman=False, women_only=True)
    assert man.status_code == 400 and man.get_json()["error"]["code"] == "invalid_input"
    late = book(client, batch, token, "Ali", class_end="22:00")
    assert late.get_json()["error"]["code"] == "invalid_input"
    bad_id = book(client, batch, token, "Ali", request_id="x")
    assert bad_id.get_json()["error"]["code"] == "invalid_input"
    assert client.post("/api/v1/demo-sessions/join", json={"joinCode": "NOPE99"}).get_json()["error"]["code"] \
        == "join_code_invalid"


def test_authorization(client, west_car):
    batch, riders = west_car
    sara_token, sara_id = riders["Sara"]
    _, rama_id = riders["Rama"]
    assert client.get(f"/api/v1/riders/{sara_id}").status_code == 401
    assert client.get(f"/api/v1/riders/{sara_id}", headers=auth("not-a-token")).status_code == 401
    other = client.get(f"/api/v1/riders/{rama_id}", headers=auth(sara_token))
    assert other.status_code == 403 and other.get_json()["error"]["code"] == "forbidden"
    assert client.post(f"/api/v1/riders/{rama_id}/decline", headers=auth(sara_token)).status_code == 403
    assert client.get(f"/api/v1/batches/{batch['id']}", headers=auth(sara_token)).status_code == 403
    assert match(client, {**batch, "operatorToken": sara_token}).status_code == 403
    elsewhere = new_batch(client)
    assert client.get(f"/api/v1/riders/{sara_id}", headers=auth(elsewhere["operatorToken"])).status_code == 403
    assert client.get(f"/api/v1/batches/{batch['id']}", headers=auth(elsewhere["operatorToken"])).status_code == 403


def test_plan_shows_shared_car_without_other_riders_details(client, west_car):
    _, riders = west_car
    token, sara_id = riders["Sara"]
    sara = client.get(f"/api/v1/riders/{sara_id}", headers=auth(token)).get_json()
    plan = sara["plan"]
    assert sara["status"] == "review"
    assert plan["gate"] == "Main gate" and plan["pickupTime"] == "16:15" and plan["womenOnly"]
    assert plan["pickupAt"].endswith("T16:15:00+03:00")
    assert plan["share"] == {"fils": 1670, "currency": "JOD"} and plan["soloFare"]["fils"] == 4500
    assert sorted(plan["riders"]) == ["Huda", "Rama"]
    assert [d["stop"] for d in plan["dropOffs"]] == ["Dabouq", "Al Bayader", "Wadi As-Seer"]
    assert "share" not in plan["dropOffs"][1]


def test_matching_closes_batch_and_repeat_returns_saved_cars(client, west_car):
    batch, _ = west_car
    again = match(client, batch).get_json()
    assert again["ranNow"] is False and len(again["batch"]["cars"]) == 1
    late = book(client, batch, join(client, batch["joinCode"]), "Lina", request_id="late-request-1")
    assert late.status_code == 409 and late.get_json()["error"]["code"] == "batch_matched"


def test_stale_confirm_returns_plan_changed_then_decline_marks_changed(client, west_car):
    _, riders = west_car
    sara_token, sara_id = riders["Sara"]
    huda_token, huda_id = riders["Huda"]
    signature = client.get(f"/api/v1/riders/{sara_id}", headers=auth(sara_token)).get_json()["plan"]["signature"]

    stale = client.post(f"/api/v1/riders/{sara_id}/confirm", headers=auth(sara_token), json={"signature": "9999|16:15|3"})
    assert stale.status_code == 409
    assert stale.get_json()["error"]["code"] == "plan_changed"
    assert stale.get_json()["rider"]["plan"]["signature"] == signature

    confirmed = client.post(f"/api/v1/riders/{sara_id}/confirm", headers=auth(sara_token), json={"signature": signature})
    assert confirmed.status_code == 200 and confirmed.get_json()["status"] == "confirmed"

    declined = client.post(f"/api/v1/riders/{huda_id}/decline", headers=auth(huda_token))
    assert declined.get_json()["status"] == "declined" and declined.get_json()["plan"] is None
    assert client.post(f"/api/v1/riders/{huda_id}/decline", headers=auth(huda_token)).status_code == 200

    sara = client.get(f"/api/v1/riders/{sara_id}", headers=auth(sara_token)).get_json()
    assert sara["status"] == "changed"
    assert sara["plan"]["share"]["fils"] == 2387 and sara["plan"]["riders"] == ["Rama"]
    old = client.post(f"/api/v1/riders/{sara_id}/confirm", headers=auth(sara_token), json={"signature": signature})
    assert old.status_code == 409 and old.get_json()["rider"]["status"] == "changed"
    again = client.post(f"/api/v1/riders/{sara_id}/confirm", headers=auth(sara_token),
                        json={"signature": sara["plan"]["signature"]})
    assert again.get_json()["status"] == "confirmed"


def test_seeded_batch_matches_the_sample_afternoon(client):
    batch = new_batch(client, "seeded")
    body = match(client, batch).get_json()["batch"]
    assert len(body["cars"]) == 5
    sara = next(r for r in body["riders"] if r["name"] == "Sara")
    assert sara["status"] == "review" and sara["share"]["fils"] == 1670
    assert next(r for r in body["riders"] if r["name"] == "Kareem")["status"] == "no_match"


def test_phone_and_dashboard_share_one_batch(client):
    """The dashboard shows a join code; a phone books into that batch; dashboard matching changes the phone's plan."""
    page = client.get("/?view=match").get_data(as_text=True)
    with client.session_transaction() as session:
        csrf, batch_id = session["csrf"], session["batch"]
    with campus.app.app_context():
        code, _ = campus.join_code(campus.database(), batch_id)
    assert code in page

    token = join(client, code)
    phone = book(client, {"id": batch_id}, token, "Maha", stop="Khalda", class_end="16:00", women_only=True)
    assert phone.status_code == 201
    rider_id = phone.get_json()["id"]

    client.post("/match", data={"csrf": csrf})
    plan = client.get(f"/api/v1/riders/{rider_id}", headers=auth(token)).get_json()
    assert plan["status"] == "review"
    assert set(plan["plan"]["riders"]) <= {"Sara", "Rama", "Huda"}  # women-only: never with Kareem


def test_unknown_api_route_returns_json(client):
    response = client.get("/api/v1/nope")
    assert response.status_code == 404 and response.get_json()["error"]["code"] == "not_found"


def test_join_code_for_deleted_batch_fails_fast_and_releases_the_lock(client):
    batch = new_batch(client)
    with campus.app.app_context():
        db = campus.database()
        with db:
            db.execute("DELETE FROM batches WHERE id = ?", (batch["id"],))
        with pytest.raises(campus.Problem) as raised:
            campus.join_code(db, batch["id"])
        assert raised.value.code == "not_found"
    other = new_batch(client)  # another connection can still write
    assert other["joinCode"]
