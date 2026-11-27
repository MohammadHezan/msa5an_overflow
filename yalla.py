"""Yalla Ride student screens (Brief 04: docs/design/campus-connect-screens).

Full-screen steps that sit on top of the same booking, matching, confirm/decline and ride-code
actions as the Jeeny ride list. The draft request lives in the browser session until it is booked.
Verification is a demo check only: no email is sent and the code is shown on screen.
"""
import re
import secrets
from datetime import datetime, timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

from pooling.config import DETOUR_EXTRA_KM, SPEED_KMH
from sharing import CORRIDORS, STOPS
from store import (
    RULES, Problem, check_request, clock, create_batch, database, fare_estimates, get_batch, insert_request,
    load_riders, locked_batch, refresh, respond_to_plan, run_matching,
)

yalla = Blueprint("yalla", __name__, url_prefix="/yalla")

UNIVERSITIES = [
    {"id": "cedar", "name": "Cedar University", "campus": "Cedar Campus", "detail": "Cedar Campus · Street pickup", "open": True},
    {"id": "hillcrest", "name": "Hillcrest University", "campus": "Hillcrest", "detail": "Hill City · Campus service updates", "open": False},
    {"id": "northfield", "name": "Northfield University", "campus": "Northfield", "detail": "North City · Campus service updates", "open": False},
]
CODE_LIFETIME = timedelta(minutes=5)
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
    return {**DEFAULT_DRAFT, **session.get("yalla", {})}


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


def render(template, **context):
    return render_template(f"yalla/{template}", university=university(), verified=verified(),
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
        session["yalla_email"] = masked(email)  # Only the masked form is kept; nothing is sent
        local = re.split(r"[._+-]", email.split("@")[0])
        session["yalla_name"] = " ".join(part.capitalize() for part in local if part)[:40] or "Student"
        session["yalla_code"] = f"{secrets.randbelow(900000) + 100000}"
        session["yalla_code_until"] = (datetime.now() + CODE_LIFETIME).isoformat()
        flash("Verification code sent")
        return redirect(url_for("yalla.verify_code", next=request.form.get("next")))
    return render("verify.html", email="" if session.get("yalla_email") else "sara.a@cedar.edu", next=safe_next())


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
    if plan.get("shared") and status in ("review",):
        return render("group.html", rider=rider, **context)
    if plan.get("shared") and status == "confirmed":
        step = request.args.get("step", "confirmed")
        if step not in ("confirmed", "pickup", "code", "trip", "receipt"):
            abort(404)
        return render(f"ride_{step}.html", rider=rider, **context)
    # States built in later phases (changed offer, lone-rider choices, go-now) use the Jeeny ride view for now.
    return redirect(url_for("index", rider=rider["id"]))


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


# ---------- demo: open any designed screen directly ----------

DEMO_SCREENS = {
    "01": ("home", {}), "02": ("verify", {}), "03": ("verify_code", {}), "04": ("choose_university", {}),
    "05": ("destination", {}), "06": ("pickup_time", {}), "07": ("preferences", {}), "08": ("review", {}),
    "09": ("ride", {}), "10": ("ride", {}), "11": ("fare", {}), "12": ("ride", {}),
    "13": ("ride", {"step": "pickup"}), "14": ("ride", {"step": "code"}), "15": ("ride", {"step": "trip"}),
    "16": ("ride", {"step": "receipt"}), "34": ("help_page", {}), "36": ("not_available", {"university": "hillcrest"}),
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
    return redirect(url_for(f"yalla.{endpoint}", **args))


# ---------- 34 · help ----------

@yalla.get("/help")
def help_page():
    return render("help.html")
