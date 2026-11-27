"""Brief 05: friends ride in one car, also after matching ran; Men only / Women only follow the passenger's gender."""
import pytest

import app as campus
from tests.test_api import verified_join
import store
from sharing import one_car_km


@pytest.fixture
def ctx(tmp_path):
    """A matched sample afternoon (the operator already ran matching), inside an app context."""
    campus.app.config.update(TESTING=True, DATABASE=tmp_path / "test.sqlite")
    with campus.app.app_context():
        db = store.database()
        with db:
            batch_id = store.create_batch(db, True)
        with db:
            store.run_matching(db, store.locked_batch(db, batch_id))
        yield db, batch_id


def batch(db, batch_id):
    return store.get_batch(db, batch_id)


def riders(db, batch_id):
    return {r["name"]: r for r in store.load_riders(db, batch(db, batch_id))[0]}


def book(db, batch_id, name, stop="Khalda", class_end="16:05", gender="man", preference="mixed", friends=None):
    with db:
        return store.insert_request(db, store.locked_batch(db, batch_id), name, class_end, stop, gender, preference, friends)


def start(db, batch_id, name="Omar K", open_group=False, preference="men", **kw):
    rider_id = book(db, batch_id, name, preference=preference, friends={"mode": "start", "open": open_group}, **kw)
    return rider_id, riders(db, batch_id)[name]["friend_group"]


def join(db, batch_id, code, name, **kw):
    return book(db, batch_id, name, friends={"mode": "join", "code": code}, **kw)


def ready(db, batch_id, code, rider_id):
    with db:
        return store.group_ready(db, store.locked_batch(db, batch_id), code, rider_id)


def test_late_group_waits_in_the_lobby_then_gets_one_car(ctx):
    db, batch_id = ctx
    omar, code = start(db, batch_id)
    join(db, batch_id, code, "Ahmad K", stop="Dabouq")
    join(db, batch_id, code, "Yousef M", stop="Wadi As-Seer")
    now = riders(db, batch_id)
    assert {now[n]["status"] for n in ("Omar K", "Ahmad K", "Yousef M")} == {"lobby"}
    assert now["Omar K"]["group"]["status"] == "lobby" and len(now["Omar K"]["group"]["members"]) == 3

    car = ready(db, batch_id, code, omar)
    now = riders(db, batch_id)
    members = now["Omar K"]["plan"]["members"]
    assert {m["name"] for m in members} == {"Omar K", "Ahmad K", "Yousef M"}  # Closed: no strangers
    assert all(now[n]["car"] == car and now[n]["status"] == "review" for n in ("Omar K", "Ahmad K", "Yousef M"))
    plan = now["Omar K"]["plan"]
    assert plan["only"] == "men" and plan["captain"] is not None
    assert sum(plan["shares"].values()) == plan["car_fare"]  # One car fare, split by km
    assert all(now[n]["share"] < now[n]["solo"] for n in ("Omar K", "Ahmad K", "Yousef M"))


def test_men_only_group_refuses_a_woman(ctx):
    db, batch_id = ctx
    _, code = start(db, batch_id)
    with pytest.raises(store.Problem, match="This group is men only."):
        join(db, batch_id, code, "Lina H", gender="woman")


def test_men_only_rider_cannot_join_a_group_with_a_woman(ctx):
    db, batch_id = ctx
    _, code = start(db, batch_id, preference="mixed")
    join(db, batch_id, code, "Noor T", gender="woman")
    with pytest.raises(store.Problem, match="Your ride option doesn't fit this group."):
        join(db, batch_id, code, "Ali S", preference="men")


def test_woman_cannot_ask_for_men_only_and_man_cannot_ask_for_women_only():
    with pytest.raises(store.Problem):
        store.check_request("Sara", "16:00", "Dabouq", "woman", "men")
    with pytest.raises(store.Problem):
        store.check_request("Omar", "16:00", "Dabouq", "man", "women")


def test_closed_group_car_takes_no_strangers_later(ctx):
    db, batch_id = ctx
    omar, code = start(db, batch_id, preference="mixed")
    join(db, batch_id, code, "Ahmad K", stop="Dabouq")
    car = ready(db, batch_id, code, omar)
    book(db, batch_id, "Late L", stop="Wadi As-Seer")
    assert riders(db, batch_id)["Late L"]["car"] != car


