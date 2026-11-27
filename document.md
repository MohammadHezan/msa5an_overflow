# Campus Connect project document

## Product and first milestone

Campus Connect is a proposed Jeeny feature for shared rides home from campus. A student books a ride before class ends with a name, class end time, drop-off area and an optional women-only preference. After booking closes, Campus Connect groups students heading the same direction at about the same time into as few cars as possible. Each student then reviews a plan with a meeting gate, pickup time, the other riders, the drop-off order, and the price for their own share compared with riding alone. The student confirms or declines. If someone declines, the remaining riders in that car see the updated plan and confirm again.

The pitch deck's first pilot covers one Amman campus. Sara's after-class ride home is the main demo story: her class ends at 16:00, she shares a women-only car with Rama and Huda from the main gate at 16:15, and pays JOD 1.67 instead of JOD 4.50 alone. Record interviews, campus selection and business assumptions in [agent.md](agent.md).

The first mobile milestone is one demo student booking from a physical phone, an operator running matching in the web dashboard, and the same phone showing the student's plan so they can confirm or decline it. The ten-student sample afternoon remains the repeatable demonstration.

## How the current demo works

### Booking

- A batch covers one trip date, tomorrow in `Asia/Amman`. Each browser session owns one batch. The app opens with the ten-student sample afternoon, or the team can start an empty batch.
- A request has a name (1–40 characters), a class end time between 08:00 and 21:00, a drop-off from the preset list, whether the student is a woman, and whether she wants women-only matching. Only women students can choose women-only matching.
- Names are unique within a batch. A batch accepts up to 40 requests. Once matching runs, the batch is closed to new requests.

### Matching

A car is valid only if all of these hold for every rider (rules and limits live in `pooling/`; `sharing.py` adapts them to this app):

1. **Same meeting gate.** Each corridor (West, North, South, East) has a gate. Distances follow the corridor: a stop's km from campus, the km difference along one corridor, or via campus between corridors.
2. **Close class end times.** Class end times in one car are at most 20 minutes apart.
3. **Women-only respected.** If anyone in the car asked for women-only matching, every rider must be a woman student.
4. **Seats.** A car holds up to 4 students.
5. **Short detour.** Nobody rides more than min(1.5 × their own km, their own km + 4 km).
6. **Real saving.** Every rider in a shared car pays at most 80% of their solo fare.

