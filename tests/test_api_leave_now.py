"""JSON API for screens 08, 13-14 and 17-25: estimate, captain details, leave now & share, and turning down a pickup."""

from tests.test_api import auth, client, match, new_batch, student  # noqa: F401  (client is a fixture)


def rider(client, token, rider_id):
    response = client.get(f"/api/v1/riders/{rider_id}", headers=auth(token))
    assert response.status_code == 200
    return response.get_json()


def test_estimate_for_a_drop_off(client):
    batch = new_batch(client)
    token, _ = student(client, batch, "Sara")
    body = client.get("/api/v1/estimate?stop=Dabouq", headers=auth(token)).get_json()
    assert body["sampleShare"]["fils"] < body["soloFare"]["fils"] and body["soloFare"]["currency"] == "JOD"
    assert body["walkMinutes"] >= 0
    assert client.get("/api/v1/estimate?stop=Nowhere", headers=auth(token)).status_code == 400
    assert client.get("/api/v1/estimate?stop=Dabouq").status_code == 401


def test_shared_plan_shows_saving_percent_and_captain(client):
    batch = new_batch(client)
    sara = student(client, batch, "Sara", stop="Dabouq", women_only=True)
    student(client, batch, "Rama", stop="Al Bayader", class_end="15:55", women_only=True)
    assert match(client, batch).status_code == 200
    plan = rider(client, *sara)["plan"]
    assert plan["savingPercent"] == round(plan["saving"]["fils"] * 100 / plan["soloFare"]["fils"])
    if plan["captain"]:
        assert set(plan["captain"]) == {"firstName", "rating", "ratingCount", "car", "plate"}


def test_leave_now_then_a_joiner_lowers_the_fare_and_can_be_turned_down(client):
    batch = new_batch(client)
    zaid = student(client, batch, "Zaid", stop="Wadi As-Seer", woman=False)
    assert match(client, batch).status_code == 200
    assert rider(client, *zaid)["status"] == "no_match"

    bad = client.post(f"/api/v1/riders/{zaid[1]}/choice", headers=auth(zaid[0]), json={"choice": "later"})
    assert bad.status_code == 400
    gone = client.post(f"/api/v1/riders/{zaid[1]}/choice", headers=auth(zaid[0]), json={"choice": "go"}).get_json()
    assert gone["status"] == "on_the_way" and gone["plan"]["goNow"]
    assert gone["plan"]["fareCap"] == gone["soloFare"] and gone["plan"]["share"] == gone["soloFare"]
    assert gone["plan"]["legs"] and gone["plan"]["legs"][0]["aboard"] == ["You"]

    ali = student(client, batch, "Ali", stop="Dabouq", woman=False)  # A late request joins the car on its way
    shared = rider(client, *zaid)
    assert shared["plan"]["riders"] == ["Ali"]
    assert shared["plan"]["share"]["fils"] < shared["plan"]["fareCap"]["fils"]
    assert any(len(leg["aboard"]) == 2 for leg in shared["plan"]["legs"])

    # Ali cannot turn down Zaid, whose car it is; Zaid can turn down Ali.
    assert client.post(f"/api/v1/riders/{ali[1]}/keep-route", headers=auth(ali[0]),
                       json={"riderIds": [zaid[1]]}).status_code == 403
    kept = client.post(f"/api/v1/riders/{zaid[1]}/keep-route", headers=auth(zaid[0]), json={"riderIds": [ali[1]]})
    assert kept.status_code == 200
    assert kept.get_json()["plan"]["riders"] == [] and kept.get_json()["plan"]["share"] == kept.get_json()["soloFare"]
    assert rider(client, *ali)["status"] == "declined"


def test_keep_route_needs_a_leave_now_car(client):
    batch = new_batch(client)
    sara = student(client, batch, "Sara")
    response = client.post(f"/api/v1/riders/{sara[1]}/keep-route", headers=auth(sara[0]), json={"riderIds": [sara[1] + 1]})
    assert response.status_code == 409
    assert client.post(f"/api/v1/riders/{sara[1]}/keep-route", headers=auth(sara[0]), json={"riderIds": []}).status_code == 400
