# Campus Connect project document

## Current implementation contract — Brief 02

The numbered briefs in `docs/replit-briefs/README.md` supersede the original planning assumptions below. The current demo supports both `to_campus` and `from_campus`, not only rides home.

- Locations are corridor + road km + side offset. Samples stay within ±1 km of a named stop, with 0–400 m offsets. Walking is at most 200 m at 1.4 m/s; excess adds a round-trip car turn-in.
- Homebound readiness is class end plus walking; campus-bound deadline is class start minus five minutes. Share only within one corridor/direction, ten-minute time gap, four seats, compatible gender preferences and existing detour limits.
- One street-car fare is 468 + round(336 × route km) integer fils. Start fare is equal; segments are split among occupants. Largest-remainder rounding conserves every fils, and solo caps apply. Shared riders save at least 25%; existing cars and friends groups can be repriced without the strict savings floor.
- Groups have up to four members and stay together. Closed groups take no strangers. Captains prefer women for women-only cars when available and get a Jeeny-paid 100 fils per extra rider.
- Holds last two demo-clock minutes. A confirmed share never rises: any shortfall is explicit Jeeny cover. Codes, signatures, retries and immediate SQLite transactions remain in use.
- Lone riders choose solo now, wait ten minutes, or go now open to sharing. A moving car collects later riders only at actual pickups still ahead; a campus student cannot join a homebound car that has left.
- Simulation uses 30 paired seeds at each of 8, 16, 24 and 32 riders. All three methods use identical scenarios/rules, reporting cars, km, km saved, match rate, per-rider saving, walk and extra in-car time, with means and ranges.

The older sample prices and fixed gate pickup times below are historical, not acceptance values for street-location matching.

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

Keep one repository. The first integration used a standalone `mobile/` Expo project. For Replit-hosted phone previews, that same app now lives in `artifacts/campus-connect/` in a pnpm workspace. Flask files and data remain at the repo root; the separate dashboard artifact runs them on port 5000.

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

### As built (Campus Connect step 1: student verification and campuses)

- **University discovery.** `GET /api/v1/universities?search=...` requires a bearer token and returns `id`, `name`, `city`, `campus`, `gate` and `available`. The seeded choices are Al-Balqa Applied University (Salt, available), University of Jordan (Amman, unavailable) and Yarmouk University (Irbid, unavailable). Search matches the name, city or campus; the query is limited to 100 characters.
- **Start verification.** `POST /api/v1/verification/start` accepts `universityId`, `email` and optional `firstName`. It rejects unavailable campuses and addresses that do not match the selected university's exact email domain. A successful response contains a masked `maskedEmail`, `expiresAt`, `resendAvailableAt` and `delivery: "console_demo"`. The six-digit code and address are logged locally for the demo; no email is sent. Expiry and resend timestamps are ISO 8601 values with the `Asia/Amman` offset.
- **Resend and confirm.** `POST /api/v1/verification/resend` replaces the current code and is limited by a 30-second cooldown. `POST /api/v1/verification/confirm` accepts the six-digit `code`; codes expire after five minutes, five incorrect submissions are allowed, and the next submission is locked until a new code is requested. Success returns a new `Bearer` student token, `nextScreen: "05"` and the verified profile. `GET /api/v1/me` reports the current student's verification state and next screen.
- **Booking requires verification.** `POST /api/v1/batches/{id}/riders` rejects a student token without a verified profile with `403 verification_required` (nothing is saved). For a verified student the rider name is the profile's first name; any `name` in the body is ignored. One request per verified student per batch: a second phone of the same student gets `409 already_booked`, while two different students with the same first name may both book. `clientRequestId` retries and `request_conflict` work as before.
- **Unavailable-campus requests.** `POST /api/v1/universities/{id}/notify` saves one notify-me request per student session and campus, and responds with `notificationRequested: true` and the toast message `"We'll keep you posted"`. It does not send a notification.
- **Persistence and privacy.** Student records, hashed verification challenges and campus notification requests are stored in the app's SQLite database. The code is stored as a keyed digest, not plaintext. Verification responses show only a masked email; the email is not returned by student profile endpoints. Other riders' plan details contain first names and stops only, not surnames, email addresses or phone numbers. Verification writes run within the same immediate SQLite transaction discipline as other batch actions. Shared API errors retain the `{"error": {"code", "message"}}` shape.
- **Phone flow.** After joining, the Expo student app shows campus search, notify-me for unavailable campuses, email entry, and the code screen with the masked address, expiry and resend countdowns. A confirmed code replaces the phone's stored token. A pending code is remembered across app restarts. Codes are still only printed in the backend console.

