"""Batch storage and the booking, matching, confirm and decline actions.

Both the HTML form routes (app.py) and the JSON API (api.py) call these functions,
so the web dashboard and the phone follow one set of rules on one batch.
"""
import hashlib
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import current_app, g

from sharing import (
    BASE_FARE, MAX_GAP, MIN_SHARE, PER_KM, SEATS, SHARED_RATE, STOP_FEE, STOPS, WALK,
    group_riders, plan_car, sample_share, solo_fare,
)

AMMAN = ZoneInfo("Asia/Amman")
MAX_REQUESTS = 40
JOIN_CODE_TTL = timedelta(hours=3)
API_BATCH_TTL = timedelta(hours=24)  # Batches created through the API (they have an operator token) are deleted after this
JOIN_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # No 0/O or 1/I

# name, class ends, drop-off, woman student, women-only matching
FIXTURE = (
    ("Sara", "16:00", "Dabouq", True, True),
    ("Rama", "15:55", "Al Bayader", True, True),
    ("Huda", "16:00", "Wadi As-Seer", True, True),
    ("Kareem", "16:05", "Khalda", False, False),
    ("Omar", "16:10", "Shafa Badran", False, False),
    ("Yazan", "16:20", "Abu Nseir", False, False),
    ("Lina", "16:15", "Al Jubeiha", True, False),
    ("Leen", "13:00", "Um Al Summaq", True, True),
    ("Dana", "13:10", "Abdoun", True, False),
    ("Zaid", "18:00", "Marka", False, False),
)


class Problem(Exception):
    """A rule the request broke. `code` is the stable API error code."""

    def __init__(self, code, message, status=409):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def database():
    if "db" not in g:
        path = Path(current_app.config["DATABASE"])
        path.parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(path, timeout=15)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
        g.db.executescript("""
            CREATE TABLE IF NOT EXISTS batches (
                id TEXT PRIMARY KEY, trip_date TEXT NOT NULL, matched INTEGER NOT NULL DEFAULT 0,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS riders (
                id INTEGER PRIMARY KEY, batch TEXT NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
                name TEXT NOT NULL, student_key TEXT NOT NULL, class_end TEXT NOT NULL, stop TEXT NOT NULL,
                woman INTEGER NOT NULL, women_only INTEGER NOT NULL,
                car INTEGER, declined INTEGER NOT NULL DEFAULT 0, confirmed_plan TEXT,
                UNIQUE(batch, student_key)
            );
            CREATE TABLE IF NOT EXISTS join_codes (
                code TEXT PRIMARY KEY, batch TEXT NOT NULL UNIQUE REFERENCES batches(id) ON DELETE CASCADE,
                expires_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS api_tokens (
                token_hash TEXT PRIMARY KEY, batch TEXT NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
                role TEXT NOT NULL CHECK (role IN ('operator', 'student')),
                rider INTEGER REFERENCES riders(id) ON DELETE CASCADE, client_request_id TEXT
            );
        """)
        columns = {row["name"] for row in g.db.execute("PRAGMA table_info(batches)")}
        if "created_at" not in columns:  # Databases made before batches recorded their creation time
            with g.db:  # Existing batches get a full retention period from now rather than being deleted at once
                g.db.execute("ALTER TABLE batches ADD COLUMN created_at TEXT")
                g.db.execute("UPDATE batches SET created_at = ? WHERE created_at IS NULL", (utc_stamp(),))
    return g.db


def close_database(_error=None):
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def now():
    return datetime.now(AMMAN).replace(microsecond=0)


def add_rider(db, batch, name, class_end, stop, woman, women_only):
    return db.execute(
        "INSERT INTO riders (batch, name, student_key, class_end, stop, woman, women_only) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (batch, name, name.casefold(), class_end, stop, woman, women_only),
    ).lastrowid


