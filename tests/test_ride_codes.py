"""Ride codes for the driver check: issued on confirm, kept on re-confirm, cleared on decline, hidden while changed."""
import re
import sqlite3

import pytest

import app as campus
from tests.test_api import auth, match, new_batch, student
from tests.test_app import csrf, post, state

CODE = re.compile(r"CC-\d{4}")


@pytest.fixture
def matched(tmp_path):
    campus.app.config.update(TESTING=True, DATABASE=tmp_path / "test.sqlite")
    with campus.app.test_client() as client:
        client.get("/")
        post(client, "/match")
        yield client


def confirm(client, name):
    rider = state(client)[0][name]
    post(client, f"/riders/{rider['id']}/confirm", plan=rider["signature"])
    return state(client)[0][name]


def test_confirm_gives_a_code_shown_on_phone_and_trips(matched):
    assert state(matched)[0]["Sara"]["ride_code"] is None  # Not before confirming
    sara = confirm(matched, "Sara")
    assert sara["status"] == "confirmed" and CODE.fullmatch(sara["ride_code"])
    phone = matched.get(f"/?rider={sara['id']}").get_data(as_text=True)
    assert "Show this to your driver" in phone and sara["ride_code"] in phone
    assert sara["ride_code"] in matched.get("/?view=trips").get_data(as_text=True)


def test_solo_confirm_gets_a_code_and_codes_are_unique(matched):
    codes = {confirm(matched, name)["ride_code"] for name in ("Sara", "Rama", "Huda", "Zaid", "Kareem")}
    assert len(codes) == 5 and all(CODE.fullmatch(c) for c in codes)
    assert state(matched)[0]["Zaid"]["status"] == "solo_confirmed"


def test_code_hidden_while_changed_and_kept_after_reconfirm(matched):
    code = confirm(matched, "Sara")["ride_code"]
    post(matched, f"/riders/{state(matched)[0]['Huda']['id']}/decline")
    sara = state(matched)[0]["Sara"]
    assert sara["status"] == "changed" and sara["ride_code"] is None
    page = matched.get(f"/?rider={sara['id']}").get_data(as_text=True)
    assert code not in page and "Show this to your driver" not in page
    assert confirm(matched, "Sara")["ride_code"] == code


def test_decline_clears_the_code(matched):
    confirm(matched, "Rama")
    post(matched, f"/riders/{state(matched)[0]['Rama']['id']}/decline")
    with sqlite3.connect(campus.app.config["DATABASE"]) as db:
        assert db.execute("SELECT ride_code FROM riders WHERE name = 'Rama'").fetchone()[0] is None


def test_dashboard_driver_check(matched):
    code = confirm(matched, "Sara")["ride_code"]
    matched.post("/driver-check", data={"csrf": csrf(matched), "code": code.lower()})
    page = matched.get("/?view=trips").get_data(as_text=True)
    assert "Valid." in page and "Sara" in page and "Dabouq" in page
    matched.post("/driver-check", data={"csrf": csrf(matched), "code": "CC-0000" if code != "CC-0000" else "CC-0001"})
    assert "Invalid." in matched.get("/?view=trips").get_data(as_text=True)


def test_migration_adds_ride_code_to_old_databases(tmp_path):
    path = tmp_path / "old.sqlite"
    with sqlite3.connect(path) as db:
        db.executescript("""
            CREATE TABLE batches (id TEXT PRIMARY KEY, trip_date TEXT NOT NULL, matched INTEGER NOT NULL DEFAULT 0, created_at TEXT);
            CREATE TABLE riders (
                id INTEGER PRIMARY KEY, batch TEXT NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
                name TEXT NOT NULL, student_key TEXT NOT NULL, class_end TEXT NOT NULL, stop TEXT NOT NULL,
                woman INTEGER NOT NULL, women_only INTEGER NOT NULL,
                car INTEGER, declined INTEGER NOT NULL DEFAULT 0, confirmed_plan TEXT, UNIQUE(batch, student_key));
            INSERT INTO batches VALUES ('b1', '2026-11-28', 0, '2026-11-27T10:00:00+00:00');
            INSERT INTO riders (batch, name, student_key, class_end, stop, woman, women_only)
                VALUES ('b1', 'Sara', 'sara', '16:00', 'Dabouq', 1, 1);
        """)
    campus.app.config.update(TESTING=True, DATABASE=path)
    with campus.app.app_context():
        db = campus.database()
        columns = {row["name"] for row in db.execute("PRAGMA table_info(riders)")}
        assert "ride_code" in columns
        assert db.execute("SELECT name, ride_code FROM riders").fetchone()["name"] == "Sara"


