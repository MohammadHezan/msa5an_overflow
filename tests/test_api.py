"""JSON API: batches, join codes, booking retries, matching, and confirm/decline on the same batch as the dashboard."""

import json
import re
import secrets
from datetime import datetime, timedelta

import pytest

import app as campus
import store
import student_verification


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


def verify(token, first_name, email=None):
    """Mark this phone session as a verified student (the real email flow is tested below)."""
    with campus.app.app_context():
        db = campus.database()
        with db:
            school = db.execute("SELECT id FROM universities WHERE email_domain = 'bau.edu.jo'").fetchone()["id"]
            email = email or f"{first_name.lower()}.{secrets.token_hex(4)}@bau.edu.jo"
            student_id = db.execute(
                "INSERT INTO students (university, email, first_name, verified_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(university, email) DO UPDATE SET first_name = first_name RETURNING id",
                (school, email, first_name, store.now().isoformat()),
            ).fetchone()[0]
            db.execute("UPDATE api_tokens SET student_id = ? WHERE token_hash = ?", (student_id, store._hash(token)))
    return token


def verified_join(client, code, first_name, email=None):
    return verify(join(client, code), first_name, email)


def profile_gender(token, gender):
    """Set the verified student's profile gender (Jeeny supplies it; booking never takes it from the phone)."""
    with campus.app.app_context():
        db = campus.database()
        with db:
            db.execute("UPDATE students SET gender = ? WHERE id = (SELECT student_id FROM api_tokens WHERE token_hash = ?)",
                       (gender, store._hash(token)))
    return token


def book(client, batch, token, name, stop="Dabouq", class_end="16:00", woman=True, women_only=False, request_id=None):
    profile_gender(token, "woman" if woman else "man")
    return client.post(
        f"/api/v1/batches/{batch['id']}/riders", headers=auth(token),
        json={"name": name, "classEnd": class_end, "stop": stop, "woman": woman, "womenOnly": women_only,
              "clientRequestId": request_id or f"req-{name.lower()}-0001"},
    )


def student(client, batch, name, **kwargs):
    token = verified_join(client, batch["joinCode"], name)
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
    assert body["rules"]["seatsPerCar"] == 4 and body["rules"]["maxClassEndGapMinutes"] == 10
    assert body["rules"]["baseFare"]["fils"] == 468 and body["rules"]["minSavingPercent"] == 25


def test_booking_returns_waiting_and_retry_returns_same_rider(client):
    batch = new_batch(client)
    token = verified_join(client, batch["joinCode"], "Sara")
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
    token = verified_join(client, batch["joinCode"], "Sara", "sara@bau.edu.jo")
    book(client, batch, token, "Sara")
    changed = book(client, batch, token, "Sara", stop="Khalda")
    assert changed.status_code == 409 and changed.get_json()["error"]["code"] == "request_conflict"
    second = book(client, batch, token, "Rama", request_id="another-request")
    assert second.status_code == 409 and second.get_json()["error"]["code"] == "already_booked"
    # The same verified student on a second phone still has only one request in the batch.
    other_phone = verified_join(client, batch["joinCode"], "Sara", "sara@bau.edu.jo")
    duplicate = book(client, batch, other_phone, "Sara", request_id="other-phone-01")
    assert duplicate.status_code == 409 and duplicate.get_json()["error"]["code"] == "already_booked"
    # A different verified student who is also called Sara may book.
    namesake = book(client, batch, verified_join(client, batch["joinCode"], "Sara"), "Sara", request_id="namesake-0001")
    assert namesake.status_code == 201 and namesake.get_json()["name"] == "Sara"


def test_unverified_student_cannot_book(client):
    batch = new_batch(client)
    token = join(client, batch["joinCode"])
    rejected = book(client, batch, token, "Sara")
    assert rejected.status_code == 403 and rejected.get_json()["error"]["code"] == "verification_required"
    # Verification was started but not confirmed: still rejected, and nothing was saved.
    school = _university(client, token, "Al-Balqa Applied University")
    started = client.post("/api/v1/verification/start", headers=auth(token), json={
        "universityId": school["id"], "email": "sara@bau.edu.jo", "firstName": "Sara",
    })
    assert started.status_code == 200
    pending = book(client, batch, token, "Sara")
    assert pending.status_code == 403 and pending.get_json()["error"]["code"] == "verification_required"
    detail = client.get(f"/api/v1/batches/{batch['id']}", headers=auth(batch["operatorToken"])).get_json()
    assert detail["riders"] == []
    with campus.app.app_context():
        assert campus.database().execute(
            "SELECT rider FROM api_tokens WHERE token_hash = ?", (store._hash(token),)).fetchone()["rider"] is None


