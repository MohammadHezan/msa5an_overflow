"""Versioned JSON API for the Expo student app and operator tools.

Each endpoint mirrors an HTML form route in app.py and calls the same functions in store.py.
Access uses bearer tokens: an operator token from creating a batch, or a student token from a join code.
"""
import hashlib
import re
import secrets
from datetime import date, datetime, time

from flask import Blueprint, current_app, jsonify, request
from werkzeug.exceptions import HTTPException

from sharing import CORRIDORS, STOPS
from pooling import config
from store import (
    AMMAN, RULES, Problem, batch_for_join_code, bind_token, check_request, create_batch, database, fare_estimates,
    find_token, get_batch, insert_request, legacy_options, refresh, issue_token, join_code, load_riders, locked_batch, now,
    choose, respond_to_plan, run_matching, summarize, verify_ride_code,
)
from yalla import car_details, leg_split, pickup_street
from student_verification import (
    confirm_verification, public_student, request_notification, resend_verification,
    search_universities, start_verification,
)

api = Blueprint("api", __name__, url_prefix="/api/v1")

CLIENT_REQUEST_ID = re.compile(r"[A-Za-z0-9_-]{8,64}")
SAMPLE_RIDERS = 3


# ---------- Errors and helpers ----------

@api.errorhandler(Problem)
def problem_response(problem):
    return error(problem.code, problem.message, problem.status)


@api.app_errorhandler(HTTPException)
def http_error(exc):
    if not request.path.startswith(api.url_prefix + "/") and request.path != api.url_prefix:
        return exc  # HTML routes keep Flask's default error pages
    codes = {404: "not_found", 405: "method_not_allowed", 413: "too_large", 400: "invalid_input"}
    return error(codes.get(exc.code, "http_error"), exc.description or exc.name, exc.code)


def error(code, message, status, **extra):
    return jsonify({"error": {"code": code, "message": message}, **extra}), status


def money(fils):
    return {"fils": fils, "currency": "JOD"}


def first_name(name):
    return name.split()[0]


def pickup_at(trip_date, clock):
    hour, minute = map(int, clock.split(":"))
    return datetime.combine(date.fromisoformat(trip_date), time(hour, minute), tzinfo=AMMAN).isoformat()


def json_body():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise Problem("invalid_input", "Send a JSON object body.", 400)
    return body


def field(body, key, kind, default=None):
    value = body.get(key, default)
    if not isinstance(value, kind) or (kind is int and isinstance(value, bool)):
        raise Problem("invalid_input", f"`{key}` is missing or has the wrong type.", 400)
    return value


def bearer(db):
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    row = find_token(db, token.strip()) if scheme.lower() == "bearer" and token.strip() else None
    if not row:
        raise Problem("unauthorized", "Send a valid bearer token.", 401)
    return row


def find_token_row(db, token_hash):
    return db.execute("SELECT * FROM api_tokens WHERE token_hash = ?", (token_hash,)).fetchone()


def forbidden():
    return Problem("forbidden", "This token does not grant access to that resource.", 403)


def student_session(db):
    token = bearer(db)
    if token["role"] != "student":
        raise forbidden()
    if not get_batch(db, token["batch"]):
        raise Problem("unauthorized", "This demo session expired. Join the demo again.", 401)
    return token


def log_verification(delivery):
    if delivery:
        email, code = delivery
        current_app.logger.warning("SIMULATED student verification for %s: code %s (no email sent)", email, code)


@api.get("/universities")
def universities():
    db = database()
    bearer(db)
    return jsonify(universities=search_universities(db, request.args.get("search", "")))


@api.get("/me")
def student_profile():
    db = database()
    token = student_session(db)
    student = public_student(db, token["student_id"])
    verified = bool(student and student["verified"])
    return jsonify(student=student, verified=verified, nextScreen="05" if verified else "02")


