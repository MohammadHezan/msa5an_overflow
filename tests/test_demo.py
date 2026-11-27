import tempfile
import unittest
import random
from pathlib import Path

from app import app, database, list_requests
from allocation import WINDOWS, first_come, optimize, summarize


class DemoAcceptance(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.previous = {key: app.config[key] for key in ("TESTING", "DATABASE")}
        app.config.update(TESTING=True, DATABASE=Path(self.temp.name) / "demo.sqlite")
        self.client = app.test_client()
        self.assertEqual(self.client.get("/").status_code, 200)

    def tearDown(self):
        app.config.update(self.previous)
        self.temp.cleanup()

    def post(self, path, **data):
        with self.client.session_transaction() as state:
            csrf = state["csrf"]
        return self.client.post(path, data={"csrf": csrf, **data}, follow_redirects=True)

    def trips(self):
        with self.client.session_transaction() as state:
            batch = state["demo"]
        with app.app_context():
            return list_requests(database(), batch)

    def allocate(self, budget="6", drivers="4"):
        return self.post(
            "/allocate", budget=budget, cap="1",
            morning=drivers, midday=drivers, evening=drivers,
        )

    def test_seeded_comparison_and_limits(self):
        trips = self.trips()
        capacity = dict(zip(WINDOWS, (4, 2, 3)))
        self.assertEqual(
            summarize(trips, optimize(trips, 6000, 1, capacity)),
            {"arrivals": 6, "unserved": 1, "spent": 6000},
        )
        self.assertEqual(
            summarize(trips, first_come(trips, 6000, 1, capacity)),
            {"arrivals": 4, "unserved": 3, "spent": 6000},
        )
        self.assertEqual(optimize(trips, 6000, 1, dict.fromkeys(WINDOWS, 0)), {})
        self.assertEqual(optimize(trips, 6000, 0, capacity), {})
        self.assertEqual(optimize(trips, 0, 1, capacity), {})

    def test_saved_allocation_and_cutoff(self):
        self.assertEqual(self.allocate().status_code, 200)
        saved = self.trips()
        self.allocate(budget="0", drivers="0")
        self.assertEqual(saved, self.trips())
        self.post("/requests", name="Late", area="Tabarbour", arrival="08:30")
        self.assertEqual(len(self.trips()), 7)

    def test_judge_results_metrics_and_browser_reload(self):
        response = self.allocate()
        self.assertIn(b"85.7% (6/7)", response.data)
        self.assertIn(b"57.1% (4/7)", response.data)
        self.assertIn(b"Credit spend per on-time arrival", response.data)
        self.assertIn(b"JOD 1.00", response.data)
        self.assertIn(b"JOD 1.50", response.data)
        self.assertIn(b"On-time by bus", response.data)
        self.assertIn(b"Scenario assumptions", response.data)
        saved = self.client.get("/?view=results")
        self.assertIn(b"85.7% (6/7)", saved.data)
        self.assertIn(b"JOD 6.00", saved.data)

    def test_ties_and_zero_arrival_cost(self):
        response = self.allocate(budget="0", drivers="0")
        self.assertIn(b"Tie: both methods", response.data)
        self.assertIn(b"28.6% (2/7)", response.data)
        self.post("/reset", mode="empty")
        self.post("/requests", name="No bus", area="Tabarbour", arrival="08:30")
        response = self.allocate(budget="0", drivers="0")
        self.assertIn(b"0.0% (0/1)", response.data)
        self.assertIn(b"Not applicable", response.data)

    def test_policies_respect_budget_capacity_and_consent(self):
        rng = random.Random(42)
        for scenario in range(12):
            requests = [
                {"id": i, "bus": rng.choice((True, False)),
                 "full_fare": rng.choice((True, False)),
                 "window": rng.choice(WINDOWS), "credits_used": rng.randrange(2)}
                for i in range(10)
            ]
            budget = rng.randrange(7) * 1000
            cap = rng.randrange(2)
            capacity = {window: rng.randrange(4) for window in WINDOWS}
            for policy in (optimize, first_come):
                with self.subTest(scenario=scenario, policy=policy.__name__):
                    assignments = policy(requests, budget, cap, capacity)
                    self.assertLessEqual(summarize(requests, assignments)["spent"], budget)
                    for window in WINDOWS:
                        rides = sum(
                            item["id"] in assignments and item["window"] == window
                            for item in requests
                        )
                        self.assertLessEqual(rides, capacity[window])
                    for item in requests:
                        status = assignments.get(item["id"])
                        if status == "credit":
                            self.assertLess(item["credits_used"], cap)
                        elif status == "full":
                            self.assertTrue(item["full_fare"])

    def test_request_duplicate_and_full_fare(self):
        self.post("/reset", mode="empty")
        response = self.post(
            "/requests", name="Test Student", area="Tabarbour",
            arrival="08:30", full_fare="yes",
        )
        self.assertIn(b"awaiting the cutoff", response.data)
        self.post("/requests", name="test student", area="Tabarbour", arrival="08:30")
        self.assertEqual(len(self.trips()), 1)
        self.allocate(budget="0", drivers="1")
        self.assertEqual(self.trips()[0]["outcome"], "full")

    def test_no_driver_and_no_consent(self):
        for drivers in ("0", "1"):
            with self.subTest(drivers=drivers):
                self.post("/reset", mode="empty")
                self.post("/requests", name="No Consent", area="Tabarbour", arrival="08:30")
                self.allocate(budget="0", drivers=drivers)
                self.assertEqual(self.trips()[0]["outcome"], "unconfirmed")

    def test_views_validation_and_csrf(self):
        for view in ("home", "student", "ops", "results"):
            self.assertEqual(self.client.get("/?view=" + view).status_code, 200)
        self.assertEqual(self.client.get("/?view=invalid").status_code, 404)
        self.post("/requests", name="", area="Invalid", arrival="25:00")
        self.assertEqual(len(self.trips()), 7)
        self.assertEqual(self.client.post("/reset", data={"mode": "empty"}).status_code, 400)


if __name__ == "__main__":
    unittest.main()