def test_verified_booking_uses_profile_name_not_client_name(client):
    batch = new_batch(client)
    token = verified_join(client, batch["joinCode"], "Lina")
    first = book(client, batch, token, "Someone Else", request_id="lina-request-0001")
    assert first.status_code == 201 and first.get_json()["name"] == "Lina"
    # A retry is matched on the profile identity, so a different client `name` cannot fork the request.
    retry = book(client, batch, token, "Another Name", request_id="lina-request-0001")
    assert retry.status_code == 200 and retry.get_json()["id"] == first.get_json()["id"]
    no_name = client.post(f"/api/v1/batches/{batch['id']}/riders", headers=auth(token), json={
        "classEnd": "16:00", "stop": "Dabouq", "woman": True, "womenOnly": False,
        "clientRequestId": "lina-request-0001",
    })
    assert no_name.status_code == 200 and no_name.get_json()["id"] == first.get_json()["id"]
    detail = client.get(f"/api/v1/batches/{batch['id']}", headers=auth(batch["operatorToken"])).get_json()
    assert [r["name"] for r in detail["riders"]] == ["Lina"]


def test_invalid_input(client):
    batch = new_batch(client)
    token = verified_join(client, batch["joinCode"], "Ali")
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
    batch, riders = west_car
    token, sara_id = riders["Sara"]
    sara = client.get(f"/api/v1/riders/{sara_id}", headers=auth(token)).get_json()
    plan = sara["plan"]
    assert sara["status"] == "review"
    assert plan["gate"] == "Main gate" and plan["womenOnly"] and plan["direction"] == "from_campus"
    assert plan["pickupAt"].endswith(f"T{plan['pickupTime']}:00+03:00")
    assert 0 < plan["share"]["fils"] < plan["soloFare"]["fils"]
    assert plan["walkMeters"] <= 200 and plan["yourPickupTime"] == plan["pickupTime"]
    assert sorted(plan["riders"]) == ["Huda", "Rama"]
    assert [d["stop"] for d in plan["dropOffs"]] == ["Dabouq", "Al Bayader", "Wadi As-Seer"]
    assert "share" not in plan["dropOffs"][1]


def test_matching_closes_batch_and_repeat_returns_saved_cars(client, west_car):
    batch, _ = west_car
    again = match(client, batch).get_json()
    assert again["ranNow"] is False and len(again["batch"]["cars"]) == 1
    # After matching, a late request is placed at once (here: alone, with the lone-rider choices)
    late = book(client, batch, verified_join(client, batch["joinCode"], "Lina"), "Lina", request_id="late-request-1")
    assert late.status_code == 201 and late.get_json()["status"] == "no_match"


def test_stale_confirm_returns_plan_changed_then_decline_marks_changed(client, west_car):
    batch, riders = west_car
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
    assert sara["plan"]["riders"] == ["Rama"]
    assert sara["plan"]["share"]["fils"] == int(signature.split("|", 1)[0])
    assert sara["plan"]["jeenyCover"]["fils"] > 0
    batch_json = client.get(f"/api/v1/batches/{batch['id']}", headers=auth(batch["operatorToken"])).get_json()
    car = next(c for c in batch_json["cars"] if any(r["name"] == "Sara" for r in c["riders"]))
    assert sum(r["share"]["fils"] for r in car["riders"]) + car["jeenyCover"]["fils"] == car["carFare"]["fils"]
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
    assert sara["status"] == "review" and 0 < sara["share"]["fils"] < sara["soloFare"]["fils"]
    assert next(r for r in body["riders"] if r["name"] == "Kareem")["status"] == "no_match"