@api.post("/verification/start")
def verification_start():
    db = database()
    token, body = student_session(db), json_body()
    university_id = field(body, "universityId", int)
    email = field(body, "email", str)
    first = field(body, "firstName", str) if "firstName" in body else None
    with db:
        locked_batch(db, token["batch"])
        delivery, result = start_verification(db, token, university_id, email, first)
    log_verification(delivery)
    return jsonify(result)


@api.post("/verification/resend")
def verification_resend():
    db = database()
    token = student_session(db)
    with db:
        locked_batch(db, token["batch"])
        delivery, result = resend_verification(db, token)
    log_verification(delivery)
    return jsonify(result)


@api.post("/verification/confirm")
def verification_confirm():
    db = database()
    token = student_session(db)
    code = field(json_body(), "code", str)
    with db:
        locked_batch(db, token["batch"])
        result = confirm_verification(db, token, code)
    if isinstance(result, Problem):
        raise result  # Failed-attempt increments were committed, not rolled back by the error.
    return jsonify(result)


@api.post("/universities/<int:university_id>/notify")
def university_notify(university_id):
    db = database()
    token = student_session(db)
    with db:
        locked_batch(db, token["batch"])
        result = request_notification(db, token, university_id)
    return jsonify(result)


def operator_batch(db, batch_id):
    token = bearer(db)
    if token["role"] != "operator" or token["batch"] != batch_id:
        raise forbidden()
    batch = get_batch(db, batch_id)
    if not batch:
        raise Problem("not_found", "No such batch.", 404)
    return batch


def rider_access(db, rider_id):
    """The batch id for a rider the token may act for: the student's own rider, or any rider in the operator's batch."""
    token = bearer(db)
    if token["role"] == "student":
        if token["rider"] != rider_id:
            raise forbidden()
        return token["batch"]
    row = db.execute("SELECT batch FROM riders WHERE id = ?", (rider_id,)).fetchone()
    if not row or row["batch"] != token["batch"]:
        raise forbidden()
    return token["batch"]


# ---------- Serializers ----------

def rider_json(batch, rider):
    """One student's view: their request, status and plan, with only first names and stops for the other riders."""
    plan = rider["plan"]
    body = {
        "id": rider["id"], "name": rider["name"], "status": rider["status"],
        "batchId": batch["id"], "tripDate": batch["trip_date"], "timezone": "Asia/Amman", "matched": bool(batch["matched"]),
        "request": {"direction": rider["direction"], "classEnd": rider["class_end"],
                    "classStart": rider["class_start"], "stop": rider["stop"], "corridor": rider["corridor"],
                    "streetKm": rider["km"], "walkMeters": min(rider["start_side_m"], 200),
                    "gender": rider["gender"],
                    "preference": rider["preference"], "friendGroup": rider["friend_group"],
                    # Older clients read these two flags
                    "woman": rider["gender"] == "woman", "womenOnly": rider["preference"] == "women"},
        "soloFare": money(rider["solo"]), "rideCode": rider["ride_code"], "plan": None,
        "holdUntil": rider["hold_until"].isoformat() if rider["hold_until"] else None,
        "waitUntil": rider["wait_until"].isoformat() if rider["wait_until"] else None,
    }
    if plan:
        body["plan"] = {
            "shared": plan["shared"], "womenOnly": plan.get("women_only", False), "only": plan.get("only"),
            "corridor": plan["corridor"], "gate": plan["gate"], "goNow": bool(plan.get("go")),
            "pickupTime": plan["pickup"], "pickupAt": pickup_at(batch["trip_date"], plan["pickup"]),
            "direction": plan.get("direction", rider["direction"]),
            "walkMeters": plan.get("walk_m", {}).get(rider["id"], 0),
            "walkMinutes": round(plan.get("walk_m", {}).get(rider["id"], 0) / 1.4 / 60, 1),
            "yourPickupTime": plan.get("rider_times", {}).get(rider["id"], plan["pickup"]),
            "yourDropOffTime": plan.get("drop_times", {}).get(rider["id"]),
            "arriveBy": plan.get("campus_arrival") if rider["direction"] == "to_campus" else None,
            "carFare": money(plan["car_fare"]), "jeenyCover": money(plan.get("jeeny_cover", 0)),
            "segmentBreakdown": plan.get("segment_breakdown", {}).get(rider["id"], []),
            "riders": [first_name(m["name"]) for m in plan["members"] if m["id"] != rider["id"]],
            "dropOffs": [
                {"order": i, "stop": m["stop"], "rider": first_name(m["name"]), "you": m["id"] == rider["id"],
                 "pickupTime": plan.get("rider_times", {}).get(m["id"])}
                for i, m in enumerate(plan["members"], 1)
            ],
            "share": money(rider["share"]), "soloFare": money(rider["solo"]),
            "saving": money(rider["solo"] - rider["share"]), "signature": rider["signature"],
            "savingPercent": round((rider["solo"] - rider["share"]) * 100 / rider["solo"]) if rider["solo"] else 0,
            "captain": captain_json(plan),
        }
        if plan.get("go"):  # Leave now & share: the fare cap and who paid for each leg (screens 17-25)
            body["plan"]["fareCap"] = money(rider["solo"])
            body["plan"]["legs"] = leg_split(plan, rider)
    return body


