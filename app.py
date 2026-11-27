import os
import re
import secrets
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, abort, flash, jsonify, redirect, render_template, request, session, url_for

from api import api
from join_qr import make_join_qr
from pooling import config
from yalla import yalla
from sharing import CORRIDORS, route_map
from store import (
    API_BATCH_TTL, RULES, WEB_BATCH_TTL, Problem, advance_clock, captain_sheets, check_request, choose, clock,
    close_database, create_batch, database, delete_old_batches, fare_estimates, get_batch, insert_request, join_code,
    load_riders, locked_batch, operator_batch_for_token, refresh, respond_to_plan, run_matching, summarize,
    verify_ride_code,
)
from simulation import run_simulation

load_dotenv(Path(__file__).with_name(".env"), override=False)

app = Flask(__name__, instance_relative_config=True)
app.config.update(
    SECRET_KEY=os.environ.get("SESSION_SECRET") or secrets.token_hex(32),
    DATABASE=Path(app.instance_path) / "campus.sqlite",
    MAX_CONTENT_LENGTH=16 * 1024,
)
app.teardown_appcontext(close_database)
app.register_blueprint(api)
app.register_blueprint(yalla)

VIEWS = {"book": "Student app", "match": "Matching", "trips": "Trips", "captains": "Captains", "simulation": "Simulation"}


# The session tracks two batches: "own_batch" is the one this browser created (replaced on reset),
# and "batch" is the one the dashboard shows and acts on. They differ after an operator opens an
# API-created batch with its operator token; that batch is never deleted by this browser.

def own_batch_id():
    return session.get("own_batch", session.get("batch"))  # Older sessions only stored "batch"


def new_batch(db, seeded):  # seeded: True, False or "busy"
    batch = create_batch(db, seeded, replaces=own_batch_id())
    session["batch"] = session["own_batch"] = batch
    session["csrf"] = secrets.token_urlsafe(32)
    return batch


def current_batch(db):
    batch_id = session.get("batch")
    if batch_id:
        batch = get_batch(db, batch_id)
        if batch:
            return batch
        if batch_id != own_batch_id():  # The opened API batch expired and was cleaned up
            flash("The API batch you opened has been removed. Showing this browser's own batch.")
            session["batch"] = own_batch_id()
            return current_batch(db)
        flash(f"This browser's demo batch was cleared after {WEB_BATCH_TTL.days} days. A fresh sample batch is ready.")
    return get_batch(db, new_batch(db, seeded=True))


