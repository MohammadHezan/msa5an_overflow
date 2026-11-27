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
    n = len(weights)
    if n == 0:
        return []
    weight_sum = sum(weights)
    raw = [total * w / weight_sum for w in weights] if weight_sum else [total / n] * n
    shares = [int(r) for r in raw]  # floor (all values are non-negative)
    # Largest remainder: hand the leftover fils to the biggest fractions, earlier rider first on ties.
    leftover = total - sum(shares)
    for i in sorted(range(n), key=lambda i: (-(raw[i] - shares[i]), i))[:leftover]:
        shares[i] += 1
    return shares
