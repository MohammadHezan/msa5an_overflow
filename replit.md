# Campus Connect

Shared rides home from campus for students (proposed Jeeny feature, hackathon demo).

## Run
- Workflow **Start application** runs `python app.py` on port 5000.
- Python 3.12; dependencies in `requirements.txt` (Flask, OR-Tools, python-dotenv, tzdata).
- `SESSION_SECRET` (in Secrets) keeps browser sessions valid across restarts.

## Layout
- `app.py` – Flask routes, SQLite demo batches (`instance/campus.sqlite`), sample afternoon fixture.
- `sharing.py` – destinations, simulated map coordinates, fare rules, CP-SAT grouping, per-car price split.
- Route maps are inline SVG drawn server-side (no map tiles or external services), labelled "Simulated map".
- `templates/index.html`, `static/` – Book, Matching and Trips views.
- `mobile/` – placeholder for a future Expo app. `document.md` and `agent.md` are team planning notes from the earlier ride-credit version.