def test_open_group_car_takes_a_late_rider_when_every_rule_passes(ctx):
    db, batch_id = ctx
    omar, code = start(db, batch_id, open_group=True, preference="mixed")
    join(db, batch_id, code, "Ahmad K", stop="Dabouq")
    car = ready(db, batch_id, code, omar)
    book(db, batch_id, "Late L", stop="Wadi As-Seer")
    now = riders(db, batch_id)
    if now["Late L"]["car"] == car:
        assert one_car_km(now["Omar K"]["plan"]["members"]) is not None
        assert now["Late L"]["status"] == "review"
    else:
        others = [now["Omar K"], now["Ahmad K"]]
        assert one_car_km(others + [now["Late L"]]) is None


def test_open_group_joins_an_existing_car_only_if_it_fits(ctx):
    db, batch_id = ctx
    before = riders(db, batch_id)
    omar, code = start(db, batch_id, "Rana B", open_group=True, preference="mixed", gender="woman",
                       stop="Um Al Summaq", class_end="13:05")
    join(db, batch_id, code, "Hiba Q", gender="woman", stop="Abdoun", class_end="13:05")
    car = ready(db, batch_id, code, omar)
    now = riders(db, batch_id)
    aboard = now["Rana B"]["plan"]["members"]
    assert car == before["Leen"]["car"]  # The South car (Leen, Dana) has two free seats and every rule passes
    assert {m["name"] for m in aboard} == {"Leen", "Dana", "Rana B", "Hiba Q"}  # Never split
    assert one_car_km(aboard) is not None
    assert now["Rana B"]["share"] < now["Rana B"]["solo"] and now["Hiba Q"]["share"] < now["Hiba Q"]["solo"]
    assert now["Leen"]["status"] == "review"  # The others see the changed car and confirm again


def test_closed_group_never_joins_an_existing_car(ctx):
    db, batch_id = ctx
    before = riders(db, batch_id)
    rana, code = start(db, batch_id, "Rana B", open_group=False, preference="mixed", gender="woman",
                       stop="Um Al Summaq", class_end="13:05")
    join(db, batch_id, code, "Hiba Q", gender="woman", stop="Abdoun", class_end="13:05")
    car = ready(db, batch_id, code, rana)
    assert car != before["Leen"]["car"]
    assert {m["name"] for m in riders(db, batch_id)["Rana B"]["plan"]["members"]} == {"Rana B", "Hiba Q"}


def test_a_friend_leaving_never_raises_a_confirmed_share(ctx):
    db, batch_id = ctx
    omar, code = start(db, batch_id)
    join(db, batch_id, code, "Ahmad K", stop="Dabouq")
    join(db, batch_id, code, "Yousef M", stop="Wadi As-Seer")
    ready(db, batch_id, code, omar)
    quoted = {}
    for name in ("Omar K", "Ahmad K", "Yousef M"):
        rider = riders(db, batch_id)[name]
        with db:
            store.respond_to_plan(db, store.locked_batch(db, batch_id), rider["id"], "confirm", rider["signature"])
        quoted[name] = rider["share"]
    yousef = riders(db, batch_id)["Yousef M"]
    with db:
        store.respond_to_plan(db, store.locked_batch(db, batch_id), yousef["id"], "decline", None)
    now = riders(db, batch_id)
    assert now["Omar K"]["car"] == now["Ahmad K"]["car"]  # Still together
    assert now["Omar K"]["share"] <= quoted["Omar K"] and now["Ahmad K"]["share"] <= quoted["Ahmad K"]


def test_group_of_four_is_full_and_gets_its_car_at_once(ctx):
    db, batch_id = ctx
    _, code = start(db, batch_id)
    for name, stop in (("Ahmad K", "Dabouq"), ("Yousef M", "Wadi As-Seer"), ("Ali S", "Al Bayader")):
        join(db, batch_id, code, name, stop=stop)
    now = riders(db, batch_id)
    assert now["Omar K"]["status"] == "review" and now["Omar K"]["group"]["status"] == "placed"
    assert len({now[n]["car"] for n in ("Omar K", "Ahmad K", "Yousef M", "Ali S")}) == 1
    with pytest.raises(store.Problem, match="already has its car"):
        join(db, batch_id, code, "Faris N")


def test_fifth_friend_is_refused_before_matching(tmp_path):
    campus.app.config.update(TESTING=True, DATABASE=tmp_path / "test.sqlite")
    with campus.app.app_context():
        db = store.database()
        with db:
            batch_id = store.create_batch(db, False)
        _, code = start(db, batch_id)
        for name, stop in (("Ahmad K", "Dabouq"), ("Yousef M", "Wadi As-Seer"), ("Ali S", "Al Bayader")):
            join(db, batch_id, code, name, stop=stop)
        with pytest.raises(store.Problem, match=r"This group is full \(4 students\)."):
            join(db, batch_id, code, "Faris N")


