import os
import secrets
import sqlite3
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for

from allocation import CREDIT, WINDOWS, first_come, optimize, summarize

app = Flask(__name__, instance_relative_config=True)
app.config.update(
    SECRET_KEY=os.environ.get("SESSION_SECRET") or secrets.token_hex(32),
    DATABASE=Path(app.instance_path) / "campus.sqlite",
    MAX_CONTENT_LENGTH=16 * 1024,
)

# Preset routes to a single demo campus in Amman.
ROUTES = {
    "Sweileh": {"minutes": 22, "fare": 3500, "bus": {"Morning", "Midday"}},
    "University Street": {"minutes": 18, "fare": 3000, "bus": {"Morning", "Midday"}},
    "Tabarbour": {"minutes": 32, "fare": 4250, "bus": set()},
    "Al Jubeiha": {"minutes": 15, "fare": 2750, "bus": {"Midday"}},
}
FIXTURE = (
    ("Lina", "Sweileh", "08:20"),
    ("Yazan", "University Street", "08:30"),
    ("Omar", "Tabarbour", "08:30"),
    ("Sara", "Sweileh", "18:15"),
    ("Noor", "Al Jubeiha", "09:00"),
    ("Leen", "University Street", "18:30"),
    ("Zaid", "Tabarbour", "17:30"),
)
BUFFER = 10
MAX_REQUESTS = 50


def database():
    if "db" not in g:
        path = Path(app.config["DATABASE"])
        path.parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(path, timeout=15)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
        g.db.executescript("""
            CREATE TABLE IF NOT EXISTS demos (
                id TEXT PRIMARY KEY, trip_date TEXT NOT NULL, finalized INTEGER NOT NULL DEFAULT 0,
                budget INTEGER NOT NULL DEFAULT 6000, cap INTEGER NOT NULL DEFAULT 1,
                morning INTEGER NOT NULL DEFAULT 4, midday INTEGER NOT NULL DEFAULT 2,
                evening INTEGER NOT NULL DEFAULT 3
            );
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY, demo TEXT NOT NULL REFERENCES demos(id) ON DELETE CASCADE,
                name TEXT NOT NULL, student_key TEXT NOT NULL, area TEXT NOT NULL, arrival TEXT NOT NULL,
                full_fare INTEGER NOT NULL, outcome TEXT, baseline TEXT,
                UNIQUE(demo, student_key)
            );
        """)
    return g.db


@app.teardown_appcontext
def close_database(_error):
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def add_request(db, batch, name, area, arrival, full_fare=False):
    return db.execute(
        "INSERT INTO requests (demo, name, student_key, area, arrival, full_fare) VALUES (?, ?, ?, ?, ?, ?)",
        (batch, name, name.casefold(), area, arrival, full_fare),
    ).lastrowid


def new_demo(db, seeded):
    batch = secrets.token_hex(16)
    trip_date = datetime.now(ZoneInfo("Asia/Amman")).date() + timedelta(days=1)
    with db:
        db.execute("INSERT INTO demos (id, trip_date) VALUES (?, ?)", (batch, trip_date.isoformat()))
        if seeded:
            for name, area, arrival in FIXTURE:
                add_request(db, batch, name, area, arrival)
        old_demo = session.get("demo")
        if old_demo:
            db.execute("DELETE FROM demos WHERE id = ?", (old_demo,))
    session["demo"] = batch
    session["csrf"] = secrets.token_urlsafe(32)
    return batch


def current_demo(db):
    batch = session.get("demo")
    if batch:
        demo = db.execute("SELECT * FROM demos WHERE id = ?", (batch,)).fetchone()
        if demo:
            return demo
    batch = new_demo(db, seeded=True)
    return db.execute("SELECT * FROM demos WHERE id = ?", (batch,)).fetchone()


def trip_details(area, arrival):
    hour, minute = map(int, arrival.split(":"))
    window = "Morning" if hour < 11 else "Midday" if hour < 16 else "Evening"
    route = ROUTES[area]
    leave = hour * 60 + minute - route["minutes"] - BUFFER
    return {
        "window": window,
        "bus": window in route["bus"],
        "fare": route["fare"],
        "leave": f"{leave // 60:02d}:{leave % 60:02d}",
    }


def list_requests(db, batch):
    rows = db.execute("SELECT * FROM requests WHERE demo = ? ORDER BY id", (batch,))
    return [
        {**dict(row), **trip_details(row["area"], row["arrival"]), "credits_used": 0}
        for row in rows
    ]


@app.template_filter("jod")
def jod(fils):
    return f"JOD {fils / 1000:,.2f}"