# ---------- API ----------

@pytest.fixture
def client(tmp_path):
    campus.app.config.update(TESTING=True, DATABASE=tmp_path / "api.sqlite")
    with campus.app.test_client() as client:
        yield client


def west_car(client):
    batch = new_batch(client)
    riders = {
        "Sara": student(client, batch, "Sara", stop="Dabouq", class_end="16:00", women_only=True),
        "Rama": student(client, batch, "Rama", stop="Al Bayader", class_end="15:55", women_only=True),
        "Huda": student(client, batch, "Huda", stop="Wadi As-Seer", class_end="16:00", women_only=True),
    }
    assert match(client, batch).status_code == 200
    return batch, riders


def api_confirm(client, token, rider_id):
    rider = client.get(f"/api/v1/riders/{rider_id}", headers=auth(token)).get_json()
    return client.post(f"/api/v1/riders/{rider_id}/confirm", headers=auth(token),
                       json={"signature": rider["plan"]["signature"]}).get_json()


def verify(client, batch, code, token=None):
    return client.post(f"/api/v1/batches/{batch['id']}/verify-code", headers=auth(token or batch["operatorToken"]),
                       json={"code": code})


def test_api_ride_code_lifecycle(client):
    batch, riders = west_car(client)
    sara_token, sara_id = riders["Sara"]
    assert client.get(f"/api/v1/riders/{sara_id}", headers=auth(sara_token)).get_json()["rideCode"] is None
    code = api_confirm(client, sara_token, sara_id)["rideCode"]
    assert CODE.fullmatch(code)
    detail = client.get(f"/api/v1/batches/{batch['id']}", headers=auth(batch["operatorToken"])).get_json()
    assert {r["name"]: r["rideCode"] for r in detail["riders"]} == {"Sara": code, "Rama": None, "Huda": None}

    huda_token, huda_id = riders["Huda"]
    client.post(f"/api/v1/riders/{huda_id}/decline", headers=auth(huda_token))
    changed = client.get(f"/api/v1/riders/{sara_id}", headers=auth(sara_token)).get_json()
    assert changed["status"] == "changed" and changed["rideCode"] is None
    assert verify(client, batch, code).get_json() == {"valid": False}
    assert api_confirm(client, sara_token, sara_id)["rideCode"] == code


def test_api_verify_code(client):
    batch, riders = west_car(client)
    sara_token, sara_id = riders["Sara"]
    code = api_confirm(client, sara_token, sara_id)["rideCode"]

    valid = verify(client, batch, f" {code.lower()} ").get_json()
    assert valid["valid"] is True
    assert valid["rider"]["firstName"] == "Sara" and valid["rider"]["stop"] == "Dabouq"
    assert valid["rider"]["pickupTime"] == "16:15" and isinstance(valid["rider"]["carId"], int)
    assert verify(client, batch, "CC-0000" if code != "CC-0000" else "CC-0001").get_json() == {"valid": False}

    other = new_batch(client)  # A code from one batch is not valid in another
    assert verify(client, other, code).get_json() == {"valid": False}
    wrong_operator = verify(client, batch, code, token=other["operatorToken"])
    assert wrong_operator.status_code == 403
    assert verify(client, batch, code, token=sara_token).status_code == 403
    assert client.post(f"/api/v1/batches/{batch['id']}/verify-code", json={"code": code}).status_code == 401
