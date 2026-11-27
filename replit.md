# Campus Connect

Shared rides to and from campus for students (proposed Jeeny feature, hackathon demo).

## Current brief contract
- The student-facing shared option is called **Yalla Ride** and belongs in the same ride-options list as Taxi and Comfort, not a separate app section.
- Follow `docs/replit-briefs/README.md` in order, one phase at a time. Skip implemented behavior that passes tests. After each implemented phase run `python -m pytest`, inspect Preview at phone width, commit, and report before starting the next phase.
- Brief 02 explicitly permits tested engine changes for street geography, both directions and segment pricing. Brief 03 is UI integration only: do not change `pooling/` or pricing rules there.
- Street locations are simulated: corridor km plus 0–400 m side offset. Riders walk at most 200 m at 1.4 m/s; excess adds a round-trip car turn-in.
- Homebound requests use class end plus walking time; campus-bound requests use class start minus five minutes. Only the same corridor/direction and times within ten minutes can share. Capacity is four; preferences are mixed, women, or men; shared savings floor is 25%, with the existing detour ceiling.
- Street fare is 468 + round(336 × route km) fils. Divide the start fare equally and each segment among occupants; use largest-remainder rounding and solo caps. After confirmation, Jeeny covers any increase caused by another rider declining.
- Friends groups stay together; closed groups take no strangers. Captains receive 100 fils per extra rider, paid by Jeeny. Two-minute holds and ten-minute waiting use the demo clock.
- Go-now pickups must still be ahead at the student's actual street location; a campus student cannot join after the car has left campus.
- Afternoon, morning, and 28-student samples are available. Simulation compares alone, greedy, and optimizer using 30 paired seeds for each of 8/16/24/32 students, including mean/range and explicitly simulated charts.

## Run
- Workflow **Start application** runs `python app.py` on port 5000.
- Python 3.12; dependencies in `requirements.txt` (Flask, OR-Tools, python-dotenv, tzdata).
- `SESSION_SECRET` (in Secrets) keeps browser sessions valid across restarts.

## Layout
- `app.py` – Flask HTML routes (browser session owns a batch; Matching view shows the batch's student join code and lets an operator paste an API operator token to open that batch instead — resetting never deletes an opened API batch).
- API-created batches (those with an operator token) are deleted 24 h after creation and browser batches 3 days after creation; cleanup runs whenever a batch is created or opened. A browser whose batch was cleared gets a fresh sample batch.
- `api.py` – `/api/v1` JSON API for the Expo app and operators (bearer tokens).
- `store.py` – SQLite demo batches (`instance/campus.sqlite`), sample fixture, and the booking/matching/confirm/decline actions shared by both.
- `sharing.py` – adapter only: keeps the app's interface (`group_riders`, `plan_car`, `solo_fare`, `sample_share`, `compatible`, `route_map`) and calls the `pooling/` engine.
- `pooling/` – matching and pricing engine (owned by Mohammad): `model.py` `evaluate` applies every rule and prices a car, `regroup.py` CP-SAT grouping, `pricing.py` LTRC tariff and proportional split, `codes.py` ride codes (`CC-1234`) for the driver check, `places.py`/`geo.py` map data and distances.
- Ride codes: a student gets one on confirm (kept on re-confirm, cleared on decline, hidden while `changed`). Operators check them on the Trips view or via `POST /api/v1/batches/{id}/verify-code`.
- Route maps are inline SVG drawn server-side (no map tiles or external services), labelled "Simulated map".
- `templates/phone.html` + `static/jeeny.css` – student app, styled as a feature inside Jeeny's ride section (magenta #EC008C, Poppins, map + bottom sheet, phone frame on desktop, full-screen on mobile).
- `templates/index.html` + `static/style.css` – operator Matching and Trips views, using the same Jeeny palette.
- `mobile/` – TypeScript Expo (SDK 58, pnpm) student app: join code → book → plan review → confirm/decline against `/api/v1`. Not run by a Replit workflow; teams run Metro locally (see `mobile/README.md`). `document.md` (rules, task split, proposed JSON API) and `agent.md` (team decisions, interview form, acceptance checklist) are the team planning notes.

## Rules
- `pooling/` is the matching and pricing engine, owned by Mohammad. Outside Brief 02's explicit permission, do not change its rules or numbers. Record open questions in `agent.md`.
- `sharing.py` is only an adapter from the app to `pooling/`. Keep its functions and their inputs.
- Street fares use the regulated demo tariff above. The car pays one fare; segment shares plus any explicitly recorded Jeeny cover must add up to that fare. Never add discounts, per-seat prices or rounding to 50 fils.
- Money is integer fils everywhere. The UI formats 1670 as "JOD 1.67".
- Run `python -m pytest` before every push. Never push with failing tests.
- `scripts/git_sync.sh` pulls and pushes `origin/main` every 3 minutes; run it from the agent shell (workflows have no GitHub credentials).
- `yalla.py` + `templates/yalla/` + `static/yalla.css`/`yalla.js` – Brief 04 full-screen Yalla Ride flow at `/yalla` (design exports in `docs/design/campus-connect-screens`, titled "Yalla Ride" instead of "Campus Connect"). Draft request lives in the session; booking, matching, confirm/decline and ride codes use the same `store.py` actions. Email verification is demo-only: the code is shown on screen and only a masked email is kept.
