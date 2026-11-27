"""Open a batch by QR code: the operator gets a scannable deep link, and the dashboard shows it."""
from tests.test_api import auth, client, join, new_batch  # noqa: F401  (client is a fixture)


def test_join_qr_authorization_and_dashboard(client):
    batch = new_batch(client)
    path = f"/api/v1/batches/{batch['id']}/join-qr"

    response = client.get(path, headers=auth(batch["operatorToken"]))
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["joinCode"] == batch["joinCode"]
    assert payload["joinCodeExpiresAt"] == batch["joinCodeExpiresAt"]
    assert payload["joinUrl"] == f"campus-connect://join?code={batch['joinCode']}"
    assert "<svg" in payload["svg"]

    assert client.get(path, headers=auth(join(client, payload["joinCode"]))).status_code == 403
    assert client.get(path).status_code == 401

    assert client.get("/?view=match").status_code == 200
    with client.session_transaction() as session:
        csrf = session["csrf"]
    page = client.post("/batches/open", data={"csrf": csrf, "operator_token": batch["operatorToken"]},
                       follow_redirects=True)
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert f"<strong>{batch['joinCode']}</strong>" in html
    assert 'aria-label="QR code to join this batch"' in html
    assert payload["svg"] in html
