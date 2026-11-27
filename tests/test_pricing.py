from datetime import datetime

from pooling.config import TZ
from pooling.pricing import car_fare, is_night, split_fare

DAY = datetime(2026, 11, 28, 16, 0, tzinfo=TZ)
NIGHT = datetime(2026, 11, 28, 23, 0, tzinfo=TZ)


def test_12km_day_is_4500():
    assert car_fare(12, DAY) == 4500


def test_night_tariff():
    assert car_fare(12, NIGHT) == 480 + round(396 * 12)


def test_night_window_wraps_midnight():
    assert is_night(datetime(2026, 11, 28, 5, 59, tzinfo=TZ))
    assert not is_night(DAY)


def test_split_sums_exactly():
    shares = split_fare(4850, [1, 1, 1])
    assert sum(shares) == 4850 and sorted(shares) == [1616, 1617, 1617]


def test_split_spec_example():
    assert split_fare(5710, [8.96, 12.0, 14.85]) == [1429, 1913, 2368]


def test_earlier_dropoff_never_pays_more():
    s = split_fare(5000, [5, 9, 9.0001])
    assert s[0] < s[1] <= s[2]


def test_all_zero_weights_split_equally():
    assert sorted(split_fare(1000, [0, 0, 0])) == [333, 333, 334]


def test_single_rider_pays_all():
    assert split_fare(4500, [12.0]) == [4500]
