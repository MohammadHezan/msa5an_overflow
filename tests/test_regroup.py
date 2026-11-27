from pooling.model import evaluate
from pooling.regroup import regroup
from tests.helpers import rider


def km(plans):
    return sum(p.route_km for p in plans)


def bad_pairing():
    # Greedy mistake: north and south riders paired across corridors (or left alone).
    north = [rider("n1", "sweileh"), rider("n2", "al-jubeiha")]
    south = [rider("s1", "khalda"), rider("s2", "tla-al-ali")]
    return [evaluate([north[0]]), evaluate([south[0]]), evaluate([north[1]]), evaluate([south[1]])]


def test_every_rider_exactly_once():
    result = regroup(bad_pairing())
    ids = [r.request_id for p in result for r in p.riders]
    assert sorted(ids) == ["n1", "n2", "s1", "s2"]


def test_never_worse_than_input():
    current = bad_pairing()
    assert km(regroup(current)) <= km(current) + 1e-9


def test_fixes_greedy_order_trap():
    current = bad_pairing()
    result = regroup(current)
    assert km(result) < km(current) and len(result) < len(current)


def test_regroup_respects_confirmed_quotes():
    pair = evaluate([rider("a", "sweileh"), rider("b", "sweileh")])
    quoted = evaluate([rider("a", "sweileh", quote=pair.shares["a"]), rider("b", "sweileh")])
    result = regroup([quoted, evaluate([rider("z", "zarqa")])])
    for plan in result:
        for r in plan.riders:
            if r.quoted_share is not None:
                assert plan.shares[r.request_id] <= r.quoted_share


def test_empty_input_returns_empty():
    assert regroup([]) == []


# ---- Phase 0 fixes: one objective, never "everyone alone", prune only on hereditary rules ----

import random
import time

from pooling import config
from pooling.places import CORRIDORS, DEMO_CAMPUS


def demo_rider(rid, stop, gender="man", preference="mixed", gate=None):
    corridor = next(c for c in CORRIDORS.values() if stop in c["stops"])
    return rider(rid, stop, after="16:15", before="16:40", gender=gender, preference=preference,
                 campus=DEMO_CAMPUS, gate=gate or corridor["gate"])


def busy_wave(seed, n=28):
    rng = random.Random(seed)
    stops = [s for c in CORRIDORS.values() for s in c["stops"]]
    riders = []
    for i in range(n):
        gender = rng.choice(["woman", "man"])
        preference = "women" if gender == "woman" and rng.random() < 0.3 else "mixed"
        riders.append(demo_rider(f"r{i:02d}", rng.choice(stops), gender, preference))
    return riders


def test_busy_wave_of_28_forms_shared_cars_quickly():
    for seed in range(15):
        riders = busy_wave(seed)
        started = time.perf_counter()
        result = regroup([evaluate([r]) for r in riders])
        elapsed = time.perf_counter() - started
        solo = sum(1 for p in result if len(p.riders) == 1)
        assert sorted(r.request_id for p in result for r in p.riders) == sorted(r.request_id for r in riders)
        assert solo < 20, f"seed {seed}: {solo} solo cars"
        assert elapsed < 3, f"seed {seed}: {elapsed:.1f}s"


def test_trio_is_found_when_a_pair_inside_it_fails_the_savings_floor():
    # Al Jubeiha 3 km + Abu Nseir 10 km: the Abu Nseir rider saves only 23% (< 25%), so that pair fails.
    # With a second Abu Nseir rider, all three save at least 25%, so the trio is valid.
    near, far1, far2 = demo_rider("near", "Al Jubeiha"), demo_rider("far1", "Abu Nseir"), demo_rider("far2", "Abu Nseir")
    assert config.MIN_SAVING == 0.25
    assert evaluate([near, far1]) is None
    assert evaluate([near, far1, far2]) is not None
    result = regroup([evaluate([near]), evaluate([far1]), evaluate([far2])])
    assert [sorted(r.request_id for r in p.riders) for p in result] == [["far1", "far2", "near"]]


def test_friends_group_rides_together_and_a_closed_group_takes_no_strangers():
    a, b, c, d = (demo_rider(x, "Dabouq") for x in "abcd")
    singles = [evaluate([r]) for r in (a, b, c, d)]
    together = regroup(singles, together=[frozenset({"a", "c"})])
    assert any({"a", "c"} <= {r.request_id for r in p.riders} for p in together)
    closed = regroup(singles, together=[frozenset({"a", "b"})], closed=[frozenset({"a", "b"})])
    assert sorted(sorted(r.request_id for r in p.riders) for p in closed) == [["a", "b"], ["c", "d"]]
