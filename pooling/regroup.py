"""Lock-time regroup: re-partition riders into the cheapest set of feasible groups (CP-SAT)."""
from collections.abc import Iterable, Sequence

from ortools.sat.python import cp_model

from pooling import config
from pooling.model import GroupPlan, basic_ok, evaluate


def _feasible_groups(riders) -> dict[frozenset[str], GroupPlan]:
    """Every valid car of 1..MAX_RIDERS riders.

    A group is only generated if all its sub-groups pass the hereditary rules (seats, meeting point,
    gender, window): those hold for every subset of a valid car. Detour, savings and quotes are
    checked on the full group only, because a pair can fail the savings floor while a trio passes.
    """
    by_id = {r.request_id: r for r in riders}
    basic: set[frozenset[str]] = set()
    feasible: dict[frozenset[str], GroupPlan] = {}
    level = [frozenset([i]) for i in sorted(by_id)]
    for k in range(1, config.MAX_RIDERS + 1):
        next_level = []
        for key in level:
            if k > 1 and any(key - {x} not in basic for x in key):
                continue
            members = [by_id[i] for i in sorted(key)]
            if basic_ok(members) is None:
                continue
            basic.add(key)
            next_level.append(key)
            plan = evaluate(members)
            if plan is not None:
                feasible[key] = plan
        level = sorted({key | {x} for key in next_level for x in by_id if x > max(key)}, key=sorted)
    return feasible


def cost(plan: GroupPlan) -> int:
    """What the plan costs in the objective: the car fare, plus a penalty for a student riding alone."""
    return plan.car_fare + (config.SOLO_PENALTY if len(plan.riders) == 1 else 0)


def _allowed(key: frozenset[str], together: Sequence[frozenset[str]], closed: set[frozenset[str]]) -> bool:
    for group in together:
        if key & group and not group <= key:
            return False  # a friends group rides all together or not at all
        if group in closed and key & group and key != group:
            return False  # a closed group takes no strangers
    return True


def _greedy(keys, plans, rider_ids) -> list[frozenset[str]]:
    """A valid partition, cheapest cost per rider first. Used as the solver hint and the fallback."""
    left, chosen = set(rider_ids), []
    for key in sorted(keys, key=lambda k: (cost(plans[k]) / len(k), sorted(k))):
        if key <= left:
            chosen.append(key)
            left -= key
    return chosen if not left else []


def regroup(current: Sequence[GroupPlan], together: Iterable[frozenset[str]] = (),
            closed: Iterable[frozenset[str]] = (), solver_seconds: float | None = None) -> list[GroupPlan]:
    """Minimize Σ car fare + SOLO_PENALTY × riders alone, in one objective.

    `together`: groups of rider ids (friends) that must share one car. Groups in `closed` take no
    one else. Keeps the best solution found when the time limit hits; never returns a plan that
    costs more than `current`.
    """
    riders = [r for plan in current for r in plan.riders]
    if not riders:
        return []
    ids = {r.request_id for r in riders}
    by_id = {r.request_id: r for r in riders}
    together = [frozenset(g) & ids for g in together]
    together = [g for g in together if len(g) > 1]
    closed = {frozenset(g) & ids for g in closed}

    feasible = _feasible_groups(riders)
    for group in together:
        if group not in feasible:  # Friends ride together even if the group fails the savings floor
            plan = evaluate([by_id[i] for i in sorted(group)], strict=False)
            if plan is not None:
                feasible[group] = plan
    together = [g for g in together if g in feasible]  # an impossible group (validated on join) is not forced
    keys = [key for key in feasible if _allowed(key, together, closed)]

    model = cp_model.CpModel()
    use = {key: model.new_bool_var(f"g{i}") for i, key in enumerate(keys)}
    for rid in ids:
        model.add_exactly_one(use[key] for key in keys if rid in key)
    model.minimize(sum(cost(feasible[key]) * use[key] for key in keys))
    hint = set(_greedy(keys, feasible, ids))
    for key in keys:
        model.add_hint(use[key], key in hint)

    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = config.SOLVER_WORKERS
    solver.parameters.max_time_in_seconds = config.SOLVER_SECONDS if solver_seconds is None else solver_seconds
    status = solver.solve(model)
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        chosen = [feasible[key] for key in keys if solver.value(use[key])]
    elif hint:
        chosen = [feasible[key] for key in hint]
    else:
        return list(current)

    current_ok = all(p.ids in feasible and _allowed(p.ids, together, closed) for p in current)
    if current_ok and sum(map(cost, chosen)) > sum(map(cost, current)):
        return list(current)
    return chosen

