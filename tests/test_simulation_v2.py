"""Simulation v2: per-student limits, friends groups, the three methods on equal terms, and the JSON endpoint."""
from collections import Counter
from datetime import timedelta

import pytest

import app as campus
from pooling import config
from pooling.model import evaluate, extra_minutes, gender_ok
from simulation import (
    COUNTS, FRIENDS_TIME_MIN, LIMIT_CHOICES, METHODS, _greedy, _metrics, _optimizer, _scenario, simulate,
)

FEW_SEEDS = range(5)


@pytest.fixture
def client(tmp_path):
    campus.app.config.update(TESTING=True, DATABASE=tmp_path / "test.sqlite")
    with campus.app.test_client() as client:
        yield client


def methods(n, seed):
    riders, groups = _scenario(n, seed)
    singles = [evaluate([r]) for r in riders]
    return riders, groups, singles, {"greedy": _greedy(riders, groups), "optimizer": _optimizer(singles, groups)}


def test_scenarios_are_deterministic_with_exactly_n_students_and_valid_friends_groups():
    students = friends = 0
    groups_seen = Counter()
    limits = Counter()
    for n in COUNTS:
        for seed in FEW_SEEDS:
            riders, groups = _scenario(n, seed)
            assert (riders, groups) == _scenario(n, seed)
            assert len(riders) == n
            assert {r.request_id for r in riders} == {str(i) for i in range(n)}
            by_id = {r.request_id: r for r in riders}
            for r in riders:
                assert r.max_gate_wait_min in LIMIT_CHOICES and r.max_extra_ride_min in LIMIT_CHOICES
                assert r.max_gate_wait_min <= config.MAX_GATE_WAIT_CAP_MIN
                assert r.max_extra_ride_min <= config.MAX_EXTRA_RIDE_CAP_MIN
                limits[r.max_gate_wait_min] += 1
                limits[r.max_extra_ride_min] += 1
            placed = [rid for ids, _ in groups for rid in ids]
            assert len(placed) == len(set(placed))  # a student is in at most one friends group
            for ids, closed in groups:
                assert 2 <= len(ids) <= 3
                groups_seen[closed] += 1
                members = sorted((by_id[rid] for rid in ids), key=lambda r: int(r.request_id))
                anchor, clones = members[0], members[1:]
                assert {(r.corridor, r.direction) for r in members} == {(anchor.corridor, anchor.direction)}
                walk = timedelta(seconds=config.MAX_WALK_M / config.WALK_SPEED_MPS)
                for clone in clones:
                    assert clone.stop_id != anchor.stop_id
                    if anchor.direction == "to_campus":
                        assert abs(clone.arrive_by - anchor.arrive_by) <= timedelta(minutes=FRIENDS_TIME_MIN)
                    else:
                        assert abs(clone.ready_at - anchor.ready_at) <= timedelta(minutes=FRIENDS_TIME_MIN) + walk
                assert gender_ok(members)
                assert evaluate(members, strict=False) is not None  # passes the app's join validation
            students += n
            friends += len(placed)
    assert 0.10 <= friends / students <= 0.25
    assert groups_seen[True] and groups_seen[False]
    assert 0.15 <= groups_seen[True] / sum(groups_seen.values()) <= 0.55
    assert limits.most_common(1)[0][0] == config.DEFAULT_MAX_GATE_WAIT_MIN == config.DEFAULT_MAX_EXTRA_RIDE_MIN
    assert set(limits) == set(LIMIT_CHOICES)


