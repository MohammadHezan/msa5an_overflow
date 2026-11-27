"""Rules the pitch depends on: grouping, ride options (anyone / women only / men only) and fair price splits."""
import itertools

import pytest

from pooling.model import evaluate
from sharing import SEATS, STOPS, _rider, compatible, group_riders, plan_car, solo_fare

from store import FIXTURE


def make_riders(rows):
    """Rows of (name, class end, stop, gender, preference). The old (woman, women_only) booleans still work."""
    riders = []
    for i, (name, end, stop, gender, preference) in enumerate(rows):
        if isinstance(gender, bool):
            gender, preference = ("woman" if gender else "man"), ("women" if preference else "mixed")
        riders.append({"id": i + 1, "name": name, "class_end": end, "stop": stop, "gender": gender, "preference": preference})
    return riders


@pytest.fixture
def sample():
    return make_riders(FIXTURE)


def by_name(riders):
    return {r["name"]: r for r in riders}


def cars_by_name(riders, groups):
    names = {r["id"]: r["name"] for r in riders}
    return [sorted(names[i] for i in car) for car in groups]


def test_sara_pays_167_instead_of_450(sample):
    # Regulated app tariff: 468 + 336 x 12 km = 4500 fils alone. Shared to Wadi As-Seer (16 km):
    # car fare 468 + 336 x 16 = 5844, split 12:14:16 by distance -> Sara 1670 (63% saved).
    riders = by_name(sample)
    assert solo_fare("Dabouq") == 4500
    car = plan_car([riders["Sara"], riders["Rama"], riders["Huda"]])
    assert car["shared"] is True
    assert car["car_fare"] == 5844
    assert car["shares"][riders["Sara"]["id"]] == 1670
    assert sum(car["shares"].values()) == car["car_fare"]
    assert car["women_only"] is True


def test_sample_afternoon_groups_into_expected_cars(sample):
    groups = group_riders(sample)
    assert sorted(cars_by_name(sample, groups)) == sorted([
        ["Huda", "Rama", "Sara"],
        ["Kareem"],
        ["Lina", "Omar", "Yazan"],
        ["Dana", "Leen"],
        ["Zaid"],
    ])


def test_every_rider_is_placed_exactly_once(sample):
    groups = group_riders(sample)
    placed = [i for car in groups for i in car]
    assert sorted(placed) == sorted(r["id"] for r in sample)


def test_cars_respect_seats_corridor_time_and_women_only(sample):
    riders = {r["id"]: r for r in sample}
    for car in group_riders(sample):
        assert len(car) <= SEATS
        # The whole car meets every rule (a pair inside it may miss the savings floor on its own)
        assert evaluate([_rider(riders[i]) for i in car]) is not None
        for a, b in itertools.combinations(car, 2):
            assert STOPS[riders[a]["stop"]]["corridor"] == STOPS[riders[b]["stop"]]["corridor"]


def test_women_only_rider_never_grouped_with_a_man():
    riders = make_riders([
        ("Sara", "16:00", "Dabouq", True, True),
        ("Kareem", "16:00", "Khalda", False, False),
        ("Ali", "16:05", "Dabouq", False, False),
    ])
    groups = cars_by_name(riders, group_riders(riders))
    sara_car = next(car for car in groups if "Sara" in car)
    assert sara_car == ["Sara"]
    assert ["Ali", "Kareem"] in groups


def test_women_only_rider_can_ride_with_women_who_did_not_ask_for_it():
    riders = make_riders([
        ("Leen", "13:00", "Um Al Summaq", True, True),
        ("Dana", "13:10", "Abdoun", True, False),
    ])
    assert len(group_riders(riders)) == 1


def test_different_corridors_and_far_apart_times_are_not_grouped():
    riders = make_riders([
        ("A", "16:00", "Dabouq", False, False),
        ("B", "16:00", "Marka", False, False),
        ("C", "16:30", "Khalda", False, False),
    ])
    assert len(group_riders(riders)) == 3


def test_full_car_splits_when_more_than_four_riders():
    riders = make_riders([(f"R{i}", "16:00", "Khalda", False, False) for i in range(6)])
    groups = group_riders(riders)
    assert len(groups) == 2
    assert all(len(car) <= SEATS for car in groups)


def test_empty_batch_has_no_cars():
    assert group_riders([]) == []


def test_nobody_pays_more_than_riding_alone():
    stops = list(STOPS)
    for corridor_stops in ({s for s in stops if STOPS[s]["corridor"] == c} for c in {STOPS[s]["corridor"] for s in stops}):
        for size in range(2, SEATS + 1):
            for combo in itertools.combinations_with_replacement(sorted(corridor_stops), size):
                members = make_riders([(f"R{i}", "16:00", stop, False, False) for i, stop in enumerate(combo)])
                car = plan_car(members)
                for rider in members:
                    share = car["shares"][rider["id"]]
                    assert share <= solo_fare(rider["stop"])
                assert sum(car["shares"].values()) == car["car_fare"]


def test_solo_rider_pays_solo_fare():
    car = plan_car(make_riders([("Zaid", "18:00", "Marka", False, False)]))
    assert car["shared"] is False
    assert car["shares"][1] == solo_fare("Marka")
    assert car["pickup"] == "18:15"


def test_pickup_waits_for_last_class_and_rounds_to_five_minutes():
    car = plan_car(make_riders([
        ("A", "16:00", "Khalda", False, False),
        ("B", "16:08", "Dabouq", False, False),
    ]))
    assert car["pickup"] == "16:25"  # 16:08 + 15 min walk, rounded up to 5 minutes
    assert [r["name"] for r in car["members"]] == ["A", "B"]  # nearest drop-off first


def test_mixed_car_is_not_labelled_women_only():
    car = plan_car(make_riders([
        ("Lina", "16:15", "Al Jubeiha", True, False),
        ("Omar", "16:10", "Shafa Badran", False, False),
    ]))
    assert car["women_only"] is False


def test_mixed_woman_can_join_a_women_only_car():
    riders = make_riders([
        ("Sara", "16:00", "Dabouq", "woman", "women"),
        ("Noor", "16:00", "Dabouq", "woman", "mixed"),
    ])
    assert cars_by_name(riders, group_riders(riders)) == [["Noor", "Sara"]]
    assert plan_car(riders)["only"] == "women"


def test_man_never_joins_a_women_car_and_woman_never_joins_a_men_car():
    riders = make_riders([
        ("Sara", "16:00", "Dabouq", "woman", "women"),
        ("Ali", "16:00", "Dabouq", "man", "mixed"),
        ("Omar", "16:00", "Khalda", "man", "men"),
        ("Lina", "16:00", "Khalda", "woman", "mixed"),
    ])
    for car in cars_by_name(riders, group_riders(riders)):
        assert not ("Sara" in car and ("Ali" in car or "Omar" in car))
        assert not ("Omar" in car and ("Lina" in car or "Sara" in car))


def test_men_only_car_is_labelled():
    riders = make_riders([("Omar", "16:00", "Khalda", "man", "men"), ("Ali", "16:00", "Dabouq", "man", "mixed")])
    assert len(group_riders(riders)) == 1
    assert plan_car(riders)["only"] == "men"


def test_mixed_riders_of_both_genders_share():
    riders = make_riders([("Lina", "16:00", "Khalda", "woman", "mixed"), ("Ali", "16:00", "Dabouq", "man", "mixed")])
    assert len(group_riders(riders)) == 1
    assert plan_car(riders)["only"] is None