def captain_json(plan):
    """Screens 13-14: the assigned captain and car, or None before a captain is assigned."""
    if not plan.get("captain"):
        return None
    car = car_details(plan)
    return {"firstName": first_name(plan["captain"]["name"]), "rating": float(car["rating"]),
            "ratingCount": car["ratings"], "car": car["car"], "plate": car["plate"]}


def batch_json(db, batch):
    riders, cars = load_riders(db, batch)
    by_id = {r["id"]: r for r in riders}
    code, expires = join_code(db, batch["id"])
    summary = summarize(riders, cars)
    return {
        "id": batch["id"], "tripDate": batch["trip_date"], "timezone": "Asia/Amman", "matched": bool(batch["matched"]),
        "joinCode": code, "joinCodeExpiresAt": expires.isoformat(),
        "riders": [
            {"id": r["id"], "name": r["name"], "direction": r["direction"], "classEnd": r["class_end"],
             "classStart": r["class_start"], "stop": r["stop"], "corridor": r["corridor"],
             "streetKm": r["km"], "walkMeters": min(r["start_side_m"], 200),
             "gender": r["gender"], "preference": r["preference"], "friendGroup": r["friend_group"],
             "woman": r["gender"] == "woman", "womenOnly": r["preference"] == "women", "status": r["status"],
             "car": r["car"] if r["plan"] else None, "share": money(r["share"]) if r["plan"] else None,
             "soloFare": money(r["solo"]), "rideCode": r["ride_code"]}
            for r in riders
        ],
        "cars": [
            {"id": plan["members"][0]["car"], "corridor": plan["corridor"], "gate": plan["gate"],
             "pickupTime": plan["pickup"], "pickupAt": pickup_at(batch["trip_date"], plan["pickup"]),
             "shared": plan["shared"], "womenOnly": plan.get("women_only", False), "only": plan.get("only"),
             "carFare": money(plan["car_fare"]),
              "jeenyCover": money(plan.get("jeeny_cover", 0)), "direction": plan.get("direction"),
              "routeKm": plan["route_km"],
             "captain": plan["captain"]["name"] if plan.get("captain") else None,
             "riders": [
                 {"id": m["id"], "name": m["name"], "stop": m["stop"], "status": by_id[m["id"]]["status"],
                  "share": money(plan["shares"][m["id"]]), "soloFare": money(m["solo"])}
                 for m in plan["members"]
             ]}
            for plan in cars
        ],
        "summary": {
            "requests": summary["requests"], "sharing": summary["shared"], "cars": summary["cars"],
            "confirmed": summary["confirmed"], "paidTotal": money(summary["paid_total"]),
            "soloTotal": money(summary["solo_total"]),
        },
    }


