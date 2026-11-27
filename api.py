"""Versioned JSON API for the Expo student app and operator tools.

Each endpoint mirrors an HTML form route in app.py and calls the same functions in store.py.
Access uses bearer tokens: an operator token from creating a batch, or a student token from a join code.
"""
import re
from datetime import date, datetime, time

from flask import Blueprint, jsonify, request
from werkzeug.exceptions import HTTPException

from sharing import CORRIDORS
from store import (
    AMMAN, RULES, Problem, batch_for_join_code, bind_token, check_request, create_batch, database, fare_estimates,
    find_token, get_batch, insert_request, legacy_options, refresh, issue_token, join_code, load_riders, locked_batch, now,
    respond_to_plan, run_matching, summarize, verify_ride_code,
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
                    "classStart": rider["class_start"], "stop": rider["stop"], "gender": rider["gender"],
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
            "arriveBy": rider["class_start"] if rider["direction"] == "to_campus" else None,
            "riders": [first_name(m["name"]) for m in plan["members"] if m["id"] != rider["id"]],
            "dropOffs": [
                {"order": i, "stop": m["stop"], "rider": first_name(m["name"]), "you": m["id"] == rider["id"]}
                for i, m in enumerate(plan["members"], 1)
            ],
            "share": money(rider["share"]), "soloFare": money(rider["solo"]),
            "saving": money(rider["solo"] - rider["share"]), "signature": rider["signature"],
        }
    return body


def batch_json(db, batch):
    riders, cars = load_riders(db, batch)
    by_id = {r["id"]: r for r in riders}
    code, expires = join_code(db, batch["id"])
    summary = summarize(riders, cars)
    return {
        "id": batch["id"], "tripDate": batch["trip_date"], "timezone": "Asia/Amman", "matched": bool(batch["matched"]),
        "joinCode": code, "joinCodeExpiresAt": expires.isoformat(),
        "riders": [
            {"id": r["id"], "name": r["name"], "classEnd": r["class_end"], "stop": r["stop"], "corridor": r["corridor"],
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
    if mode not in {"seeded", "empty"}:
        raise Problem("invalid_input", "`mode` must be `seeded` or `empty`.", 400)
    db = database()
    batch_id = create_batch(db, seeded=mode == "seeded")
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
    return jsonify({
        "token": issue_token(db, batch_id, "student"), "tokenType": "Bearer",
        "batchId": batch_id, "tripDate": batch["trip_date"], "timezone": "Asia/Amman", "matched": bool(batch["matched"]),
    }), 201


@api.get("/stops")
def stops():
    estimates = fare_estimates()
    return jsonify({
        "currency": "JOD",
        "corridors": [
            {"name": name, "gate": corridor["gate"], "stops": [
                {"name": stop, "km": km, "soloFare": money(estimates[stop]["solo"]),
                 "sampleShare": money(estimates[stop]["shared"])}
                for stop, km in corridor["stops"].items()
            ]}
            for name, corridor in CORRIDORS.items()
        ],
        "rules": {
            "seatsPerCar": RULES["seats"], "maxClassEndGapMinutes": RULES["gap"], "walkToGateMinutes": RULES["walk"],
            "classEndEarliest": "08:00", "classEndLatest": "21:00", "sampleShareRiders": SAMPLE_RIDERS,
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
        "pickupTime": rider["plan"]["pickup"],
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
