import random
import re

from pooling.codes import new_code


def test_format():
    assert re.fullmatch(r"CC-\d{4}", new_code(set()))


def test_avoids_existing():
    first = new_code(set(), random.Random(7))
    assert new_code({first}, random.Random(7)) != first