def test_morning_sample_forms_shared_cars_with_individual_pickup_times(client):
    batch = new_batch(client, "morning")
    body = match(client, batch).get_json()["batch"]
    assert len(body["riders"]) == 9
    assert any(len(car["riders"]) > 1 for car in body["cars"])
    with campus.app.app_context():
        saved = campus.get_batch(campus.database(), batch["id"])
        riders, cars = campus.load_riders(campus.database(), saved)
    assert all(r["direction"] == "to_campus" for r in riders)
    for car in cars:
        members = car["members"]
        assert [m["start_km"] for m in members] == sorted(
            (m["start_km"] for m in members), reverse=True)
        assert car["campus_arrival"] <= min(m["class_start"] for m in members)
        assert all(car["rider_times"][m["id"]] < car["campus_arrival"] for m in members)
        assert sum(car["shares"].values()) == car["car_fare"]


def test_to_campus_booking_accepts_class_start_without_class_end(client):
    batch = new_batch(client)
    token = verified_join(client, batch["joinCode"], "Demo")
    response = client.post(f"/api/v1/batches/{batch['id']}/riders", headers=auth(token), json={
        "name": "Demo student", "direction": "to_campus", "classStart": "08:30",
        "stop": "Dabouq", "gender": "woman", "preference": "mixed",
        "clientRequestId": "morning-request-0001",
    })
    assert response.status_code == 201, response.get_json()
    rider = response.get_json()
    assert rider["request"]["direction"] == "to_campus"
    assert match(client, batch).status_code == 200
    with client.session_transaction() as session:
        session["batch"] = batch["id"]
    page = client.get(f"/?rider={rider['id']}").get_data(as_text=True)
    assert "08:30" in page


def test_phone_and_dashboard_share_one_batch(client):
    """The dashboard shows a join code; a phone books into that batch; dashboard matching changes the phone's plan."""
    page = client.get("/?view=match").get_data(as_text=True)
    with client.session_transaction() as session:
        csrf, batch_id = session["csrf"], session["batch"]
    with campus.app.app_context():
        code, _ = campus.join_code(campus.database(), batch_id)
    assert code in page

    token = verified_join(client, code, "Maha")
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


def _verification_code(caplog):
    codes = re.findall(r"SIMULATED student verification for \S+: code (\d{6}) \(no email sent\)", caplog.text)
    assert codes, caplog.text
    return codes[-1]


def _university(client, token, name):
    response = client.get("/api/v1/universities", headers=auth(token))
    assert response.status_code == 200
    return next(row for row in response.get_json()["universities"] if row["name"] == name)


def test_universities_require_bearer_and_return_screen_fields(client):
    batch = new_batch(client)
    token = join(client, batch["joinCode"])
    assert client.get("/api/v1/universities").status_code == 401

    results = client.get("/api/v1/universities", headers=auth(token)).get_json()["universities"]
    assert results == [
        {"id": row["id"], "name": row["name"], "city": row["city"], "campus": row["campus"],
         "gate": row["gate"], "available": row["available"]}
        for row in results
    ]
    assert {row["name"]: row["available"] for row in results} == {
        "Al-Balqa Applied University": True,
        "University of Jordan": False,
        "Yarmouk University": False,
    }
    assert _university(client, token, "University of Jordan")["campus"] == "Amman campus"


def test_verification_start_rejects_wrong_domain_and_unavailable_campus(client):
    batch = new_batch(client)
    token = join(client, batch["joinCode"])
    available = _university(client, token, "Al-Balqa Applied University")
    unavailable = _university(client, token, "University of Jordan")

    wrong_domain = client.post("/api/v1/verification/start", headers=auth(token), json={
        "universityId": available["id"], "email": "lina@ju.edu.jo", "firstName": "Lina",
    })
    assert wrong_domain.status_code == 400
    assert wrong_domain.get_json()["error"]["code"] == "email_not_university"

    closed = client.post("/api/v1/verification/start", headers=auth(token), json={
        "universityId": unavailable["id"], "email": "lina@ju.edu.jo", "firstName": "Lina",
    })
    assert closed.status_code == 409
    assert closed.get_json()["error"]["code"] == "campus_unavailable"
    with campus.app.app_context():
        db = campus.database()
        assert db.execute("SELECT COUNT(*) FROM students").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM verification_challenges").fetchone()[0] == 0