def load_rider(db, batch_id, rider_id):
    batch = refresh(db, batch_id)
    riders, _ = load_riders(db, batch)
    return batch, next(r for r in riders if r["id"] == rider_id)


# ---------- Endpoints ----------

@api.get("/health")
def health():
    try:
        database().execute("SELECT 1").fetchone()
    except Exception:  # Report rather than crash so the phone can show the backend is unreachable
        return jsonify({"status": "unavailable"}), 503
    return jsonify({"status": "ok", "time": now().isoformat()})


@api.post("/batches")
def create():
    mode = field(json_body(), "mode", str)
    if mode not in {"seeded", "morning", "empty"}:
        raise Problem("invalid_input", "`mode` must be `seeded`, `morning` or `empty`.", 400)
    db = database()
    batch_id = create_batch(db, seeded=mode if mode == "morning" else mode == "seeded")
    token = issue_token(db, batch_id, "operator")
    code, expires = join_code(db, batch_id)
    return jsonify({
        "id": batch_id, "tripDate": get_batch(db, batch_id)["trip_date"], "timezone": "Asia/Amman",
        "joinCode": code, "joinCodeExpiresAt": expires.isoformat(), "operatorToken": token,
    }), 201


@api.post("/demo-sessions/join")
def join():
    code = field(json_body(), "joinCode", str).strip().upper()
    db = database()
    batch_id = batch_for_join_code(db, code)
    if not batch_id:
        raise Problem("join_code_invalid", "That join code is unknown or has expired.", 404)
    batch = get_batch(db, batch_id)
    identity = student_session(db) if request.headers.get("Authorization") else None
    student = public_student(db, identity["student_id"]) if identity else None
    verified = bool(student and student["verified"])
    return jsonify({
        "token": issue_token(db, batch_id, "student", student_id=student["id"] if verified else None), "tokenType": "Bearer",
        "batchId": batch_id, "tripDate": batch["trip_date"], "timezone": "Asia/Amman", "matched": bool(batch["matched"]),
        "verified": verified, "student": student if verified else None, "nextScreen": "05" if verified else "02",
    }), 201


@api.get("/stops")
def stops():
    estimates = fare_estimates()
    return jsonify({
        "currency": "JOD",
        "directions": [
            {"id": "from_campus", "label": "From campus", "timeField": "classEnd"},
            {"id": "to_campus", "label": "To campus", "timeField": "classStart"},
        ],
        "corridors": [
            {"name": name, "gate": corridor["gate"], "stops": [
                {"name": stop, "km": km, "soloFare": money(estimates[stop]["solo"]),
                 "sampleShare": money(estimates[stop]["shared"])}
                for stop, km in corridor["stops"].items()
            ]}
            for name, corridor in CORRIDORS.items()
        ],
        "rules": {
            "seatsPerCar": RULES["seats"], "maxTimeGapMinutes": RULES["gap"],
            "maxClassEndGapMinutes": RULES["gap"], "maxWalkMeters": 200, "walkSpeedMetersPerSecond": 1.4,
            "classEndEarliest": "08:00", "classEndLatest": "21:00",
            "classStartEarliest": "07:00", "classStartLatest": "23:00", "sampleShareRiders": SAMPLE_RIDERS,
            "baseFare": money(RULES["base"]), "perKm": money(RULES["per_km"]),
            "minSavingPercent": RULES["min_saving"],
        },
    })


@api.get("/batches/<batch_id>")
def batch_detail(batch_id):
    db = database()
    return jsonify(batch_json(db, refresh(db, operator_batch(db, batch_id)["id"])))


@api.post("/batches/<batch_id>/verify-code")
def verify_code(batch_id):
    """Driver check at the meeting point: is this ride code held by a confirmed rider in the batch?"""
    db = database()
    batch = operator_batch(db, batch_id)
    rider = verify_ride_code(db, batch, field(json_body(), "code", str))
    if not rider:
        return jsonify({"valid": False})
    return jsonify({"valid": True, "rider": {
        "firstName": first_name(rider["name"]), "stop": rider["stop"], "carId": rider["car"],
        "pickupTime": rider["plan"].get("rider_times", {}).get(rider["id"], rider["plan"]["pickup"]),
    }})


