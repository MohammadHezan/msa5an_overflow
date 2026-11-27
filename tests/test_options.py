"""Captains, friends groups, seat holds and races, and the three choices for a student left alone."""
import threading

import pytest

import app as campus
import store
from sharing import solo_fare


@pytest.fixture
def client(tmp_path):
    campus.app.config.update(TESTING=True, DATABASE=tmp_path / "test.sqlite")
    with campus.app.test_client() as client:
        client.get("/")  # Seeded batch and CSRF token
        yield client


def post(client, path, **form):
    with client.session_transaction() as session:
        token = session["csrf"]
    return client.post(path, data={"csrf": token, **form})


def batch_id(client):
    with client.session_transaction() as session:
        return session["batch"]


def state(client):
    with campus.app.app_context():
        db = campus.database()
        riders, cars = store.load_riders(db, store.get_batch(db, batch_id(client)))
    return {r["name"]: r for r in riders}, cars


def sql(query, *args):
    with campus.app.app_context():
        db = campus.database()
        with db:
            return db.execute(query, args).fetchall()


def book(client, name, stop, class_end="16:00", gender="man", preference="mixed", **extra):
    return post(client, "/requests", name=name, stop=stop, class_end=class_end, gender=gender, preference=preference, **extra)


@pytest.fixture
def empty(client):
    post(client, "/reset", mode="empty")
    return client


# ---------- Captains ----------

def test_women_only_car_gets_a_woman_captain(client):
    post(client, "/match")
    riders, _ = state(client)
    car = riders["Sara"]["plan"]
    assert car["only"] == "women" and car["captain"]["gender"] == "woman"
    assert all(plan["captain"] for plan in state(client)[1])  # Every car has a captain


def test_women_only_car_gets_a_man_when_no_woman_captain_is_free(client):
    sql("UPDATE captains SET available = 0 WHERE gender = 'woman'")
    post(client, "/match")
    assert state(client)[0]["Sara"]["plan"]["captain"]["gender"] == "man"


def test_captain_sheet_shows_bonus_paid_by_jeeny_not_students(client):
    post(client, "/match")
    riders, cars = state(client)
    sheet = next(s for s in store.captain_sheets(list(riders.values()), cars) if s["plan"]["id"] == riders["Sara"]["car"])
    assert sheet["stops"] == ["Dabouq", "Al Bayader", "Wadi As-Seer"]
    assert sheet["bonus"] == 200
    assert sum(sheet["plan"]["shares"].values()) == sheet["plan"]["car_fare"]  # The bonus is not in any share
    page = client.get("/?view=captains").get_data(as_text=True)
    assert "paid by Jeeny" in page and "JOD 0.20" in page


def test_captain_bonus_counts_riders_not_distinct_neighborhoods(empty):
    for name in ("Demo one", "Demo two", "Demo three"):
        book(empty, name, "Dabouq")
    post(empty, "/match")
    riders, cars = state(empty)
    sheets = store.captain_sheets(list(riders.values()), cars)
    assert len(sheets) == 1 and len(sheets[0]["stops"]) == 1
    assert sheets[0]["bonus"] == 200
    assert all(step["time"] for step in sheets[0]["steps"])
    assert sum(cars[0]["shares"].values()) == cars[0]["car_fare"]


# ---------- Friends ----------

def group_code(client, name):
    return state(client)[0][name]["friend_group"]


def test_friends_group_always_lands_together(empty):
    book(empty, "Aya", "Wadi As-Seer", friends="start", group_open="yes")
    code = group_code(empty, "Aya")
    assert code.startswith("GR-")
    book(empty, "Bana", "Sweileh", class_end="16:05", friends="join", group_code=code)
    book(empty, "Dima", "Dabouq")
    book(empty, "Farah", "Dabouq")
    post(empty, "/match")
    riders, _ = state(empty)
    assert riders["Aya"]["car"] == riders["Bana"]["car"]
    assert riders["Aya"]["share"] != riders["Bana"]["share"]  # Each friend pays for their own km


def test_closed_group_of_two_gets_no_strangers(empty):
    book(empty, "Aya", "Dabouq", friends="start")  # Toggle off: "group_open" not sent
    book(empty, "Bana", "Dabouq", friends="join", group_code=group_code(empty, "Aya"))
    book(empty, "Dima", "Dabouq")
    post(empty, "/match")
    riders, _ = state(empty)
    assert riders["Aya"]["car"] == riders["Bana"]["car"] != riders["Dima"]["car"]
    assert len(riders["Aya"]["plan"]["members"]) == 2