def test_verification_start_masks_email_logs_demo_code_and_uses_amman_expiry(client, caplog, monkeypatch):
    batch = new_batch(client)
    token = join(client, batch["joinCode"])
    school = _university(client, token, "Al-Balqa Applied University")
    at = datetime(2026, 11, 27, 12, 0, tzinfo=student_verification.now().tzinfo)
    monkeypatch.setattr(student_verification, "now", lambda: at)
    monkeypatch.setattr(student_verification.secrets, "randbelow", lambda _limit: 123456)
    email = "lina.haddad@bau.edu.jo"

    response = client.post("/api/v1/verification/start", headers=auth(token), json={
        "universityId": school["id"], "email": email, "firstName": "Lina Haddad",
    })
    assert response.status_code == 200
    body = response.get_json()
    assert body["maskedEmail"] == "l***@bau.edu.jo"
    assert body["delivery"] == "console_demo"
    assert body["expiresAt"] == (at + timedelta(minutes=5)).isoformat()
    assert body["resendAvailableAt"] == (at + timedelta(seconds=30)).isoformat()
    assert body["expiresAt"].endswith("+03:00")
    assert "code" not in body and email not in json.dumps(body) and "Haddad" not in json.dumps(body)
    assert _verification_code(caplog) == "123456"
    assert email in caplog.text and "no email sent" in caplog.text


def test_verification_resend_is_throttled_and_replaces_previous_code(client, caplog, monkeypatch):
    batch = new_batch(client)
    token = join(client, batch["joinCode"])
    school = _university(client, token, "Al-Balqa Applied University")
    at = datetime(2026, 11, 27, 12, 0, tzinfo=student_verification.now().tzinfo)
    monkeypatch.setattr(student_verification, "now", lambda: at)
    start = client.post("/api/v1/verification/start", headers=auth(token), json={
        "universityId": school["id"], "email": "rama@bau.edu.jo", "firstName": "Rama",
    })
    assert start.status_code == 200
    old_code = _verification_code(caplog)

    too_soon = client.post("/api/v1/verification/resend", headers=auth(token))
    assert too_soon.status_code == 429
    assert too_soon.get_json()["error"]["code"] == "verification_resend_too_soon"

    monkeypatch.setattr(student_verification, "now", lambda: at + timedelta(seconds=31))
    caplog.clear()
    resent = client.post("/api/v1/verification/resend", headers=auth(token))
    assert resent.status_code == 200
    body = resent.get_json()
    new_code = _verification_code(caplog)
    assert new_code != old_code
    assert body["maskedEmail"] == "r***@bau.edu.jo"
    assert body["message"] == "New code sent" and body["delivery"] == "console_demo"
    assert "rama@bau.edu.jo" not in json.dumps(body) and new_code not in json.dumps(body)

    old_attempt = client.post("/api/v1/verification/confirm", headers=auth(token), json={"code": old_code})
    assert old_attempt.status_code == 400
    assert old_attempt.get_json()["error"]["code"] == "verification_code_invalid"
    verified = client.post("/api/v1/verification/confirm", headers=auth(token), json={"code": new_code})
    assert verified.status_code == 200
    assert verified.get_json()["student"]["firstName"] == "Rama"


def test_verification_code_expiry_and_lockout_on_sixth_attempt(client, caplog, monkeypatch):
    batch = new_batch(client)
    token = join(client, batch["joinCode"])
    school = _university(client, token, "Al-Balqa Applied University")
    at = datetime(2026, 11, 27, 12, 0, tzinfo=student_verification.now().tzinfo)
    monkeypatch.setattr(student_verification, "now", lambda: at)
    start = client.post("/api/v1/verification/start", headers=auth(token), json={
        "universityId": school["id"], "email": "huda@bau.edu.jo", "firstName": "Huda",
    })
    assert start.status_code == 200
    correct_code = _verification_code(caplog)

    monkeypatch.setattr(student_verification, "now", lambda: at + timedelta(minutes=5))
    expired = client.post("/api/v1/verification/confirm", headers=auth(token), json={"code": correct_code})
    assert expired.status_code == 410
    assert expired.get_json()["error"]["code"] == "verification_code_expired"

    # A fresh phone session has its own challenge, so the expiry check above cannot affect lockout.
    other_token = join(client, batch["joinCode"])
    monkeypatch.setattr(student_verification, "now", lambda: at)
    other_start = client.post("/api/v1/verification/start", headers=auth(other_token), json={
        "universityId": school["id"], "email": "dana@bau.edu.jo", "firstName": "Dana",
    })
    assert other_start.status_code == 200
    actual = int(_verification_code(caplog))
    wrong_code = f"{(actual + 1) % 10**6:06d}"

    for _ in range(5):
        wrong = client.post("/api/v1/verification/confirm", headers=auth(other_token), json={"code": wrong_code})
        assert wrong.status_code == 400
        assert wrong.get_json()["error"]["code"] == "verification_code_invalid"
    locked = client.post("/api/v1/verification/confirm", headers=auth(other_token), json={"code": wrong_code})
    assert locked.status_code == 429
    assert locked.get_json()["error"]["code"] == "verification_locked"