def test_lobby_runs_out_and_the_group_gets_its_car(ctx):
    db, batch_id = ctx
    _, code = start(db, batch_id)
    join(db, batch_id, code, "Ahmad K", stop="Dabouq")
    with db:
        store.advance_clock(db, batch_id, 11)
    with db:
        store.locked_batch(db, batch_id)
    now = riders(db, batch_id)
    assert now["Omar K"]["car"] is not None and now["Omar K"]["car"] == now["Ahmad K"]["car"]


def test_only_the_creator_can_say_everyone_is_in(ctx):
    db, batch_id = ctx
    _, code = start(db, batch_id)
    ahmad = join(db, batch_id, code, "Ahmad K", stop="Dabouq")
    with pytest.raises(store.Problem, match="Only the student who started the group"):
        ready(db, batch_id, code, ahmad)


# ---------- Web screens (Yalla Ride) ----------

@pytest.fixture
def client(tmp_path):
    campus.app.config.update(TESTING=True, DATABASE=tmp_path / "test.sqlite")
    with campus.app.test_client() as client:
        client.get("/")
        yield client


def post(client, path, **form):
    with client.session_transaction() as session:
        token = session["csrf"]
    return client.post(path, data={"csrf": token, **form}, follow_redirects=True)


def test_demo_profile_is_a_man_and_sees_men_only_not_women_only(client):
    page = client.get("/yalla/plan/preferences").get_data(as_text=True)
    assert 'value="men" data-gender="man"' in page
    women = page.split('value="women"')[0].rsplit("<label", 1)[1]
    assert "hidden" in women
    assert "Omar K" in client.get("/yalla?live=1").get_data(as_text=True)


def test_i_am_switch_changes_the_ride_options(client):
    post(client, "/yalla/profile", gender="woman")
    page = client.get("/yalla/plan/preferences").get_data(as_text=True)
    men = page.split('value="men"')[0].rsplit("<label", 1)[1]
    assert "hidden" in men


def test_web_flow_friends_after_matching(client):
    page = client.get("/yalla/demo/friends", follow_redirects=True).get_data(as_text=True)
    assert "Waiting for your friends" in page and "GR-" in page
    page = post(client, "/yalla/ride/demo-friend").get_data(as_text=True)
    assert "Ahmad" in page
    page = post(client, "/yalla/ride/demo-friend", gender="woman").get_data(as_text=True)
    assert "This group is men only." in page
    post(client, "/yalla/ride/demo-friend")
    page = post(client, "/yalla/ride/ready").get_data(as_text=True)
    assert "One car for your friends" in page and "Men only car" in page and "Friends · GR-" in page


# ---------- JSON API ----------

def test_api_books_a_friends_group_after_matching_and_marks_it_ready(tmp_path):
    campus.app.config.update(TESTING=True, DATABASE=tmp_path / "test.sqlite")
    with campus.app.test_client() as client:
        made = client.post("/api/v1/batches", json={"mode": "seeded"}).get_json()
        client.post(f"/api/v1/batches/{made['id']}/matching", headers={"Authorization": f"Bearer {made['operatorToken']}"})

        def student(name, stop, friends):
            token = verified_join(client, made["joinCode"], name)  # Booking needs a verified profile
            response = client.post(f"/api/v1/batches/{made['id']}/riders", headers={"Authorization": f"Bearer {token}"},
                                   json={"name": name, "classEnd": "16:05", "stop": stop, "gender": "man",
                                         "preference": "men", "friends": friends,
                                         "clientRequestId": f"req-{name.lower().replace(' ', '')}-0001"})
            assert response.status_code == 201, response.get_json()
            return token, response.get_json()

        omar_token, omar = student("Omar K", "Khalda", {"mode": "start", "open": False})
        assert omar["status"] == "lobby" and omar["group"]["youStarted"] and omar["group"]["status"] == "lobby"
        _, ahmad = student("Ahmad K", "Dabouq", {"mode": "join", "code": omar["group"]["code"]})
        assert not ahmad["group"]["youStarted"] and len(ahmad["group"]["members"]) == 2

        placed = client.post(f"/api/v1/groups/{omar['group']['code']}/ready",
                             headers={"Authorization": f"Bearer {omar_token}"}).get_json()
        assert placed["status"] == "review" and placed["group"]["status"] == "placed"
        assert placed["plan"]["only"] == "men" and placed["plan"]["riders"] == ["Ahmad"]
        again = client.post(f"/api/v1/groups/{omar['group']['code']}/ready",
                            headers={"Authorization": f"Bearer {omar_token}"})
        assert again.status_code == 200  # Retrying is safe
