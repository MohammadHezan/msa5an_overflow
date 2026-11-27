"""Scenario tour: one demo batch where every student in "View the app as" shows a different situation.

The batch is built with the same store functions the app uses (confirm, decline, seat holds,
"wait" and "go now" choices, late requests, friends groups), so each screen is a real state of the
app rather than a mock-up. Only the clock is set by hand: a seat hold or a wait that already ran
out, and "go now" cars that left a few minutes (or an hour) ago.
"""
from datetime import timedelta

# name, class end, neighborhood, gender, preference, direction, class start
# Morning trips toward campus, so all class ends are empty (like the morning sample).
BASE_WAVE = (
    ("Hadi", "", "Dabouq", "man", "mixed", "to_campus", "08:00"),
    ("Samir", "", "Khalda", "man", "mixed", "to_campus", "08:05"),
    ("Salma", "", "Abu Nseir", "woman", "women", "to_campus", "08:00"),
    ("Hala", "", "Shafa Badran", "woman", "women", "to_campus", "08:05"),
    ("Tala", "", "Al Jubeiha", "woman", "women", "to_campus", "08:05"),
    ("Majd", "", "Tabarbour", "man", "mixed", "to_campus", "08:00"),
    ("Laith", "", "Marka", "man", "mixed", "to_campus", "08:05"),
    ("Rami", "", "Um Al Summaq", "man", "mixed", "to_campus", "09:30"),
    ("Bana", "", "Abdoun", "woman", "mixed", "to_campus", "08:05"),
    ("Rawan", "", "Sweileh", "woman", "mixed", "to_campus", "10:00"),
    ("Omar", "", "Wadi As-Seer", "man", "mixed", "to_campus", "07:00"),
    ("Nada", "", "Tla' Al Ali", "woman", "mixed", "to_campus", "11:00"),
)
# Booked after matching ran (late requests), in this order
LATE = {
    "Lama": ("", "Tabarbour", "woman", "mixed", "to_campus", "08:05"),
    "Jana": ("", "Al Bayader", "woman", "mixed", "to_campus", "08:30"),
}

# What each button shows: (short label for the button, one sentence for the presenter)
LABELS = {
    "Hadi": ("Seat held · confirm", "Matched with Samir. His seat is held for 2 minutes: confirm, decline, or move the clock and lose it."),
    "Samir": ("Confirmed shared ride", "Confirmed and holds a ride code for the captain. If Hadi's hold runs out, Samir's plan changes."),
    "Salma": ("Women-only car", "Women-only car with a woman captain. Salma confirmed after Tala left, so her plan is current."),
    "Hala": ("Plan changed · reconfirm", "Hala confirmed, then Tala left the car. Her old confirmation no longer matches, so she reviews the new plan and confirms again."),
    "Tala": ("Left the ride", "Tala declined her seat. The others were re-planned without her."),
    "Majd": ("Seat released", "Majd did not confirm within 2 minutes, so the seat was released and Laith's car was re-planned."),
    "Laith": ("Go now · on the way", "Left alone after Majd's seat was released, Laith chose option C: the car left and is open to share."),
    "Lama": ("Joined a car on the way", "Booked after matching. Laith's car had not passed her street, so she was picked up on its route."),
    "Rami": ("No match · choose A/B/C", "No one from his area reaches campus near 09:30. He picks: ride alone, wait, or go now."),
    "Bana": ("Waiting for a match", "Chose option B. Book a new student to Abdoun or South, or move the clock to run the wait out."),
    "Nada": ("Wait ran out", "Waited the full 10 minutes and no one booked. She is offered the lone-rider choices again."),
    "Rawan": ("Solo ride confirmed", "No match for 10:00, so she confirmed a regular ride alone at the solo fare."),
    "Omar": ("Ride ended · receipt", "Took a go-now car an hour ago. The ride ended and the price is final."),
    "Jana": ("Friends group lobby", "Started a friends group after matching. Friends join with her code before the lobby closes."),
}


def stage(db, batch_id):
    """Turn a freshly seeded scenario batch into the tour. Call inside a write transaction."""
    from store import (
        SEAT_HOLD, assign_captain, choose, clock, get_batch, insert_request, load_riders, release_expired_holds,
        respond_to_plan,
    )

    def riders():
        return {r["name"]: r for r in load_riders(db, get_batch(db, batch_id))[0]}

    def batch():
        return get_batch(db, batch_id)

    def confirm(name):
        rider = riders()[name]
        respond_to_plan(db, batch(), rider["id"], "confirm", rider["signature"])

    people = riders()
    cars = [["Hadi", "Samir"], ["Salma", "Hala", "Tala"], ["Majd", "Laith"],
            ["Rami"], ["Bana"], ["Rawan"], ["Omar"], ["Nada"]]
    at = clock(batch())
    hold = (at + SEAT_HOLD).isoformat()
    for car, names in enumerate(cars):
        for name in names:
            db.execute("UPDATE riders SET car = ?, hold_until = ? WHERE id = ?",
                       (car, hold if len(names) > 1 else None, people[name]["id"]))
    db.execute("UPDATE batches SET matched = 1 WHERE id = ?", (batch_id,))
    for car, names in enumerate(cars):
        assign_captain(db, batch_id, car, "women" if all(people[n]["preference"] == "women" for n in names) else None)

    confirm("Samir")                                    # Confirmed shared ride; Hadi keeps his seat hold

    confirm("Hala")                                     # Hala confirms the three-woman car...
    respond_to_plan(db, batch(), riders()["Tala"]["id"], "decline", None)  # ...then Tala leaves
    confirm("Salma")                                    # Salma confirms the updated two-woman car

    db.execute("UPDATE riders SET hold_until = ? WHERE id = ?",  # Majd's hold already ran out
               ((at - timedelta(seconds=30)).isoformat(), people["Majd"]["id"]))
    release_expired_holds(db, batch())

    choose(db, batch(), people["Laith"]["id"], "go")    # Laith, now alone, goes now open to share
    db.execute("UPDATE cars SET departed_at = ? WHERE batch = ? AND car = 2",
               ((at - timedelta(minutes=2)).isoformat(), batch_id))

    choose(db, batch(), people["Omar"]["id"], "go")     # Omar's go-now ride finished an hour ago
    db.execute("UPDATE cars SET departed_at = ? WHERE batch = ? AND car = 6",
               ((at - timedelta(minutes=70)).isoformat(), batch_id))

    confirm("Rawan")                                    # Solo ride confirmed

    choose(db, batch(), people["Bana"]["id"], "wait")   # Waiting for a match
    choose(db, batch(), people["Nada"]["id"], "wait")   # Waited, but the wait already ran out
    db.execute("UPDATE riders SET wait_until = ? WHERE id = ?",
               ((at - timedelta(minutes=1)).isoformat(), people["Nada"]["id"]))

    for name, row in LATE.items():                      # Late requests after matching
        friends = {"mode": "start", "open": True} if name == "Jana" else None
        class_end, stop, gender, preference, direction, class_start = row
        insert_request(db, batch(), name, class_end, stop, gender, preference, friends,
                       direction=direction, class_start=class_start)