def test_successful_verification_issues_student_token_and_limits_other_rider_details(client, caplog):
    batch = new_batch(client)
    school = None
    verified_tokens = []
    for email, first_name in (("lina@bau.edu.jo", "Lina Haddad"), ("rama@bau.edu.jo", "Rama Saleh")):
        phone_token = join(client, batch["joinCode"])
        school = school or _university(client, phone_token, "Al-Balqa Applied University")
        started = client.post("/api/v1/verification/start", headers=auth(phone_token), json={
            "universityId": school["id"], "email": email, "firstName": first_name,
        })
        assert started.status_code == 200
        code = _verification_code(caplog)
        caplog.clear()
        result = client.post("/api/v1/verification/confirm", headers=auth(phone_token), json={"code": code})
        assert result.status_code == 200
        body = result.get_json()
        assert body["tokenType"] == "Bearer" and body["token"]
        assert body["nextScreen"] == "05"
        assert body["student"]["firstName"] == first_name.split()[0]
        assert body["student"]["verified"] is True
        assert body["student"]["verifiedAt"].endswith("+03:00")
        assert "email" not in body["student"] and "phone" not in json.dumps(body).lower()
        me = client.get("/api/v1/me", headers=auth(body["token"]))
        assert me.status_code == 200 and me.get_json()["verified"] is True
        verified_tokens.append(profile_gender(body["token"], "woman"))  # Both book women-only rides below

    rider_ids = []
    for student_token, name, stop, request_id in (
        (verified_tokens[0], "Lina Haddad", "Dabouq", "lina-request-0001"),
        (verified_tokens[1], "Rama Saleh", "Al Bayader", "rama-request-0001"),
    ):
        booked = client.post(f"/api/v1/batches/{batch['id']}/riders", headers=auth(student_token), json={
            "name": name, "classEnd": "16:00", "stop": stop, "woman": True, "womenOnly": True,
            "clientRequestId": request_id,
        })
        assert booked.status_code == 201
        rider_ids.append(booked.get_json()["id"])
    assert match(client, batch).status_code == 200
    own = client.get(f"/api/v1/riders/{rider_ids[0]}", headers=auth(verified_tokens[0]))
    assert own.status_code == 200
    view = own.get_json()
    serialized = json.dumps(view)
    assert "Rama" in view["plan"]["riders"]
    assert "Rama Saleh" not in serialized
    assert "rama@bau.edu.jo" not in serialized and "lina@bau.edu.jo" not in serialized
    assert "phone" not in serialized.lower()
    assert any(drop["rider"] == "Rama" and drop["stop"] == "Al Bayader" for drop in view["plan"]["dropOffs"])


def test_unavailable_campus_notify_request_is_saved_and_returns_toast_message(client):
    batch = new_batch(client)
    token = join(client, batch["joinCode"])
    school = _university(client, token, "University of Jordan")
    response = client.post(f"/api/v1/universities/{school['id']}/notify", headers=auth(token))
    assert response.status_code == 200
    body = response.get_json()
    assert body["notificationRequested"] is True
    assert body["message"] == "We'll keep you posted"
    assert body["university"]["id"] == school["id"] and body["university"]["available"] is False
    repeated = client.post(f"/api/v1/universities/{school['id']}/notify", headers=auth(token))
    assert repeated.status_code == 200
    with campus.app.app_context():
        db = campus.database()
        assert db.execute(
            "SELECT COUNT(*) FROM university_notifications WHERE university_id = ?", (school["id"],)
        ).fetchone()[0] == 1


