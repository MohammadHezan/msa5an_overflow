"""Every tunable limit for ride pooling, in one place (spec: Global Constraints)."""
from datetime import time
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Amman")

# LTRC smart-app tariff, in effect since 11 May 2026. Money is integer fils.
START_DAY = 468
PER_KM_DAY = 336
START_NIGHT = 480
PER_KM_NIGHT = 396
# Night hours are not defined by any source we found; this window is an assumption.
NIGHT_START = time(22, 0)
NIGHT_END = time(6, 0)

MAX_RIDERS = 4
DETOUR_RATIO = 1.5      # in-car km <= solo km * ratio ...
DETOUR_EXTRA_KM = 4.0   # ... and <= solo km + this
MIN_SAVING = 0.25       # each pooled rider pays <= (1 - MIN_SAVING) * solo fare
MIN_WINDOW_MIN = 5      # shared departure window must be at least this long
MAX_GAP_MIN = 10        # class ends in one car are at most this far apart (the app's departure windows)
MERGE_KM = 0.4          # stops closer than this count as one stop
ROAD_FACTOR = 1.35      # road km ~= straight-line km * factor
SPEED_KMH = 25          # city average, for time estimates only
MAX_WALK_M = 200        # street pickup/drop-off limit before the captain turns in
WALK_SPEED = 1.4        # metres per second
WALK_SPEED_MPS = WALK_SPEED
LOCK_LEAD_MIN = 15
SOLVER_SECONDS = 2.0
SOLVER_WORKERS = 4
# Planned ride request (screens 06-08). A rider's own limits; the car must respect every member's.
PICKUP_SLOTS_MIN = (0, 5, 10)        # preferred pickup: readyAt, +5 or +10 minutes
MAX_READY_AFTER_CLASS_MIN = 60       # readyAt may be at most this long after class ends
DEFAULT_MAX_GATE_WAIT_MIN = 10       # pickup is at most this long after the rider's readyAt
MAX_GATE_WAIT_CAP_MIN = 30           # highest gate-wait limit a rider may ask for
DEFAULT_MAX_EXTRA_RIDE_MIN = 10      # extra in-car minutes over riding alone (km at SPEED_KMH)
MAX_EXTRA_RIDE_CAP_MIN = 30          # highest extra-ride limit a rider may ask for
PAYMENT_METHODS = ("cash",)          # no payment is taken at request time
ESTIMATE_FULL_RIDERS = MAX_RIDERS    # estimate low: share in a full car
ESTIMATE_PAIR_RIDERS = 2             # estimate high: share with two riders

SOLO_PENALTY = 1500      # fils: regroup will spend up to this much of the group's savings to keep one student from riding alone

# Simulated student verification. Codes are printed locally, never emailed.
VERIFY_CODE_MIN = 5
VERIFY_RESEND_SEC = 30
VERIFY_MAX_WRONG = 5
VERIFY_CODE_DIGITS = 6
STUDENT_EMAIL_MAX = 254
STUDENT_FIRST_NAME_MAX = 40
UNIVERSITY_SEARCH_MAX = 100
# Demo Jeeny profile for the student (no real profile integration yet): the gender drives "Men only"/"Women only"
DEMO_STUDENT_NAME = "Omar K"
DEMO_STUDENT_GENDER = "man"