def test_fifth_friend_is_refused(empty):
    book(empty, "A1", "Dabouq", friends="start", group_open="yes")
    code = group_code(empty, "A1")
    for name in ("A2", "A3", "A4"):
        book(empty, name, "Dabouq", friends="join", group_code=code)
    book(empty, "A5", "Dabouq", friends="join", group_code=code)
    riders, _ = state(empty)
    assert "A5" not in riders
    assert sum(1 for r in riders.values() if r["friend_group"] == code) == 4


def test_friend_from_another_gate_is_refused(empty):
    book(empty, "Aya", "Dabouq", friends="start", group_open="yes")
    book(empty, "Bana", "Marka", friends="join", group_code=group_code(empty, "Aya"))
    assert "Bana" not in state(empty)[0]


# ---------- Seat holds and races ----------

def test_expired_hold_frees_the_seat_and_replans_the_car(client):
    post(client, "/match")
    rama = state(client)[0]["Rama"]
    post(client, f"/riders/{rama['id']}/confirm", plan=rama["signature"])
    post(client, "/clock", minutes="1")
    assert state(client)[0]["Sara"]["status"] == "review"  # Still inside the 2-minute hold
    post(client, "/clock", minutes="1")
    riders, _ = state(client)
    assert riders["Sara"]["status"] == "declined" and riders["Sara"]["released"]
    assert riders["Huda"]["status"] == "declined"
    assert [m["name"] for m in riders["Rama"]["plan"]["members"]] == ["Rama"]
    assert riders["Rama"]["status"] == "changed"  # She confirmed a shared price; the new plan needs her OK
    assert riders["Zaid"]["status"] == "no_match"  # Students riding alone have no hold


