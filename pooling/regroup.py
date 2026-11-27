"""Lock-time regroup: re-partition riders into the cheapest set of feasible groups (CP-SAT)."""
from collections.abc import Sequence
from itertools import combinations

from ortools.sat.python import cp_model

from pooling import config
from pooling.model import GroupPlan, evaluate


def _feasible_groups(riders) -> dict[frozenset[str], GroupPlan]:
    by_id = {r.request_id: r for r in riders}
    feasible: dict[frozenset[str], GroupPlan] = {}
    for k in range(1, config.MAX_RIDERS + 1):
        for combo in combinations(sorted(by_id), k):
            key = frozenset(combo)
            # A group can only work if every smaller group inside it works (Alonso-Mora pruning).
            if k > 1 and any(key - {x} not in feasible for x in key):
                continue
            plan = evaluate([by_id[i] for i in combo])
            if plan is not None:
                feasible[key] = plan
    return feasible


def regroup(current: Sequence[GroupPlan]) -> list[GroupPlan]:
    """Minimize total car-km, then the number of cars. Never returns a worse answer than `current`."""
    riders = [r for plan in current for r in plan.riders]
    if not riders:
        return []
    feasible = _feasible_groups(riders)
    keys = list(feasible)

    model = cp_model.CpModel()
    use = [model.new_bool_var(f"g{i}") for i in range(len(keys))]
    for r in riders:
        model.add_exactly_one(use[i] for i, key in enumerate(keys) if r.request_id in key)

    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.max_time_in_seconds = config.SOLVER_SECONDS
    objectives = (
        sum(round(feasible[key].route_km * 1000) * use[i] for i, key in enumerate(keys)),
        sum(use),
    )
    for score in objectives:
        model.minimize(score)
        status = solver.solve(model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return list(current)
        model.add(score == round(solver.objective_value))

    chosen = [feasible[key] for i, key in enumerate(keys) if solver.value(use[i])]
    if sum(p.route_km for p in chosen) > sum(p.route_km for p in current) + 1e-9:
        return list(current)
    return chosen
