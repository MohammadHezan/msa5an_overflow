"""Yalla Ride student screens (Brief 04: docs/design/campus-connect-screens).

Full-screen steps that sit on top of the same booking, matching, confirm/decline and ride-code
actions as the Jeeny ride list. The draft request lives in the browser session until it is booked.
Verification is a demo check only: no email is sent and the code is shown on screen.
"""
import re
from pathlib import Path
import secrets
from datetime import datetime, timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

from pooling.config import DETOUR_EXTRA_KM, SPEED_KMH
from sharing import CORRIDORS, STOPS
from store import (
    RULES, Problem, advance_clock, check_request, choose, clock, create_batch, database, fare_estimates, get_batch, insert_request,
    load_riders, locked_batch, refresh, respond_to_plan, run_matching,
)

yalla = Blueprint("yalla", __name__, url_prefix="/yalla")

UNIVERSITIES = [
    {"id": "cedar", "name": "Cedar University", "campus": "Cedar Campus", "detail": "Cedar Campus · Street pickup", "open": True,
     "domain": "cedar.edu"},
    {"id": "hillcrest", "name": "Hillcrest University", "campus": "Hillcrest", "detail": "Hill City · Campus service updates", "open": False,
     "domain": "hillcrest.edu"},
    {"id": "northfield", "name": "Northfield University", "campus": "Northfield", "detail": "North City · Campus service updates", "open": False,
     "domain": "northfield.edu"},
]
CODE_LIFETIME = timedelta(minutes=5)
DEMO_JOINERS = ["Lina", "Noor", "Huda", "Rama", "Dima", "Tala"]
CAR_COLORS = ["White sedan", "Silver sedan", "Grey hatchback", "Black sedan"]
PREFERENCE_NAMES = {"mixed": "Anyone", "women": "Women only", "men": "Men only"}
DEFAULT_DRAFT = {"direction": "from_campus", "stop": "Dabouq", "class_end": "16:00", "class_start": "08:30",
                 "gender": "woman", "preference": "mixed", "quiet": False, "friends": "", "group_code": "",
                 "group_open": True}


def ampm(value):
    """'16:15' -> '4:15 PM'."""
    if not value:
        return ""
    hour, minute = map(int, str(value)[:5].split(":"))
    return f"{(hour - 1) % 12 + 1}:{minute:02d} {'AM' if hour < 12 else 'PM'}"


def add_minutes(value, minutes):
    hour, minute = map(int, value.split(":"))
    total = hour * 60 + minute + minutes
    return f"{total // 60 % 24:02d}:{total % 60:02d}"


def minutes_between(start, end):
    (h1, m1), (h2, m2) = map(int, start.split(":")), map(int, end.split(":"))
    return (h2 * 60 + m2) - (h1 * 60 + m1)


@yalla.app_template_filter("ampm")
def ampm_filter(value):
    return ampm(value)


def draft():
    profile = {"gender": session.get("student_gender", DEFAULT_DRAFT["gender"]),
               "direction": session.get("student_direction", DEFAULT_DRAFT["direction"])}  # From the Jeeny profile
    return {**DEFAULT_DRAFT, **profile, **session.get("yalla", {})}


def save_draft(**changes):
    session["yalla"] = {**draft(), **changes}


def university():
    chosen = session.get("yalla_university", "cedar")
    return next(u for u in UNIVERSITIES if u["id"] == chosen)


def verified():
    return session.get("student_verified", True)


def student_name():
    return session.get("yalla_name", "Sara A")


