import math

from pooling import config
from simulation import COUNTS, METHODS, _scenario, run_simulation


def test_simulation_compares_three_methods_over_thirty_paired_seeds():
    original_budget = config.SOLVER_SECONDS
    result = run_simulation()
    assert config.SOLVER_SECONDS == original_budget
    assert result["seeds"] == 30
    assert result["counts"] == (8, 16, 24, 32)
    for n in COUNTS:
        assert _scenario(n, 0) == _scenario(n, 0)
        assert {r.direction for r in _scenario(n, 0)} == {"from_campus", "to_campus"}
        assert set(result["summary"][n]) == set(METHODS)
        for method in METHODS:
            metrics = result["summary"][n][method]
            assert len(metrics) == 7
            for metric in metrics.values():
                assert all(math.isfinite(value) for value in metric.values())
                assert metric["min"] <= metric["mean"] <= metric["max"]
            assert 0 <= metrics["matched_pct"]["mean"] <= 100
            assert 0 <= metrics["walk_m"]["mean"] <= 200
        alone = result["summary"][n]["alone"]
        assert alone["cars"]["mean"] == n
        assert alone["matched_pct"]["mean"] == 0
        assert alone["km_saved_pct"]["mean"] == 0
