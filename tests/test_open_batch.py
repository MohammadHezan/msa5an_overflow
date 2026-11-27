"""Dashboard opening API-created batches with an operator token, and cleanup of old API batches."""
from datetime import datetime, timedelta, timezone

import pytest

import app as campus
from store import utc_stamp


@pytest.fixture
def client(tmp_path):
    campus.app.config.update(TESTING=True, DATABASE=tmp_path / "test.sqlite")
    with campus.app.test_client() as client:
        client.get("/")
        yield client


def post(client, path, **form):
    with client.session_transaction() as session:
        token = session["csrf"]
    return client.post(path, data={"csrf": token, **form})


def session_batches(client):
    with client.session_transaction() as session:
        return session["batch"], session.get("own_batch", session["batch"])


def api_batch(client, mode="seeded"):
    response = client.post("/api/v1/batches", json={"mode": mode})
    assert response.status_code == 201
    return response.get_json()


def sql(query, *args):
    with campus.app.app_context():
        db = campus.database()
        with db:
            return db.execute(query, args).fetchall()


def test_open_api_batch_then_match_and_confirm_from_dashboard(client):
    own, _ = session_batches(client)
    batch = api_batch(client)
    response = post(client, "/batches/open", operator_token=batch["operatorToken"])
    assert response.status_code == 302 and "view=match" in response.location
    viewing, kept = session_batches(client)
    assert viewing == batch["id"] and kept == own
    page = client.get("/?view=match").get_data(as_text=True)
    assert "Viewing an API-created batch" in page and batch["joinCode"] in page

    assert post(client, "/match").status_code == 302
    detail = client.get(f"/api/v1/batches/{batch['id']}",
                        headers={"Authorization": f"Bearer {batch['operatorToken']}"}).get_json()
    assert detail["matched"] and detail["cars"]
    rider = next(r for r in detail["cars"][0]["riders"])
    full = client.get(f"/api/v1/riders/{rider['id']}",
                      headers={"Authorization": f"Bearer {batch['operatorToken']}"}).get_json()
    post(client, f"/riders/{rider['id']}/confirm", plan=full["plan"]["signature"])
    assert sql("SELECT confirmed_plan FROM riders WHERE id = ?", rider["id"])[0][0] is not None
    assert "Pickup" in client.get("/?view=trips").get_data(as_text=True)

    # The browser's own batch was kept and can be reopened
    assert post(client, "/batches/own").status_code == 302
    assert session_batches(client)[0] == own
    assert sql("SELECT 1 FROM batches WHERE id = ?", batch["id"])


def test_reset_while_viewing_api_batch_keeps_it(client):
    own, _ = session_batches(client)
    batch = api_batch(client)
    post(client, "/batches/open", operator_token=batch["operatorToken"])
    post(client, "/reset", mode="empty")
    viewing, kept = session_batches(client)
    assert viewing == kept != own
    assert sql("SELECT 1 FROM batches WHERE id = ?", batch["id"])
    assert not sql("SELECT 1 FROM batches WHERE id = ?", own)


def test_bad_or_student_token_is_rejected(client):
    own, _ = session_batches(client)
    batch = api_batch(client)
    student = client.post("/api/v1/demo-sessions/join", json={"joinCode": batch["joinCode"]}).get_json()["token"]
    for token in ("nope", student, ""):
        response = post(client, "/batches/open", operator_token=token)
        assert response.status_code == 302
        assert session_batches(client)[0] == own


def test_old_api_batches_are_deleted_but_web_batches_stay(client):
    own, _ = session_batches(client)
    old = api_batch(client)
    fresh = api_batch(client)
    stale = utc_stamp(datetime.now(timezone.utc) - timedelta(hours=25))
    sql("UPDATE batches SET created_at = ? WHERE id IN (?, ?)", stale, old["id"], own)
    api_batch(client)  # Creating a batch runs the cleanup
    assert not sql("SELECT 1 FROM batches WHERE id = ?", old["id"])
    assert not sql("SELECT 1 FROM api_tokens WHERE batch = ?", old["id"])
    assert sql("SELECT 1 FROM batches WHERE id = ?", fresh["id"])
    assert sql("SELECT 1 FROM batches WHERE id = ?", own)  # Browser batches are replaced on reset instead


