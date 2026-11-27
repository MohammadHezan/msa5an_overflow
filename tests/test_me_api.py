"""Student trip history, saved routes, public sharing and ratings (screens 16, 26-28 and the share sheet)."""
import hashlib

import pytest

import app as campus
from store import advance_clock, choose, clock, find_token, locked_batch, now
from tests.test_api import auth, client, join, match, new_batch, student, west_car  # noqa: F401  (fixtures)
from yalla import car_details


BASE = "/api/v1"


def identity(token, student_id=None):
    """Bind a demo token to a verified identity without exercising email delivery."""
    with campus.app.app_context():
        db = campus.database()
        with db:
            if student_id is None:
                school = db.execute("SELECT * FROM universities WHERE available = 1 LIMIT 1").fetchone()
                student_id = db.execute(
                    "INSERT INTO students (university, email, first_name, verified_at) VALUES (?, ?, ?, ?)",
                    (school["id"], f"{token[:16]}@{school['email_domain']}", "Student", now().isoformat()),
                ).lastrowid
            db.execute("UPDATE api_tokens SET student_id = ? WHERE token_hash = ?",
                       (student_id, find_token(db, token)["token_hash"]))
        return student_id


def finish(batch, rider_id, shared=False):
    """Advance the real demo clock; simulate departure for a confirmed shared car."""
    with campus.app.app_context():
        db = campus.database()
        with db:
            saved = locked_batch(db, batch["id"])
            if shared:
                row = db.execute("SELECT car FROM riders WHERE id = ?", (rider_id,)).fetchone()
                db.execute("UPDATE cars SET mode = 'go', departed_at = ? WHERE batch = ? AND car = ?",
                           (clock(saved).isoformat(), batch["id"], row["car"]))
            else:
                choose(db, saved, rider_id, "go")
            advance_clock(db, batch["id"], 120)


def assert_error(response, status, code):
    assert response.status_code == status, response.get_json()
    assert response.get_json()["error"]["code"] == code


def test_trips_across_batches(client):
    old = new_batch(client)
    old_token, old_id = student(client, old, "Sara")
    owner = identity(old_token)
    assert match(client, old).status_code == 200
    finish(old, old_id)
    current = new_batch(client)
    token, rider_id = student(client, current, "Sara")
    identity(token, owner)
    student(client, current, "Other", stop="Khalda")
    declined = new_batch(client)
    declined_token, declined_id = student(client, declined, "Sara")
    identity(declined_token, owner)
    assert match(client, declined).status_code == 200
    assert client.post(f"{BASE}/riders/{declined_id}/decline", headers=auth(declined_token)).status_code == 200
    upcoming = client.get(f"{BASE}/me/trips", headers=auth(token)).get_json()["trips"]
    past = client.get(f"{BASE}/me/trips?tab=past", headers=auth(token)).get_json()["trips"]
    assert [r["riderId"] for r in upcoming] == [rider_id]
    assert upcoming[0]["status"] == "waiting" and upcoming[0]["journey"] == "planned"
    assert upcoming[0]["to"] == "Dabouq" and "rideCode" in upcoming[0]
    assert upcoming[0]["share"] is None and upcoming[0]["soloFare"]["currency"] == "JOD"
    assert [r["riderId"] for r in past] == [old_id]
    assert past[0]["batchId"] == old["id"] and past[0]["status"] == "arrived"
    assert past[0]["journey"] == "leave_now" and "rideCode" not in past[0]
    assert past[0]["share"]["currency"] == "JOD"
    anonymous = join(client, current["joinCode"])
    assert client.get(f"{BASE}/me/trips", headers=auth(anonymous)).get_json() == {"trips": []}
    assert_error(client.get(f"{BASE}/me/trips?tab=invalid", headers=auth(token)), 400, "invalid_input")


@pytest.mark.parametrize("changes", [
    {"name": " "}, {"name": "x" * 41}, {"stop": "Unknown"}, {"direction": "other"},
    {"readyAt": "7:00"}, {"readyAt": "06:59"}, {"readyAt": "23:01"}, {"readyAt": "12:60"},
    {"readyAt": 700}, {"mode": "now"}, {"quiet": 1},
])
def test_saved_route_validation(client, changes):
    batch = new_batch(client)
    token = join(client, batch["joinCode"])
    identity(token)
    body = {"name": "Home", "stop": "Dabouq", "readyAt": "16:00", **changes}
    assert_error(client.post(f"{BASE}/me/routes", headers=auth(token), json=body), 400, "invalid_input")
    assert client.get(f"{BASE}/me/routes", headers=auth(token)).get_json() == {"routes": []}


