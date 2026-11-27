# Campus Connect — student app (Expo)

Sara's side of the demo: join a batch with the operator's join code, book a ride home, review the plan, then confirm or decline. It talks to the unchanged Flask `/api/v1` backend (`../../api.py`; contract in `../../document.md`, "As built (B1)"). This is the canonical app source, moved from `mobile/`.

## Open on a phone from Replit

1. Click **Run**. It starts **Campus Connect Dashboard** (Flask on port 5000) and **Campus Connect** (managed Expo/Metro preview).
2. Select the **Campus Connect** mobile preview. Open the URL-bar menu and scan its **Expo Go** QR code using Expo Go on Android or the Camera app on iPhone. Expo Go must support SDK 58.
3. Keep the Replit project running while rehearsing. No laptop, local Metro server, tunnel, or `.env` copy is required. The phone needs internet access, not the same Wi-Fi.
4. Open **Campus Connect Dashboard** in Replit to create/open a batch and get its join code. Enter that code on the phone. Run matching on the dashboard to see the plan update on the phone.

The ordinary project URL still serves the Flask dashboard at `/` and the same `/api/v1` endpoints. The student browser preview lives at `/student-app`; the Expo hostname serves native manifests and bundles from Metro's root. Keep these as separate artifacts so native requests do not reach Flask.

### Backend configuration

The managed mobile startup supplies `EXPO_PUBLIC_DOMAIN` from Replit's backend development domain. The client automatically uses `https://<that domain>`. An explicit `EXPO_PUBLIC_API_URL` overrides this, for example to target a different backend; put it in this directory's `.env` and restart **artifacts/campus-connect: expo**. Never use `localhost` for a physical phone or put tokens/secrets in public Expo variables.

If the QR code stops working, ensure both managed workflows are running, restart the mobile workflow and scan the fresh QR code. If Expo Go reports an SDK mismatch, update Expo Go to a compatible version. If the join screen says the backend is unreachable, check that the dashboard workflow and `/api/v1/health` are responding, and remove any stale API URL override.

## Optional local development

```sh
pnpm install               # repository root; Node 22.13+ and pnpm 10.26.1
cd artifacts/campus-connect
cp .env.example .env        # uncomment EXPO_PUBLIC_API_URL and set a phone-reachable HTTPS backend origin
pnpm exec expo start       # local machine only; on Replit use the managed workflow
pnpm run typecheck
pnpm test
pnpm test:api               # real phone client against an isolated temporary Flask backend
```

Public configuration is embedded in the bundle at startup; restart Metro after changing it. The phone must reach the backend over HTTPS.

The `mobile-typecheck`, `mobile-unit` and `mobile-api` validation workflows remain
available and now target this directory. `test:api` runs
`../../scripts/check_mobile_api.py` against a disposable database and free local
port, so it needs no phone, running preview, join code or API URL configuration.
It preserves the real-client booking, retry, plan-change and confirm/decline
regression checks. See [the regression check notes](../../mobile/README.md) for details.

## Screens

| Screen | Shown when | What it does |
| --- | --- | --- |
| Join | No stored session | Checks `GET /health`, exchanges the join code (`POST /demo-sessions/join`) for a student bearer token, stored on the device with AsyncStorage. |
| Verify | Joined, university not verified, not booked yet | Searches campuses (`GET /universities?search=`), available ones first. An unavailable campus offers "Notify me in Jeeny" (`POST /universities/{id}/notify`) and shows "We'll keep you posted". An available campus asks for the university email (`POST /verification/start`), then shows the masked address, a code-expiry countdown, a resend cooldown (`POST /verification/resend`) and "Use a different email". `POST /verification/confirm` returns a new token, which replaces the stored one. Demo only: no email is sent; the code is printed in the backend console. |
| Book | Joined and verified, not booked yet | Loads drop-offs, solo fares and sample shares from `GET /stops`. Name, class end time (08:00–21:00, 5-minute steps), drop-off, "Ride with" (Anyone, or only the profile gender's option: Men only or Women only), and "Book with friends" (Just me, Start a group with an open-seats toggle, or Join a group by code). Gender comes from the profile. `POST /batches/{id}/riders`. |
| Plan | Booked | `GET /riders/{id}`: status, gate, pickup time, other riders' first names, drop-off order, share vs solo fare, shared vs solo, the friends group code to share, and a Men only / Women only badge. Confirm sends the plan `signature` the student is looking at; decline asks first. |

The plan screen reloads every 10 s while open, when the app returns to the foreground, and on pull-to-refresh, so it picks up matching from the dashboard and declines by other riders.

## Retries and errors

- **Booking retries.** A `clientRequestId` is created once per joined session and stored with the token. The details are stored before each send. If a send gets no answer, the form locks and the only action is to send those same details again; the server returns the same rider (`200`) if it saved them. Server errors (5xx) count as unanswered too, since the booking may have been saved. Only a definite rejection (invalid input, duplicate name, closed or full batch, unknown, full or mismatched friends group) lifts the lock. Resending works even if drop-off data failed to load. This also works after closing and reopening the app. Logic in `src/booking.ts`, covered by `pnpm test`.
- **Statuses.** `waiting` (booked, matching not run), `review`, `no_match` (solo ride offered), `confirmed`, `solo_confirmed`, `changed` (another rider left — confirm again), `declined` (join with a new code to book again).
- **`409 plan_changed`.** The app shows the updated plan returned with the error and asks the student to confirm again.
- **Offline / slow.** Requests time out after 15 s, including a response body that stalls. Network failures show a banner with a retry; the plan screen keeps showing the last plan it received.
- **Session lost.** `401`/`403`/`404` on the plan (for example after the operator starts a new batch) offers to join with a new code. The log-out button in the header clears the stored session.

Distances and fares are simulated; no rides or payments are made.