@api.post("/batches/<batch_id>/riders")
def book(batch_id):
    db = database()
    token = bearer(db)
    if token["role"] != "student" or token["batch"] != batch_id:
        raise forbidden()
    body = json_body()
    client_request_id = field(body, "clientRequestId", str)
    if not CLIENT_REQUEST_ID.fullmatch(client_request_id):
        raise Problem("invalid_input", "`clientRequestId` must be 8–64 letters, digits, `-` or `_`.", 400)
    direction = field(body, "direction", str, "from_campus")
    class_end, class_start, stop = field(body, "classEnd", str, ""), field(body, "classStart", str, ""), field(body, "stop", str)
    if "gender" in body or "preference" in body:
        gender, preference = field(body, "gender", str), field(body, "preference", str, "mixed")
    else:  # Older clients send woman/womenOnly flags
        gender, preference = legacy_options(field(body, "woman", bool, False), field(body, "womenOnly", bool, False))
    name = check_request(field(body, "name", str), class_end, stop, gender, preference, direction, class_start)

    with db:
        batch = locked_batch(db, batch_id)
        token = find_token_row(db, token["token_hash"])
        if not batch or not token:
            raise Problem("unauthorized", "This batch no longer exists.", 401)
        if token["rider"] is not None:
            if token["client_request_id"] != client_request_id:
                raise Problem("already_booked", "This student session already booked a ride.")
            saved = db.execute("SELECT * FROM riders WHERE id = ?", (token["rider"],)).fetchone()
            if (saved["name"], saved["class_end"], saved["class_start"], saved["stop"], saved["gender"],
                saved["preference"], saved["direction"]) != (name, class_end, class_start, stop, gender, preference, direction):
                raise Problem("request_conflict", "This clientRequestId was already used with different details.")
            rider_id, status = saved["id"], 200
        else:
            rider_id, status = insert_request(db, batch, name, class_end, stop, gender, preference,
                                              direction=direction, class_start=class_start), 201
            bind_token(db, token["token_hash"], rider_id, client_request_id)
    return jsonify(rider_json(*load_rider(db, batch_id, rider_id))), status


@api.post("/batches/<batch_id>/matching")
def matching(batch_id):
    db = database()
    operator_batch(db, batch_id)
    with db:
        ran, _, _ = run_matching(db, locked_batch(db, batch_id))
    return jsonify({"ranNow": ran, "batch": batch_json(db, get_batch(db, batch_id))})


@api.get("/riders/<int:rider_id>")
def rider_detail(rider_id):
    db = database()
    batch_id = rider_access(db, rider_id)
    return jsonify(rider_json(*load_rider(db, batch_id, rider_id)))


@api.post("/riders/<int:rider_id>/confirm")
def confirm(rider_id):
    db = database()
    batch_id = rider_access(db, rider_id)
    reviewed = field(json_body(), "signature", str)
    try:
        with db:
            respond_to_plan(db, locked_batch(db, batch_id), rider_id, "confirm", reviewed)
    except Problem as problem:
        if problem.code == "already_confirmed":  # A retried confirm returns the confirmed rider
            return jsonify(rider_json(*load_rider(db, batch_id, rider_id)))
        if problem.code != "plan_changed":
            raise
        return error(problem.code, problem.message, 409, rider=rider_json(*load_rider(db, batch_id, rider_id)))
    return jsonify(rider_json(*load_rider(db, batch_id, rider_id)))


@api.post("/riders/<int:rider_id>/decline")
def decline(rider_id):
    db = database()
    batch_id = rider_access(db, rider_id)
    try:
        with db:
            respond_to_plan(db, locked_batch(db, batch_id), rider_id, "decline", None)
    except Problem as problem:
        if problem.code != "rider_declined":  # A retried decline returns the declined rider
            raise
    return jsonify(rider_json(*load_rider(db, batch_id, rider_id)))