def test_saved_routes_owner_limit_and_no_booking(client):
    batch = new_batch(client)
    owner_token, other_token = (join(client, batch["joinCode"]) for _ in range(2))
    identity(owner_token)
    identity(other_token)
    url = f"{BASE}/me/routes"
    body = {"name": "Home", "stop": "Dabouq", "readyAt": "07:00", "quiet": True}
    saved = client.post(url, headers=auth(owner_token), json=body)
    assert saved.status_code == 201
    route = saved.get_json()
    assert route == {"id": route["id"], **body, "direction": "from_campus", "mode": "planned"}
    assert client.get(url, headers=auth(other_token)).get_json() == {"routes": []}
    item_url = f"{url}/{route['id']}"
    assert_error(client.delete(item_url, headers=auth(other_token)), 404, "not_found")
    for i in range(9):
        assert client.post(url, headers=auth(owner_token), json={**body, "name": f"Route {i}"}).status_code == 201
    assert_error(client.post(url, headers=auth(owner_token), json=body), 409, "too_many_routes")
    assert len(client.get(url, headers=auth(owner_token)).get_json()["routes"]) == 10
    assert client.delete(item_url, headers=auth(owner_token)).status_code == 204
    assert client.post(url, headers=auth(owner_token), json={"name": "Now", "stop": "Dabouq",
                       "mode": "leave_now"}).status_code == 201
    assert client.post(url, headers=auth(other_token), json=body).status_code == 201
    with campus.app.app_context():
        assert campus.database().execute("SELECT COUNT(*) FROM riders").fetchone()[0] == 0


def test_share_link_private_and_expires(client, west_car):
    batch, riders = west_car
    token, rider_id = riders["Sara"]
    codes = []
    for member_token, member_id in riders.values():
        detail = client.get(f"{BASE}/riders/{member_id}", headers=auth(member_token)).get_json()
        confirmed = client.post(f"{BASE}/riders/{member_id}/confirm", headers=auth(member_token),
                                json={"signature": detail["plan"]["signature"]})
        assert confirmed.status_code == 200
        codes.append(confirmed.get_json()["rideCode"])
    endpoint = f"{BASE}/riders/{rider_id}/share-link"
    assert_error(client.post(endpoint, headers=auth(riders["Rama"][0])), 403, "forbidden")
    assert_error(client.post(endpoint, headers=auth(batch["operatorToken"])), 403, "forbidden")
    created = client.post(endpoint, headers=auth(token))
    assert created.status_code == 201
    url = created.get_json()["url"]
    secret = url.rsplit("/", 1)[1]
    with campus.app.app_context():
        db = campus.database()
        row = db.execute("SELECT * FROM trip_shares").fetchone()
        assert row["token_hash"] == hashlib.sha256(secret.encode()).hexdigest()
        assert row["rider"] == rider_id and secret != row["token_hash"]
        loaded, _ = campus.load_riders(db, campus.get_batch(db, batch["id"]))
        plan = next(r["plan"] for r in loaded if r["id"] == rider_id)
    response = client.get(url)
    assert response.status_code == 200
    public = response.get_json()
    car = car_details(plan)
    assert public == {"stop": "Dabouq", "pickupTime": plan["rider_times"].get(rider_id, plan["pickup"]),
                      "status": "confirmed", "captain": plan["captain"]["name"].split()[0],
                      "car": car["car"], "plate": car["plate"]}
    for private in ["Sara", "Rama", "Huda", "Al Bayader", "Wadi As-Seer", *codes]:
        assert private and private not in response.get_data(as_text=True)
    assert_error(client.get(f"{BASE}/shared/unknown"), 404, "not_found")
    finish(batch, rider_id, shared=True)
    assert_error(client.get(url), 410, "trip_finished")


def test_share_link_declined(client):
    batch = new_batch(client)
    token, rider_id = student(client, batch, "Sara")
    assert match(client, batch).status_code == 200
    endpoint = f"{BASE}/riders/{rider_id}"
    url = client.post(endpoint + "/share-link", headers=auth(token)).get_json()["url"]
    assert client.post(endpoint + "/decline", headers=auth(token)).status_code == 200
    assert_error(client.get(url), 410, "trip_finished")


def test_rating_after_arrival_only_once(client):
    batch = new_batch(client)
    token, rider_id = student(client, batch, "Sara")
    assert match(client, batch).status_code == 200
    endpoint = f"{BASE}/riders/{rider_id}/rating"
    assert_error(client.post(endpoint, headers=auth(token), json={"stars": 5}), 409, "not_finished")
    finish(batch, rider_id)
    for body in ({"stars": 0}, {"stars": 6}, {"stars": True}, {"stars": 3.5},
                 {"stars": 5, "comment": "x" * 301}):
        assert_error(client.post(endpoint, headers=auth(token), json=body), 400, "invalid_input")
    assert_error(client.post(endpoint, headers=auth(batch["operatorToken"]), json={"stars": 5}), 403, "forbidden")
    other = join(client, batch["joinCode"])
    assert_error(client.post(endpoint, headers=auth(other), json={"stars": 5}), 403, "forbidden")
    rating = client.post(endpoint, headers=auth(token), json={"stars": 5, "comment": "Great ride"})
    assert rating.status_code == 201
    assert rating.get_json() == {"riderId": rider_id, "stars": 5, "comment": "Great ride"}
    assert_error(client.post(endpoint, headers=auth(token), json={"stars": 1}), 409, "already_rated")
    with campus.app.app_context():
        rows = campus.database().execute("SELECT * FROM ride_ratings").fetchall()
        assert len(rows) == 1 and rows[0]["stars"] == 5 and rows[0]["comment"] == "Great ride"
