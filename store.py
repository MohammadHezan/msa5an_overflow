"""Batch storage and the booking, matching, confirm and decline actions.

Both the HTML form routes (app.py) and the JSON API (api.py) call these functions,
so the web dashboard and the phone follow one set of rules on one batch.
"""
import hashlib
import math
import random
import secrets
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import current_app, g

import go_now
from pooling import config
from pooling.codes import new_code
from pooling.model import PREFERENCES
from sharing import (
    BASE_FARE, CORRIDORS, MAX_GAP, MIN_SAVING_PCT, PER_KM, SEATS, STOPS, WALK,
    group_problem, group_riders, plan_car, sample_share, solo_fare, trip_time,
)

AMMAN = ZoneInfo("Asia/Amman")
MAX_REQUESTS = 40
JOIN_CODE_TTL = timedelta(hours=3)
API_BATCH_TTL = timedelta(hours=24)  # Batches created through the API (they have an operator token) are deleted after this
WEB_BATCH_TTL = timedelta(days=3)  # Browser-session batches (no operator token) are deleted after this, even if the browser never resets
JOIN_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # No 0/O or 1/I
SEAT_HOLD = timedelta(minutes=2)  # After matching, a student in a shared car has this long to confirm
WAIT_FOR_MATCH = timedelta(minutes=10)  # Option B for a student left alone
EXTRA_STOP_BONUS = 100  # Fils per drop-off after the first, paid to the captain by Jeeny (not by students)

# name, class end, neighborhood, gender, preference, direction, class start
FIXTURE = (
    ("Sara", "16:00", "Dabouq", "woman", "women", "from_campus", None),
    ("Rama", "15:55", "Al Bayader", "woman", "women", "from_campus", None),
    ("Huda", "16:00", "Wadi As-Seer", "woman", "women", "from_campus", None),
    ("Kareem", "16:05", "Khalda", "man", "mixed", "from_campus", None),
    ("Omar", "16:10", "Shafa Badran", "man", "mixed", "from_campus", None),
    ("Yazan", "16:20", "Abu Nseir", "man", "mixed", "from_campus", None),
    ("Lina", "16:15", "Al Jubeiha", "woman", "mixed", "from_campus", None),
    ("Leen", "13:00", "Um Al Summaq", "woman", "women", "from_campus", None),
    ("Dana", "13:10", "Abdoun", "woman", "mixed", "from_campus", None),
    ("Zaid", "18:00", "Marka", "man", "mixed", "from_campus", None),
)


def _busy_wave():
    """28 students whose classes all end around 16:00 (fixed seed, so the demo is repeatable)."""
    rng = random.Random(28)
    women = ["Aya", "Bana", "Dima", "Farah", "Ghada", "Hala", "Jana", "Lama", "Maya", "Nada", "Raneem", "Salma", "Tala", "Yara"]
    men = ["Adam", "Bilal", "Fares", "Hamza", "Issa", "Jad", "Khalil", "Laith", "Majd", "Nabil", "Qais", "Rami", "Saif", "Tamer"]
    stops = [stop for corridor in CORRIDORS.values() for stop in corridor["stops"]]
    rows = []
    for i, (woman, man) in enumerate(zip(women, men)):
        for name, gender in ((woman, "woman"), (man, "man")):
            preference = "mixed"
            if gender == "woman" and i % 4 == 0:
                preference = "women"
            elif gender == "man" and i % 7 == 3:
                preference = "men"
            rows.append((name, rng.choice(["15:55", "16:00", "16:00", "16:05"]), rng.choice(stops),
                         gender, preference, "from_campus", None))
    return tuple(rows)


BUSY_WAVE = _busy_wave()
MORNING_WAVE = (
    ("Hadi", "", "Dabouq", "man", "mixed", "to_campus", "08:00"),
    ("Samir", "", "Khalda", "man", "mixed", "to_campus", "08:05"),
    ("Salma", "", "Abu Nseir", "woman", "women", "to_campus", "08:00"),
    ("Hala", "", "Shafa Badran", "woman", "mixed", "to_campus", "08:05"),
    ("Tala", "", "Al Jubeiha", "woman", "mixed", "to_campus", "08:10"),
    ("Majd", "", "Marka", "man", "mixed", "to_campus", "08:00"),
    ("Laith", "", "Tabarbour", "man", "mixed", "to_campus", "08:05"),
    ("Rami", "", "Um Al Summaq", "man", "mixed", "to_campus", "08:00"),
    ("Bana", "", "Abdoun", "woman", "mixed", "to_campus", "08:05"),
)

# Simulated captains (drivers): name, gender, available
CAPTAINS = (
    ("Rania", "woman", 1), ("Hiba", "woman", 1), ("Noor", "woman", 1), ("Aseel", "woman", 1),
    ("Ahmad", "man", 1), ("Khaled", "man", 1), ("Mahmoud", "man", 1), ("Basel", "man", 1),
    ("Fadi", "man", 1), ("Samer", "man", 1), ("Yousef", "man", 1), ("Tariq", "man", 1),
)

UNIVERSITIES = (
    ("Al-Balqa Applied University", "Salt", "Salt campus", "Main gate", "bau.edu.jo", 1),
    ("University of Jordan", "Amman", "Amman campus", "Main gate", "ju.edu.jo", 0),
    ("Yarmouk University", "Irbid", "Irbid campus", "Main gate", "yu.edu.jo", 0),
)

