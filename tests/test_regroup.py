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