app.jinja_env.globals["route_map"] = route_map


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
    batch = refresh(db, current_batch(db)["id"])
    riders, cars = load_riders(db, batch)
    active = request.args.get("view", "book")
    if active not in VIEWS:
        abort(404)
    try:
        selected_id = int(request.args.get("rider", "0"))
    except ValueError:
        selected_id = 0
    selected = next((r for r in riders if r["id"] == selected_id), None)
    code, code_expires, qr_svg = None, None, None
    if active == "match":
        try:
            code, code_expires = join_code(db, batch["id"])
            _, qr_svg = make_join_qr(code)
        except Problem:  # The batch was reset by another request while this page loaded
            pass
    return render_template(
        "phone.html" if active == "book" else "index.html", screen=request.args.get("screen", "home"),
        batch=batch, date_label=date.fromisoformat(batch["trip_date"]).strftime("%a, %d %b"),
        riders=riders, cars=cars, active=active, views=VIEWS, selected=selected, summary=summarize(riders, cars),
        corridors=CORRIDORS, estimates=fare_estimates(), rules=RULES,
        join_code=code, join_expires=code_expires, join_qr_svg=qr_svg, opened=batch["id"] != own_batch_id(),
        api_ttl_hours=int(API_BATCH_TTL.total_seconds() // 3600),
        driver_check=session.pop("driver_check", None) if active == "trips" else None,
        captains=captain_sheets(riders, cars) if active == "captains" else None, now=clock(batch),
        simulation=run_simulation() if active == "simulation" else None,
        student_verified=session.get("student_verified", True), profile=student_profile(),
    )


def student_profile():
    """The student's Jeeny profile (demo): name and gender, plus the trip direction Jeeny knows from the pickup."""
    return {"name": session.get("yalla_name", config.DEMO_STUDENT_NAME),
            "gender": session.get("student_gender", config.DEMO_STUDENT_GENDER),
            "direction": session.get("student_direction", "from_campus")}


@app.before_request
def check_form():
    if request.method == "POST" and request.blueprint != api.name:  # The JSON API uses bearer tokens instead
        token = session.get("csrf")
        submitted = request.form.get("csrf", "")
        if not token or not submitted.isascii() or not secrets.compare_digest(token, submitted):
            abort(400, "This demo form expired. Open the demo again and retry.")


@app.post("/requests")
def submit_request():
    form = request.form
    if form.get("ride", "campus") != "campus":
        flash("Demo only. This prototype books Yalla Ride shared rides only.")
        return redirect(url_for("index", screen="book"))
    if not session.get("student_verified", True):
        flash("Verify your university email to choose Yalla Ride. This is a demo check only.")
        return redirect(url_for("index", screen="book", ride="campus"))
    direction = form.get("direction", "from_campus")
    class_end, class_start, stop = form.get("class_end", ""), form.get("class_start", ""), form.get("stop", "")
    # Older forms sent woman/women_only checkboxes instead of gender/preference
    gender = form.get("gender") or ("woman" if form.get("woman") == "yes" else "man")
    preference = form.get("preference") or ("women" if form.get("women_only") == "yes" else "mixed")
    friends = None
    if form.get("friends") == "start":
        friends = {"mode": "start", "open": form.get("group_open") == "yes"}
    elif form.get("friends") == "join":
        friends = {"mode": "join", "code": form.get("group_code", "")[:10]}
    db = database()
    try:
        name = check_request(form.get("name", ""), class_end, stop, gender, preference, direction, class_start)
        with db:
            batch = locked_batch(db, session.get("batch"))
            if not batch:  # Cleared by the cleanup of old batches; the redirect gives this browser a fresh one
                raise Problem("not_found", "Your request was not saved. Please submit it again.")
            rider_id = insert_request(db, batch, name, class_end, stop, gender, preference, friends,
                                      direction=direction, class_start=class_start)
    except Problem as problem:
        flash(problem.message)
        return redirect(url_for("index", screen="book"))
    batch = get_batch(db, session.get("batch"))
    rider = next(r for r in load_riders(db, batch)[0] if r["id"] == rider_id)
    if not batch["matched"]:
        if friends and friends["mode"] == "start":
            flash(f"Group {rider['friend_group']} created. Friends join with this code (up to {RULES['seats']} in a car).")
        elif friends:
            flash(f"{name} joined group {rider['friend_group']}. You'll ride in one car.")
        else:
            flash(f"Request saved. {name} will see a shared-ride plan once matching runs.")
    elif rider["status"] == "on_the_way":
        flash(f"A car on its way can pick {name} up at {rider['plan']['boards'][rider_id]}.")
    elif rider["status"] == "review":
        flash(f"{name} matched with a student who was waiting.")
    return redirect(url_for("index", rider=rider_id))


@app.post("/demo/student-verification")
def demo_student_verification():
    """Session-only prototype check. No email is stored or sent; this is not real identity verification."""
    if request.form.get("action") == "reset":
        session["student_verified"] = False
        return jsonify(verified=False)
    email = request.form.get("email", "").strip()
    if len(email) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return jsonify(error="Enter a valid university email for the demo."), 400
    session["student_verified"] = True
    return jsonify(verified=True)


@app.post("/match")
def match():
    db = database()
    try:
        with db:
            batch = locked_batch(db, session.get("batch"))
            if not batch:
                return redirect(url_for("index"))
            ran, rider_count, car_count = run_matching(db, batch)
    except Problem as problem:
        flash(problem.message)
        return redirect(url_for("index", view="match"))
    if ran:
        flash(f"{rider_count} students matched into {car_count} cars. Each student can now review their plan.")
    return redirect(url_for("index", view="trips"))


@app.post("/riders/<int:rider_id>/<action>")
def respond(rider_id, action):
    if action not in {"confirm", "decline", "wait", "go"}:
        abort(404)
    db = database()
    try:
        with db:
            batch = locked_batch(db, session.get("batch"))
            if not batch or not batch["matched"]:
                return redirect(url_for("index"))
            if action in {"wait", "go"}:
                choose(db, batch, rider_id, action)
            else:
                rider = respond_to_plan(db, batch, rider_id, action, request.form.get("plan"))
    except Problem as problem:
        if problem.code not in ("plan_changed", "not_alone", "on_the_way", "already_confirmed"):
            abort(404)
        if problem.code != "plan_changed":
            flash(problem.message)
            return redirect(url_for("index", rider=rider_id))
        flash("This plan changed before you confirmed. Review the updated plan below.")
        return redirect(url_for("index", rider=rider_id))
    if action == "wait":
        flash(f"Waiting up to {RULES['wait_minutes']} minutes for a student going your way.")
    elif action == "go":
        flash("Your car is on its way. Students going your way can join on the route.")
    elif action == "confirm":
        flash("Ride confirmed." if rider["plan"]["shared"] else "Solo ride confirmed.")
    else:
        flash(f"{rider['name']} left the ride. Anyone else in the car sees an updated plan.")
    return redirect(url_for("index", rider=rider_id))


@app.post("/driver-check")
def driver_check():
    """The driver types the code a student shows at the meeting point."""
    code = request.form.get("code", "")[:20]
    db = database()
    batch = get_batch(db, session.get("batch"))
    rider = verify_ride_code(db, batch, code) if batch else None
    session["driver_check"] = {"code": code.strip().upper(), "valid": bool(rider)} | (
        {"name": rider["name"].split()[0], "stop": rider["stop"], "pickup": rider["plan"]["pickup"],
         "gate": rider["plan"]["gate"]} if rider else {})
    return redirect(url_for("index", view="trips"))


@app.post("/clock")
def move_clock():
    """Demo control: move this batch's clock forward (seat holds, waiting, cars on the way follow it)."""
    minutes = 1 if request.form.get("minutes") == "1" else 5
    db = database()
    with db:
        batch = get_batch(db, session.get("batch"))
        if batch:
            advance_clock(db, batch["id"], minutes)
    if batch:
        refresh(db, batch["id"])  # Release holds that ran out at the new time
    flash(f"Demo clock moved forward {minutes} minute{'s' if minutes > 1 else ''}.")
    return redirect(request.form.get("back") if request.form.get("back", "").startswith("/") else url_for("index", view="trips"))


@app.post("/batches/open")
def open_batch():
    """Show an API-created batch in this dashboard, given its operator token."""
    db = database()
    with db:
        delete_old_batches(db)
    batch = operator_batch_for_token(db, request.form.get("operator_token", "").strip())
    if not batch:
        flash("That operator token is unknown or its batch has expired.")
        return redirect(url_for("index", view="match"))
    session.setdefault("own_batch", session.get("batch"))
    session["batch"] = batch["id"]
    flash("Opened the API batch. Matching and Trips now act on it.")
    return redirect(url_for("index", view="trips" if batch["matched"] else "match"))


@app.post("/batches/own")
def return_to_own_batch():
    session["batch"] = own_batch_id()
    flash("Back to this browser's own batch.")
    return redirect(url_for("index", view="match"))


@app.post("/reset")
def reset():
    action = request.form.get("mode")
    if action not in {"seeded", "empty", "busy", "morning"}:
        abort(400)
    new_batch(database(), seeded={"seeded": True, "empty": False, "busy": "busy", "morning": "morning"}[action])
    flash({"seeded": "Sample afternoon loaded: ten students leaving campus.",
           "busy": "Busy afternoon loaded: 28 students leaving campus around 16:00.",
           "morning": "Sample morning loaded: students share rides toward campus.",
           "empty": "A new empty batch is ready."}[action])
    return redirect(url_for("index", view="book" if action == "empty" else "match"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
