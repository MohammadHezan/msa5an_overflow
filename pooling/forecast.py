"""Demand forecast for the ride-pooling demo. SIMULATED data only: no real bookings exist yet.

`synthetic_history` makes 12 weeks of booking counts from a class-timetable pattern, `fit` trains
a Poisson regression on them with numpy only (penalized IRLS), `predict` gives expected requests,
and `backtest` compares the model with a seasonal-naive baseline on the last 2 weeks.

A "slot" is the 15-minute window that holds the rider's gate time: when the student is ready at
the gate (from_campus, class end plus the walk) or must be at the gate (to_campus, class start
minus 5 minutes). Slots are named by their start minute of the day (07:00 = 420).
"""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from functools import lru_cache
import numpy as np

from pooling.places import CORRIDORS

SLOT_MIN = 15
SERVICE_START = 7 * 60  # first slot 07:00
SERVICE_END = 21 * 60   # last slot starts 20:45
SLOTS = tuple(range(SERVICE_START, SERVICE_END, SLOT_MIN))  # 56 slots
DIRECTIONS = ("from_campus", "to_campus")
CORRIDOR_NAMES = tuple(CORRIDORS)  # West, North, South, East

# ---- The simulated world (every number below is an assumption, not data) ----
HISTORY_START = date(2026, 9, 6)  # a Sunday: week 1 of the simulated fall semester
HISTORY_WEEKS = 12                # ends Saturday 2026-11-28
HISTORY_SEED = 7
TEACHING_WEEKDAYS = (6, 0, 1, 2, 3)  # date.weekday(): Sunday-Thursday; Friday and Saturday are the weekend
WEEKDAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
CORRIDOR_WEIGHT = {"West": 1.0, "North": 0.7, "South": 0.8, "East": 0.45}  # share of students living there
WEEKDAY_FACTOR = {6: 1.10, 0: 1.00, 1: 1.05, 2: 0.95, 3: 0.85}
# Thursday afternoon: students leave early for the weekend. The model has no feature for this,
# so it is a deliberate misspecification the backtest has to live with.
THURSDAY_EARLY = 1.20   # from_campus 12:00-13:59 on Thursday
THURSDAY_LATE = 0.80    # from_campus from 14:00 on Thursday
EXAM_PERIODS = (       # first exams, second exams, finals (inclusive, Sunday-Thursday)
    (date(2026, 10, 11), date(2026, 10, 15)),
    (date(2026, 11, 15), date(2026, 11, 19)),
    (date(2027, 1, 3), date(2027, 1, 14)),
)
EXAM_FACTOR = 1.30      # students come in for exams and stay to study
GATE_DELAY_MIN = 6.0    # mean minutes between class end and reaching the gate (exponential)
ARRIVE_LEAD_MIN = 5.0   # to_campus riders want to be at the gate 5 minutes before class ...
EARLY_MEAN_MIN = 6.0    # ... plus an exponential safety margin with this mean
# Relative size of each class end / start wave; DEMAND_SCALE turns them into expected app bookings
# per corridor-weight unit on an average teaching day (about 520 bookings a teaching day campus-wide).
DEMAND_SCALE = 4.0
CLASS_ENDS = {"10:00": 1.2, "11:00": 1.0, "12:00": 3.0, "13:00": 1.4, "14:00": 3.4, "15:00": 1.4,
              "16:00": 3.0, "17:00": 1.0, "18:00": 2.0, "19:00": 0.6, "20:00": 0.4}
CLASS_STARTS = {"08:00": 4.0, "09:00": 2.6, "10:00": 2.0, "11:00": 1.2, "12:00": 0.8, "13:00": 0.8,
                "14:00": 0.7, "15:00": 0.4, "16:00": 0.4, "17:00": 0.5, "18:00": 0.3}
BASE_RATE = {"from_campus": 0.12, "to_campus": 0.08}  # relative bookings per slot outside the peaks

