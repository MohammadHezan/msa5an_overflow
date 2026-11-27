import os
import secrets
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for

from sharing import (
    BASE_FARE, CORRIDORS, MAX_GAP, PER_KM, SEATS, SHARED_RATE, STOP_FEE, STOPS, WALK,
    group_riders, plan_car, sample_share, solo_fare,
)

load_dotenv(Path(__file__).with_name(".env"), override=False)

app = Flask(__name__, instance_relative_config=True)
app.config.update(
    SECRET_KEY=os.environ.get("SESSION_SECRET") or secrets.token_hex(32),
    DATABASE=Path(app.instance_path) / "campus.sqlite",
    MAX_CONTENT_LENGTH=16 * 1024,
)

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
MAX_REQUESTS = 40
VIEWS = {"book": "Book", "match": "Matching", "trips": "Trips"}


def database():
    if "db" not in g:
        path = Path(app.config["DATABASE"])
        path.parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(path, timeout=15)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
        g.db.executescript("""
            CREATE TABLE IF NOT EXISTS batches (
                id TEXT PRIMARY KEY, trip_date TEXT NOT NULL, matched INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS riders (
                id INTEGER PRIMARY KEY, batch TEXT NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
                name TEXT NOT NULL, student_key TEXT NOT NULL, class_end TEXT NOT NULL, stop TEXT NOT NULL,
                woman INTEGER NOT NULL, women_only INTEGER NOT NULL,
                car INTEGER, declined INTEGER NOT NULL DEFAULT 0, confirmed_plan TEXT,
                UNIQUE(batch, student_key)
            );
        """)
    return g.db


@app.teardown_appcontext
def close_database(_error):
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def add_rider(db, batch, name, class_end, stop, woman, women_only):
    return db.execute(
        "INSERT INTO riders (batch, name, student_key, class_end, stop, woman, women_only) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (batch, name, name.casefold(), class_end, stop, woman, women_only),
    ).lastrowid


def new_batch(db, seeded):
    batch = secrets.token_hex(16)
    trip_date = datetime.now(ZoneInfo("Asia/Amman")).date() + timedelta(days=1)
    with db:
        db.execute("INSERT INTO batches (id, trip_date) VALUES (?, ?)", (batch, trip_date.isoformat()))
        if seeded:
            for row in FIXTURE:
                add_rider(db, batch, *row)
        old = session.get("batch")
        if old:
            db.execute("DELETE FROM batches WHERE id = ?", (old,))
    session["batch"] = batch
    session["csrf"] = secrets.token_urlsafe(32)
    return batch


def current_batch(db):
    batch_id = session.get("batch")
    if batch_id:
        batch = db.execute("SELECT * FROM batches WHERE id = ?", (batch_id,)).fetchone()
        if batch:
            return batch
    batch_id = new_batch(db, seeded=True)
    return db.execute("SELECT * FROM batches WHERE id = ?", (batch_id,)).fetchone()


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


@app.template_filter("jod")
def jod(fils):
    return f"JOD {fils / 1000:,.2f}"


@app.template_filter("names")
def names(items):
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


@app.get("/")
def index():
    db = database()
    batch = current_batch(db)
    riders, cars = load_riders(db, batch)
    active = request.args.get("view", "book")
    if active not in VIEWS:
        abort(404)
    try:
        selected_id = int(request.args.get("rider", "0"))
    except ValueError:
        selected_id = 0
    selected = next((r for r in riders if r["id"] == selected_id), None)
    active_riders = [r for r in riders if not r["declined"]]
    summary = {
        "requests": len(riders),
        "shared": sum(1 for r in active_riders if r["plan"] and r["plan"]["shared"]),
        "cars": len(cars),
        "solo_total": sum(r["solo"] for r in active_riders),
        "paid_total": sum(r["share"] or r["solo"] for r in active_riders),
        "confirmed": sum(1 for r in riders if r["status"] in ("confirmed", "solo_confirmed")),
    }
    return render_template(
        "index.html", batch=batch, date_label=date.fromisoformat(batch["trip_date"]).strftime("%a, %d %b"),
        riders=riders, cars=cars, active=active, views=VIEWS, selected=selected, summary=summary,
        corridors=CORRIDORS, estimates={stop: {"solo": solo_fare(stop), "shared": sample_share(stop)} for stop in STOPS},
        rules={"seats": SEATS, "gap": MAX_GAP, "walk": WALK, "base": BASE_FARE, "per_km": PER_KM,
               "stop_fee": STOP_FEE, "rate": round(SHARED_RATE * 100)},
    )


