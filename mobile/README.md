# Campus Connect — student app (Expo)

Sara's side of the demo: join a batch with the operator's join code, book a ride home, review the plan, then confirm or decline. It talks to the Flask `/api/v1` backend (`../api.py`; contract in `../document.md`, "As built (B1)").

## Run

```sh
cd mobile
pnpm install
cp .env.example .env        # set EXPO_PUBLIC_API_URL to the backend's HTTPS origin, no /api path
pnpm start                  # scan the QR code with Expo Go (SDK 58)
pnpm typecheck
pnpm test                   # booking retry rules (no backend needed)
```

`EXPO_PUBLIC_API_URL` is embedded in the bundle at start-up; restart Metro after changing it. On Replit, use the project's dev or deployment URL. The phone must reach it over HTTPS.

## Screens

| Screen | Shown when | What it does |
| --- | --- | --- |
| Join | No stored session | Checks `GET /health`, exchanges the join code (`POST /demo-sessions/join`) for a student bearer token, stored on the device with AsyncStorage. |
| Book | Joined, not booked yet | Loads drop-offs, solo fares and sample shares from `GET /stops`. Name, class end time (08:00–21:00, 5-minute steps), drop-off, woman student, women-only. `POST /batches/{id}/riders`. |
| Plan | Booked | `GET /riders/{id}`: status, gate, pickup time, other riders' first names, drop-off order, share vs solo fare, shared vs solo. Confirm sends the plan `signature` the student is looking at; decline asks first. |

The plan screen reloads every 10 s while open, when the app returns to the foreground, and on pull-to-refresh, so it picks up matching from the dashboard and declines by other riders.

## Retries and errors

- **Booking retries.** A `clientRequestId` is created once per joined session and stored with the token. The details are stored before each send. If a send gets no answer, the form locks and the only action is to send those same details again; the server returns the same rider (`200`) if it saved them. Server errors (5xx) count as unanswered too, since the booking may have been saved. Only a definite rejection (invalid input, duplicate name, closed or full batch) lifts the lock. Resending works even if drop-off data failed to load. This also works after closing and reopening the app. Logic in `src/booking.ts`, covered by `pnpm test`.
- **Statuses.** `waiting` (booked, matching not run), `review`, `no_match` (solo ride offered), `confirmed`, `solo_confirmed`, `changed` (another rider left — confirm again), `declined` (join with a new code to book again).
- **`409 plan_changed`.** The app shows the updated plan returned with the error and asks the student to confirm again.
- **Offline / slow.** Requests time out after 15 s, including a response body that stalls. Network failures show a banner with a retry; the plan screen keeps showing the last plan it received.
- **Session lost.** `401`/`403`/`404` on the plan (for example after the operator starts a new batch) offers to join with a new code. The log-out button in the header clears the stored session.

Distances and fares are simulated; no rides or payments are made.
