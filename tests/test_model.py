from pooling.model import evaluate
from tests.helpers import rider


def test_single_rider_pays_solo():
    p = evaluate([rider("a", "sweileh")])
    assert p.shares["a"] == p.solo_fare["a"] == p.car_fare


def test_shares_sum_to_car_fare():
    p = evaluate([rider("a", "sweileh"), rider("b", "al-jubeiha")])
    assert sum(p.shares.values()) == p.car_fare


def test_pooled_riders_each_save_20pct():
    p = evaluate([rider("a", "sweileh"), rider("b", "al-jubeiha"), rider("c", "university-street")])
    assert all(p.shares[r] <= 0.8 * p.solo_fare[r] for r in p.shares)


def test_fifth_rider_refused():
    assert evaluate([rider(str(i), "sweileh") for i in range(5)]) is None


def test_four_riders_allowed():
    assert evaluate([rider(str(i), "sweileh") for i in range(4)]) is not None


def test_women_only_must_not_mix():
    assert evaluate([rider("a", "sweileh", women_only=True), rider("b", "sweileh")]) is None


def test_disjoint_windows_refused():
    assert evaluate([rider("a", "sweileh"), rider("b", "sweileh", after="16:40", before="17:00")]) is None


def test_window_overlap_under_5_min_refused():
    assert evaluate([rider("a", "sweileh", before="16:10"), rider("b", "sweileh", after="16:06")]) is None


def test_far_rider_breaks_detour():
    assert evaluate([rider("a", "khalda"), rider("b", "zarqa")]) is None


def test_picks_shortest_drop_order():
    p = evaluate([rider("far", "al-jubeiha"), rider("near", "sweileh")])
    assert [r.request_id for r in p.riders] == ["near", "far"]


def test_pickup_is_window_start():
    p = evaluate([rider("a", "sweileh", after="16:00"), rider("b", "sweileh", after="16:10")])
    assert p.pickup_time.strftime("%H:%M") == "16:10"


def test_quote_cap_blocks_higher_share():
    assert evaluate([rider("a", "sweileh", quote=1), rider("b", "sweileh")]) is None