OR-Tools CP-SAT considers every valid car of up to 4 students and assigns each student to exactly one car, using the fewest total car-km and then the fewest cars. A student with no valid partner gets a car alone and is offered a solo ride. A car is labelled women-only when all riders are women and at least one asked for it. [Google OR-Tools CP-SAT](https://developers.google.com/optimization/cp)

### Pickup time and drop-off order

- Pickup is at the corridor's gate, 15 minutes after the latest class end in the car, rounded up to the next 5 minutes.
- Drop-offs follow the shortest route, which along one corridor is nearest stop first.

### Pricing

All amounts are in fils (1 JOD = 1,000 fils). Distances and fares are simulated.

| Rule | Value |
| --- | --- |
| Solo fare | LTRC smart-app tariff (11 May 2026): 468 fils + 336 fils per km to the student's drop-off |
| Shared car fare | One regular ride at the same tariff over the whole route: 468 + 336 × route km |
| Each rider's share | Car fare × the rider's km ÷ total km of all riders, with largest-remainder rounding so the shares add up to the car fare exactly |
| When a student shares | Only if every rider saves at least 20% versus riding alone and no rider's in-car distance exceeds min(1.5 × own km, own km + 4 km) |

Example: Sara (Dabouq, 12 km), Rama (Al Bayader, 14 km) and Huda (Wadi As-Seer, 16 km) share a West car. The car fare is 468 + 336 × 16 = 5,844 fils. Sara pays 5,844 × 12/42 = 1,670 fils instead of 4,500 alone. Rama pays 1,948 instead of 5,172, and Huda pays 2,226 instead of 5,844. Everyone saves about 63%.

The booking page shows each drop-off's solo fare and a sample share for three riders before the student books.

### Review and confirm

Each student's status is one of:

| Status | Meaning |
| --- | --- |
| `waiting` | Booked; matching has not run. |
| `review` | Matched into a shared car; the plan needs the student's confirmation. |
| `no_match` | No compatible partner; a solo ride is offered at the solo fare. |
| `confirmed` | The student confirmed the current shared plan. |
| `solo_confirmed` | The student confirmed a solo ride. |
| `changed` | The student confirmed earlier, but another rider left and the share, pickup time or rider count changed. They must confirm again. |
| `declined` | The student left the ride. Their seat is removed and the car is re-planned for the remaining riders. |

A confirmation records the plan the student saw (share, pickup time and rider count). If the plan changed before the confirmation arrives, the app rejects it and shows the updated plan. If a declined rider leaves one student in a car, that student is offered a solo ride.

### Sample afternoon

The fixture produces five cars:

| Car | Riders and share (solo fare) |
| --- | --- |
| West · Main gate · 16:15 · women-only | Sara 1.67 (4.50), Rama 1.95 (5.17), Huda 2.23 (5.84) |
| West · Main gate · 16:20 | Kareem 3.16 alone. He matches by direction and time, but the car above is women-only. |
| North · North gate · 16:35 | Lina 0.57 (1.48), Omar 1.34 (2.82), Yazan 1.91 (3.83) |
| South · Main gate · 13:25 | Leen 1.66 (2.82), Dana 2.84 (4.50) |
| East · East gate · 18:15 | Zaid 4.84 alone. No one else heads east near 18:00. |

## Current implementation and proposed split

| Component | Today | First Expo milestone |
| --- | --- | --- |
| Student experience | Flask renders the Book, Matching and Trips views in `templates/index.html` with `static/`. | Add a TypeScript React Native app under `mobile/`. It owns booking, the plan review screen and confirm/decline. It reads fares and plans from the backend. |
| Backend | `app.py` serves HTML form routes and stores batches in SQLite. A browser session owns its batch. | Add a versioned JSON API that calls the same functions. The phone and the operator must use the same batch. Keep Flask and SQLite for the single-instance demo. |
| Operations | The Matching view runs matching for the batch and the Trips view lists every car. | Keep the dashboard on Replit. Connect it to the same batch and rules as the Expo app. |
| Rules | `sharing.py` holds corridors, stops, fare rules, CP-SAT grouping and the per-car price split. | Reuse it unchanged from both the HTML routes and the JSON API. |

Keep one repository. `mobile/` will be a separate Expo project with its own dependencies. Keep the Flask files at the repo root during the first integration so the Replit Run command stays usable.

## Task ownership and build order

These are proposed owners and estimates in focused person-hours. The first demo is **11–17 person-hours**, or roughly **7–11 working hours on the critical path** if the mobile, backend and scenario tasks run in parallel. Expo account setup, device access and deployment delays can extend that estimate.

| Task | Proposed owner | Estimate | Depends on | Done when |
| --- | --- | ---: | --- | --- |
| T0. Agree on the contract and demo story | All, with Mohammad coordinating | 1–2 h | — | Agree on the campus, drop-offs, demo roles, request fields, API errors, and the device for rehearsal. |
| B1. Build the shared JSON API | Mohammad | 3–4 h | T0 | Health, join, fare estimates, booking, matching, plan, confirm and decline endpoints work on the same batch as the web dashboard. Repeating matching returns the saved cars. |
| M1. Build the Expo student app | Laith | 3–4 h | T0 | Book, plan review and confirm/decline screens work with sample API responses. Handle the `changed` status, delayed responses, offline errors and retries. |
| S1. Build repeatable scenarios | Abdallatif | 2–3 h | T0 | Replay the sample afternoon and run seeded scenarios: more students per corridor, spread-out class end times, many women-only requests, and a decline that leaves one rider. Report cars used and total paid versus riding alone. |
| I1. Connect the phone to Replit | Mohammad and Laith | 2–3 h | B1, M1 | A physical phone calls the Replit backend over HTTPS. Matching in the dashboard changes the plan seen on that phone, and a decline on another device shows `changed` on the phone. |
| T1. Rehearse the judging flow | All, with Abdallatif coordinating | 1 h | I1, S1 | Run the mobile and web flow, replay the sample afternoon, and record the device, branch and expected screenshots. |

First agree on T0, then work in parallel from the same example responses. Use the current web demo as a rehearsal fallback while integrating Expo.

## Proposed API contract

This is the implementation target. Each JSON endpoint mirrors a current Flask route so the web form and the API share one code path.

| Endpoint | Current Flask route | Used by | Expected behavior |
| --- | --- | --- | --- |
| `GET /api/v1/health` | — | Device and operators | Reports whether the backend can respond. The phone calls this first to verify the configured origin. |
| `POST /api/v1/batches` | `POST /reset` (`mode=seeded` or `empty`) | Operations | Creates a batch for tomorrow, empty or loaded with the sample afternoon, and returns its ID and a short-lived student join code. |
| `POST /api/v1/demo-sessions/join` | — (today the browser session owns the batch) | Student app | Exchanges the join code for a student token scoped to that batch. |
| `GET /api/v1/stops` | Data rendered by `GET /` (`corridors`, `estimates`, `rules`) | Student app | Returns corridors, gates, drop-offs with km, each drop-off's solo fare and sample share, and the matching rules. |
| `GET /api/v1/batches/{id}` | `GET /?view=match` and `GET /?view=trips` | Operations | Returns the trip date, whether matching ran, every rider with status, every car's plan, and the summary totals. |
| `POST /api/v1/batches/{id}/riders` | `POST /requests` | Student app | Saves one request with `name`, `classEnd`, `stop`, `woman`, `womenOnly` and a client-generated `clientRequestId`. Returns the rider ID and `waiting`. |
| `POST /api/v1/batches/{id}/matching` | `POST /match` | Operations | Groups all riders into cars and closes the batch. On repeat it returns the saved cars without regrouping. |
| `GET /api/v1/riders/{id}` | `GET /?rider={id}` | Student app | Returns the student's status, and when matched: gate, pickup time, other riders' first names, drop-off order, share, solo fare and the plan `signature`. |
| `POST /api/v1/riders/{id}/confirm` | `POST /riders/{id}/confirm` | Student app | Requires the `signature` the student reviewed. Returns `confirmed` or `solo_confirmed`, or `409 plan_changed` with the new plan. |
| `POST /api/v1/riders/{id}/decline` | `POST /riders/{id}/decline` | Student app | Removes the student from the car. Remaining riders are re-planned and any earlier confirmations become `changed`. |

- Return dates with an ISO 8601 offset and show times in `Asia/Amman`. Send money in integer fils with explicit `JOD` currency.
- Use the statuses in the table above. Mobile refreshes from the server after matching, after a confirm or decline, and when the plan screen reopens.
- A network retry with the same `clientRequestId` and payload returns the original rider. A different request with an existing name in the batch returns `409`. Include a stable JSON error code for a closed batch (`batch_matched`), a full batch, a duplicate name, invalid input (including women-only for a student who is not a woman), a changed plan, and failed authorization.
- The operator creates the batch and runs matching. A student token grants access only to that student's plan and actions. Do not expose other riders' surnames or drop-off details beyond what the plan shows. Keep credentials out of query strings and logs. Today's form routes use a CSRF token in the session; the JSON API needs bearer tokens instead.
- Keep the fare and matching rules on the backend. Run booking, matching, confirm and decline in one transaction each, as the form routes already do, so a retry or concurrent action cannot double-book or confirm a stale plan.

### As built (B1)

The API lives in `api.py`; the HTML routes in `app.py` and the API both call the booking, matching, confirm and decline functions in `store.py`.

- **Tokens.** `POST /api/v1/batches` (`{"mode": "seeded" | "empty"}`) returns the batch `id`, a six-character `joinCode` valid for 3 hours, and an `operatorToken`. The web dashboard shows the join code for its own batch on the Matching view, so a phone can join the batch the operator is running. `POST /api/v1/demo-sessions/join` (`{"joinCode"}`) returns a student `token`. Send tokens as `Authorization: Bearer <token>`.
- **Scope.** A student token can book once; it is then bound to that rider and can only read, confirm or decline that rider. An operator token can read the batch, run matching, and act on any rider in its batch.
- **Retries.** Repeating a booking with the same token, `clientRequestId` (8–64 letters, digits, `-`, `_`) and payload returns the original rider with `200` (the first booking returns `201`). Decline is also safe to repeat.
- **Money and time.** Money is `{"fils": 1500, "currency": "JOD"}`. Plans include `pickupTime` (`16:15`) and `pickupAt` with the Amman offset.
- **Errors.** `{"error": {"code", "message"}}` with codes `invalid_input` (400), `unauthorized` (401), `forbidden` (403), `not_found` / `join_code_invalid` (404), and `batch_matched`, `batch_full`, `batch_empty`, `duplicate_name`, `already_booked`, `request_conflict`, `not_matched`, `rider_declined`, `plan_changed` (409). `plan_changed` also returns the current plan under `rider`.

## Repeatable scenarios

The sample afternoon is the fixed regression check: ten students, five cars, Sara's share JOD 1.67 versus JOD 4.50 alone, and Kareem offered a solo ride because the West car is women-only.

For additional scenarios, generate requests from a recorded random seed. Vary the number of students per corridor, how spread out class end times are, the share of women-only requests, and declines after matching. Report the number of cars, the share of students who found a match, the total paid versus everyone riding alone, and each student's saving. Label all results **simulated**; real distances, fares, demand and decline rates are pilot questions.

## Environment and running the project

| Location | Name | Purpose |
| --- | --- | --- |
| Backend root `.env` | `PORT` | Flask port. The Replit config currently maps port 5000. |
| Backend root `.env` or Replit Secrets | `SESSION_SECRET` | Signs Flask browser sessions. Set a unique value for your deployment. The actual local file is ignored by Git. |
| Future `mobile/.env` | `EXPO_PUBLIC_API_URL` | Public HTTPS origin used by the Expo app, with no API path. Copy `mobile/.env.example` when the Expo project is scaffolded. |

**Current backend.** Copy [the backend template](.env.example) to `.env` on a new checkout. Run `python -m pip install -r requirements.txt` and then `python app.py`, or click **Run** in Replit. The app loads `.env` at startup and existing process variables take precedence. Configure backend secrets via Replit Secrets. [Replit Secrets](https://docs.replit.com/core-concepts/project-editor/app-setup/secrets)

**Expo after M1.** Scaffold a TypeScript Expo app under `mobile/` with an SDK compatible with the test device. Start Metro from that directory with `npx expo start`. Use Expo Go if the chosen modules are supported on the test device, or use a development build. Set the backend origin separately and verify the phone can reach `/api/v1/health` over HTTPS before testing the flow. A phone's `localhost` points to the phone. [Expo setup](https://docs.expo.dev/get-started/create-a-project/) · [Expo development workflows](https://docs.expo.dev/develop/development-builds/development-workflows/) · [React Native networking](https://reactnative.dev/docs/network.html)

**Client settings are visible.** Expo embeds `EXPO_PUBLIC_*` values in the bundle. Keep server secrets out of them. [Expo environment variables](https://docs.expo.dev/guides/environment-variables/)

## Expo milestone acceptance

- [ ] Open the app on a physical device and connect to the backend at its HTTPS origin.
- [ ] Join a batch, see the solo fare and sample share for a drop-off, book once, and keep the same request after a network retry.
- [ ] Run matching in the web dashboard. Refresh or reopen the phone app and see the gate, pickup time, other riders, drop-off order and share versus solo fare.
- [ ] Confirm the plan. Decline as another rider in the same car from the dashboard or a second device, and see the phone switch to **plan changed** and ask to confirm again.
- [ ] Check a women-only request is never matched with a man, a solo-ride offer, a closed batch, and no access to another student's plan.
- [ ] Replay the sample afternoon and confirm five cars and Sara's JOD 1.67 share.

Record agreed product decisions in [agent.md](agent.md). Update this document when the API, fare rules, estimates or repository layout change.