## Repeatable scenarios

The sample afternoon is the fixed regression check: ten students, five cars, Sara's share JOD 1.67 versus JOD 4.50 alone, and Kareem offered a solo ride because the West car is women-only.

For additional scenarios, generate requests from a recorded random seed. Vary the number of students per corridor, how spread out class end times are, the share of women-only requests, and declines after matching. Report the number of cars, the share of students who found a match, the total paid versus everyone riding alone, and each student's saving. Label all results **simulated**; real distances, fares, demand and decline rates are pilot questions.

## Environment and running the project

| Location | Name | Purpose |
| --- | --- | --- |
| Backend root `.env` | `PORT` | Flask port. The Replit config currently maps port 5000. |
| Backend root `.env` or Replit Secrets | `SESSION_SECRET` | Signs Flask browser sessions. Set a unique value for your deployment. The actual local file is ignored by Git. |
| `artifacts/campus-connect/.env` (optional) | `EXPO_PUBLIC_API_URL` | Explicit backend HTTPS origin, with no API path. Unset on Replit to use its automatically supplied backend domain. |

**Current backend.** Copy [the backend template](.env.example) to `.env` on a new checkout. Run `python -m pip install -r requirements.txt` and then `python app.py`, or click **Run** in Replit. The app loads `.env` at startup and existing process variables take precedence. Configure backend secrets via Replit Secrets. [Replit Secrets](https://docs.replit.com/core-concepts/project-editor/app-setup/secrets)

**Expo app (M1).** The TypeScript Expo SDK 58 app moved from `mobile/` to `artifacts/campus-connect/`. Click **Run** in Replit, select **Campus Connect**, and scan the URL-bar menu's Expo Go QR code. The managed startup supplies the public backend domain automatically; no local Metro server or `.env` copy is needed. The join screen calls `/api/v1/health` first and shows whether the origin is reachable. An explicit `EXPO_PUBLIC_API_URL` overrides automatic configuration; a phone's `localhost` points to the phone. See [the student app guide](artifacts/campus-connect/README.md) for local development, screens, retries and errors. [Expo setup](https://docs.expo.dev/get-started/create-a-project/) · [React Native networking](https://reactnative.dev/docs/network.html)

**Client settings are visible.** Expo embeds `EXPO_PUBLIC_*` values in the bundle. Keep server secrets out of them. [Expo environment variables](https://docs.expo.dev/guides/environment-variables/)

## Expo milestone acceptance

- [ ] Open the app on a physical device and connect to the backend at its HTTPS origin.
- [ ] Join a batch, see the solo fare and sample share for a drop-off, book once, and keep the same request after a network retry.
- [ ] Run matching in the web dashboard. Refresh or reopen the phone app and see the gate, pickup time, other riders, drop-off order and share versus solo fare.
- [ ] Confirm the plan. Decline as another rider in the same car from the dashboard or a second device, and see the phone switch to **plan changed** and ask to confirm again.
- [ ] Check a women-only request is never matched with a man, a solo-ride offer, a closed batch, and no access to another student's plan.
- [ ] Replay the sample afternoon and confirm five cars and Sara's JOD 1.67 share.

Record agreed product decisions in [agent.md](agent.md). Update this document when the API, fare rules, estimates or repository layout change.