def _in_threads(*jobs):
    barrier = threading.Barrier(len(jobs))
    results = [None] * len(jobs)

    def run(i, job):
        with campus.app.app_context():
            db = campus.database()
            barrier.wait()
            try:
                with db:
                    results[i] = job(db)
            except store.Problem as problem:
                results[i] = problem.code
            finally:
                store.close_database()

    threads = [threading.Thread(target=run, args=(i, job)) for i, job in enumerate(jobs)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return results


def test_two_confirms_on_the_same_seat_at_once_exactly_one_succeeds(client):
    post(client, "/match")
    sara = state(client)[0]["Sara"]
    bid = batch_id(client)

    def confirm(db):
        store.respond_to_plan(db, store.locked_batch(db, bid), sara["id"], "confirm", sara["signature"])
        return "ok"

    assert sorted(_in_threads(confirm, confirm)) == ["already_confirmed", "ok"]
    assert state(client)[0]["Sara"]["status"] == "confirmed"


def test_two_friends_racing_for_the_last_group_seat(empty):
    book(empty, "A1", "Dabouq", friends="start", group_open="yes")
    code = group_code(empty, "A1")
    book(empty, "A2", "Dabouq", friends="join", group_code=code)
    book(empty, "A3", "Dabouq", friends="join", group_code=code)
    bid = batch_id(empty)

    def join(name):
        def job(db):
            batch = store.locked_batch(db, bid)
            store.insert_request(db, batch, name, "16:00", "Dabouq", "man", "mixed", {"mode": "join", "code": code})
            return "ok"
        return job

    assert sorted(_in_threads(join("B1"), join("B2"))) == ["group_full", "ok"]
    assert len(sql("SELECT 1 FROM riders WHERE friend_group = ?", code)) == 4


# ---------- A student left alone: A, B, C ----------

@pytest.fixture
def alone(empty):
    """Zaid is matched alone, heading to Wadi As-Seer (16 km)."""
    book(empty, "Zaid", "Wadi As-Seer")
    post(empty, "/match")
    zaid = state(empty)[0]["Zaid"]
    assert zaid["status"] == "no_match"
    return empty, zaid


def test_a_ride_alone_now(alone):
    client, zaid = alone
    post(client, f"/riders/{zaid['id']}/confirm", plan=zaid["signature"])
    assert state(client)[0]["Zaid"]["status"] == "solo_confirmed"


def test_b_wait_then_a_new_request_shares(alone):
    client, zaid = alone
    post(client, f"/riders/{zaid['id']}/wait")
    assert state(client)[0]["Zaid"]["status"] == "waiting_match"
    book(client, "Ali", "Dabouq")
    riders, _ = state(client)
    assert riders["Ali"]["car"] == riders["Zaid"]["car"]
    assert riders["Zaid"]["status"] == riders["Ali"]["status"] == "review"
    assert riders["Zaid"]["share"] < riders["Zaid"]["solo"]


def test_b_wait_with_no_one_shows_ride_alone_again(alone):
    client, zaid = alone
    post(client, f"/riders/{zaid['id']}/wait")
    post(client, "/clock", minutes="5")
    post(client, "/clock", minutes="5")
    zaid = state(client)[0]["Zaid"]
    assert zaid["status"] == "no_match" and zaid["wait_expired"]
    assert "Ride alone now" in client.get(f"/?rider={zaid['id']}").get_data(as_text=True)


def test_c_nobody_joins_pays_exactly_the_solo_fare(alone):
    client, zaid = alone
    post(client, f"/riders/{zaid['id']}/go")
    page = client.get(f"/?rider={zaid['id']}").get_data(as_text=True)
    assert f"You pay at most JOD {zaid['solo'] / 1000:.2f}. Less if someone joins." in page
    for _ in range(10):
        post(client, "/clock", minutes="5")
    zaid = state(client)[0]["Zaid"]
    assert zaid["status"] == "arrived"
    assert zaid["share"] == zaid["solo"]


def test_c_solo_includes_campus_turn_in_and_keeps_pickup_time_stable(alone):
    client, zaid = alone
    sql("UPDATE riders SET start_side_m = 350 WHERE id = ?", zaid["id"])
    post(client, f"/riders/{zaid['id']}/go")
    first = state(client)[0]["Zaid"]
    assert first["share"] == first["solo"]
    pickup = first["plan"]["rider_times"][zaid["id"]]
    post(client, "/clock", minutes="5")
    later = state(client)[0]["Zaid"]
    assert later["plan"]["rider_times"][zaid["id"]] == pickup
    assert client.get("/?view=captains").status_code == 200


def test_c_to_campus_allows_only_a_street_pickup_still_ahead(empty):
    book(empty, "Morning far", "Wadi As-Seer", direction="to_campus", class_start="08:30")
    post(empty, "/match")
    far = state(empty)[0]["Morning far"]
    post(empty, f"/riders/{far['id']}/go")
    post(empty, "/clock", minutes="5")
    book(empty, "Morning near", "Dabouq", direction="to_campus", class_start="08:30")
    riders, _ = state(empty)
    assert riders["Morning near"]["car"] == riders["Morning far"]["car"]
    assert all(riders[name]["share"] < riders[name]["solo"] for name in ("Morning far", "Morning near"))
    plan = riders["Morning far"]["plan"]
    assert sum(plan["shares"].values()) == plan["car_fare"]
    assert empty.get("/?view=captains").status_code == 200


def test_c_someone_joins_on_the_way_both_pay_less(alone):
    client, zaid = alone
    post(client, f"/riders/{zaid['id']}/go")
    # At the instant of departure, a second campus student can still board.
    book(client, "Ali", "Dabouq")
    riders, cars = state(client)
    car = riders["Zaid"]["plan"]
    assert riders["Ali"]["car"] == riders["Zaid"]["car"] and riders["Ali"]["status"] == "on_the_way"
    assert car["boards"][riders["Ali"]["id"]] == "Main gate"
    assert riders["Zaid"]["share"] < riders["Zaid"]["solo"] and riders["Ali"]["share"] < riders["Ali"]["solo"]
    assert sum(car["shares"].values()) == car["car_fare"]


def test_c_does_not_move_a_campus_student_to_a_street_ahead(alone):
    client, zaid = alone
    post(client, f"/riders/{zaid['id']}/go")
    post(client, "/clock", minutes="5")
    book(client, "Campus late", "Wadi As-Seer")
    riders, _ = state(client)
    assert riders["Campus late"]["car"] != riders["Zaid"]["car"]


def test_c_rider_whose_stop_is_behind_the_car_cannot_join(alone):
    client, zaid = alone
    post(client, f"/riders/{zaid['id']}/go")
    for _ in range(6):
        post(client, "/clock", minutes="5")  # 30 min at 25 km/h: past Dabouq (12 km)
    book(client, "Ali", "Dabouq")
    riders, _ = state(client)
    assert riders["Ali"]["car"] != riders["Zaid"]["car"]
    assert riders["Ali"]["status"] == "no_match"
    assert riders["Zaid"]["share"] == riders["Zaid"]["solo"]
