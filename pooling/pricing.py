"""Jeeny app tariff and the proportional fare split. All money is integer fils."""
from collections.abc import Sequence
from datetime import datetime

from pooling import config


def is_night(at: datetime) -> bool:
    t = at.astimezone(config.TZ).time()
    return t >= config.NIGHT_START or t < config.NIGHT_END


def car_fare(km: float, at: datetime) -> int:
    """The single approved fare for one car over `km`, priced at departure time `at`."""
    if is_night(at):
        return config.START_NIGHT + round(config.PER_KM_NIGHT * km)
    return config.START_DAY + round(config.PER_KM_DAY * km)


def split_fare(total: int, weights: Sequence[float]) -> list[int]:
    """Split `total` fils in proportion to `weights` (each rider's solo km).

    Contract (pinned by tests/test_pricing.py):
    - the result has one integer per weight and sums EXACTLY to `total`;
    - a larger weight never gets a smaller share;
    - all-zero weights split equally.
    """
    # TODO(human): implement the proportional split with integer rounding.
    raise NotImplementedError