@api.get("/estimate")
def estimate():
    """Screen 08: solo fare and sample shared fare for a drop-off, before the student books."""
    db = database()
    student_session(db)
    stop, direction = request.args.get("stop", ""), request.args.get("direction", "from_campus")
    estimates = fare_estimates()
    if stop not in estimates or direction not in ("from_campus", "to_campus"):
        raise Problem("invalid_input", "Send a known `stop` and a `direction` of from_campus or to_campus.", 400)
    e, pickup = estimates[stop], estimates[stop]["pickups"][direction]
    return jsonify({"stop": stop, "direction": direction, "soloFare": money(e["solo"]),
                    "sampleShare": money(e["shared"]), "savingPercent": e["save_percent"],
                    "walkMeters": pickup["walk_meters"], "walkMinutes": pickup["walk_minutes"]})


@api.post("/riders/<int:rider_id>/choice")
def lone_rider_choice(rider_id):
    """Screens 17-19, 29: a student riding alone waits for a match ("wait") or leaves now open to share ("go")."""
    choice = field(json_body(), "choice", str)
    if choice not in ("wait", "go"):
        raise Problem("invalid_input", "`choice` must be `wait` or `go`.", 400)
    db = database()
    batch_id = rider_access(db, rider_id)
    with db:
        choose(db, locked_batch(db, batch_id), rider_id, choice)
    return jsonify(rider_json(*load_rider(db, batch_id, rider_id)))


@api.post("/riders/<int:rider_id>/keep-route")
def keep_route(rider_id):
    """Screens 20-21: turn down students who joined this leave-now car on the way; the route and fare cap stay."""
    body = json_body()
    ids = body.get("riderIds")
    if not isinstance(ids, list) or not ids or not all(isinstance(i, int) and not isinstance(i, bool) for i in ids):
        raise Problem("invalid_input", "`riderIds` must be a non-empty list of rider ids.", 400)
    db = database()
    batch_id = rider_access(db, rider_id)
    with db:
        batch = locked_batch(db, batch_id)
        riders, _ = load_riders(db, batch)
        me = next(r for r in riders if r["id"] == rider_id)
        plan = me["plan"] or {}
        if not plan.get("go") or me["status"] != "on_the_way":
            raise Problem("not_on_the_way", "Only a leave-now car that is on its way can turn down a pickup.")
        others = {m["id"] for m in plan["members"] if m["id"] > rider_id}  # Joiners book after the car's rider, so their ids are higher
        if not set(ids) <= others:
            raise forbidden()
        db.executemany("UPDATE riders SET declined = 1, ride_code = NULL, confirmed_plan = NULL WHERE id = ? AND batch = ?",
                       [(i, batch_id) for i in ids])
    return jsonify(rider_json(*load_rider(db, batch_id, rider_id)))


# ---------- Screens 26-28, 16 and the share sheet (drafted by ChatGPT, reviewed and tested here) ----------

def trip_pickup(rider):
    plan = rider["plan"] or {}
    return ((plan.get("rider_times") or {}).get(rider["id"]) or plan.get("pickup")
            or rider["class_end"] or None)


