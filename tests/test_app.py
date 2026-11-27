"""Flask flow: load sample, match, confirm and decline."""

import pytest

import app as campus


@pytest.fixture
def client(tmp_path):
    campus.app.config.update(TESTING=True, DATABASE=tmp_path / "test.sqlite")
    with campus.app.test_client() as client:
        client.get("/")  # creates a seeded batch and CSRF token
        yield client


def csrf(client):
    with client.session_transaction() as session:
        return session["csrf"]


def post(client, path, **form):
    return client.post(path, data={"csrf": csrf(client), **form})


def state(client):
    """Riders keyed by name, using the same plan logic the pages use."""
    with client.session_transaction() as session:
        batch_id = session["batch"]
    with campus.app.app_context():
        db = campus.database()
        batch = db.execute("SELECT * FROM batches WHERE id = ?", (batch_id,)).fetchone()
        riders, cars = campus.load_riders(db, batch)
    return {r["name"]: r for r in riders}, cars


@pytest.fixture
def matched(client):
    assert post(client, "/match").status_code == 302
    return client


def test_matching_gives_sara_a_shared_ride_at_167(matched):
    riders, cars = state(matched)
    assert len(cars) == 5
    sara = riders["Sara"]
    assert sara["status"] == "review"
    assert sara["share"] == 1670 and sara["solo"] == 4500
    assert {m["name"] for m in sara["plan"]["members"]} == {"Sara", "Rama", "Huda"}
    assert riders["Zaid"]["status"] == "no_match"


def test_page_shows_sara_price(matched):
    riders, _ = state(matched)
    page = matched.get(f"/?view=trips&rider={riders['Sara']['id']}").get_data(as_text=True)
    assert "JOD 1.67" in page


def test_confirm_records_the_plan(matched):
    sara = state(matched)[0]["Sara"]
    post(matched, f"/riders/{sara['id']}/confirm", plan=sara["signature"])
    assert state(matched)[0]["Sara"]["status"] == "confirmed"


def test_confirm_with_stale_plan_is_rejected(matched):
    sara = state(matched)[0]["Sara"]
    response = post(matched, f"/riders/{sara['id']}/confirm", plan="9999|16:15|3")
    assert response.status_code == 302
    assert state(matched)[0]["Sara"]["status"] == "review"


def test_decline_reprices_the_rest_of_the_car(matched):
    riders = state(matched)[0]
    post(matched, f"/riders/{riders['Sara']['id']}/confirm", plan=riders["Sara"]["signature"])
    post(matched, f"/riders/{riders['Huda']['id']}/decline")

    riders, cars = state(matched)
    assert riders["Huda"]["status"] == "declined"
    assert riders["Huda"]["plan"] is None
    assert {m["name"] for m in riders["Sara"]["plan"]["members"]} == {"Sara", "Rama"}
    assert riders["Sara"]["share"] == 2387
    assert riders["Rama"]["share"] == 2785
    assert riders["Sara"]["status"] == "changed"  # her confirmation no longer matches the new price
    for name in ("Sara", "Rama"):
        assert riders[name]["share"] <= riders[name]["solo"]
    assert len(cars) == 5


def test_last_rider_left_in_car_falls_back_to_solo_fare(matched):
    riders = state(matched)[0]
    post(matched, f"/riders/{riders['Dana']['id']}/decline")
    leen = state(matched)[0]["Leen"]
    assert leen["status"] == "no_match"
    assert leen["share"] == leen["solo"]


def test_declined_rider_cannot_act_again(matched):
    huda = state(matched)[0]["Huda"]
    post(matched, f"/riders/{huda['id']}/decline")
    assert post(matched, f"/riders/{huda['id']}/decline").status_code == 404


def test_post_without_csrf_is_rejected(matched):
    sara = state(matched)[0]["Sara"]
    assert matched.post(f"/riders/{sara['id']}/decline").status_code == 400
    assert state(matched)[0]["Sara"]["status"] == "review"


def test_men_cannot_request_women_only(client):
    post(client, "/reset", mode="empty")
    post(client, "/requests", name="Ali", class_end="16:00", stop="Dabouq", women_only="yes")
    assert state(client)[0] == {}


def test_new_request_is_matched_with_women_only_rules(client):
    post(client, "/reset", mode="empty")
    post(client, "/requests", name="Sara", class_end="16:00", stop="Dabouq", woman="yes", women_only="yes")
    post(client, "/requests", name="Kareem", class_end="16:00", stop="Khalda")
    post(client, "/match")
    riders = state(client)[0]
    assert riders["Sara"]["car"] != riders["Kareem"]["car"]
    assert riders["Sara"]["share"] == 4500
