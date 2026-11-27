# Campus Connect

Shared rides home from campus for students (proposed Jeeny feature, hackathon demo).

## Run
- Workflow **Start application** runs `python app.py` on port 5000.
- Python 3.12; dependencies in `requirements.txt` (Flask, OR-Tools, python-dotenv, tzdata).
- `SESSION_SECRET` (in Secrets) keeps browser sessions valid across restarts.

## Layout
- `app.py` – Flask HTML routes (browser session owns a batch; Matching view shows the batch's student join code).
- `api.py` – `/api/v1` JSON API for the Expo app and operators (bearer tokens).
- `store.py` – SQLite demo batches (`instance/campus.sqlite`), sample fixture, and the booking/matching/confirm/decline actions shared by both.
- `sharing.py` – destinations, simulated map coordinates, fare rules, CP-SAT grouping, per-car price split.
- Route maps are inline SVG drawn server-side (no map tiles or external services), labelled "Simulated map".
- `templates/phone.html` + `static/jeeny.css` – student app, styled as a feature inside Jeeny's ride section (magenta #EC008C, Poppins, map + bottom sheet, phone frame on desktop, full-screen on mobile).
- `templates/index.html` + `static/style.css` – operator Matching and Trips views, using the same Jeeny palette.
- `mobile/` – placeholder for a future Expo app. `document.md` (rules, task split, proposed JSON API) and `agent.md` (team decisions, interview form, acceptance checklist) are the team planning notes.
