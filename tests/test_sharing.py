"""Rules the pitch depends on: grouping, women-only matching and fair price splits."""
import itertools

import pytest

from sharing import MIN_SHARE, SEATS, STOPS, compatible, group_riders, plan_car, solo_fare

from store import FIXTURE


def make_riders(rows):
    return [
        {"id": i + 1, "name": name, "class_end": end, "stop": stop, "woman": woman, "women_only": women_only}
        for i, (name, end, stop, woman, women_only) in enumerate(rows)
    ]


@pytest.fixture
def sample():
    return make_riders(FIXTURE)


def by_name(riders):
    return {r["name"]: r for r in riders}


def cars_by_name(riders, groups):
    names = {r["id"]: r["name"] for r in riders}
    return [sorted(names[i] for i in car) for car in groups]


def test_sara_pays_150_instead_of_450(sample):
    riders = by_name(sample)
    assert solo_fare("Dabouq") == 4500
    car = plan_car([riders["Sara"], riders["Rama"], riders["Huda"]])
    assert car["shared"] is True
    assert car["shares"][riders["Sara"]["id"]] == 1500
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
        for a, b in itertools.combinations(car, 2):
            assert compatible(riders[a], riders[b])


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
                    assert share >= min(MIN_SHARE, solo_fare(rider["stop"]))


def test_solo_rider_pays_solo_fare():
    car = plan_car(make_riders([("Zaid", "18:00", "Marka", False, False)]))
    assert car["shared"] is False
    assert car["shares"][1] == solo_fare("Marka")
    assert car["pickup"] == "18:15"


def test_pickup_waits_for_last_class_and_rounds_to_five_minutes():
    car = plan_car(make_riders([
        ("A", "16:00", "Khalda", False, False),
        ("B", "16:12", "Dabouq", False, False),
    ]))
    assert car["pickup"] == "16:30"
    assert [r["name"] for r in car["members"]] == ["A", "B"]  # nearest drop-off first


def test_mixed_car_is_not_labelled_women_only():
    car = plan_car(make_riders([
        ("Lina", "16:15", "Al Jubeiha", True, False),
        ("Omar", "16:10", "Shafa Badran", False, False),
    ]))
    assert car["women_only"] is False