RIDER_COLUMNS = {  # Columns added after the first release, with their definitions (migrations add them)
    "ride_code": "TEXT", "gender": "TEXT", "preference": "TEXT NOT NULL DEFAULT 'mixed'", "friend_group": "TEXT",
    "hold_until": "TEXT", "choice": "TEXT", "wait_until": "TEXT", "board_km": "REAL",
    "released": "INTEGER NOT NULL DEFAULT 0",
    "direction": "TEXT NOT NULL DEFAULT 'from_campus'", "class_start": "TEXT", "corridor": "TEXT",
    "start_km": "REAL", "start_side_m": "INTEGER NOT NULL DEFAULT 0",
    "end_km": "REAL", "end_side_m": "INTEGER NOT NULL DEFAULT 0",
}
BATCH_COLUMNS = {"created_at": "TEXT", "clock_offset": "INTEGER NOT NULL DEFAULT 0", "clock_start": "TEXT"}


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
                created_at TEXT, clock_offset INTEGER NOT NULL DEFAULT 0, clock_start TEXT
            );
            CREATE TABLE IF NOT EXISTS riders (
                id INTEGER PRIMARY KEY, batch TEXT NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
                name TEXT NOT NULL, student_key TEXT NOT NULL, class_end TEXT NOT NULL, stop TEXT NOT NULL,
                gender TEXT, preference TEXT NOT NULL DEFAULT 'mixed',
                car INTEGER, declined INTEGER NOT NULL DEFAULT 0, confirmed_plan TEXT, ride_code TEXT,
                friend_group TEXT, hold_until TEXT, choice TEXT, wait_until TEXT, board_km REAL,
                released INTEGER NOT NULL DEFAULT 0, direction TEXT NOT NULL DEFAULT 'from_campus',
                class_start TEXT, corridor TEXT, start_km REAL, start_side_m INTEGER NOT NULL DEFAULT 0,
                end_km REAL, end_side_m INTEGER NOT NULL DEFAULT 0,
                UNIQUE(batch, student_key)
            );
            CREATE TABLE IF NOT EXISTS join_codes (
                code TEXT PRIMARY KEY, batch TEXT NOT NULL UNIQUE REFERENCES batches(id) ON DELETE CASCADE,
                expires_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS api_tokens (
                token_hash TEXT PRIMARY KEY, batch TEXT NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
                role TEXT NOT NULL CHECK (role IN ('operator', 'student')),
                rider INTEGER REFERENCES riders(id) ON DELETE CASCADE, client_request_id TEXT,
                student_id INTEGER REFERENCES students(id)
            );
            CREATE TABLE IF NOT EXISTS captains (
                id INTEGER PRIMARY KEY, name TEXT NOT NULL, gender TEXT NOT NULL, available INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS cars (
                batch TEXT NOT NULL REFERENCES batches(id) ON DELETE CASCADE, car INTEGER NOT NULL,
                captain INTEGER REFERENCES captains(id), mode TEXT NOT NULL DEFAULT 'gate', departed_at TEXT,
                PRIMARY KEY (batch, car)
            );
            CREATE TABLE IF NOT EXISTS friend_groups (
                batch TEXT NOT NULL REFERENCES batches(id) ON DELETE CASCADE, code TEXT NOT NULL,
                open INTEGER NOT NULL DEFAULT 1, PRIMARY KEY (batch, code)
            );
            CREATE TABLE IF NOT EXISTS universities (
                id INTEGER PRIMARY KEY, name TEXT NOT NULL, city TEXT NOT NULL, campus TEXT NOT NULL,
                gate TEXT NOT NULL, email_domain TEXT NOT NULL UNIQUE,
                available INTEGER NOT NULL DEFAULT 0 CHECK (available IN (0, 1))
            );
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY, university INTEGER NOT NULL REFERENCES universities(id),
                email TEXT NOT NULL COLLATE NOCASE, first_name TEXT NOT NULL, verified_at TEXT,
                UNIQUE(university, email)
            );
            CREATE TABLE IF NOT EXISTS saved_routes (
                id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL REFERENCES students(id),
                name TEXT NOT NULL, stop TEXT NOT NULL, direction TEXT NOT NULL DEFAULT 'from_campus',
                ready_at TEXT, quiet INTEGER NOT NULL DEFAULT 0,
                mode TEXT NOT NULL DEFAULT 'planned' CHECK (mode IN ('planned', 'leave_now'))
            );
            CREATE TABLE IF NOT EXISTS trip_shares (
                token_hash TEXT PRIMARY KEY, rider INTEGER NOT NULL REFERENCES riders(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS ride_ratings (
                rider INTEGER PRIMARY KEY REFERENCES riders(id) ON DELETE CASCADE,
                stars INTEGER NOT NULL CHECK (stars BETWEEN 1 AND 5), comment TEXT, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS verification_challenges (
                token_hash TEXT PRIMARY KEY REFERENCES api_tokens(token_hash) ON DELETE CASCADE,
                student_id INTEGER NOT NULL REFERENCES students(id), code_digest TEXT NOT NULL,
                nonce TEXT NOT NULL, expires_at TEXT NOT NULL, sent_at TEXT NOT NULL,
                wrong_attempts INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS university_notifications (
                university_id INTEGER NOT NULL REFERENCES universities(id),
                token_hash TEXT NOT NULL, requested_at TEXT NOT NULL,
                PRIMARY KEY (university_id, token_hash)
            );
        """)
        _migrate(g.db)
        g.db.execute("CREATE UNIQUE INDEX IF NOT EXISTS riders_ride_code ON riders (batch, ride_code)")
        if not g.db.execute("SELECT 1 FROM captains LIMIT 1").fetchone():
            with g.db:
                g.db.executemany("INSERT INTO captains (name, gender, available) VALUES (?, ?, ?)", CAPTAINS)
        with g.db:
            g.db.executemany(
                "INSERT OR IGNORE INTO universities (name, city, campus, gate, email_domain, available) "
                "VALUES (?, ?, ?, ?, ?, ?)", UNIVERSITIES,
            )
    return g.db


def _migrate(db):
    """Bring databases made by earlier versions up to the current schema."""
    token_columns = {row["name"] for row in db.execute("PRAGMA table_info(api_tokens)")}
    if "student_id" not in token_columns:
        with db:
            db.execute("ALTER TABLE api_tokens ADD COLUMN student_id INTEGER REFERENCES students(id)")
    batch_columns = {row["name"] for row in db.execute("PRAGMA table_info(batches)")}
    for column, kind in BATCH_COLUMNS.items():
        if column not in batch_columns:
            with db:
                db.execute(f"ALTER TABLE batches ADD COLUMN {column} {kind}")
                if column == "created_at":  # Existing batches get a full retention period from now rather than being deleted at once
                    db.execute("UPDATE batches SET created_at = ? WHERE created_at IS NULL", (utc_stamp(),))
    rider_columns = {row["name"] for row in db.execute("PRAGMA table_info(riders)")}
    with db:
        for column, kind in RIDER_COLUMNS.items():
            if column not in rider_columns:
                db.execute(f"ALTER TABLE riders ADD COLUMN {column} {kind}")
        if "women_only" in rider_columns:  # Before ride options: woman/women_only became gender/preference
            db.execute("UPDATE riders SET gender = CASE woman WHEN 1 THEN 'woman' ELSE 'man' END, "
                       "preference = CASE women_only WHEN 1 THEN 'women' ELSE 'mixed' END")
            db.execute("ALTER TABLE riders DROP COLUMN woman")
            db.execute("ALTER TABLE riders DROP COLUMN women_only")


def close_database(_error=None):
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def now():
    return datetime.now(AMMAN).replace(microsecond=0)


def clock(batch):
    """The batch's simulated demo clock. It starts when the batch is created and only moves when the
    operator presses "move clock", so seat holds, waiting and cars on the way never run out while
    someone is presenting. (Batches from before the demo clock follow real time.)"""
    start = datetime.fromisoformat(batch["clock_start"]) if batch["clock_start"] else now()
    return start + timedelta(seconds=batch["clock_offset"] or 0)


def _at(stamp):
    return datetime.fromisoformat(stamp) if stamp else None


def _street_location(name, stop, direction):
    """Repeatable simulated location within ±1 km of a preset stop and 0–400 m from its road."""
    seed = int.from_bytes(hashlib.sha256(name.casefold().encode()).digest()[:8], "big")
    rng = random.Random(seed)
    place = STOPS[stop]
    km = max(0.2, place["km"] + rng.uniform(-1, 1))
    side = rng.randint(0, 400)
    campus_side = rng.randint(0, 400)
    if direction == "from_campus":
        return place["corridor"], 0.0, campus_side, km, side
    return place["corridor"], km, side, 0.0, campus_side


def add_rider(db, batch, name, class_end, stop, gender, preference, direction="from_campus",
              class_start=None, friend_group=None):
    corridor, start_km, start_side_m, end_km, end_side_m = _street_location(name, stop, direction)
    return db.execute(
        "INSERT INTO riders (batch, name, student_key, class_end, class_start, stop, gender, preference, "
        "friend_group, direction, corridor, start_km, start_side_m, end_km, end_side_m) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (batch, name, name.casefold(), class_end, class_start, stop, gender, preference, friend_group,
         direction, corridor, start_km, start_side_m, end_km, end_side_m),
    ).lastrowid


def utc_stamp(moment=None):
    return (moment or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(timespec="seconds")


def delete_old_batches(db):
    """Delete API batches older than API_BATCH_TTL and browser batches older than WEB_BATCH_TTL. Call inside a transaction."""
    moment = datetime.now(timezone.utc)
    operator_batches = "SELECT batch FROM api_tokens WHERE role = 'operator'"
    return db.execute(
        f"DELETE FROM batches WHERE (created_at < ? AND id IN ({operator_batches})) "
        f"OR (created_at < ? AND id NOT IN ({operator_batches}))",
        (utc_stamp(moment - API_BATCH_TTL), utc_stamp(moment - WEB_BATCH_TTL)),
    ).rowcount


SAMPLES = {"seeded": FIXTURE, "busy": BUSY_WAVE, "morning": MORNING_WAVE, "empty": ()}


def create_batch(db, seeded, replaces=None):
    """New batch for tomorrow in Amman. Deletes `replaces` (a previous batch id) and expired batches in the same transaction.

    `seeded`: True/"seeded" for the sample afternoon, "busy" for 28 students leaving together, False/"empty" for none.
    """
    rows = SAMPLES[{True: "seeded", False: "empty"}.get(seeded, seeded)]
    batch = secrets.token_hex(16)
    trip_date = now().date() + timedelta(days=1)
    with db:
        delete_old_batches(db)
        db.execute("INSERT INTO batches (id, trip_date, created_at, clock_start) VALUES (?, ?, ?, ?)",
                   (batch, trip_date.isoformat(), utc_stamp(), now().isoformat()))
        for row in rows:
            add_rider(db, batch, *row)
        if replaces:
            db.execute("DELETE FROM batches WHERE id = ?", (replaces,))
    return batch


def get_batch(db, batch_id):
    return db.execute("SELECT * FROM batches WHERE id = ?", (batch_id,)).fetchone()


def locked_batch(db, batch_id):
    """Start a write transaction and read the batch, so concurrent actions run one at a time.

    Seats whose hold ran out are released first, so every action sees the current cars.
    """
    db.execute("BEGIN IMMEDIATE")
    batch = get_batch(db, batch_id)
    if batch:
        release_expired_holds(db, batch)
    return batch


def signature(plan, rider_id):
    return f"{plan['shares'][rider_id]}|{plan['pickup']}|{len(plan['members'])}"


def _go_plan(members, car_row, at):
    """Plan for an option-C car that left with one student and picks others up on the way."""
    departed = _at(car_row["departed_at"])  # On the demo clock, for the car's position
    corridor = members[0]["corridor"]
    direction = members[0]["direction"]
    route_origin = max((m["start_km"] or 0.0) for m in members) if direction == "to_campus" else 0.0
    riders = [
        (m["id"], float(m["board_km"] if m["board_km"] is not None else
                         (m["start_km"] if direction == "to_campus" else 0.0)),
         float(0.0 if direction == "to_campus" else m["km"]))
        for m in members
    ]
    extras = {}
    caps = {}
    for m in members:
        pickup_km = float(m["board_km"] if m["board_km"] is not None else
                          (m["start_km"] if direction == "to_campus" else 0.0))
        extras[m["id"]] = []
        if direction == "from_campus":
            if pickup_km == 0:
                if m["start_side_m"] > 200:
                    extras[m["id"]].append((0.0, 2 * (m["start_side_m"] - 200) / 1000, "pickup"))
            if m["end_side_m"] > 200:
                extras[m["id"]].append((m["km"], 2 * (m["end_side_m"] - 200) / 1000, "dropoff"))
        else:
            if m["start_side_m"] > 200:
                extras[m["id"]].append((pickup_km, 2 * (m["start_side_m"] - 200) / 1000, "pickup"))
            if m["end_side_m"] > 200:
                extras[m["id"]].append((0.0, 2 * (m["end_side_m"] - 200) / 1000, "dropoff"))
        caps[m["id"]] = m["solo"]
    # Retain the time of the original booking and price this entire route at the regulated rate.
    pickup = car_row["departed_at"][11:16]
    shares, fare, route_km = go_now.split(
        riders, trip_time(pickup), direction=direction, extras=extras, caps=caps,
    )
    position = go_now.position_km(departed, at, route_km, direction, route_origin)
    ordered = sorted(members, key=lambda m: ((m["km"] if direction == "from_campus" else -m["start_km"]), m["id"]))
    boards = {
        m["id"]: (m["stop"] + " street" if direction == "to_campus"
                  else go_now.pickup_point(corridor, m["board_km"] or 0.0)[0])
        for m in members
    }
    walk_m = {m["id"]: min(int(m["start_side_m"] or 0), 200) for m in members}
    def time_at(distance):
        return (departed + timedelta(hours=distance / config.SPEED_KMH)).astimezone(AMMAN).strftime("%H:%M")

    rider_times = {}
    drop_times = {}
    all_turns = [turn for entries in extras.values() for turn in entries]
    for rid, board, drop in riders:
        before_board = sum(distance for point, distance, _ in all_turns
                           if point > board) if direction == "to_campus" else sum(
                               distance for point, distance, _ in all_turns if point < board)
        before_drop = sum(distance for point, distance, _ in all_turns if point <= drop)
        rider_times[rid] = time_at((route_origin - board if direction == "to_campus" else board) + before_board)
        drop_times[rid] = time_at(route_km if direction == "to_campus" else drop + before_drop)
    arrived = (at - departed).total_seconds() >= route_km * 3600 / config.SPEED_KMH
    return {
        "gate": CORRIDORS[corridor]["gate"], "corridor": corridor, "pickup": pickup,
        "members": ordered, "car_fare": fare, "route_km": route_km, "shares": shares,
        "shared": len(members) > 1, "only": None, "women_only": False,
        "go": True, "position_km": round(position, 1),
        "arrived": arrived,
        "boards": boards, "direction": direction, "street": True,
        "walk_m": walk_m, "rider_times": rider_times, "drop_times": drop_times,
        "campus_arrival": time_at(route_km) if direction == "to_campus" else None,
        "segment_breakdown": {}, "jeeny_cover": 0,
    }


def load_riders(db, batch, at=None):
    """Riders with their current car plan and status, on the batch's demo clock (or `at`)."""
    at = at or clock(batch)
    riders = [
        {**dict(row), "corridor": row["corridor"] or STOPS[row["stop"]]["corridor"],
         "km": float((row["end_km"] if row["direction"] == "from_campus" else row["start_km"])
                     if row["start_km"] is not None else STOPS[row["stop"]]["km"]),
         "solo": solo_fare(row["stop"]),
         "quoted_share": int(row["confirmed_plan"].split("|", 1)[0]) if row["confirmed_plan"] else None,
         "ready_at": (datetime.strptime(row["class_end"], "%H:%M").replace(
             year=date.fromisoformat(batch["trip_date"]).year,
             month=date.fromisoformat(batch["trip_date"]).month,
             day=date.fromisoformat(batch["trip_date"]).day, tzinfo=AMMAN
         ) + timedelta(seconds=min(row["start_side_m"], 200) / 1.4)).isoformat()
         if row["direction"] == "from_campus" and row["class_end"] else None,
         "arrive_by": (datetime.strptime(row["class_start"], "%H:%M").replace(
             year=date.fromisoformat(batch["trip_date"]).year,
             month=date.fromisoformat(batch["trip_date"]).month,
             day=date.fromisoformat(batch["trip_date"]).day, tzinfo=AMMAN
         ) - timedelta(minutes=5)).isoformat()
         if row["direction"] == "to_campus" and row["class_start"] else None,
         "group_open": bool(row["group_open"]) if row["group_open"] is not None else True}
        for row in db.execute(
            "SELECT riders.*, friend_groups.open AS group_open FROM riders "
            "LEFT JOIN friend_groups ON friend_groups.batch = riders.batch AND friend_groups.code = riders.friend_group "
            "WHERE riders.batch = ? ORDER BY class_end, id", (batch["id"],))
    ]
    for rider in riders:
        if rider["start_km"] is not None and rider["end_km"] is not None:
            solo_plan = plan_car([rider])
            rider["solo"] = solo_plan["shares"][rider["id"]]
    car_rows = {row["car"]: row for row in db.execute(
        "SELECT cars.*, captains.name AS captain_name, captains.gender AS captain_gender FROM cars "
        "LEFT JOIN captains ON captains.id = cars.captain WHERE batch = ?", (batch["id"],))}
    cars = {}
    for rider in riders:
        if rider["car"] is not None and not rider["declined"]:
            cars.setdefault(rider["car"], []).append(rider)
    plans = {}
    for car, members in cars.items():
        row = car_rows.get(car)
        plans[car] = _go_plan(members, row, at) if row and row["mode"] == "go" else plan_car(members)
        plans[car]["id"] = car
        plans[car]["captain"] = {"name": row["captain_name"], "gender": row["captain_gender"]} \
            if row and row["captain_name"] else None
    for rider in riders:
        plan = plans.get(rider["car"]) if not rider["declined"] else None
        rider["plan"] = plan
        hold, wait = _at(rider["hold_until"]), _at(rider["wait_until"])
        if not batch["matched"]:
            rider["status"] = "waiting"
        elif rider["declined"]:
            rider["status"] = "declined"
        elif plan is None:
            rider["status"] = "waiting"  # A late request being placed
        elif plan.get("go"):
            rider["status"] = "arrived" if plan["arrived"] else "on_the_way"
        elif rider["confirmed_plan"] and rider["confirmed_plan"] == signature(plan, rider["id"]):
            rider["status"] = "confirmed" if plan["shared"] else "solo_confirmed"
        elif rider["confirmed_plan"]:
            rider["status"] = "changed"
        elif plan["shared"]:
            rider["status"] = "review"
        elif rider["choice"] == "wait" and wait and wait > at:
            rider["status"] = "waiting_match"
        else:
            rider["status"] = "no_match"
        rider["wait_expired"] = rider["status"] == "no_match" and rider["choice"] == "wait"
        rider["hold_until"] = hold if rider["status"] == "review" and hold else None
        rider["wait_until"] = wait if rider["status"] == "waiting_match" else None
        # The driver check only accepts a code while the student's confirmation matches the current plan
        rider["ride_code"] = rider["ride_code"] if rider["status"] in ACTIVE_RIDES else None
        rider["share"] = plan["shares"][rider["id"]] if plan else None
        rider["signature"] = signature(plan, rider["id"]) if plan else None
        if plan and plan.get("street"):
            rider["walk_m"] = plan["walk_m"].get(rider["id"], 0)
            rider["pickup_at"] = plan["rider_times"].get(rider["id"])
    ordered = sorted(plans.values(), key=lambda p: (p["pickup"], p["gate"], -len(p["members"])))
    return riders, ordered


ACTIVE_RIDES = ("confirmed", "solo_confirmed", "on_the_way", "arrived")


def summarize(riders, cars):
    active = [r for r in riders if not r["declined"]]
    return {
        "requests": len(riders),
        "shared": sum(1 for r in active if r["plan"] and r["plan"]["shared"]),
        "cars": len(cars),
        "solo_total": sum(r["solo"] for r in active),
        "paid_total": sum(r["share"] or r["solo"] for r in active),
        "confirmed": sum(1 for r in riders if r["status"] in ACTIVE_RIDES),
    }


def check_request(name, class_end, stop, gender, preference, direction="from_campus", class_start=None):
    """Validate a homebound or campus-bound request. Returns the cleaned name."""
    name = " ".join(name.split())
    def valid_time(value, earliest="06:00", latest="23:00"):
        try:
            return datetime.strptime(value or "", "%H:%M").strftime("%H:%M") == value and earliest <= value <= latest
        except ValueError:
            return False

    valid_schedule = (
        direction == "from_campus" and valid_time(class_end, "08:00", "21:00")
        or direction == "to_campus" and valid_time(class_start, "07:00", "23:00")
    )
    if not 1 <= len(name) <= 40 or stop not in STOPS or not valid_schedule or direction not in ("to_campus", "from_campus") or gender not in ("woman", "man") \
            or preference not in PREFERENCES:
        raise Problem("invalid_input", "Enter a name, a drop-off, and a class end time between 08:00 and 21:00.", 400)
    if preference == "women" and gender != "woman":
        raise Problem("invalid_input", "Women-only matching is available to women students.", 400)
    if preference == "men" and gender != "man":
        raise Problem("invalid_input", "Men-only matching is available to men students.", 400)
    return name


def legacy_options(woman, women_only):
    """Map the old woman/women_only flags to (gender, preference)."""
    return ("woman" if woman else "man"), ("women" if women_only else "mixed")


def _new_group_code(db, batch_id):
    taken = {row[0] for row in db.execute("SELECT code FROM friend_groups WHERE batch = ?", (batch_id,))}
    free = [f"GR-{n}" for n in range(10, 100) if f"GR-{n}" not in taken]
    if not free:
        raise Problem("batch_full", "No free group codes in this batch.")
    return secrets.choice(free)


def insert_request(db, batch, name, class_end, stop, gender, preference, friends=None,
                   direction="from_campus", class_start=None):
    """Save a checked request. Call inside a locked_batch transaction.

    friends: None (just me), {"mode": "start", "open": bool} or {"mode": "join", "code": "GR-48"}.
    After matching has run, the request is a late request: it is placed at once (see place_late_request).
    """
    if db.execute("SELECT COUNT(*) FROM riders WHERE batch = ?", (batch["id"],)).fetchone()[0] >= MAX_REQUESTS:
        raise Problem("batch_full", "This demo batch is full.")
    if batch["matched"] and friends:
        raise Problem("batch_matched", "Matching already ran, so friends can't book together now. Book on your own.")
    if db.execute("SELECT 1 FROM riders WHERE batch = ? AND student_key = ?", (batch["id"], name.casefold())).fetchone():
        raise Problem("duplicate_name", "That name already has a request in this batch.")
    code = None
    if friends and friends["mode"] == "start":
        code = _new_group_code(db, batch["id"])
        db.execute("INSERT INTO friend_groups (batch, code, open) VALUES (?, ?, ?)", (batch["id"], code, int(friends["open"])))
    elif friends and friends["mode"] == "join":
        code = friends["code"].strip().upper()
        if not db.execute("SELECT 1 FROM friend_groups WHERE batch = ? AND code = ?", (batch["id"], code)).fetchone():
            raise Problem("group_not_found", "No group with that code in this batch.", 404)
        members = [dict(row) for row in db.execute(
            "SELECT * FROM riders WHERE batch = ? AND friend_group = ?", (batch["id"], code))]
        if len(members) >= SEATS:
            raise Problem("group_full", f"That group already has {SEATS} students.")
        corridor, start_km, start_side_m, end_km, end_side_m = _street_location(name, stop, direction)
        newcomer = {"id": 0, "name": name, "class_end": class_end, "class_start": class_start,
                    "stop": stop, "gender": gender, "preference": preference, "direction": direction,
                    "corridor": corridor, "start_km": start_km, "start_side_m": start_side_m,
                    "end_km": end_km, "end_side_m": end_side_m}
        problem = group_problem(members + [newcomer])
        if problem:
            raise Problem("group_mismatch", problem)
    rider_id = add_rider(db, batch["id"], name, class_end, stop, gender, preference,
                         direction, class_start, friend_group=code)
    if batch["matched"]:
        place_late_request(db, batch, rider_id)
    return rider_id


def _next_car(db, batch_id):
    row = db.execute("SELECT MAX(m) FROM (SELECT MAX(car) AS m FROM riders WHERE batch = ? "
                     "UNION ALL SELECT MAX(car) FROM cars WHERE batch = ?)", (batch_id, batch_id)).fetchone()
    return (row[0] if row[0] is not None else -1) + 1


def assign_captain(db, batch_id, car, only):
    """Give `car` a free captain. A women-only car gets a woman captain if one is free; other cars
    prefer men captains, so women captains stay free for women-only cars. No captain free: none."""
    busy = "SELECT captain FROM cars WHERE batch = ? AND captain IS NOT NULL"
    free = db.execute(f"SELECT * FROM captains WHERE available = 1 AND id NOT IN ({busy}) ORDER BY id", (batch_id,)).fetchall()
    wanted = "woman" if only == "women" else "man"
    pick = next((c for c in free if c["gender"] == wanted), free[0] if free else None)
    db.execute("INSERT INTO cars (batch, car, captain) VALUES (?, ?, ?) "
               "ON CONFLICT(batch, car) DO UPDATE SET captain = excluded.captain",
               (batch_id, car, pick["id"] if pick else None))
    return pick


def run_matching(db, batch):
    """Group every rider into cars, give each car a captain, hold each shared seat, and close the batch.
    Call inside a locked_batch transaction.

    Returns (ran_now, rider_count, car_count). A repeat returns the saved cars without regrouping.
    """
    riders, cars = load_riders(db, batch)
    if batch["matched"]:
        return False, len(riders), len(cars)
    if not riders:
        raise Problem("batch_empty", "Add a ride request or load the sample afternoon first.")
    groups = group_riders(riders)
    hold = (clock(batch) + SEAT_HOLD).isoformat()
    db.executemany(
        "UPDATE riders SET car = ?, hold_until = ? WHERE id = ?",
        [(car, hold if len(members) > 1 else None, rider_id) for car, members in enumerate(groups) for rider_id in members],
    )
    db.execute("UPDATE batches SET matched = 1 WHERE id = ?", (batch["id"],))
    _, plans = load_riders(db, get_batch(db, batch["id"]))
    for plan in sorted(plans, key=lambda p: (p["only"] != "women", p["pickup"])):  # Women-only cars pick first
        assign_captain(db, batch["id"], plan["id"], plan["only"])
    return True, len(riders), len(groups)


def release_expired_holds(db, batch):
    """Students in a shared car who did not confirm within SEAT_HOLD lose the seat (a decline); the car is re-planned.
    Call inside a write transaction. Returns the released riders' names."""
    if not batch["matched"]:
        return []
    at = clock(batch)
    riders, _ = load_riders(db, batch, at)
    expired = [r for r in riders if r["status"] == "review" and r["hold_until"] and r["hold_until"] <= at]
    db.executemany("UPDATE riders SET declined = 1, released = 1, ride_code = NULL, confirmed_plan = NULL WHERE id = ?",
                   [(r["id"],) for r in expired])
    return [r["name"] for r in expired]


def refresh(db, batch_id):
    """Apply expired seat holds before a read. Returns the batch row (None if it no longer exists)."""
    batch = get_batch(db, batch_id)
    if not batch or not batch["matched"]:
        return batch
    riders, _ = load_riders(db, batch)
    if any(r["hold_until"] and r["hold_until"] <= clock(batch) for r in riders):
        with db:
            locked_batch(db, batch_id)
    return get_batch(db, batch_id)


def _give_code(db, batch_id, rider_id):
    if not db.execute("SELECT ride_code FROM riders WHERE id = ?", (rider_id,)).fetchone()["ride_code"]:
        taken = {row[0] for row in db.execute(
            "SELECT ride_code FROM riders WHERE batch = ? AND ride_code IS NOT NULL", (batch_id,))}
        db.execute("UPDATE riders SET ride_code = ? WHERE id = ?", (new_code(taken), rider_id))


def place_late_request(db, batch, rider_id):
    """A request after matching. In order: share with students who chose "wait for a match"; join a
    "go now" car whose route is still ahead; otherwise ride alone with the three lone-rider choices."""
    at = clock(batch)
    riders, plans = load_riders(db, batch, at)
    newcomer = next(r for r in riders if r["id"] == rider_id)

    waiting = [r for r in riders if r["status"] == "waiting_match"]
    if waiting:
        for group in group_riders(waiting + [newcomer]):
            if rider_id in group and len(group) > 1:
                car = next(r["car"] for r in waiting if r["id"] in group)
                db.executemany("UPDATE riders SET car = ?, choice = NULL, wait_until = NULL, hold_until = ? WHERE id = ?",
                               [(car, (at + SEAT_HOLD).isoformat(), rid) for rid in group])
                db.execute("DELETE FROM cars WHERE batch = ? AND car NOT IN "
                           "(SELECT car FROM riders WHERE batch = ? AND car IS NOT NULL AND declined = 0)",
                           (batch["id"], batch["id"]))
                return "matched"

    for plan in plans:
        if plan.get("go") and not plan["arrived"]:
            car_row = db.execute("SELECT * FROM cars WHERE batch = ? AND car = ?", (batch["id"], plan["id"])).fetchone()
            pickup = go_now.can_join(plan["members"], newcomer, plan["corridor"], plan["position_km"], _at(car_row["departed_at"]))
            if pickup:
                db.execute("UPDATE riders SET car = ?, board_km = ?, choice = 'go' WHERE id = ?", (plan["id"], pickup[1], rider_id))
                _give_code(db, batch["id"], rider_id)
                return "joined"

    car = _next_car(db, batch["id"])
    db.execute("UPDATE riders SET car = ? WHERE id = ?", (car, rider_id))
    assign_captain(db, batch["id"], car, None)
    return "alone"


def choose(db, batch, rider_id, choice):
    """A student left alone picks B ("wait") or C ("go"). Option A is a normal confirm. Call inside locked_batch."""
    riders, _ = load_riders(db, batch)
    rider = next((r for r in riders if r["id"] == rider_id), None)
    if not rider:
        raise Problem("not_found", "No such rider in this batch.", 404)
    alone = rider["plan"] is not None and not rider["plan"]["shared"] and not rider["plan"].get("go")
    if choice == "wait" and alone and rider["status"] in ("no_match", "changed"):
        db.execute("UPDATE riders SET choice = 'wait', wait_until = ? WHERE id = ?",
                   ((clock(batch) + WAIT_FOR_MATCH).isoformat(), rider_id))
    elif choice == "go" and alone and rider["status"] in ("no_match", "changed", "waiting_match"):
        board = rider["start_km"] if rider["direction"] == "to_campus" else 0.0
        db.execute("UPDATE riders SET choice = 'go', wait_until = NULL, board_km = ?, confirmed_plan = NULL WHERE id = ?",
                   (board, rider_id))
        db.execute("INSERT INTO cars (batch, car, mode, departed_at) VALUES (?, ?, 'go', ?) "
                   "ON CONFLICT(batch, car) DO UPDATE SET mode = 'go', departed_at = excluded.departed_at",
                   (batch["id"], rider["car"], clock(batch).isoformat()))
        _give_code(db, batch["id"], rider_id)
    else:
        raise Problem("not_alone", "That choice is only for a student riding alone.")
    return rider


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
    if rider["status"] in ("on_the_way", "arrived"):
        raise Problem("on_the_way", "This ride has already left.")
    if action == "confirm":
        if rider["status"] in ("confirmed", "solo_confirmed") and reviewed == rider["signature"]:
            raise Problem("already_confirmed", "This seat is already confirmed.")
        if reviewed != rider["signature"]:
            raise Problem("plan_changed", "This plan changed before you confirmed. Review the updated plan.")
        db.execute("UPDATE riders SET confirmed_plan = ?, choice = NULL, wait_until = NULL WHERE id = ?",
                   (rider["signature"], rider_id))
        _give_code(db, batch["id"], rider_id)  # Re-confirming after a plan change keeps the code the student already has
    else:
        db.execute("UPDATE riders SET declined = 1, confirmed_plan = NULL, ride_code = NULL WHERE id = ?", (rider_id,))
    return rider


def verify_ride_code(db, batch, code):
    """The confirmed rider holding `code` in this batch, or None. Codes of riders whose plan changed are not valid."""
    code = code.strip().upper()
    riders, _ = load_riders(db, batch)
    return next((r for r in riders if code and r["ride_code"] == code), None)


def advance_clock(db, batch_id, minutes):
    """Move the batch's demo clock forward (seat holds, waiting and "go now" cars all follow it)."""
    db.execute("UPDATE batches SET clock_offset = clock_offset + ? WHERE id = ?", (minutes * 60, batch_id))


def captain_sheets(riders, cars):
    """What each captain sees: their car, the stops in order, codes to check, the fare and Jeeny's extra-stop bonus."""
    by_id = {r["id"]: r for r in riders}
    sheets = []
    for plan in cars:
        stops = list(dict.fromkeys(m["stop"] for m in plan["members"]))
        if plan.get("street"):
            if plan["direction"] == "to_campus":
                steps = [
                    {"kind": "pickup", "place": m["stop"] + " street",
                     "time": plan["rider_times"][m["id"]], "rider": m["name"].split()[0]}
                    for m in plan["members"]
                ]
                steps.append({"kind": "drop-off", "place": plan["gate"], "time": plan["campus_arrival"],
                              "rider": "All riders"})
            else:
                pickups = sorted(plan["members"], key=lambda m: (m.get("start_side_m", 0), m["id"]))
                steps = [
                    {"kind": "pickup", "place": "Campus street",
                     "time": plan["rider_times"][m["id"]], "rider": m["name"].split()[0]}
                    for m in pickups
                ]
                steps.extend(
                    {"kind": "drop-off", "place": m["stop"],
                     "time": plan["drop_times"][m["id"]], "rider": m["name"].split()[0]}
                    for m in plan["members"]
                )
        else:
            steps = [{"kind": "stop", "place": place, "time": plan["pickup"], "rider": ""}
                     for place in stops]
        sheets.append({
            "plan": plan, "captain": plan["captain"], "stops": stops,
            "steps": steps,
            "codes": [(m["name"], by_id[m["id"]]["ride_code"]) for m in plan["members"]],
            "bonus": EXTRA_STOP_BONUS * (len(plan["members"]) - 1),
        })
    return sheets


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


def issue_token(db, batch_id, role, student_id=None, commit=True):
    token = secrets.token_urlsafe(32)
    db.execute("INSERT INTO api_tokens (token_hash, batch, role, student_id) VALUES (?, ?, ?, ?)",
               (_hash(token), batch_id, role, student_id))
    if commit:
        db.commit()
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


def fare_estimates(student_name="Sara"):
    """Destination estimates for the chooser; comparison services never book rides."""
    result = {}
    for stop, info in STOPS.items():
        solo, shared = solo_fare(stop), sample_share(stop)
        pickups = {}
        for direction in ("from_campus", "to_campus"):
            corridor, _, side, _, _ = _street_location(student_name, stop, direction)
            walk = min(side, config.MAX_WALK_M)
            pickups[direction] = {
                "walk_meters": walk,
                "walk_minutes": math.ceil(walk / config.WALK_SPEED / 60),
                "street": "Cedar Campus street" if direction == "from_campus" else f"{corridor} corridor street",
            }
        result[stop] = {
            "solo": solo, "shared": shared,
            "taxi": 390 + round(280 * info["km"]),
            "comfort": round(solo * 13 / 10), "box": solo,
            "save_percent": round((solo - shared) * 100 / solo) if solo else 0,
            "pickups": pickups,
        }
    return result


RULES = {"seats": SEATS, "gap": MAX_GAP, "walk": WALK, "base": BASE_FARE, "per_km": PER_KM,
         "min_saving": MIN_SAVING_PCT, "hold_minutes": int(SEAT_HOLD.total_seconds() // 60),
         "wait_minutes": int(WAIT_FOR_MATCH.total_seconds() // 60), "stop_bonus": EXTRA_STOP_BONUS}