# ---- Model and backtest settings ----
L2_ALPHA = 1.0
TEST_WEEKS = 2
DEFAULT_DATE = HISTORY_START + timedelta(weeks=HISTORY_WEEKS)  # Sunday 2026-11-29, the day after the history


def _minutes(clock: str) -> int:
    hour, minute = map(int, clock.split(":"))
    return hour * 60 + minute


def slot_start(value) -> int:
    """The start minute of the 15-minute slot holding `value` ("HH:MM", datetime.time, datetime or minutes)."""
    if isinstance(value, datetime):
        value = value.hour * 60 + value.minute
    elif isinstance(value, time):
        value = value.hour * 60 + value.minute
    elif isinstance(value, str):
        value = _minutes(value)
    return int(value) // SLOT_MIN * SLOT_MIN


def slot_label(minute: int) -> str:
    return f"{minute // 60:02d}:{minute % 60:02d}"


def as_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def is_teaching_day(day) -> bool:
    return as_date(day).weekday() in TEACHING_WEEKDAYS


def is_exam_day(day) -> bool:
    day = as_date(day)
    return any(start <= day <= end for start, end in EXAM_PERIODS)


def _exp_cdf(x, mean):
    return np.where(x > 0, 1 - np.exp(-np.maximum(x, 0) / mean), 0.0)


def daily_profile(direction: str) -> np.ndarray:
    """Expected bookings per slot (corridor weight 1, weekday factor 1, no exams): the timetable shape.

    from_campus: each class end sends its riders to the gate after an exponential delay
    (mean GATE_DELAY_MIN), so a 12:00 class end lands mostly in the 12:00 slot.
    to_campus: riders want to be at the gate ARRIVE_LEAD_MIN before class plus an exponential
    margin, so an 08:00 start lands mostly in the 07:45 slot.
    """
    lo = np.array(SLOTS, dtype=float)
    hi = lo + SLOT_MIN
    rate = np.full(len(SLOTS), BASE_RATE[direction] * DEMAND_SCALE)
    if direction == "from_campus":
        for clock, amount in CLASS_ENDS.items():
            end = _minutes(clock)
            rate += amount * DEMAND_SCALE * (_exp_cdf(hi - end, GATE_DELAY_MIN) - _exp_cdf(lo - end, GATE_DELAY_MIN))
    else:
        for clock, amount in CLASS_STARTS.items():
            latest = _minutes(clock) - ARRIVE_LEAD_MIN  # gate time = latest - margin
            rate += amount * DEMAND_SCALE * (_exp_cdf(latest - lo, EARLY_MEAN_MIN) - _exp_cdf(latest - hi, EARLY_MEAN_MIN))
    return rate


@dataclass(frozen=True, eq=False)
class History:
    """One row per (date, corridor, direction, slot). Column arrays share one index."""
    day: np.ndarray        # datetime64[D]
    week: np.ndarray       # 0-based week of the history
    weekday: np.ndarray    # date.weekday(): Monday 0 ... Sunday 6
    corridor: np.ndarray   # index into CORRIDOR_NAMES
    direction: np.ndarray  # index into DIRECTIONS
    slot: np.ndarray       # index into SLOTS
    exam: np.ndarray       # bool: exam period
    count: np.ndarray      # simulated bookings
    rate: np.ndarray       # the true Poisson mean that generated `count` (for diagnostics only)

    def __len__(self):
        return len(self.count)

    def subset(self, mask: np.ndarray) -> "History":
        return History(**{name: getattr(self, name)[mask] for name in self.__dataclass_fields__})


