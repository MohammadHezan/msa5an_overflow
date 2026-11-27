import os
import secrets
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, abort, flash, redirect, render_template, request, session, url_for

from api import api
from sharing import CORRIDORS, route_map
from store import (
    API_BATCH_TTL, RULES, WEB_BATCH_TTL, Problem, check_request, close_database, create_batch, database, delete_old_batches, fare_estimates,
    get_batch, insert_request, join_code, load_riders, locked_batch, operator_batch_for_token, respond_to_plan,
    run_matching, summarize,
)

load_dotenv(Path(__file__).with_name(".env"), override=False)

app = Flask(__name__, instance_relative_config=True)
app.config.update(
    SECRET_KEY=os.environ.get("SESSION_SECRET") or secrets.token_hex(32),
    DATABASE=Path(app.instance_path) / "campus.sqlite",
    MAX_CONTENT_LENGTH=16 * 1024,
)
app.teardown_appcontext(close_database)
app.register_blueprint(api)

VIEWS = {"book": "Student app", "match": "Matching", "trips": "Trips"}


# The session tracks two batches: "own_batch" is the one this browser created (replaced on reset),
# and "batch" is the one the dashboard shows and acts on. They differ after an operator opens an
# API-created batch with its operator token; that batch is never deleted by this browser.

def own_batch_id():
    return session.get("own_batch", session.get("batch"))  # Older sessions only stored "batch"


def new_batch(db, seeded):
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
    code, code_expires = None, None
    if active == "match":
        try:
            code, code_expires = join_code(db, batch["id"])
        except Problem:  # The batch was reset by another request while this page loaded
            pass
    return render_template(
        "phone.html" if active == "book" else "index.html", screen=request.args.get("screen", "home"),
        batch=batch, date_label=date.fromisoformat(batch["trip_date"]).strftime("%a, %d %b"),
        riders=riders, cars=cars, active=active, views=VIEWS, selected=selected, summary=summarize(riders, cars),
        corridors=CORRIDORS, estimates=fare_estimates(), rules=RULES,
        join_code=code, join_expires=code_expires, opened=batch["id"] != own_batch_id(),
        api_ttl_hours=int(API_BATCH_TTL.total_seconds() // 3600),
    )


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
    class_end, stop = form.get("class_end", ""), form.get("stop", "")
    woman, women_only = form.get("woman") == "yes", form.get("women_only") == "yes"
    db = database()
    try:
        name = check_request(form.get("name", ""), class_end, stop, woman, women_only)
        with db:
            batch = locked_batch(db, session.get("batch"))
            if not batch:  # Cleared by the cleanup of old batches; the redirect gives this browser a fresh one
                raise Problem("not_found", "Your request was not saved. Please submit it again.")
            rider_id = insert_request(db, batch, name, class_end, stop, woman, women_only)
    except Problem as problem:
        flash(problem.message)
        return redirect(url_for("index"))
    flash(f"Request saved. {name} will see a shared-ride plan once matching runs.")
    return redirect(url_for("index", rider=rider_id))


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
    if action not in {"confirm", "decline"}:
        abort(404)
    db = database()
    try:
        with db:
            batch = locked_batch(db, session.get("batch"))
            if not batch or not batch["matched"]:
                return redirect(url_for("index"))
            rider = respond_to_plan(db, batch, rider_id, action, request.form.get("plan"))
    except Problem as problem:
        if problem.code != "plan_changed":
            abort(404)
        flash("This plan changed before you confirmed. Review the updated plan below.")
        return redirect(url_for("index", rider=rider_id))
    if action == "confirm":
        flash("Ride confirmed." if rider["plan"]["shared"] else "Solo ride confirmed.")
    else:
        flash(f"{rider['name']} left the ride. Anyone else in the car sees an updated plan.")
    return redirect(url_for("index", rider=rider_id))


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
    if action not in {"seeded", "empty"}:
        abort(400)
    new_batch(database(), seeded=action == "seeded")
    flash("Sample afternoon loaded: ten students leaving campus." if action == "seeded" else "A new empty batch is ready.")
    return redirect(url_for("index", view="match" if action == "seeded" else "book"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