def test_opened_batch_removed_falls_back_to_own(client):
    own, _ = session_batches(client)
    batch = api_batch(client)
    post(client, "/batches/open", operator_token=batch["operatorToken"])
    sql("DELETE FROM batches WHERE id = ?", batch["id"])
    page = client.get("/?view=match").get_data(as_text=True)
    assert "has been removed" in page
    assert session_batches(client)[0] == own
    assert post(client, "/batches/open", operator_token=batch["operatorToken"]).status_code == 302
    assert session_batches(client)[0] == own


def test_legacy_api_batch_survives_migration_then_expires(tmp_path):
    """A database from before created_at existed: its API batch keeps a full retention period."""
    import sqlite3
    from unittest import mock

    import store

    path = tmp_path / "legacy.sqlite"
    with sqlite3.connect(path) as db:
        db.executescript("""
            CREATE TABLE batches (id TEXT PRIMARY KEY, trip_date TEXT NOT NULL, matched INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE riders (
                id INTEGER PRIMARY KEY, batch TEXT NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
                name TEXT NOT NULL, student_key TEXT NOT NULL, class_end TEXT NOT NULL, stop TEXT NOT NULL,
                woman INTEGER NOT NULL, women_only INTEGER NOT NULL,
                car INTEGER, declined INTEGER NOT NULL DEFAULT 0, confirmed_plan TEXT, UNIQUE(batch, student_key));
            CREATE TABLE api_tokens (
                token_hash TEXT PRIMARY KEY, batch TEXT NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
                role TEXT NOT NULL, rider INTEGER REFERENCES riders(id) ON DELETE CASCADE, client_request_id TEXT);
            INSERT INTO batches (id, trip_date) VALUES ('legacy', '2026-11-28');
            INSERT INTO riders (batch, name, student_key, class_end, stop, woman, women_only)
                VALUES ('legacy', 'Sara', 'sara', '16:00', 'Dabouq', 1, 1);
        """)
        db.execute("INSERT INTO api_tokens (token_hash, batch, role) VALUES (?, 'legacy', 'operator')",
                   (store._hash("legacy-operator-token"),))
    campus.app.config.update(TESTING=True, DATABASE=path)
    with campus.app.test_client() as client:
        client.get("/")
        client.post("/api/v1/batches", json={"mode": "empty"})  # Runs cleanup
        post(client, "/batches/open", operator_token="legacy-operator-token")
        assert session_batches(client)[0] == "legacy"
        assert sql("SELECT COUNT(*) FROM riders WHERE batch = 'legacy'")[0][0] == 1
        assert sql("SELECT COUNT(*) FROM api_tokens WHERE batch = 'legacy'")[0][0] == 1

        later = datetime.now(timezone.utc) + store.API_BATCH_TTL + timedelta(hours=1)
        with mock.patch.object(store, "datetime", wraps=datetime) as fake:
            fake.now.side_effect = lambda tz=None: later if tz is timezone.utc else datetime.now(tz)
            client.post("/api/v1/batches", json={"mode": "empty"})
        assert not sql("SELECT 1 FROM batches WHERE id = 'legacy'")
        assert not sql("SELECT 1 FROM api_tokens WHERE batch = 'legacy'")


def test_legacy_database_gets_created_at_column(tmp_path):
    import sqlite3
    path = tmp_path / "legacy.sqlite"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE batches (id TEXT PRIMARY KEY, trip_date TEXT NOT NULL, matched INTEGER NOT NULL DEFAULT 0)")
    campus.app.config.update(TESTING=True, DATABASE=path)
    with campus.app.test_client() as client:
        assert client.get("/").status_code == 200