def synthetic_history(weeks: int = HISTORY_WEEKS, seed: int = HISTORY_SEED) -> History:
    """SIMULATED booking counts per (date, corridor, direction, 15-minute slot) for the demo campus.

    Generator (all assumptions, chosen to look like a Jordanian campus timetable):
    - dates: `weeks` full weeks from Sunday HISTORY_START; slots 07:00-20:45;
    - teaching days are Sunday-Thursday; Friday and Saturday have no demand at all;
    - mean = daily_profile(direction)[slot] x CORRIDOR_WEIGHT[corridor] x WEEKDAY_FACTOR[weekday]
      x EXAM_FACTOR (in EXAM_PERIODS) x the Thursday early-exodus factors (from_campus only);
    - from_campus peaks right after the big class ends (12:00, 14:00, 16:00, 18:00); to_campus
      peaks in the slot before the 08:00-10:00 starts (07:45, 08:45, 09:45);
    - count ~ Poisson(mean), drawn with numpy's default_rng(seed): the same seed gives the same history.
    """
    rng = np.random.default_rng(seed)
    n_days = weeks * 7
    days = np.datetime64(HISTORY_START.isoformat(), "D") + np.arange(n_days)
    grid = np.meshgrid(np.arange(n_days), np.arange(len(CORRIDOR_NAMES)), np.arange(len(DIRECTIONS)),
                       np.arange(len(SLOTS)), indexing="ij")
    d_idx, c_idx, dir_idx, s_idx = (axis.ravel() for axis in grid)
    calendar = [HISTORY_START + timedelta(days=i) for i in range(n_days)]
    weekday_of = np.array([d.weekday() for d in calendar])
    exam_of = np.array([is_exam_day(d) for d in calendar])
    weekday = weekday_of[d_idx]
    profiles = np.stack([daily_profile(d) for d in DIRECTIONS])
    weights = np.array([CORRIDOR_WEIGHT[c] for c in CORRIDOR_NAMES])
    day_factor = np.array([WEEKDAY_FACTOR.get(w, 0.0) for w in range(7)])
    rate = profiles[dir_idx, s_idx] * weights[c_idx] * day_factor[weekday] * np.where(exam_of[d_idx], EXAM_FACTOR, 1.0)
    slot_minute = np.array(SLOTS)[s_idx]
    thursday_out = (weekday == 3) & (dir_idx == 0)
    rate = rate * np.where(thursday_out & (slot_minute >= 12 * 60) & (slot_minute < 14 * 60), THURSDAY_EARLY, 1.0)
    rate = rate * np.where(thursday_out & (slot_minute >= 14 * 60), THURSDAY_LATE, 1.0)
    count = rng.poisson(rate)
    return History(day=days[d_idx], week=d_idx // 7, weekday=weekday, corridor=c_idx, direction=dir_idx,
                   slot=s_idx, exam=exam_of[d_idx], count=count, rate=rate)


# ---- Poisson regression (numpy only) ----

def feature_names() -> tuple[str, ...]:
    names = ["intercept"]
    names += [f"corridor={c}" for c in CORRIDOR_NAMES[1:]]
    names += [f"weekday={WEEKDAY_NAMES[w]}" for w in TEACHING_WEEKDAYS[1:]]
    names += ["exam_week", "direction=to_campus"]
    names += [f"slot={slot_label(s)}" for s in SLOTS[1:]]
    names += [f"to_campus x slot={slot_label(s)}" for s in SLOTS[1:]]
    return tuple(names)


_WEEKDAY_COLUMN = {w: i for i, w in enumerate(TEACHING_WEEKDAYS[1:])}  # Sunday is the reference


def design_matrix(corridor, direction, weekday, slot, exam) -> np.ndarray:
    """Columns as in feature_names(): one-hots with West, Sunday, from_campus and 07:00 as references."""
    corridor, direction, weekday, slot, exam = map(np.asarray, (corridor, direction, weekday, slot, exam))
    n, n_slots, n_corr = len(corridor), len(SLOTS), len(CORRIDOR_NAMES)
    X = np.zeros((n, len(feature_names())))
    rows = np.arange(n)
    X[:, 0] = 1.0
    col = 1
    mask = corridor > 0
    X[rows[mask], col + corridor[mask] - 1] = 1.0
    col += n_corr - 1
    for w, i in _WEEKDAY_COLUMN.items():
        X[weekday == w, col + i] = 1.0
    col += len(_WEEKDAY_COLUMN)
    X[:, col] = exam.astype(float)
    X[:, col + 1] = (direction == 1).astype(float)
    col += 2
    mask = slot > 0
    X[rows[mask], col + slot[mask] - 1] = 1.0
    col += n_slots - 1
    mask = (slot > 0) & (direction == 1)
    X[rows[mask], col + slot[mask] - 1] = 1.0
    return X


