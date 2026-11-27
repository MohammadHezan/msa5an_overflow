"""Build web/index.html: the Campus Connect friends demo as one static web page.

Every price on the page comes from the real engine. This script books each case on a fresh, already-matched
sample afternoon (store.insert_request, store.group_ready), records the car the group gets, and injects
those results into web/friends.template.html.

Run: python scripts/build_friends_web.py
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import app as campus  # noqa: E402
import store  # noqa: E402
from sharing import CORRIDORS  # noqa: E402

PROFILES = {"man": {"name": "Omar K", "only": "men"}, "woman": {"name": "Joud A", "only": "women"}}
FRIENDS = {"man": ["Ahmad K", "Yousef M", "Ali S"], "woman": ["Lina H", "Noor T", "Dima R"]}
USER_STOP, CLASS_END = "Khalda", "16:05"


def friend_stops():
    """Same rule as the app's demo button: the nearest unused stop on the student's corridor."""
    corridor = CORRIDORS["West"]["stops"]
    used, stops = {USER_STOP}, []
    for _ in range(3):
        stop = min(corridor, key=lambda s: (s in used, abs(corridor[s] - corridor[USER_STOP])))
        used.add(stop)
        stops.append(stop)
    return stops


def run_case(db, gender, option, open_group, size):
    with db:
        batch_id = store.create_batch(db, True)
    with db:
        store.run_matching(db, store.locked_batch(db, batch_id))
    me = PROFILES[gender]["name"]
    with db:
        my_id = store.insert_request(db, store.locked_batch(db, batch_id), me, CLASS_END, USER_STOP, gender, option,
                                     {"mode": "start", "open": open_group})
    code = next(r for r in store.load_riders(db, store.get_batch(db, batch_id))[0] if r["id"] == my_id)["friend_group"]
    for name, stop in list(zip(FRIENDS[gender], friend_stops()))[:size - 1]:
        with db:
            store.insert_request(db, store.locked_batch(db, batch_id), name, CLASS_END, stop, gender, "mixed",
                                 {"mode": "join", "code": code})
    if size < 4:  # Four friends get their car as soon as the fourth joins
        with db:
            store.group_ready(db, store.locked_batch(db, batch_id), code, my_id)
    riders = {r["id"]: r for r in store.load_riders(db, store.get_batch(db, batch_id))[0]}
    mine = riders[my_id]
    plan = mine["plan"]
    return {
        "carFare": plan["car_fare"], "routeKm": round(plan["route_km"], 1), "only": plan.get("only"),
        "captain": plan["captain"], "pickup": mine.get("pickup_at") or plan["pickup"],
        "walkM": int(mine.get("walk_m") or 0), "joinedExisting": any(not m["friend_group"] for m in plan["members"]),
        "breakdown": plan.get("segment_breakdown", {}).get(my_id, []),
        "members": [{"name": m["name"], "stop": m["stop"], "share": m["share"] if "share" in m else plan["shares"][m["id"]],
                     "solo": riders[m["id"]]["solo"], "km": round(riders[m["id"]]["km"], 1),
                     "you": m["id"] == my_id, "friend": m["friend_group"] == code}
                    for m in plan["members"]],
    }


def refusal(db, gender, option):
    """What the real rules say when someone of the other gender tries to join a single-gender group."""
    with db:
        batch_id = store.create_batch(db, True)
    with db:
        store.run_matching(db, store.locked_batch(db, batch_id))
    with db:
        my_id = store.insert_request(db, store.locked_batch(db, batch_id), PROFILES[gender]["name"], CLASS_END, USER_STOP,
                                     gender, option, {"mode": "start", "open": False})
    code = next(r for r in store.load_riders(db, store.get_batch(db, batch_id))[0] if r["id"] == my_id)["friend_group"]
    other = "woman" if gender == "man" else "man"
    try:
        with db:
            store.insert_request(db, store.locked_batch(db, batch_id), "Guest X", CLASS_END, "Dabouq", other, "mixed",
                                 {"mode": "join", "code": code})
    except store.Problem as problem:
        return problem.message
    return None


def main():
    campus.app.config.update(TESTING=True, DATABASE=Path(tempfile.mkdtemp()) / "web.sqlite")
    data = {"profiles": PROFILES, "friends": FRIENDS, "friendStops": friend_stops(), "userStop": USER_STOP,
            "classEnd": CLASS_END, "seats": store.SEATS, "lobbyMinutes": int(store.GROUP_LOBBY.total_seconds() // 60),
            "cases": {}, "refusals": {}}
    with campus.app.app_context():
        db = store.database()
        for gender, profile in PROFILES.items():
            data["refusals"][gender] = refusal(db, gender, profile["only"])
            for option in ("mixed", profile["only"]):
                for open_group in (False, True):
                    for size in range(1, 5):
                        key = f"{gender}|{option}|{'open' if open_group else 'closed'}|{size}"
                        data["cases"][key] = run_case(db, gender, option, open_group, size)
    template = (ROOT / "web" / "friends.template.html").read_text(encoding="utf-8")
    page = template.replace("/*DATA*/null", json.dumps(data, separators=(",", ":"), ensure_ascii=False))
    (ROOT / "web" / "index.html").write_text(page, encoding="utf-8")
    print(f"web/index.html: {len(data['cases'])} cases, {len(page) // 1024} KB")


if __name__ == "__main__":
    main()