def utc_stamp(moment=None):
    return (moment or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(timespec="seconds")


def delete_old_api_batches(db):
    """Delete API-created batches older than API_BATCH_TTL. Call inside a transaction."""
    cutoff = utc_stamp(datetime.now(timezone.utc) - API_BATCH_TTL)
    return db.execute(
        "DELETE FROM batches WHERE created_at < ? AND id IN "
        "(SELECT batch FROM api_tokens WHERE role = 'operator')",
        (cutoff,),
    ).rowcount


def create_batch(db, seeded, replaces=None):
    """New batch for tomorrow in Amman. Deletes `replaces` (a previous batch id) and expired API batches in the same transaction."""
    batch = secrets.token_hex(16)
    trip_date = now().date() + timedelta(days=1)
    with db:
        delete_old_api_batches(db)
        db.execute("INSERT INTO batches (id, trip_date, created_at) VALUES (?, ?, ?)", (batch, trip_date.isoformat(), utc_stamp()))
        if seeded:
            for row in FIXTURE:
                add_rider(db, batch, *row)
        if replaces:
            db.execute("DELETE FROM batches WHERE id = ?", (replaces,))
    return batch


def get_batch(db, batch_id):
    return db.execute("SELECT * FROM batches WHERE id = ?", (batch_id,)).fetchone()


def locked_batch(db, batch_id):
    """Start a write transaction and read the batch, so concurrent actions run one at a time."""
    db.execute("BEGIN IMMEDIATE")
    return get_batch(db, batch_id)


def signature(plan, rider_id):
    return f"{plan['shares'][rider_id]}|{plan['pickup']}|{len(plan['members'])}"


def load_riders(db, batch):
    """Riders with their current car plan and status."""
    riders = [
        {**dict(row), "corridor": STOPS[row["stop"]]["corridor"], "km": STOPS[row["stop"]]["km"], "solo": solo_fare(row["stop"])}
        for row in db.execute("SELECT * FROM riders WHERE batch = ? ORDER BY class_end, id", (batch["id"],))
    ]
    cars = {}
    for rider in riders:
        if rider["car"] is not None and not rider["declined"]:
            cars.setdefault(rider["car"], []).append(rider)
    plans = {car: plan_car(members) for car, members in cars.items()}
    for rider in riders:
        plan = plans.get(rider["car"]) if not rider["declined"] else None
        rider["plan"] = plan
        if not batch["matched"]:
            rider["status"] = "waiting"
        elif rider["declined"]:
            rider["status"] = "declined"
        elif rider["confirmed_plan"] and rider["confirmed_plan"] == signature(plan, rider["id"]):
            rider["status"] = "confirmed" if plan["shared"] else "solo_confirmed"
        elif rider["confirmed_plan"]:
            rider["status"] = "changed"
        else:
            rider["status"] = "review" if plan["shared"] else "no_match"
        rider["share"] = plan["shares"][rider["id"]] if plan else None
        rider["signature"] = signature(plan, rider["id"]) if plan else None
    ordered = sorted(plans.values(), key=lambda p: (p["pickup"], p["gate"], -len(p["members"])))
    return riders, ordered


def summarize(riders, cars):
    active = [r for r in riders if not r["declined"]]
    return {
        "requests": len(riders),
        "shared": sum(1 for r in active if r["plan"] and r["plan"]["shared"]),
        "cars": len(cars),
        "solo_total": sum(r["solo"] for r in active),
        "paid_total": sum(r["share"] or r["solo"] for r in active),
        "confirmed": sum(1 for r in riders if r["status"] in ("confirmed", "solo_confirmed")),
    }


def check_request(name, class_end, stop, woman, women_only):
    """Validate one ride request. Returns the cleaned name."""
    name = " ".join(name.split())
    try:
        valid_time = datetime.strptime(class_end, "%H:%M").strftime("%H:%M") == class_end and "08:00" <= class_end <= "21:00"
    except ValueError:
        valid_time = False
    if not 1 <= len(name) <= 40 or stop not in STOPS or not valid_time:
        raise Problem("invalid_input", "Enter a name, a drop-off, and a class end time between 08:00 and 21:00.", 400)
    if women_only and not woman:
        raise Problem("invalid_input", "Women-only matching is available to women students.", 400)
    return name


def insert_request(db, batch, name, class_end, stop, woman, women_only):
    """Save a checked request. Call inside a locked_batch transaction."""
    if batch["matched"]:
        raise Problem("batch_matched", "Matching has already run for this batch. Start a new batch to add requests.")
    if db.execute("SELECT COUNT(*) FROM riders WHERE batch = ?", (batch["id"],)).fetchone()[0] >= MAX_REQUESTS:
        raise Problem("batch_full", "This demo batch is full.")
    try:
        return add_rider(db, batch["id"], name, class_end, stop, woman, women_only)
    except sqlite3.IntegrityError:
        raise Problem("duplicate_name", "That name already has a request in this batch.") from None


def run_matching(db, batch):
    """Group every rider into cars and close the batch. Call inside a locked_batch transaction.

    Returns (ran_now, rider_count, car_count). A repeat returns the saved cars without regrouping.
    """
    riders, cars = load_riders(db, batch)
    if batch["matched"]:
        return False, len(riders), len(cars)
    if not riders:
        raise Problem("batch_empty", "Add a ride request or load the sample afternoon first.")
    groups = group_riders(riders)
    db.executemany(
        "UPDATE riders SET car = ? WHERE id = ?",
        [(car, rider_id) for car, members in enumerate(groups) for rider_id in members],
    )
    db.execute("UPDATE batches SET matched = 1 WHERE id = ?", (batch["id"],))
    return True, len(riders), len(groups)


def respond_to_plan(db, batch, rider_id, action, reviewed):
    """Confirm (against the reviewed plan signature) or decline. Call inside a locked_batch transaction.

    Returns the rider as it was before the change.
    """
    if not batch["matched"]:
        raise Problem("not_matched", "Matching has not run for this batch yet.")
    riders, _ = load_riders(db, batch)
    rider = next((r for r in riders if r["id"] == rider_id), None)
    if not rider:
        raise Problem("not_found", "No such rider in this batch.", 404)
    if rider["declined"]:
        raise Problem("rider_declined", "This student already left the ride.")
    if action == "confirm":
        if reviewed != rider["signature"]:
            raise Problem("plan_changed", "This plan changed before you confirmed. Review the updated plan.")
        db.execute("UPDATE riders SET confirmed_plan = ? WHERE id = ?", (rider["signature"], rider_id))
    else:
        db.execute("UPDATE riders SET declined = 1, confirmed_plan = NULL WHERE id = ?", (rider_id,))
    return rider


def join_code(db, batch_id):
    """The batch's current student join code and its expiry, issuing a new one if needed."""
    row = db.execute("SELECT * FROM join_codes WHERE batch = ?", (batch_id,)).fetchone()
    if row and datetime.fromisoformat(row["expires_at"]) > now():
        return row["code"], datetime.fromisoformat(row["expires_at"])
    expires = now() + JOIN_CODE_TTL
    with db:
        db.execute("BEGIN IMMEDIATE")
        if not get_batch(db, batch_id):
            raise Problem("not_found", "No such batch.", 404)
        for _ in range(20):  # 32^6 codes, so a collision is rare; never loop without bound
            code = "".join(secrets.choice(JOIN_ALPHABET) for _ in range(6))
            if not db.execute("SELECT 1 FROM join_codes WHERE code = ?", (code,)).fetchone():
                break
        else:
            raise RuntimeError("Could not pick an unused join code.")
        db.execute(
            "INSERT INTO join_codes (code, batch, expires_at) VALUES (?, ?, ?) "
            "ON CONFLICT(batch) DO UPDATE SET code = excluded.code, expires_at = excluded.expires_at",
            (code, batch_id, expires.isoformat()),
        )
    return code, expires


def batch_for_join_code(db, code):
    row = db.execute("SELECT * FROM join_codes WHERE code = ?", (code,)).fetchone()
    if not row or datetime.fromisoformat(row["expires_at"]) <= now():
        return None
    return row["batch"]


def _hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def issue_token(db, batch_id, role):
    token = secrets.token_urlsafe(32)
    with db:
        db.execute("INSERT INTO api_tokens (token_hash, batch, role) VALUES (?, ?, ?)", (_hash(token), batch_id, role))
    return token


def find_token(db, token):
    return db.execute("SELECT * FROM api_tokens WHERE token_hash = ?", (_hash(token),)).fetchone()


def operator_batch_for_token(db, token):
    """The batch an operator token controls, or None for an unknown, student or expired token."""
    row = find_token(db, token) if token else None
    if not row or row["role"] != "operator":
        return None
    return get_batch(db, row["batch"])


def bind_token(db, token_hash, rider_id, client_request_id):
    db.execute(
        "UPDATE api_tokens SET rider = ?, client_request_id = ? WHERE token_hash = ?",
        (rider_id, client_request_id, token_hash),
    )


def fare_estimates():
    """Each drop-off's solo fare and a sample share for three riders, in fils."""
    return {stop: {"solo": solo_fare(stop), "shared": sample_share(stop)} for stop in STOPS}


RULES = {"seats": SEATS, "gap": MAX_GAP, "walk": WALK, "base": BASE_FARE, "per_km": PER_KM,
         "stop_fee": STOP_FEE, "rate": round(SHARED_RATE * 100), "min_share": MIN_SHARE}