@app.before_request
def check_form():
    if request.method == "POST":
        token = session.get("csrf")
        submitted = request.form.get("csrf", "")
        if not token or not submitted.isascii() or not secrets.compare_digest(token, submitted):
            abort(400, "This demo form expired. Open the demo again and retry.")


def locked_batch(db):
    db.execute("BEGIN IMMEDIATE")
    return db.execute("SELECT * FROM batches WHERE id = ?", (session.get("batch"),)).fetchone()


@app.post("/requests")
def submit_request():
    name = " ".join(request.form.get("name", "").split())
    class_end = request.form.get("class_end", "")
    stop = request.form.get("stop", "")
    woman = request.form.get("woman") == "yes"
    women_only = request.form.get("women_only") == "yes"
    try:
        valid_time = datetime.strptime(class_end, "%H:%M").strftime("%H:%M") == class_end and "08:00" <= class_end <= "21:00"
    except ValueError:
        valid_time = False
    if not 1 <= len(name) <= 40 or stop not in STOPS or not valid_time:
        flash("Enter a name, a drop-off, and a class end time between 08:00 and 21:00.")
        return redirect(url_for("index"))
    if women_only and not woman:
        flash("Women-only matching is available to women students.")
        return redirect(url_for("index"))

    db = database()
    with db:
        batch = locked_batch(db)
        if not batch or batch["matched"]:
            flash("Matching has already run for this batch. Start a new batch to add requests.")
            return redirect(url_for("index"))
        if db.execute("SELECT COUNT(*) FROM riders WHERE batch = ?", (batch["id"],)).fetchone()[0] >= MAX_REQUESTS:
            flash("This demo batch is full.")
            return redirect(url_for("index"))
        try:
            rider_id = add_rider(db, batch["id"], name, class_end, stop, woman, women_only)
        except sqlite3.IntegrityError:
            flash("That name already has a request in this batch.")
            return redirect(url_for("index"))
    flash(f"Request saved. {name} will see a shared-ride plan once matching runs.")
    return redirect(url_for("index", rider=rider_id))


@app.post("/match")
def match():
    db = database()
    with db:
        batch = locked_batch(db)
        if not batch:
            return redirect(url_for("index"))
        if batch["matched"]:
            return redirect(url_for("index", view="trips"))
        riders, _ = load_riders(db, batch)
        if not riders:
            flash("Add a ride request or load the sample afternoon first.")
            return redirect(url_for("index", view="match"))
        groups = group_riders(riders)
        db.executemany(
            "UPDATE riders SET car = ? WHERE id = ?",
            [(car, rider_id) for car, members in enumerate(groups) for rider_id in members],
        )
        db.execute("UPDATE batches SET matched = 1 WHERE id = ?", (batch["id"],))
    flash(f"{len(riders)} students matched into {len(groups)} cars. Each student can now review their plan.")
    return redirect(url_for("index", view="trips"))


@app.post("/riders/<int:rider_id>/<action>")
def respond(rider_id, action):
    if action not in {"confirm", "decline"}:
        abort(404)
    db = database()
    with db:
        batch = locked_batch(db)
        if not batch or not batch["matched"]:
            return redirect(url_for("index"))
        riders, _ = load_riders(db, batch)
        rider = next((r for r in riders if r["id"] == rider_id), None)
        if not rider or rider["declined"]:
            abort(404)
        if action == "confirm" and request.form.get("plan") != rider["signature"]:
            flash("This plan changed before you confirmed. Review the updated plan below.")
        elif action == "confirm":
            db.execute("UPDATE riders SET confirmed_plan = ? WHERE id = ?", (signature(rider["plan"], rider_id), rider_id))
            flash("Ride confirmed." if rider["plan"]["shared"] else "Solo ride confirmed.")
        else:
            db.execute("UPDATE riders SET declined = 1, confirmed_plan = NULL WHERE id = ?", (rider_id,))
            flash(f"{rider['name']} left the ride. Anyone else in the car sees an updated plan.")
    return redirect(url_for("index", rider=rider_id))


@app.post("/reset")
def reset():
    action = request.form.get("mode")
    if action not in {"seeded", "empty"}:
        abort(400)
    new_batch(database(), seeded=action == "seeded")
    flash("Sample afternoon loaded: ten students leaving campus." if action == "seeded" else "A new empty batch is ready.")
    return redirect(url_for("index", view="match" if action == "seeded" else "book"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
