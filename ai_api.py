"""AI endpoints on the /api/v1 blueprint (all simulated data): demand forecast, match chance, captain plan, model card.

They are added to api.py's blueprint, so they share its error shape (Problem -> JSON) and its web-app CORS headers.
Import this module before app.register_blueprint(api).
"""
import math
from datetime import date

from flask import jsonify, request

from api import api
from pooling import config, forecast
from pooling.match_chance import SAMPLES, corridor_of, match_chance
from pooling.places import CORRIDORS
from store import Problem

AVG_RIDERS_PER_CAR = 2.6  # from simulation v2 at 24-32 students (optimizer); used to turn demand into cars
SIMULATED = {"simulated": True, "note": "Trained and evaluated on synthetic bookings. Not live demand."}


def _day():
    value = request.args.get("date") or forecast.DEFAULT_DATE.isoformat()
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise Problem("invalid_input", "`date` must be YYYY-MM-DD.", 400)


def _choice(name, allowed, default=None):
    value = request.args.get(name, default)
    if value not in allowed:
        raise Problem("invalid_input", f"`{name}` must be one of: {', '.join(allowed)}.", 400)
    return value


def _minutes(name, default):
    raw = request.args.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise Problem("invalid_input", f"`{name}` must be a whole number of minutes.", 400)
    if not 1 <= value <= config.MAX_EXTRA_RIDE_CAP_MIN:
        raise Problem("invalid_input", f"`{name}` must be between 1 and {config.MAX_EXTRA_RIDE_CAP_MIN}.", 400)
    return value


def _money(fils):
    return None if fils is None else {"fils": int(fils), "currency": "JOD"}


@api.get("/ai/forecast")
def ai_forecast():
    """Expected ride requests per 15-minute slot for one corridor and direction (or every corridor)."""
    day = _day()
    direction = _choice("direction", forecast.DIRECTIONS, "from_campus")
    corridors = [request.args["corridor"]] if request.args.get("corridor") else list(forecast.CORRIDOR_NAMES)
    if any(c not in CORRIDORS for c in corridors):
        raise Problem("invalid_input", f"`corridor` must be one of: {', '.join(CORRIDORS)}.", 400)
    slots = [{"slot": forecast.slot_label(s),
              "expectedRequests": round(sum(forecast.forecast(day, c, direction, s) for c in corridors), 2)}
             for s in forecast.SLOTS]
    return jsonify({**SIMULATED, "method": "Poisson regression on 10 weeks of simulated bookings",
                    "date": day.isoformat(), "teachingDay": forecast.is_teaching_day(day), "examDay": forecast.is_exam_day(day),
                    "direction": direction, "corridors": corridors, "slots": slots,
                    "peak": max(slots, key=lambda s: s["expectedRequests"])})


@api.get("/ai/match-chance")
def ai_match_chance():
    """Chance this request gets a shared car, its expected share, and up to two better times."""
    stop = request.args.get("stop", "")
    if not corridor_of(stop):
        raise Problem("invalid_input", "Send a known `stop`.", 400)
    direction = _choice("direction", forecast.DIRECTIONS, "from_campus")
    time = request.args.get("time", "")
    try:
        hour, minute = map(int, time.split(":"))
        ok = len(time) == 5 and forecast.SERVICE_START <= hour * 60 + minute < forecast.SERVICE_END
    except ValueError:
        ok = False
    if not ok:
        raise Problem("invalid_input", "`time` must be HH:MM between 07:00 and 20:59.", 400)
    gender = _choice("gender", ("man", "woman"))
    preference = _choice("preference", ("mixed", "men", "women"), "mixed")
    if (preference == "men" and gender != "man") or (preference == "women" and gender != "woman"):
        raise Problem("invalid_input", "Men only is for men and Women only is for women.", 400)
    result = match_chance(stop, direction, time, gender, preference,
                          _minutes("maxGateWaitMinutes", config.DEFAULT_MAX_GATE_WAIT_MIN),
                          _minutes("maxExtraRideMinutes", config.DEFAULT_MAX_EXTRA_RIDE_MIN), _day().isoformat())
    return jsonify({**SIMULATED, "method": f"{SAMPLES} Monte Carlo draws of forecast demand, each matched by the real pooling rules",
                    "stop": stop, "direction": direction, "time": time, "chance": round(result["chance"], 3),
                    "chancePercent": round(result["chance"] * 100), "expectedShare": _money(result["expected_share_fils"]),
                    "soloFare": _money(result["solo_fare_fils"]), "expectedRequestsNearby": result["expected_requests_nearby"],
                    "suggestions": [{"time": s["time"], "shiftMinutes": s["shiftMinutes"], "chancePercent": round(s["chance"] * 100),
                                     "expectedShare": _money(s["expected_share_fils"])} for s in result["suggestions"]]})


@api.get("/ai/captain-plan")
def ai_captain_plan():
    """Captains to have ready per gate and 15-minute slot: forecast demand turned into cars, plus a buffer at busy times."""
    day = _day()
    rows = []
    for slot in forecast.SLOTS:
        for gate in sorted({info["gate"] for info in CORRIDORS.values()}):
            demand = sum(forecast.forecast(day, c, d, slot) for c, info in CORRIDORS.items() if info["gate"] == gate
                         for d in forecast.DIRECTIONS)
            if demand < 0.5:
                continue
            cars = math.ceil(demand / AVG_RIDERS_PER_CAR) + (1 if demand >= 3 else 0)
            rows.append({"slot": forecast.slot_label(slot), "gate": gate, "expectedRequests": round(demand, 2), "captains": cars})
    return jsonify({**SIMULATED, "method": f"ceil(forecast / {AVG_RIDERS_PER_CAR} riders per car) + 1 when 3 or more requests",
                    "date": day.isoformat(), "rows": rows, "peakCaptains": max((r["captains"] for r in rows), default=0)})


@api.get("/ai/model-card")
def ai_model_card():
    result = forecast.backtest()
    return jsonify({**SIMULATED, "model": "Poisson regression (numpy IRLS, L2), features: " + ", ".join(forecast.feature_names()),
                    "training": f"{result['train_weeks']} weeks of synthetic bookings, tested on the next {result['test_weeks']} weeks",
                    "backtest": {"model": result["model"], "seasonalNaive": result["baseline"], "trueRate": result["oracle"]},
                    "matchChance": f"{SAMPLES} Monte Carlo draws per answer; greedy best car of up to 4 using the real rules",
                    "limitations": ["Demand is simulated from an assumed class timetable, not real Jeeny data.",
                                    "Match chance assumes other students book like the simulation; real behaviour will differ.",
                                    "Captain counts use an average car size from simulation."]})
