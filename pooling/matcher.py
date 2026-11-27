"""Real-time insertion: place one new request into the best open group, or open a new one."""
from collections.abc import Sequence
from dataclasses import dataclass

from pooling.model import GroupPlan, Rider, evaluate


@dataclass(frozen=True)
class OpenGroup:
    group_id: str
    plan: GroupPlan


@dataclass(frozen=True)
class Insertion:
    group_id: str | None  # None means "open a new group"
    plan: GroupPlan


def insert(open_groups: Sequence[OpenGroup], rider: Rider) -> Insertion:
    """Join the feasible group that adds the fewest km (ties: fuller group, then earlier id).

    `evaluate` re-checks every existing rider, so a newcomer can never push an earlier
    rider past their detour or savings limit, or above a confirmed quote.
    """
    best_key, best = None, None
    for group in open_groups:
        plan = evaluate(group.plan.riders + (rider,))
        if plan is None:
            continue
        key = (round(plan.route_km - group.plan.route_km, 6), -len(group.plan.riders), group.group_id)
        if best_key is None or key < best_key:
            best_key, best = key, Insertion(group.group_id, plan)
    if best is not None:
        return best
    solo = evaluate([rider])
    if solo is None:
        raise ValueError(f"Request {rider.request_id} is not valid on its own.")
    return Insertion(None, solo)