# ---------- Friends groups and the profile's men-only / women-only option ----------

def book_with(client, batch, token, request_id, stop="Dabouq", class_end="16:00", **extra):
    """A current-client booking: gender comes from the profile unless sent, plus preference and friends."""
    return client.post(f"/api/v1/batches/{batch['id']}/riders", headers=auth(token), json={
        "classEnd": class_end, "stop": stop, "clientRequestId": request_id, "preference": "mixed", **extra})


def test_student_profile_gender_defaults_to_man(client):
    batch = new_batch(client)
    token = verified_join(client, batch["joinCode"], "Omar")
    assert client.get("/api/v1/me", headers=auth(token)).get_json()["student"]["gender"] == "man"
    rejoined = client.post("/api/v1/demo-sessions/join", json={"joinCode": batch["joinCode"]}, headers=auth(token))
    assert rejoined.get_json()["student"]["gender"] == "man"
    rider = book_with(client, batch, token, "omar-profile-01").get_json()
    assert rider["request"]["gender"] == "man" and rider["request"]["preference"] == "mixed"


def test_start_group_returns_code_and_retry_returns_same_rider(client):
    batch = new_batch(client)
    token = verified_join(client, batch["joinCode"], "Omar")
    first = book_with(client, batch, token, "omar-group-0001", friends={"mode": "start", "open": False})
    assert first.status_code == 201, first.get_json()
    request = first.get_json()["request"]
    assert re.fullmatch(r"GR-\d\d", request["friendGroup"]) and request["groupOpen"] is False
    retry = book_with(client, batch, token, "omar-group-0001", friends={"mode": "start", "open": False})
    assert retry.status_code == 200 and retry.get_json()["id"] == first.get_json()["id"]
    for changed in ({"mode": "start", "open": True}, None, {"mode": "join", "code": "GR-99"}):
        conflict = book_with(client, batch, token, "omar-group-0001", friends=changed)
        assert conflict.status_code == 409 and conflict.get_json()["error"]["code"] == "request_conflict"


def test_friends_who_join_a_group_ride_in_one_car(client):
    batch = new_batch(client)
    omar = verified_join(client, batch["joinCode"], "Omar")
    started = book_with(client, batch, omar, "omar-friends-01", gender="man", preference="men",
                        friends={"mode": "start", "open": True}).get_json()
    code = started["request"]["friendGroup"]
    zaid = verified_join(client, batch["joinCode"], "Zaid")
    joined = book_with(client, batch, zaid, "zaid-friends-01", stop="Wadi As-Seer", class_end="16:05",
                       friends={"mode": "join", "code": code.lower()})
    assert joined.status_code == 201, joined.get_json()
    assert joined.get_json()["request"]["friendGroup"] == code
    retry = book_with(client, batch, zaid, "zaid-friends-01", stop="Wadi As-Seer", class_end="16:05",
                      friends={"mode": "join", "code": code})
    assert retry.status_code == 200
    # Two other students nearby who would otherwise be a better fit for one of the friends
    student(client, batch, "Sami", stop="Khalda", class_end="16:00", woman=False)
    student(client, batch, "Lina", stop="Al Bayader", class_end="16:10")
    assert match(client, batch).status_code == 200
    detail = client.get(f"/api/v1/batches/{batch['id']}", headers=auth(batch["operatorToken"])).get_json()
    cars = {r["name"]: r["car"] for r in detail["riders"]}
    assert cars["Omar"] is not None and cars["Omar"] == cars["Zaid"]
    plan = client.get(f"/api/v1/riders/{started['id']}", headers=auth(omar)).get_json()["plan"]
    assert plan["friendGroup"] == code and "Zaid" in plan["riders"]


def test_men_only_for_a_man_and_women_only_rejected(client):
    batch = new_batch(client)
    omar = verified_join(client, batch["joinCode"], "Omar")
    men = book_with(client, batch, omar, "omar-men-only-1", preference="men")
    assert men.status_code == 201 and men.get_json()["request"]["preference"] == "men"
    zaid = verified_join(client, batch["joinCode"], "Zaid")
    women = book_with(client, batch, zaid, "zaid-women-only", preference="women")
    assert women.status_code == 400 and women.get_json()["error"]["code"] == "invalid_input"
    assert book_with(client, batch, zaid, "zaid-men-only-1", stop="Al Bayader", preference="men").status_code == 201
    assert match(client, batch).status_code == 200
    plan = client.get(f"/api/v1/riders/{men.get_json()['id']}", headers=auth(omar)).get_json()["plan"]
    assert plan["shared"] and plan["only"] == "men" and plan["womenOnly"] is False