def walk_minutes(meters):
    return max(1, -(-int(meters) // 84))  # 1.4 m/s = 84 m per minute, rounded up


def pickup_street(rider_or_draft):
    """The street a student walks to (brief 02): the campus street homebound, their corridor street campus-bound."""
    if rider_or_draft["direction"] == "from_campus":
        return "Cedar Campus street"
    return f"{rider_or_draft.get('corridor') or STOPS[rider_or_draft['stop']]['corridor']} corridor street"


def car_details(plan):
    """Made-up car and plate for the demo captain, repeatable per car."""
    number = int(plan.get("id") or 1)
    return {"car": CAR_COLORS[number % len(CAR_COLORS)], "plate": f"{10 + number:02d}-{(number * 7919) % 90000 + 10000}",
            "rating": "4.9", "ratings": 120 + number * 37}


def current_rider():
    """(batch, rider) for the rider this browser booked through Yalla Ride, or (batch, None)."""
    db = database()
    batch = refresh(db, session.get("batch")) if session.get("batch") else None
    if not batch:
        return None, None
    rider_id = request.args.get("rider", type=int) or session.get("yalla_rider")
    riders, _ = load_riders(db, batch)
    rider = next((r for r in riders if r["id"] == rider_id), None)
    if rider:
        session["yalla_rider"] = rider["id"]
    return batch, rider


def asset_version():
    """Changes whenever yalla.css or yalla.js changes, so phones never keep an old copy."""
    folder = Path(__file__).parent / "static"
    return int(max((folder / name).stat().st_mtime for name in ("yalla.css", "yalla.js")))


def render(template, **context):
    return render_template(f"yalla/{template}", university=university(), verified=verified(), asset_version=asset_version(),
                           rules=RULES, draft=draft(), **context)


# ---------- 01 · home ----------

@yalla.get("")
def home():
    _, rider = current_rider()
    return render("home.html", rider=rider)


# ---------- 02-04 · student verification (demo only) ----------

@yalla.route("/verify", methods=["GET", "POST"])
def verify():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        if len(email) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            flash("Enter a valid university email.")
            return redirect(url_for("yalla.verify", next=request.form.get("next")))
        domain = email.rsplit("@", 1)[1].lower()
        if not any(domain == u["domain"] or domain.endswith("." + u["domain"]) for u in UNIVERSITIES):
            session["yalla_bad_email"] = email
            return redirect(url_for("yalla.email_recovery", next=request.form.get("next")))
        session.pop("yalla_bad_email", None)
        session["yalla_email"] = masked(email)  # Only the masked form is kept; nothing is sent
        local = re.split(r"[._+-]", email.split("@")[0])
        session["yalla_name"] = " ".join(part.capitalize() for part in local if part)[:40] or "Student"
        session["yalla_code"] = f"{secrets.randbelow(900000) + 100000}"
        session["yalla_code_until"] = (datetime.now() + CODE_LIFETIME).isoformat()
        flash("Verification code sent")
        return redirect(url_for("yalla.verify_code", next=request.form.get("next")))
    return render("verify.html", email=session.get("yalla_bad_email") or ("" if session.get("yalla_email") else "sara.a@cedar.edu"),
                  next=safe_next())


@yalla.get("/verify/check")
def email_recovery():
    """37: the address is not a university-issued email, so student status cannot be verified."""
    if not session.get("yalla_bad_email"):
        return redirect(url_for("yalla.verify"))
    return render("email_recovery.html", email=session["yalla_bad_email"], next=safe_next())


def masked(email):
    name, _, domain = email.partition("@")
    return f"{name[:1]}***@{domain}"


@yalla.route("/verify/code", methods=["GET", "POST"])
def verify_code():
    if not session.get("yalla_code"):
        return redirect(url_for("yalla.verify"))
    until = datetime.fromisoformat(session["yalla_code_until"])
    if request.method == "POST":
        entered = "".join(request.form.getlist("digit"))[:6] or request.form.get("code", "")
        if datetime.now() > until:
            flash("That code expired. Send a new one.")
        elif not secrets.compare_digest(entered, session["yalla_code"]):
            flash("That code is not right. Check it and try again.")
        else:
            session["student_verified"] = True
            session.pop("yalla_code", None)
            return redirect(url_for("yalla.choose_university", next=request.form.get("next")))
        return redirect(url_for("yalla.verify_code", next=request.form.get("next")))
    left = max(0, int((until - datetime.now()).total_seconds()))
    return render("verify_code.html", masked=session.get("yalla_email", ""), demo_code=session["yalla_code"],
                  left=f"{left // 60:02d}:{left % 60:02d}", next=safe_next())


@yalla.post("/verify/resend")
def resend_code():
    if not session.get("yalla_email"):
        return redirect(url_for("yalla.verify"))
    session["yalla_code"] = f"{secrets.randbelow(900000) + 100000}"
    session["yalla_code_until"] = (datetime.now() + CODE_LIFETIME).isoformat()
    flash("Verification code sent")
    return redirect(url_for("yalla.verify_code", next=request.form.get("next")))


@yalla.route("/university", methods=["GET", "POST"])
def choose_university():
    if request.method == "POST":
        chosen = next((u for u in UNIVERSITIES if u["id"] == request.form.get("university")), None)
        if not chosen:
            abort(400)
        if not chosen["open"]:
            return redirect(url_for("yalla.not_available", university=chosen["id"]))
        session["yalla_university"] = chosen["id"]
        return redirect(safe_next() or url_for("yalla.home"))
    return render("university.html", universities=UNIVERSITIES, next=safe_next())


@yalla.post("/notify")
def notify():
    session.setdefault("yalla_notify", [])
    if request.form.get("university") not in session["yalla_notify"]:
        session["yalla_notify"] = session["yalla_notify"] + [request.form.get("university", "")[:20]]
    flash("Campus notifications on")
    return redirect(safe_next() or url_for("yalla.choose_university"))


@yalla.get("/not-available")
def not_available():
    chosen = next((u for u in UNIVERSITIES if u["id"] == request.args.get("university")), UNIVERSITIES[1])
    return render("not_available.html", chosen=chosen)


def safe_next():
    target = request.values.get("next") or ""
    return target if target.startswith("/") and not target.startswith("//") else ""


def need_verified():
    if not verified():
        return redirect(url_for("yalla.verify", next=request.path))
    return None


# ---------- 05-08 · plan a shared ride ----------

@yalla.route("/plan/destination", methods=["GET", "POST"])
def destination():
    if (blocked := need_verified()):
        return blocked
    if request.method == "POST" or request.args.get("stop"):
        values = request.values
        stop = values.get("stop", draft()["stop"])
        direction = values.get("direction", draft()["direction"])
        if stop not in STOPS or direction not in ("from_campus", "to_campus"):
            abort(400)
        save_draft(stop=stop, direction=direction)
        if request.method == "POST" and values.get("go") == "next":
            return redirect(url_for("yalla.pickup_time"))
        return redirect(url_for("yalla.destination"))
    return render("destination.html", corridors=CORRIDORS, saved=session.get("yalla_saved", []),
                  recent=session.get("yalla_recent", []))


@yalla.route("/plan/time", methods=["GET", "POST"])
def pickup_time():
    if (blocked := need_verified()):
        return blocked
    d = draft()
    if request.method == "POST":
        field = "class_end" if d["direction"] == "from_campus" else "class_start"
        value = request.form.get(field, "")
        save_draft(**{field: value})
        return redirect(url_for("yalla.preferences"))
    pickup = fare_estimates(student_name())[d["stop"]]["pickups"][d["direction"]]
    return render("time.html", pickup=pickup, ready=add_minutes(d["class_end"], pickup["walk_minutes"]),
                  arrive=add_minutes(d["class_start"], -5), batch_date=batch_date())


@yalla.route("/plan/preferences", methods=["GET", "POST"])
def preferences():
    if (blocked := need_verified()):
        return blocked
    if request.method == "POST":
        form = request.form
        gender = form.get("gender") if form.get("gender") in ("woman", "man") else draft()["gender"]
        preference = form.get("preference") if form.get("preference") in PREFERENCE_NAMES else "mixed"
        if (preference == "women" and gender != "woman") or (preference == "men" and gender != "man"):
            preference = "mixed"
        friends = form.get("friends") if form.get("friends") in ("", "start", "join") else ""
        save_draft(gender=gender, preference=preference, quiet=form.get("quiet") == "yes", friends=friends,
                   group_code=form.get("group_code", "")[:10].strip().upper(), group_open=form.get("group_open") == "yes")
        return redirect(url_for("yalla.review"))
    return render("preferences.html", batch=get_batch(database(), session.get("batch")),
                  extra_minutes=round(DETOUR_EXTRA_KM / SPEED_KMH * 60))


@yalla.post("/plan/save")
def save_route():
    """Save a stop (the draft's, or the one just ridden) as the student's Home route (this browser only)."""
    stop = request.form.get("stop") or draft()["stop"]
    direction = request.form.get("direction") or draft()["direction"]
    if stop not in STOPS or direction not in ("from_campus", "to_campus"):
        abort(400)
    session["yalla_saved"] = [{"label": "Home", "stop": stop, "direction": direction}]
    flash(f"Saved {stop} as Home")
    return redirect(safe_next() or url_for("yalla.destination"))


@yalla.get("/plan/review")
def review():
    if (blocked := need_verified()):
        return blocked
    d = draft()
    estimate = fare_estimates(student_name())[d["stop"]]
    pickup = estimate["pickups"][d["direction"]]
    if d["direction"] == "from_campus":
        start = add_minutes(d["class_end"], pickup["walk_minutes"])
        end = add_minutes(start, round(STOPS[d["stop"]]["km"] * 2.4))
    else:
        end = add_minutes(d["class_start"], -5)
        start = add_minutes(end, -round(STOPS[d["stop"]]["km"] * 2.4))
    return render("review.html", estimate=estimate, pickup=pickup, start=start, end=end, name=student_name(),
                  preference_name=PREFERENCE_NAMES[d["preference"]])


def release_unmatched(db, batch):
    """Booking again after "no group found" replaces the old request instead of leaving a second one open."""
    old = session.get("yalla_rider")
    if old and batch["matched"]:
        riders, _ = load_riders(db, batch)
        if any(r["id"] == old and r["status"] in ("no_match", "waiting_match") for r in riders):
            respond_to_plan(db, batch, old, "decline", None)


@yalla.post("/plan/book")
def book():
    if (blocked := need_verified()):
        return blocked
    d = draft()
    friends = None
    if d["friends"] == "start":
        friends = {"mode": "start", "open": d["group_open"]}
    elif d["friends"] == "join":
        friends = {"mode": "join", "code": d["group_code"]}
    db = database()
    try:
        name = check_request(student_name(), d["class_end"], d["stop"], d["gender"], d["preference"],
                             d["direction"], d["class_start"])
        with db:
            batch = locked_batch(db, session.get("batch"))
            if not batch:
                raise Problem("not_found", "Your request was not saved. Open the demo again and retry.")
            release_unmatched(db, batch)
            rider_id = insert_request(db, batch, name, d["class_end"], d["stop"], d["gender"], d["preference"],
                                      friends, direction=d["direction"], class_start=d["class_start"])
    except Problem as problem:
        flash(problem.message)
        return redirect(url_for("yalla.review"))
    session["yalla_rider"] = rider_id
    recent = [s for s in session.get("yalla_recent", []) if s != d["stop"]]
    session["yalla_recent"] = [d["stop"]] + recent[:2]
    return redirect(url_for("yalla.ride"))


# ---------- 09-16 · matching, group, fare, confirmed ride ----------

def batch_date():
    batch = get_batch(database(), session.get("batch"))
    if not batch:
        return "Tomorrow"
    day = datetime.fromisoformat(batch["trip_date"]).date()
    days = (day - clock(batch).date()).days
    return {0: "Today", 1: "Tomorrow"}.get(days, day.strftime("%a, %d %b"))


def ride_context(batch, rider):
    plan = rider["plan"] or {}
    members = plan.get("members") or [rider]
    me_first = [rider] + [m for m in members if m["id"] != rider["id"]]
    saving = round((rider["solo"] - rider["share"]) * 100 / rider["solo"]) if rider.get("share") and rider["solo"] else 0
    pickup = rider.get("pickup_at") or plan.get("pickup")
    drop = (plan.get("drop_times") or {}).get(rider["id"])
    walk_min = walk_minutes((plan.get("walk_m") or {}).get(rider["id"], rider.get("walk_m") or 0))
    now = clock(batch)
    arrive_in = minutes_between(now.strftime("%H:%M"), pickup) if pickup and now.date().isoformat() == batch["trip_date"][:10] else None
    return {"plan": plan, "members": members, "me_first": me_first, "saving": saving,
            "street": pickup_street(rider), "walk_min": walk_min,
            "ready": add_minutes(rider["class_end"] or "16:00", walk_min),
            "arrive_in": arrive_in if arrive_in and arrive_in > 0 else None,
            "pickup": pickup, "drop": drop, "car": car_details(plan) if plan else None,
            "ride_minutes": minutes_between(pickup, drop) if pickup and drop else None,
            "now": clock(batch), "batch_date": batch_date(), "quiet": draft()["quiet"]}


@yalla.get("/ride")
def ride():
    batch, rider = current_rider()
    if not rider:
        flash("Plan a shared ride first.")
        return redirect(url_for("yalla.home"))
    status = rider["status"]
    context = ride_context(batch, rider)
    if not batch["matched"]:
        return render("matching.html", rider=rider, batch=batch,
                      preference_name=PREFERENCE_NAMES.get(rider["preference"], "Anyone"), **context)
    plan = rider["plan"] or {}
    if plan.get("go"):
        return go_ride(batch, rider, context)
    quote = session.get("yalla_quote") or {}
    if status == "review" and quote.get("rider") == rider["id"] and quote["signature"] != rider["signature"]:
        return render("offer_changed.html", rider=rider, previous=quote["share"], **context)  # 30
    if plan.get("shared") and status in ("review",):
        session["yalla_quote"] = {"rider": rider["id"], "signature": rider["signature"], "share": rider["share"]}
        return render("group.html", rider=rider, **context)
    if status in ("confirmed", "solo_confirmed") and session.get("yalla_updated") and not request.args.get("seen"):
        return render("offer_accepted.html", rider=rider, **context)  # 31
    if request.args.get("seen"):
        session.pop("yalla_updated", None)
        return redirect(url_for("yalla.ride"))
    if plan.get("shared") and status == "confirmed":
        step = request.args.get("step", "confirmed")
        if step not in ("confirmed", "pickup", "code", "trip", "receipt"):
            abort(404)
        return render(f"ride_{step}.html", rider=rider, **context)
    if status == "declined":
        return render("cancelled.html", rider=rider, **context)
    if status in ("no_match", "waiting_match"):
        return render("no_match.html", rider=rider, **context)
    if status == "changed":
        return render("offer_changed.html", rider=rider, previous=quote.get("share"), **context)
    if status == "solo_confirmed":
        return render("ride_confirmed.html", rider=rider, **context)
    return redirect(url_for("yalla.home"))


@yalla.get("/ride/fare")
def fare():
    batch, rider = current_rider()
    if not rider or not batch["matched"] or not (rider["plan"] or {}).get("shared"):
        return redirect(url_for("yalla.ride"))
    return render("fare.html", rider=rider, **ride_context(batch, rider))


@yalla.post("/ride/match")
def match_now():
    """Demo control: run the batch's matching now (the operator does this on the Matching view)."""
    db = database()
    try:
        with db:
            batch = locked_batch(db, session.get("batch"))
            if batch and not batch["matched"]:
                run_matching(db, batch)
    except Problem as problem:
        flash(problem.message)
    return redirect(url_for("yalla.ride"))


@yalla.post("/ride/<action>")
def respond(action):
    if action not in ("confirm", "decline"):
        abort(404)
    rider_id = session.get("yalla_rider")
    db = database()
    try:
        with db:
            batch = locked_batch(db, session.get("batch"))
            if not batch or not batch["matched"] or not rider_id:
                return redirect(url_for("yalla.home"))
            respond_to_plan(db, batch, rider_id, action, request.form.get("plan"))
        if action == "confirm" and request.form.get("updated"):
            session["yalla_updated"] = True
        session.pop("yalla_quote", None)
    except Problem as problem:
        flash("This plan changed before you confirmed. Review the updated plan." if problem.code == "plan_changed"
              else problem.message)
    return redirect(url_for("yalla.ride"))


@yalla.post("/ride/rate")
def rate():
    stars = request.form.get("stars", type=int)
    if stars and 1 <= stars <= 5:
        session["yalla_rating"] = stars
        flash("Thanks for rating your shared ride")
    return redirect(url_for("yalla.ride", step="receipt"))


# ---------- 17-25, 38-39 · leave now and share (lone-rider choice C) ----------

@yalla.get("/now")
def leave_now():
    if (blocked := need_verified()):
        return blocked
    d = draft()
    return render("now.html", estimate=fare_estimates(student_name())[d["stop"]],
                  preference_name=PREFERENCE_NAMES[d["preference"]])


@yalla.post("/now")
def leave_now_book():
    """Book a request for right now and, if no car can take it, leave at once open to share (choice C)."""
    if (blocked := need_verified()):
        return blocked
    d = draft()
    db = database()
    try:
        with db:
            batch = locked_batch(db, session.get("batch"))
            if not batch:
                raise Problem("not_found", "Your request was not saved. Open the demo again and retry.")
            if not batch["matched"]:  # Demo: today's planned requests are matched first, as the operator would
                run_matching(db, batch)
                batch = get_batch(db, batch["id"])
            riders, _ = load_riders(db, batch)
            old = next((r for r in riders if r["id"] == session.get("yalla_rider")), None)
            if old and old["status"] in ("no_match", "waiting_match") and old["stop"] == d["stop"]:
                choose(db, batch, old["id"], "go")  # 29 → Leave now & share keeps the same request
                rider_id = old["id"]
            else:
                rider_id = book_now(db, batch, d)
    except Problem as problem:
        flash(problem.message)
        return redirect(url_for("yalla.leave_now"))
    session["yalla_rider"] = rider_id
    session["yalla_seen"] = [rider_id]
    session["yalla_started"] = False
    return redirect(url_for("yalla.ride"))


def book_now(db, batch, d):
    """Insert a request for right now; if no car can take it, the student leaves at once open to share."""
    release_unmatched(db, batch)
    ready = min(max(clock(batch).strftime("%H:%M"), "08:00"), "21:00")
    start = min(max(add_minutes(ready, 5), "07:00"), "23:00")
    name = check_request(student_name(), ready, d["stop"], d["gender"], d["preference"], d["direction"], start)
    rider_id = insert_request(db, batch, name, ready, d["stop"], d["gender"], d["preference"],
                              direction=d["direction"], class_start=start)
    riders, _ = load_riders(db, batch)
    rider = next(r for r in riders if r["id"] == rider_id)
    if rider["status"] == "no_match":
        choose(db, batch, rider_id, "go")
    return rider_id


def leg_split(plan, rider):
    """Legs of a go-now route between pickups and drop-offs, with who is aboard each leg."""
    members = plan["members"]
    to_campus = plan["direction"] == "to_campus"
    origin = max((m["start_km"] or 0.0) for m in members) if to_campus else 0.0
    def on(m):
        board = m["board_km"] if m["board_km"] is not None else (m["start_km"] if to_campus else 0.0)
        return round(origin - board if to_campus else board, 2)
    def off(m):
        return round(origin if to_campus else m["km"], 2)
    points = sorted({round(on(m), 2) for m in members} | {round(off(m), 2) for m in members})
    def place(km):
        for m in members:
            if round(on(m), 2) == km:
                return plan["boards"][m["id"]] if km else ("Campus street" if not to_campus else plan["boards"][m["id"]])
            if round(off(m), 2) == km:
                return "Campus" if to_campus else m["stop"]
        return f"{km:.1f} km"
    legs = []
    for start, end in zip(points, points[1:]):
        aboard = [m for m in members if on(m) <= start + 1e-6 and off(m) >= end - 1e-6]
        if aboard:
            legs.append({"from": place(start), "to": place(end), "km": round(end - start, 1),
                         "aboard": ["You" if m["id"] == rider["id"] else m["name"]
                                    for m in sorted(aboard, key=lambda m: m["id"] != rider["id"])]})
    return legs


def go_ride(batch, rider, context):
    plan = context["plan"]
    seen = session.get("yalla_seen", [rider["id"]])
    joined = [m for m in plan["members"] if m["id"] not in seen]
    others = [m for m in plan["members"] if m["id"] != rider["id"]]
    gate = CORRIDORS[plan["corridor"]]["gate"]
    plan = {**plan, "boards": {rid: (pickup_street(rider) if board == gate else board) for rid, board in plan["boards"].items()}}
    context["plan"] = plan
    context.update(others=others, cap=rider["solo"], street=plan["boards"][rider["id"]],
                   saving=round((rider["solo"] - rider["share"]) * 100 / rider["solo"]) if rider["solo"] else 0)
    if rider["status"] == "arrived":
        return render("now_receipt.html", rider=rider, **context)
    if joined:
        return render("now_joined.html", rider=rider, joined=joined, **context)
    if request.args.get("step") == "legs":
        return render("now_legs.html", rider=rider, legs=leg_split(plan, rider), **context)
    if not session.get("yalla_started") or request.args.get("step") == "pickup":
        return render("now_pickup.html", rider=rider, **context)
    return render("now_ride.html", rider=rider, **context)


@yalla.get("/ride/started")
def ride_started():
    session["yalla_started"] = True
    return redirect(url_for("yalla.ride"))


@yalla.post("/ride/seen")
def joined_seen():
    batch, rider = current_rider()
    if rider and rider["plan"]:
        session["yalla_seen"] = [m["id"] for m in rider["plan"]["members"]]
    return redirect(url_for("yalla.ride"))


@yalla.post("/ride/keep")
def keep_route():
    """Turn down students who asked to join on the way; the car keeps its current route and fare cap."""
    batch, rider = current_rider()
    if rider and (rider["plan"] or {}).get("go"):
        seen = session.get("yalla_seen", [rider["id"]])
        new = [m["id"] for m in rider["plan"]["members"] if m["id"] not in seen]
        db = database()
        with db:
            db.executemany("UPDATE riders SET declined = 1, ride_code = NULL, confirmed_plan = NULL WHERE id = ? AND batch = ?",
                           [(rid, batch["id"]) for rid in new])
    return redirect(url_for("yalla.ride"))


@yalla.post("/ride/demo-joiner")
def demo_joiner():
    """Demo control: a made-up student on the same corridor requests a ride while the car is on its way."""
    rider_id = session.get("yalla_rider")
    db = database()
    try:
        with db:
            batch = locked_batch(db, session.get("batch"))
            riders, _ = load_riders(db, batch) if batch else ([], [])
            rider = next((r for r in riders if r["id"] == rider_id), None)
            if not rider or not (rider["plan"] or {}).get("go") or rider["status"] != "on_the_way":
                raise Problem("not_on_the_way", "Students can join only while your car is on its way.")
            taken = {r["name"] for r in riders}
            name = next((n for n in DEMO_JOINERS if n not in taken), None)
            if not name or len(rider["plan"]["members"]) >= RULES["seats"]:
                raise Problem("car_full", "Your car is full.")
            corridor = CORRIDORS[rider["corridor"]]["stops"]
            used = {m["stop"] for m in rider["plan"]["members"]}
            stop = min(corridor, key=lambda s: (s in used, abs(corridor[s] - corridor[rider["stop"]])))
            preference = "women" if rider["plan"].get("only") == "women" else "men" if rider["plan"].get("only") == "men" else "mixed"
            joiner_id = insert_request(db, batch, name, rider["class_end"] or "16:00", stop, rider["gender"], preference,
                                       direction=rider["direction"], class_start=rider["class_start"] or "09:00")
            riders, _ = load_riders(db, batch)
            joiner = next(r for r in riders if r["id"] == joiner_id)
            if joiner["car"] != rider["car"]:
                respond_to_plan(db, batch, joiner_id, "decline", None)
                raise Problem("passed", f"{name} asked to join, but your car has already passed their street.")
    except Problem as problem:
        flash(problem.message)
    return redirect(url_for("yalla.ride"))


@yalla.post("/ride/finish")
def finish_ride():
    """Demo control: move the batch clock to the end of this go-now ride."""
    batch, rider = current_rider()
    if rider and (rider["plan"] or {}).get("go") and rider["status"] == "on_the_way":
        plan = rider["plan"]
        departed = datetime.fromisoformat(database().execute(
            "SELECT departed_at FROM cars WHERE batch = ? AND car = ?", (batch["id"], plan["id"])).fetchone()[0])
        left = plan["route_km"] * 60 / SPEED_KMH - (clock(batch) - departed).total_seconds() / 60
        db = database()
        with db:
            advance_clock(db, batch["id"], max(1, int(left) + 1))
    return redirect(url_for("yalla.ride"))


# ---------- demo: open any designed screen directly ----------

DEMO_SCREENS = {
    "01": ("home", {}), "02": ("verify", {}), "03": ("verify_code", {}), "04": ("choose_university", {}),
    "05": ("destination", {}), "06": ("pickup_time", {}), "07": ("preferences", {}), "08": ("review", {}),
    "09": ("ride", {}), "10": ("ride", {}), "11": ("fare", {}), "12": ("ride", {}),
    "13": ("ride", {"step": "pickup"}), "14": ("ride", {"step": "code"}), "15": ("ride", {"step": "trip"}),
    "16": ("ride", {"step": "receipt"}), "17": ("leave_now", {}),
    "18": ("ride", {}), "19": ("ride", {}), "20": ("ride", {}), "21": ("ride", {}), "22": ("ride", {}),
    "23": ("ride", {}), "24": ("ride", {}), "25": ("ride", {"step": "legs"}), "38": ("ride", {}), "39": ("ride", {}), "34": ("help_page", {}),
    "26": ("trips", {}), "27": ("trips", {"tab": "past"}), "28": ("saved", {}), "29": ("ride", {}), "30": ("ride", {}),
    "31": ("ride", {}), "32": ("cancel", {}), "33": ("ride", {}), "35": ("ride", {"offline": 1}),
    "37": ("email_recovery", {}), "36": ("not_available", {"university": "hillcrest"}),
}


@yalla.get("/demo/<screen>")
def demo(screen):
    """Open a designed screen with a seeded booking. Screens after booking start a fresh sample batch for this browser."""
    if screen not in DEMO_SCREENS:
        abort(404)
    endpoint, args = DEMO_SCREENS[screen]
    session["student_verified"] = True
    session["yalla_name"] = "Sara A"
    session["yalla"] = {**DEFAULT_DRAFT, "quiet": True}
    session["yalla_recent"] = ["Sweileh"]
    session.pop("yalla_saved", None)
    if screen == "03":
        session["yalla_email"] = "s***@cedar.edu"
        session["yalla_code"] = f"{secrets.randbelow(900000) + 100000}"
        session["yalla_code_until"] = (datetime.now() + CODE_LIFETIME).isoformat()
    if screen >= "09" and screen <= "16":
        db = database()
        with db:
            batch_id = create_batch(db, True, replaces=session.get("own_batch", session.get("batch")))
        session["batch"] = session["own_batch"] = batch_id
        session["csrf"] = session.get("csrf") or secrets.token_urlsafe(32)
        d = draft()
        with db:
            batch = locked_batch(db, batch_id)
            rider_id = insert_request(db, batch, student_name(), d["class_end"], d["stop"], d["gender"], d["preference"],
                                      direction=d["direction"], class_start=d["class_start"])
            if screen >= "10":
                run_matching(db, batch)
                batch = get_batch(db, batch_id)
            if screen >= "12":
                rider = next(r for r in load_riders(db, batch)[0] if r["id"] == rider_id)
                respond_to_plan(db, batch, rider_id, "confirm", rider["signature"])
        session["yalla_rider"] = rider_id
    session.pop("yalla_quote", None)
    session.pop("yalla_updated", None)
    session.pop("yalla_history", None)
    if screen == "37":
        session["yalla_bad_email"] = "sara.a@example.com"
    if screen == "28":
        session["yalla_saved"] = [{"label": "Home", "stop": "Dabouq", "direction": "from_campus", "time": "16:10", "quiet": True},
                                  {"label": "Now", "stop": "Sweileh", "direction": "from_campus", "mode": "now"}]
    if screen == "27":
        session["yalla_history"] = [
            {"when": "Today · 4:15 PM", "route": "Campus street → Dabouq", "kind": "Planned shared ride · 3 students", "paid": 1670},
            {"when": "Today · 4:05 PM", "route": "Campus street → Sweileh", "kind": "Shared along the way · 3 students", "paid": 2750}]
    if screen in ("26", "29", "30", "31", "32", "33", "35"):
        seed_planned(screen)
    if screen in GO_STEPS:
        db = database()
        with db:
            batch_id = create_batch(db, True, replaces=session.get("own_batch", session.get("batch")))
        session["batch"] = session["own_batch"] = batch_id
        session["csrf"] = session.get("csrf") or secrets.token_urlsafe(32)
        session["yalla"] = {**draft(), "stop": "Al Bayader"}
        for step in GO_STEPS[screen]:  # The same handlers the buttons use
            {"book": leave_now_book, "start": ride_started, "join": demo_joiner,
             "seen": joined_seen, "finish": finish_ride}[step]()
        session.pop("_flashes", None)
    return redirect(url_for(f"yalla.{endpoint}", **args))


def seed_planned(screen):
    """26, 29-33, 35: a planned request in a fresh sample batch, moved to the state the screen shows."""
    db = database()
    with db:
        batch_id = create_batch(db, True, replaces=session.get("own_batch", session.get("batch")))
    session["batch"] = session["own_batch"] = batch_id
    session["csrf"] = session.get("csrf") or secrets.token_urlsafe(32)
    if screen == "29":  # Nobody else rides toward Marka at this time, so no group fits
        session["yalla"] = {**draft(), "stop": "Marka", "class_end": "20:30", "preference": "women"}
    d = draft()
    with db:
        batch = locked_batch(db, batch_id)
        rider_id = insert_request(db, batch, student_name(), d["class_end"], d["stop"], d["gender"], d["preference"],
                                  direction=d["direction"], class_start=d["class_start"])
        if screen in ("30", "31"):  # A third student, so two are left after one leaves
            insert_request(db, batch, "Rama K", add_minutes(d["class_end"], 10), "Al Bayader", "woman", "mixed", direction=d["direction"],
                           class_start=d["class_start"])
        run_matching(db, batch)
        batch = get_batch(db, batch_id)
        rider = next(r for r in load_riders(db, batch)[0] if r["id"] == rider_id)
        if screen in ("30", "31"):  # Sara saw a group offer, then one of the others left before she confirmed
            session["yalla_quote"] = {"rider": rider_id, "signature": rider["signature"], "share": rider["share"]}
            other = next(m for m in rider["plan"]["members"] if m["id"] != rider_id and m["name"] != "Rama K")
            respond_to_plan(db, batch, other["id"], "decline", None)
            if screen == "31":
                rider = next(r for r in load_riders(db, batch)[0] if r["id"] == rider_id)
                respond_to_plan(db, batch, rider_id, "confirm", rider["signature"])
                session["yalla_updated"] = True
        elif screen in ("26", "32", "33", "35"):
            respond_to_plan(db, batch, rider_id, "confirm", rider["signature"])
            if screen == "33":
                respond_to_plan(db, batch, rider_id, "decline", None)
    session["yalla_rider"] = rider_id


# Leave now & share states (17-25, 38-39), reached by replaying the demo buttons in order.
_SHARED_THREE = ["book", "start", "join", "seen", "join", "seen"]
GO_STEPS = {
    "18": ["book"], "19": ["book", "start"], "20": ["book", "start", "join"],
    "21": ["book", "start", "join", "seen", "join"], "22": _SHARED_THREE, "23": _SHARED_THREE + ["finish"],
    "24": ["book", "start", "finish"], "25": _SHARED_THREE, "38": ["book", "start", "join", "seen"],
    "39": ["book", "start", "join", "seen", "finish"],
}


# ---------- 26-33 · trips, saved routes, no group, changed offer, cancel ----------

def trip_card(batch, rider):
    """One line in My campus trips for a booked request."""
    plan = rider["plan"] or {}
    street = (plan.get("boards") or {}).get(rider["id"]) or pickup_street(rider)
    if street == (CORRIDORS.get(plan.get("corridor") or "") or {}).get("gate"):
        street = pickup_street(rider)
    route = f"{street} → {rider['stop']}" if rider["direction"] == "from_campus" else f"{rider['stop']} → {university()['campus']}"
    count = len(plan.get("members") or [rider])
    quiet = " · Quiet ride" if draft()["quiet"] else ""
    group = {"women": "women students", "men": "men students"}.get(plan.get("only"), "students")
    if plan.get("go"):
        kind = f"Shared along the way · {count} students" if count > 1 else "Leave now & share · Private ride"
    else:
        kind = f"{count} {group}{quiet}"
    when = rider.get("pickup_at") or plan.get("pickup") or rider["class_end"]
    labels = {"confirmed": ("Confirmed", ""), "solo_confirmed": ("Confirmed", ""), "on_the_way": ("On the way", "pink"),
              "review": ("Review offer", "pink"), "changed": ("Offer changed", "pink"), "waiting": ("Finding group", "muted"),
              "waiting_match": ("Finding group", "muted"), "no_match": ("No group yet", "muted"), "arrived": ("Completed", "")}
    label, tone = labels.get(rider["status"], (rider["status"].replace("_", " ").capitalize(), "muted"))
    return {"when": f"{batch_date()} · {ampm(when)}", "route": route, "kind": kind, "paid": rider.get("share"),
            "label": label, "tone": tone, "status": rider["status"]}


@yalla.get("/trips")
def trips():
    batch, rider = current_rider()
    card = trip_card(batch, rider) if rider and rider["status"] != "declined" else None
    upcoming = card if card and card["status"] != "arrived" and not session.get("yalla_done") else None
    history = list(session.get("yalla_history", []))
    if card and (card["status"] == "arrived" or session.get("yalla_done")) and card["route"] not in [h["route"] for h in history]:
        history.insert(0, {**card, "kind": card["kind"].replace(" · Quiet ride", "") if card["kind"].startswith("Shared") else
                           "Planned shared ride · " + card["kind"].split(" ")[0] + " students"})
    return render("trips.html", tab=request.args.get("tab"), upcoming=upcoming, history=history)


@yalla.get("/saved")
def saved():
    routes = []
    for route in session.get("yalla_saved", []):
        line = (f"{university()['campus']} · Campus street → {route['stop']}" if route["direction"] == "from_campus"
                else f"{route['stop']} street → {university()['campus']}")
        if route.get("mode") == "now":
            routes.append({"title": f"{route['stop']}, when I’m ready", "line": line,
                           "detail": "Leave now and share if someone matches", "action": "Check today’s fare"})
        else:
            routes.append({"title": "Home after class" if route["direction"] == "from_campus" else "To campus",
                           "line": line, "detail": f"Ready at {ampm(route.get('time') or draft()['class_end'])}"
                           + (" · Quiet ride" if route.get("quiet") else ""), "action": "Use this route"})
    return render("saved.html", routes=routes)


@yalla.post("/saved/use")
def use_saved():
    routes = session.get("yalla_saved", [])
    index = request.form.get("index", type=int)
    if index is None or not 0 <= index < len(routes):
        abort(400)
    route = routes[index]
    save_draft(stop=route["stop"], direction=route["direction"], quiet=bool(route.get("quiet")),
               **({"class_end": route["time"]} if route.get("time") else {}))
    return redirect(url_for("yalla.leave_now") if route.get("mode") == "now" else url_for("yalla.review"))


@yalla.get("/ride/cancel")
def cancel():
    batch, rider = current_rider()
    if not rider or rider["status"] in ("declined", "on_the_way", "arrived"):
        return redirect(url_for("yalla.ride"))
    return render("cancel.html", rider=rider, **ride_context(batch, rider))


# ---------- 34 · help ----------

@yalla.get("/help")
def help_page():
    return render("help.html")
