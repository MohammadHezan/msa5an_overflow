# Replit brief 05: friends ride in one car, also after matching

Do not change `pooling/` pricing rules. Run `python -m pytest` before and after. Commit after each phase.

## Goal
A group of friends (2–4) books together and always gets **one car**, even when the operator already ran matching for the batch. The ride option follows the passenger's gender:

| Passenger | Options shown |
|---|---|
| Man | Anyone · Men only |
| Woman | Anyone · Women only |

**Demo user is a man**: default profile "Omar K", gender man. Women only is hidden for him.

## What exists (keep it)
- `store.insert_request` with `friends = {"mode": "start", "open": bool}` or `{"mode": "join", "code": "GR-48"}`, `friend_groups` table, `group_problem`, max 4 seats.
- Batch matching keeps friends together; closed groups take no strangers.
- Captain choice: a women-only car gets a woman captain when one is free.

**The gap:** after matching ran, `insert_request` raises `batch_matched` ("friends can't book together now"). Remove that block and add the late-group flow below.

## PHASE 1: demo profile and ride option
- Yalla home gets a small "I am: [Man] [Woman]" switch (demo only). Default **Man**, name "Omar K". It sets `session["student_gender"]` and `session["yalla_name"]`.
- Preferences screen (07): show Anyone + the option for the user's gender only. Under Men only / Women only: "Matching may take longer."
- Backend already rejects `men` for a woman and `women` for a man. Keep that.

## PHASE 2: group rules (start and join)
- Creator: "Start a group" → code `GR-xx`, choose **open** (strangers may fill empty seats) or **closed**.
- The group's ride option is the creator's choice. A friend who joins must fit it:
  - Men-only group: only men can join. Error: "This group is men only."
  - Women-only group: only women can join. Error: "This group is women only."
  - A man who picked Men only cannot join a group that has a woman (and the same for women). Error: "Your ride option doesn't fit this group."
- Every friend books from their own phone with their own street stop. All must share direction and corridor, and class ends within 10 min (`group_problem` already checks; show its message).
- 5th person: "This group is full (4 students)."

## PHASE 3: late group (after matching ran)
Before matching: unchanged, the optimizer places the whole group.

After matching, the group waits in a **lobby** until it is complete, then is placed at once:
1. **Lobby screen** (new, Jeeny style): "Waiting for friends · 2 of 4", the code GR-xx big with Copy/Share, member avatars with names, and a "We're all here, find our car" button for the creator. Also auto-places when 4 join or after 10 min (demo clock).
2. **Place the group, in this order:**
   1. **Open group only:** an existing car that has not left, is not a closed group, has free seats ≥ group size, and passes `model.evaluate` with everyone (detour, savings, gender option, confirmed shares never rise). Pick the one with the fewest added km.
   2. Otherwise a **new car for the group**. Open group: it accepts later late riders (same path as "wait for a match").
   3. Captain: `assign_captain(db, batch, car, only)` with the group's option (women → woman captain if free; men/anyone → man captain preferred).
3. Fare: one car fare, split by km ridden per friend (the brief 02 per-km split). Each friend sees their own share and a 2-minute confirm hold.
4. **Never split the group.** If no car fits and the group is big, still give it its own car.
5. A friend cancels: the others stay in the car and are re-priced. A confirmed share never goes up (Jeeny covers the difference). The group stays together.

API: add `POST /api/v1/groups/{code}/ready` (creator only, idempotent with `clientRequestId`) and include `group: {code, open, option, members:[{name, joined}], status: "lobby" | "placed"}` in the rider's plan response.

## PHASE 4: screens to update
- 07 preferences: gender-based option (Phase 1).
- 10 matched group: a "Friends · GR-xx" tag on the friends, strangers shown as "Student".
- 11 fare: every friend's km and share.
- 13 captain pickup: each friend sees their own street pickup.
- New lobby screen from Phase 3.

## Done when (Preview at 390 px)
- As Omar (man): preferences show Anyone + Men only, no Women only.
- Omar starts a closed men-only group after "Run matching", 2 friends join, creator taps "find our car" → all 3 in one new car with one fare split by km, captain shown.
- A woman tries to join that group → "This group is men only."
- An open group of 2 fills a free seat pair in an existing car when one fits.
- Tests (add): late group gets one car; men-only group refuses a woman; closed group takes no strangers; open group joins an existing car only if `evaluate` passes; a friend's cancel never raises a confirmed share; group of 4 is full.
- `python -m pytest` passes. Update `replit.md`.