def test_group_errors(client):
    batch = new_batch(client)
    lead = verified_join(client, batch["joinCode"], "Omar")
    code = book_with(client, batch, lead, "lead-group-0001", friends={"mode": "start", "open": True}).get_json()["request"]["friendGroup"]

    def try_join(name, join_code=None, **kwargs):
        token = verified_join(client, batch["joinCode"], name)
        return book_with(client, batch, token, f"{name.lower()}-join-001", friends={"mode": "join", "code": join_code or code}, **kwargs)

    def code_of(response):
        return response.status_code, response.get_json()["error"]["code"]

    assert code_of(try_join("Ali", "GR-00")) == (404, "group_not_found")
    assert code_of(try_join("Badr", stop="Marka")) == (409, "group_mismatch")
    assert code_of(try_join("Fadi", class_end="16:30")) == (409, "group_mismatch")
    assert code_of(try_join("Hadi", direction="to_campus", classStart="08:30")) == (409, "group_mismatch")
    bad = verified_join(client, batch["joinCode"], "Jad")
    assert code_of(book_with(client, batch, bad, "jad-join-00001", friends={"mode": "join"})) == (400, "invalid_input")
    assert code_of(book_with(client, batch, bad, "jad-join-00002", friends={"mode": "invite"})) == (400, "invalid_input")
    for name in ("Karim", "Majd", "Nabil"):
        assert try_join(name).status_code == 201
    assert code_of(try_join("Rami")) == (409, "group_full")
    assert match(client, batch).status_code == 200
    late = verified_join(client, batch["joinCode"], "Tariq")
    # Brief 05: after matching, a new friends group waits in a lobby for its own car instead of being refused
    started = book_with(client, batch, late, "tariq-start-001", friends={"mode": "start", "open": True})
    assert started.status_code == 201 and started.get_json()["group"]["status"] == "lobby"


def test_web_demo_student_is_a_man_by_default(client):
    with campus.app.test_request_context():
        assert campus.student_profile()["gender"] == "man"
    page = client.get("/yalla/plan/preferences").get_data(as_text=True)
    assert re.search(r'<label hidden><input type="radio" name="preference" value="women"', page)
    assert re.search(r'<label><input type="radio" name="preference" value="men"', page)


@pytest.mark.parametrize("open_seats, friend_joins, shares_with_stranger", [
    (False, False, False),  # closed group of one: no friend joined yet, still no strangers
    (True, False, True),    # open group of one: strangers may fill the seats
    (False, True, False),   # closed group of two: the friends ride without strangers
])
def test_closed_group_takes_no_strangers_even_before_a_friend_joins(client, open_seats, friend_joins, shares_with_stranger):
    batch = new_batch(client)
    omar = verified_join(client, batch["joinCode"], "Omar")
    lead = book_with(client, batch, omar, "closed-lead-001", friends={"mode": "start", "open": open_seats}).get_json()
    if friend_joins:
        zaid = verified_join(client, batch["joinCode"], "Zaid")
        joined = book_with(client, batch, zaid, "closed-zaid-001", stop="Al Bayader",
                           friends={"mode": "join", "code": lead["request"]["friendGroup"]})
        assert joined.status_code == 201, joined.get_json()
    student(client, batch, "Sami", stop="Al Bayader", class_end="16:00", woman=False)
    student(client, batch, "Fadi", stop="Wadi As-Seer", class_end="16:00", woman=False)
    assert match(client, batch).status_code == 200
    cars = {r["name"]: r["car"] for r in client.get(
        f"/api/v1/batches/{batch['id']}", headers=auth(batch["operatorToken"])).get_json()["riders"]}
    strangers = {cars["Sami"], cars["Fadi"]}
    assert (cars["Omar"] in strangers) is shares_with_stranger
    if friend_joins:
        assert cars["Zaid"] == cars["Omar"]
