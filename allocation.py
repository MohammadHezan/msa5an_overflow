from ortools.sat.python import cp_model

CREDIT = 1500  # Fils
WINDOWS = ("Morning", "Midday", "Evening")


def optimize(requests, budget, cap, capacity):
    if not requests:
        return {}

    model = cp_model.CpModel()
    rides = [model.new_bool_var(f"ride_{i}") for i in range(len(requests))]
    credits = [model.new_bool_var(f"credit_{i}") for i in range(len(requests))]
    for item, ride, credit in zip(requests, rides, credits):
        model.add(credit <= ride)
        if item["bus"] or item["credits_used"] >= cap:
            model.add(credit == 0)
        if not item["full_fare"]:
            model.add(ride == credit)

    model.add(sum(credits) * CREDIT <= budget)
    for window in WINDOWS:
        model.add(sum(ride for item, ride in zip(requests, rides) if item["window"] == window) <= capacity[window])

    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    # Optimize in order so fairness and optional rides can't reduce on-time arrivals.
    objectives = (
        sum(ride for item, ride in zip(requests, rides) if not item["bus"]),
        -sum(credits),
        sum(rides),
        sum((len(requests) - i) * ride for i, ride in enumerate(rides)),
        sum((len(requests) - i) * credit for i, credit in enumerate(credits)),
    )
    for score in objectives:
        model.maximize(score)
        if solver.solve(model) != cp_model.OPTIMAL:
            raise RuntimeError("The allocator could not complete this batch.")
        model.add(score == solver.value(score))

    return {
        item["id"]: "credit" if solver.value(credit) else "full"
        for item, ride, credit in zip(requests, rides, credits)
        if solver.value(ride)
    }


def first_come(requests, budget, cap, capacity):
    remaining = capacity.copy()
    assignments = {}
    for item in requests:
        window = item["window"]
        if not remaining[window]:
            continue
        if budget >= CREDIT and item["credits_used"] < cap:
            assignments[item["id"]] = "credit"
            budget -= CREDIT
        elif item["full_fare"]:
            assignments[item["id"]] = "full"
        else:
            continue
        remaining[window] -= 1
    return assignments


def summarize(requests, assignments):
    arrivals = sum(item["bus"] or item["id"] in assignments for item in requests)
    spent = sum(status == "credit" for status in assignments.values()) * CREDIT
    return {"arrivals": arrivals, "unserved": len(requests) - arrivals, "spent": spent}
