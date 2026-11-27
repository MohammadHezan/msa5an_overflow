"""Booking takes gender from the verified profile only; the phone cannot change it (men/women-only safety)."""

from tests.test_api import auth, client, join, new_batch, profile_gender, verify  # noqa: F401  (client is a fixture)


def booking(client, batch, token, request_id, **body):
    return client.post(f"/api/v1/batches/{batch['id']}/riders", headers=auth(token),
                       json={"classEnd": "16:00", "stop": "Dabouq", "clientRequestId": request_id, **body})


def test_a_man_cannot_claim_women_only_by_sending_a_gender(client):
    batch = new_batch(client)
    token = profile_gender(verify(join(client, batch["joinCode"]), "Omar"), "man")
    for body in ({"gender": "woman", "preference": "women"}, {"woman": True, "womenOnly": True}):
        response = booking(client, batch, token, "omar-claims-0001", **body)
        assert response.status_code == 400 and response.get_json()["error"]["code"] == "invalid_input"


def test_profile_gender_wins_over_the_client_value(client):
    batch = new_batch(client)
    token = profile_gender(verify(join(client, batch["joinCode"]), "Sara"), "woman")
    response = booking(client, batch, token, "sara-books-0001", gender="man", woman=False, preference="women")
    assert response.status_code == 201
    assert response.get_json()["request"]["gender"] == "woman"


def test_verification_sets_gender_once(client):
    batch = new_batch(client)
    token = join(client, batch["joinCode"])
    schools = client.get("/api/v1/universities", headers=auth(token)).get_json()["universities"]
    bau = next(u for u in schools if u["available"])
    start = {"universityId": bau["id"], "email": "huda.s@bau.edu.jo", "gender": "woman"}
    assert client.post("/api/v1/verification/start", headers=auth(token), json={**start, "gender": "x"}).status_code == 400
    assert client.post("/api/v1/verification/start", headers=auth(token), json=start).status_code == 200
    other = join(client, batch["joinCode"])  # Same student, a second phone, claiming another gender
    assert client.post("/api/v1/verification/start", headers=auth(other), json={**start, "gender": "man"}).status_code == 200
    import app as campus
    with campus.app.app_context():
        row = campus.database().execute("SELECT gender FROM students WHERE email = 'huda.s@bau.edu.jo'").fetchone()
    assert row["gender"] == "woman"
