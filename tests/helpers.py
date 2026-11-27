from datetime import datetime

from pooling.config import TZ
from pooling.model import Rider


def at(hhmm: str) -> datetime:
    h, m = map(int, hhmm.split(":"))
    return datetime(2026, 11, 28, h, m, tzinfo=TZ)


def rider(rid, stop, after="16:00", before="16:30", women_only=False, quote=None, woman=None):
    return Rider(
        request_id=rid, first_name=rid.title(), women_only=women_only,
        campus_id="ahu", meeting_point_id="ahu-main-gate", stop_id=stop,
        leave_after=at(after), leave_before=at(before), quoted_share=quote,
        woman=women_only if woman is None else woman,
    )