@api.get("/me/trips")
def my_trips():
    db = database()
    token = student_session(db)
    tab = request.args.get("tab", "upcoming")
    if tab not in ("upcoming", "past"):
        raise Problem("invalid_input", "Choose upcoming or past.", 400)
    if token["student_id"] is None:
        return jsonify(trips=[])
    student = public_student(db, token["student_id"])
    campus = student["university"]["campus"]
    owned = {}
    for row in db.execute(
        "SELECT DISTINCT r.batch, r.id FROM api_tokens t "
        "JOIN riders r ON r.id = t.rider AND r.batch = t.batch "
        "JOIN batches b ON b.id = r.batch WHERE t.role = 'student' AND t.student_id = ?",
        (token["student_id"],),
    ):
        owned.setdefault(row["batch"], set()).add(row["id"])
    trips = []
    for batch_id, ids in owned.items():
        batch = refresh(db, batch_id)
        if not batch:
            continue
        riders, _ = load_riders(db, batch)
        for rider in riders:
            status = rider["status"]
            if rider["id"] not in ids or status == "declined" or (status == "arrived") != (tab == "past"):
                continue
            plan = rider["plan"] or {}
            if rider["direction"] == "from_campus":
                origin = (plan.get("boards") or {}).get(rider["id"])
                if not origin:
                    origin = pickup_street(rider) if plan.get("street") else plan.get("gate") or pickup_street(rider)
                destination = rider["stop"]
            else:
                origin, destination = rider["stop"], campus
            item = {
                "riderId": rider["id"], "batchId": batch_id, "tripDate": batch["trip_date"],
                "pickupTime": trip_pickup(rider), "from": origin, "to": destination,
                "journey": "leave_now" if plan.get("go") else "planned",
                "riders": len(plan.get("members") or [rider]), "only": plan.get("only"),
                "share": money(rider["share"]) if rider["share"] is not None else None,
                "soloFare": money(rider["solo"]), "status": status,
            }
            if tab == "upcoming":
                item["rideCode"] = rider["ride_code"]
            trips.append(item)
    trips.sort(key=lambda trip: (trip["tripDate"], trip["pickupTime"] or "", trip["riderId"]),
               reverse=tab == "past")
    return jsonify(trips=trips)


def routes_student(db):
    token = student_session(db)
    if token["student_id"] is None:
        raise forbidden()
    return token["student_id"]


def saved_route_json(row):
    return {"id": row["id"], "name": row["name"], "stop": row["stop"],
            "direction": row["direction"], "readyAt": row["ready_at"],
            "quiet": bool(row["quiet"]), "mode": row["mode"]}


@api.get("/me/routes")
def my_routes():
    db = database()
    owner = routes_student(db)
    return jsonify(routes=[saved_route_json(row) for row in db.execute(
        "SELECT * FROM saved_routes WHERE student_id = ? ORDER BY id", (owner,))])


@api.post("/me/routes")
def save_route():
    """Screen 28: a saved route only prefills a request; it never books or charges."""
    db = database()
    owner = routes_student(db)
    body = json_body()
    name = field(body, "name", str).strip()
    stop = field(body, "stop", str)
    direction = field(body, "direction", str, "from_campus")
    mode = field(body, "mode", str, "planned")
    quiet = field(body, "quiet", bool, False)
    ready = body.get("readyAt", body.get("ready_at"))
    if "readyAt" in body and "ready_at" in body and body["readyAt"] != body["ready_at"]:
        raise Problem("invalid_input", "Conflicting ready times.", 400)
    if not 1 <= len(name) <= 40 or stop not in STOPS or direction not in ("from_campus", "to_campus") \
            or mode not in ("planned", "leave_now"):
        raise Problem("invalid_input", "Enter a valid name, stop, direction and mode.", 400)
    if ready is not None and (not isinstance(ready, str) or not re.fullmatch(r"[0-9]{2}:[0-5][0-9]", ready)
                              or not "07:00" <= ready <= "23:00"):
        raise Problem("invalid_input", "Ready time must be HH:MM between 07:00 and 23:00.", 400)
    with db:
        db.execute("BEGIN IMMEDIATE")
        if db.execute("SELECT COUNT(*) FROM saved_routes WHERE student_id = ?", (owner,)).fetchone()[0] >= 10:
            raise Problem("too_many_routes", "Save at most 10 routes.", 409)
        route_id = db.execute(
            "INSERT INTO saved_routes (student_id, name, stop, direction, ready_at, quiet, mode) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)", (owner, name, stop, direction, ready, int(quiet), mode),
        ).lastrowid
        row = db.execute("SELECT * FROM saved_routes WHERE id = ?", (route_id,)).fetchone()
    return jsonify(saved_route_json(row)), 201