@dataclass(frozen=True, eq=False)
class PoissonModel:
    coef: np.ndarray
    features: tuple[str, ...]
    alpha: float
    iterations: int
    train_rows: int

    def log_rate(self, X: np.ndarray) -> np.ndarray:
        return X @ self.coef


def _irls(X, y, alpha, max_iter=100, tol=1e-9):
    """Penalized IRLS (Newton) for log E[y] = X b with an L2 penalty alpha/2 |b|^2 (intercept unpenalized)."""
    penalty = np.full(X.shape[1], alpha)
    penalty[0] = 0.0
    beta = np.zeros(X.shape[1])
    beta[0] = np.log(max(float(y.mean()), 1e-6))
    for iteration in range(1, max_iter + 1):
        eta = np.clip(X @ beta, -30, 30)
        mu = np.exp(eta)
        z = eta + (y - mu) / mu
        xtw = X.T * mu
        new = np.linalg.solve(xtw @ X + np.diag(penalty), xtw @ z)
        step = np.max(np.abs(new - beta))
        beta = new
        if step < tol:
            break
    return beta, iteration


def fit(history: History, alpha: float = L2_ALPHA) -> PoissonModel:
    """Fit on teaching days only: Friday and Saturday are closed and always predicted as 0."""
    teach = np.isin(history.weekday, TEACHING_WEEKDAYS)
    h = history.subset(teach)
    X = design_matrix(h.corridor, h.direction, h.weekday, h.slot, h.exam)
    coef, iterations = _irls(X, h.count.astype(float), alpha)
    return PoissonModel(coef=coef, features=feature_names(), alpha=alpha, iterations=iterations, train_rows=len(h))


def _index(corridor: str, direction: str) -> tuple[int, int]:
    if corridor not in CORRIDOR_NAMES:
        raise ValueError(f"Unknown corridor {corridor!r}.")
    if direction not in DIRECTIONS:
        raise ValueError(f"Unknown direction {direction!r}.")
    return CORRIDOR_NAMES.index(corridor), DIRECTIONS.index(direction)


def predict(model: PoissonModel, day, corridor: str, direction: str, slot) -> float:
    """Expected booking requests for one (date, corridor, direction, 15-minute slot). Never negative.

    Friday/Saturday and slots outside 07:00-20:45 are 0 (no service).
    """
    day = as_date(day)
    c, d = _index(corridor, direction)
    minute = slot_start(slot)
    if day.weekday() not in TEACHING_WEEKDAYS or minute not in SLOTS:
        return 0.0
    X = design_matrix([c], [d], [day.weekday()], [SLOTS.index(minute)], [is_exam_day(day)])
    return float(np.exp(np.clip(model.log_rate(X)[0], -30, 30)))


def predict_day(model: PoissonModel, day) -> np.ndarray:
    """Expected requests for every corridor x direction x slot of one date: shape (4, 2, 56)."""
    day = as_date(day)
    shape = (len(CORRIDOR_NAMES), len(DIRECTIONS), len(SLOTS))
    if day.weekday() not in TEACHING_WEEKDAYS:
        return np.zeros(shape)
    c, d, s = (axis.ravel() for axis in np.meshgrid(*map(np.arange, shape), indexing="ij"))
    X = design_matrix(c, d, np.full(len(c), day.weekday()), s, np.full(len(c), is_exam_day(day)))
    return np.exp(np.clip(model.log_rate(X), -30, 30)).reshape(shape)


# ---- Backtest ----