@pytest.mark.parametrize("n", (16, 24))
def test_friends_ride_together_closed_groups_alone_and_every_car_meets_each_students_limits(n):
    for seed in range(3):
        riders, groups, _, plans_by_method = methods(n, seed)
        friends_of = {rid: ids for ids, _ in groups for rid in ids}
        for method, plans in plans_by_method.items():
            assert sorted(r.request_id for p in plans for r in p.riders) == sorted(r.request_id for r in riders)
            car = {r.request_id: p.ids for p in plans for r in p.riders}
            for ids, closed in groups:
                assert len({car[rid] for rid in ids}) == 1, (method, seed, ids)  # never split
                if closed:
                    assert car[next(iter(ids))] == ids, (method, seed, ids)  # no strangers
            for plan in plans:
                assert len(plan.riders) <= config.MAX_RIDERS
                if len(plan.riders) == 1:
                    continue
                if plan.ids not in friends_of.values():  # only a car of exactly one friends group may skip strict
                    assert evaluate(plan.riders) is not None
                assert gender_ok(plan.riders)
                for r in plan.riders:
                    if r.ready_at is not None:
                        assert r.ready_at <= plan.pickup_time <= r.ready_at + timedelta(minutes=r.max_gate_wait_min)
                    extra = extra_minutes(plan.in_car_km[r.request_id], plan.solo_km[r.request_id])
                    assert extra <= r.max_extra_ride_min + 1e-9


def test_optimizer_uses_no_more_car_km_than_first_come_on_average():
    for n in (16, 24, 32):
        greedy = optimizer = 0.0
        for seed in FEW_SEEDS:
            _, _, _, plans_by_method = methods(n, seed)
            greedy += sum(p.route_km for p in plans_by_method["greedy"])
            optimizer += sum(p.route_km for p in plans_by_method["optimizer"])
        assert optimizer <= greedy + 1e-9, n


def test_new_metrics():
    riders, groups, singles, plans_by_method = methods(24, 0)
    alone = _metrics(singles, singles, groups)
    assert alone["friends_together_pct"] == 0 and alone["alone_pct"] == 100 and alone["single_gender_cars"] == 0
    for plans in plans_by_method.values():
        row = _metrics(plans, singles, groups)
        assert row["friends_together_pct"] == 100
        assert row["alone_pct"] + row["matched_pct"] == pytest.approx(100)
        assert row["single_gender_cars"] == sum(
            1 for p in plans if len(p.riders) > 1 and any(r.preference != "mixed" for r in p.riders))
    assert _metrics(singles, singles)["friends_together_pct"] == 100  # no friends groups in the wave


def test_simulate_small_run_keeps_existing_keys_and_adds_friends_metrics():
    result = simulate(counts=(8, 16), seeds=(0, 1))
    assert result["counts"] == (8, 16) and result["seeds"] == 2 and result["simulated"] is True
    for n in (8, 16):
        assert set(result["summary"][n]) == set(METHODS)
        for method in METHODS:
            assert set(result["summary"][n][method]) == {
                "cars", "car_km", "km_saved_pct", "matched_pct", "saving_fils_per_rider", "walk_m",
                "extra_minutes", "friends_together_pct", "alone_pct", "single_gender_cars"}
        for method in ("greedy", "optimizer"):
            assert result["summary"][n][method]["friends_together_pct"]["min"] == 100
        assert result["summary"][n]["alone"]["alone_pct"]["mean"] == 100


def test_simulation_endpoint_returns_simulated_summary_without_auth(client):
    response = client.get("/api/v1/simulation")
    assert response.status_code == 200
    body = response.get_json()
    assert body["simulated"] is True and "simulated" in body["note"].lower()
    assert body["counts"] == list(COUNTS) and body["seeds"] == 30 and body["methods"] == list(METHODS)
    assert set(body["summary"]) == {str(n) for n in COUNTS}
    for n in COUNTS:
        for method in METHODS:
            metric = body["summary"][str(n)][method]["km_saved_pct"]
            assert metric["min"] <= metric["mean"] <= metric["max"]
        for method in ("greedy", "optimizer"):
            assert body["summary"][str(n)][method]["friends_together_pct"]["min"] == 100
        assert body["summary"][str(n)]["alone"]["cars"]["mean"] == n


def test_dashboard_simulation_view_still_renders(client):
    response = client.get("/?view=simulation")
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Simulated results only" in page and "Optimizer" in page and "First-come" in page