@api.delete("/me/routes/<int:route_id>")
def delete_route(route_id):
    db = database()
    owner = routes_student(db)
    with db:
        deleted = db.execute("DELETE FROM saved_routes WHERE id = ? AND student_id = ?", (route_id, owner))
        if not deleted.rowcount:
            raise Problem("not_found", "No such saved route.", 404)
    return "", 204


def locked_student_rider(db, rider_id):
    student_session(db)  # rider_access alone also permits operators.
    batch_id = rider_access(db, rider_id)
    batch = locked_batch(db, batch_id)
    if not batch:
        raise Problem("not_found", "No such rider.", 404)
    riders, _ = load_riders(db, batch)
    rider = next((r for r in riders if r["id"] == rider_id), None)
    if rider is None:
        raise Problem("not_found", "No such rider.", 404)
    return rider


def share_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


@api.post("/riders/<int:rider_id>/share-link")
def create_share_link(rider_id):
    """Share sheet: a link someone trusted can open without signing in; only this trip's captain and car."""
    db = database()
    with db:
        rider = locked_student_rider(db, rider_id)
        if rider["status"] in ("arrived", "declined"):
            raise Problem("trip_finished", "This trip has ended.", 410)
        token = secrets.token_urlsafe(24)
        db.execute("INSERT INTO trip_shares (token_hash, rider, created_at) VALUES (?, ?, ?)",
                   (share_hash(token), rider_id, now().isoformat()))
    response = jsonify(url=f"/api/v1/shared/{token}")
    response.headers["Cache-Control"] = "no-store"
    return response, 201


@api.get("/shared/<token>")
def shared_trip(token):
    db = database()
    row = db.execute(
        "SELECT r.id, r.batch FROM trip_shares s JOIN riders r ON r.id = s.rider WHERE s.token_hash = ?",
        (share_hash(token),),
    ).fetchone()
    batch = refresh(db, row["batch"]) if row else None
    if not batch:
        raise Problem("not_found", "No such trip link.", 404)
    riders, _ = load_riders(db, batch)
    rider = next((r for r in riders if r["id"] == row["id"]), None)
    if rider is None:
        raise Problem("not_found", "No such trip link.", 404)
    if rider["status"] in ("arrived", "declined"):
        raise Problem("trip_finished", "This trip has ended.", 410)
    plan = rider["plan"] or {}
    captain = plan.get("captain")
    car = car_details(plan) if plan else {}
    response = jsonify(stop=rider["stop"], pickupTime=trip_pickup(rider), status=rider["status"],
                       captain=first_name(captain["name"]) if captain else None,
                       car=car.get("car"), plate=car.get("plate"))
    response.headers["Cache-Control"] = "no-store"
    return response


@api.post("/riders/<int:rider_id>/rating")
def rate_ride(rider_id):
    """Screen 16: one 1-5 star rating per finished ride."""
    db = database()
    with db:
        rider = locked_student_rider(db, rider_id)
        body = json_body()
        stars = field(body, "stars", int)
        comment = field(body, "comment", str) if "comment" in body else None
        if not 1 <= stars <= 5 or (comment is not None and len(comment) > 300):
            raise Problem("invalid_input", "Choose 1–5 stars and a comment of at most 300 characters.", 400)
        if rider["status"] != "arrived":
            raise Problem("not_finished", "Rate the trip after arrival.", 409)
        if db.execute("SELECT 1 FROM ride_ratings WHERE rider = ?", (rider_id,)).fetchone():
            raise Problem("already_rated", "This trip has already been rated.", 409)
        db.execute("INSERT INTO ride_ratings (rider, stars, comment, created_at) VALUES (?, ?, ?, ?)",
                   (rider_id, stars, comment, now().isoformat()))
    return jsonify(riderId=rider_id, stars=stars, comment=comment), 201
