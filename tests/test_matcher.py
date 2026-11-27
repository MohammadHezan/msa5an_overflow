from pooling.matcher import OpenGroup, insert
from pooling.model import evaluate
from tests.helpers import rider


def group(gid, *riders):
    return OpenGroup(gid, evaluate(riders))


def test_joins_compatible_group():
    result = insert([group("g1", rider("a", "sweileh"))], rider("b", "al-jubeiha"))
    assert result.group_id == "g1" and len(result.plan.riders) == 2


def test_opens_new_group_when_none_fit():
    result = insert([group("g1", rider("a", "khalda"))], rider("z", "zarqa"))
    assert result.group_id is None and len(result.plan.riders) == 1


def test_prefers_least_added_km():
    north = group("g-north", rider("a", "sweileh"))
    south = group("g-south", rider("b", "khalda"))
    assert insert([south, north], rider("c", "sweileh-circle")).group_id == "g-north"


def test_tie_prefers_fuller_group():
    small = group("g-small", rider("a", "sweileh"))
    full = group("g-big", rider("b", "sweileh"), rider("c", "sweileh"))
    assert insert([small, full], rider("d", "sweileh")).group_id == "g-big"


def test_full_group_is_skipped():
    full = group("g-full", *(rider(str(i), "sweileh") for i in range(4)))
    assert insert([full], rider("x", "sweileh")).group_id is None


def test_rejects_when_existing_rider_would_lose_savings():
    # Abdoun pulls the car far south; the Sweileh rider would no longer save 20% or would detour.
    g = group("g1", rider("a", "sweileh"), rider("b", "al-jubeiha"))
    assert insert([g], rider("c", "abdoun")).group_id is None


def test_insert_never_raises_confirmed_share():
    # Without a quote, a Zarqa rider can join two Sweileh riders, but it raises their shares.
    pair = evaluate([rider("a", "sweileh"), rider("b", "sweileh")])
    assert insert([OpenGroup("g1", pair)], rider("z", "zarqa")).group_id == "g1"
    confirmed = evaluate([rider("a", "sweileh", quote=pair.shares["a"]), rider("b", "sweileh")])
    assert insert([OpenGroup("g1", confirmed)], rider("z", "zarqa")).group_id is None


def test_women_only_rider_skips_mixed_group():
    mixed = group("g-mixed", rider("a", "sweileh"))
    assert insert([mixed], rider("w", "sweileh", women_only=True)).group_id is None