def seasonal_naive(train: History) -> np.ndarray:
    """Average count per (corridor, direction, weekday, slot) over the training weeks: shape (4, 2, 7, 56)."""
    shape = (len(CORRIDOR_NAMES), len(DIRECTIONS), 7, len(SLOTS))
    total = np.zeros(shape)
    seen = np.zeros(shape)
    np.add.at(total, (train.corridor, train.direction, train.weekday, train.slot), train.count)
    np.add.at(seen, (train.corridor, train.direction, train.weekday, train.slot), 1)
    return np.divide(total, seen, out=np.zeros(shape), where=seen > 0)


def _scores(pred: np.ndarray, actual: np.ndarray) -> dict:
    demand = actual > 0
    return {
        "mae": float(np.mean(np.abs(pred - actual))),
        "mape_pct": float(np.mean(np.abs(pred[demand] - actual[demand]) / actual[demand]) * 100),
    }


@lru_cache(maxsize=1)
def backtest(weeks: int = HISTORY_WEEKS, test_weeks: int = TEST_WEEKS, seed: int = HISTORY_SEED) -> dict:
    """Train on the first weeks, test on the last `test_weeks` (teaching days only).

    MAE is over every teaching-day test slot; MAPE only over slots that had at least one booking.
    The baseline is seasonal-naive: the training-weeks average of the same corridor, direction,
    weekday and slot (it knows nothing about exam weeks).
    """
    history = synthetic_history(weeks, seed)
    teach = np.isin(history.weekday, TEACHING_WEEKDAYS)
    train_mask = history.week < weeks - test_weeks
    train, test = history.subset(train_mask), history.subset(~train_mask & teach)
    model = fit(train)
    X = design_matrix(test.corridor, test.direction, test.weekday, test.slot, test.exam)
    pred_model = np.exp(np.clip(model.log_rate(X), -30, 30))
    pred_base = seasonal_naive(train)[test.corridor, test.direction, test.weekday, test.slot]
    oracle = test.rate  # the generator's own mean: the best any forecast could do on average
    by_week = {}
    for week in sorted(set(test.week.tolist())):
        m = test.week == week
        by_week[int(week) + 1] = {
            "exam_week": bool(test.exam[m].any()),
            "model": _scores(pred_model[m], test.count[m]),
            "baseline": _scores(pred_base[m], test.count[m]),
        }
    return {
        "train_weeks": weeks - test_weeks,
        "test_weeks": test_weeks,
        "test_rows": int(len(test)),
        "test_rows_with_demand": int((test.count > 0).sum()),
        "model": _scores(pred_model, test.count),
        "baseline": _scores(pred_base, test.count),
        "oracle": _scores(oracle, test.count),
        "by_test_week": by_week,
        "iterations": model.iterations,
    }


@lru_cache(maxsize=1)
def trained_model() -> PoissonModel:
    """The serving model: trained once on the full simulated history (deterministic)."""
    return fit(synthetic_history())


@lru_cache(maxsize=64)
def day_forecast(day: date) -> np.ndarray:
    """predict_day with the serving model, cached per date. Treat the result as read-only."""
    result = predict_day(trained_model(), day)
    result.setflags(write=False)
    return result


def forecast(day, corridor: str, direction: str, slot) -> float:
    """Expected requests with the serving model."""
    c, d = _index(corridor, direction)
    minute = slot_start(slot)
    if minute not in SLOTS:
        return 0.0
    return float(day_forecast(as_date(day))[c, d, SLOTS.index(minute)])


def rate_per_minute(day, corridor: str, direction: str, minute: float) -> float:
    """Forecast intensity in requests per minute at a moment of the day (piecewise constant per slot)."""
    start = slot_start(int(minute))
    if start not in SLOTS:
        return 0.0
    return forecast(day, corridor, direction, start) / SLOT_MIN


__all__ = [
    "DIRECTIONS", "CORRIDOR_NAMES", "SLOTS", "SLOT_MIN", "DEFAULT_DATE", "History", "PoissonModel",
    "synthetic_history", "fit", "predict", "predict_day", "backtest", "trained_model", "day_forecast",
    "forecast", "is_exam_day", "is_teaching_day", "slot_start", "slot_label",
]
