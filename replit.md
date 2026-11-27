# Campus Connect

Shared rides home from campus for students (proposed Jeeny feature, hackathon demo).

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
- `mobile/` – placeholder for a future Expo app. `document.md` (rules, task split, proposed JSON API) and `agent.md` (team decisions, interview form, acceptance checklist) are the team planning notes.

## Rules
- `pooling/` is the matching and pricing engine, owned by Mohammad. Do not change its rules, numbers or tests. If something there looks wrong, write the question in `agent.md` and stop.
- `sharing.py` is only an adapter from the app to `pooling/`. Keep its functions and their inputs.
- Fares are the regulated LTRC app tariff: 468 fils + 336 fils per km over the whole route. The car pays one fare. Students split it by distance, and the shares must add up to the car fare exactly. Never add discounts, per-seat prices or rounding to 50 fils.
- Money is integer fils everywhere. The UI formats 1670 as "JOD 1.67".
- Run `python -m pytest` before every push. Never push with failing tests.
- `scripts/git_sync.sh` pulls and pushes `origin/main` every 3 minutes; run it from the agent shell (workflows have no GitHub credentials).