@app.get("/")
def index():
    db = database()
    demo = current_demo(db)
    trips = list_requests(db, demo["id"])
    active = request.args.get("view", "student")
    if active not in {"student", "ops", "results"}:
        abort(404)
    try:
        selected_id = int(request.args.get("ride", "0"))
    except ValueError:
        selected_id = 0
    selected = next((trip for trip in trips if trip["id"] == selected_id), None)
    comparison = {}
    if demo["finalized"]:
        for key in ("outcome", "baseline"):
            assignments = {trip["id"]: trip[key] for trip in trips if trip[key] != "unconfirmed"}
            comparison[key] = summarize(trips, assignments)
    return render_template(
        "index.html", demo=demo, date_label=date.fromisoformat(demo["trip_date"]).strftime("%a, %d %b"),
        trips=trips, active=active, selected=selected, comparison=comparison, routes=ROUTES,
        route_minutes={name: route["minutes"] for name, route in ROUTES.items()},
        buffer=BUFFER, credit=CREDIT,
    )


@app.before_request
def check_form():
    if request.method == "POST":
        token = session.get("csrf")
        submitted = request.form.get("csrf", "")
        if not token or not submitted.isascii() or not secrets.compare_digest(token, submitted):
            abort(400, "This demo form expired. Open the demo again and retry.")


@app.post("/requests")
def submit_request():
    name = " ".join(request.form.get("name", "").split())
    area = request.form.get("area", "")
    arrival = request.form.get("arrival", "")
    try:
        valid_time = datetime.strptime(arrival, "%H:%M").strftime("%H:%M") == arrival and "06:00" <= arrival <= "22:00"
    except ValueError:
        valid_time = False
    if not 1 <= len(name) <= 40 or area not in ROUTES or not valid_time:
        flash("Enter a demo name, a pickup area, and an arrival time between 06:00 and 22:00.")
        return redirect(url_for("index"))

    db = database()
    with db:
        db.execute("BEGIN IMMEDIATE")
        demo = db.execute("SELECT * FROM demos WHERE id = ?", (session["demo"],)).fetchone()
        if not demo or demo["finalized"]:
            flash("The cutoff has passed. Start a new demo batch to submit another request.")
            return redirect(url_for("index"))
        if len(list_requests(db, demo["id"])) >= MAX_REQUESTS:
            flash("This demo batch is full.")
            return redirect(url_for("index"))
        try:
            ride_id = add_request(db, demo["id"], name, area, arrival, request.form.get("full_fare") == "yes")
        except sqlite3.IntegrityError:
            flash("That demo name already has a request in this batch.")
            return redirect(url_for("index"))
    flash("Request added to this evening’s batch.")
    return redirect(url_for("index", ride=ride_id))


@app.post("/allocate")
def allocate():
    try:
        amount = Decimal(request.form["budget"])
        if not amount.is_finite() or not 0 <= amount <= 500:
            raise ValueError
        fils = amount * 1000
        if fils != fils.to_integral_value() or int(fils) % 10:
            raise ValueError
        budget = int(fils)
        cap = int(request.form["cap"])
        capacity = {window: int(request.form[window.lower()]) for window in WINDOWS}
        if cap not in (0, 1) or any(not 0 <= value <= MAX_REQUESTS for value in capacity.values()):
            raise ValueError
    except (InvalidOperation, ValueError, KeyError):
        flash("Enter a budget from JOD 0 to 500, a per-student cap of 0 or 1, and up to 50 drivers per window.")
        return redirect(url_for("index", view="ops"))

    db = database()
    with db:
        db.execute("BEGIN IMMEDIATE")
        demo = db.execute("SELECT * FROM demos WHERE id = ?", (session["demo"],)).fetchone()
        if not demo:
            return redirect(url_for("index"))
        if demo["finalized"]:
            return redirect(url_for("index", view="results"))
        trips = list_requests(db, demo["id"])
        if not trips:
            flash("Add a student request or load the seven-student scenario first.")
            return redirect(url_for("index", view="ops"))
        planned = optimize(trips, budget, cap, capacity)
        baseline = first_come(trips, budget, cap, capacity)
        db.executemany(
            "UPDATE requests SET outcome = ?, baseline = ? WHERE id = ?",
            [(planned.get(trip["id"], "unconfirmed"), baseline.get(trip["id"], "unconfirmed"), trip["id"]) for trip in trips],
        )
        db.execute(
            "UPDATE demos SET finalized = 1, budget = ?, cap = ?, morning = ?, midday = ?, evening = ? WHERE id = ?",
            (budget, cap, *(capacity[window] for window in WINDOWS), demo["id"]),
        )
    return redirect(url_for("index", view="results"))


@app.post("/reset")
def reset():
    action = request.form.get("mode")
    if action not in {"seeded", "empty"}:
        abort(400)
    new_demo(database(), seeded=action == "seeded")
    flash("Seven demo requests loaded." if action == "seeded" else "A new empty demo batch is ready.")
    return redirect(url_for("index", view="ops" if action == "seeded" else "student"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
