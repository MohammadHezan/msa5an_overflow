# Continue the Jeeny Campus Connect MVP

## Start here

This is the working Jeeny-style Campus Connect hackathon demo, not a request to recreate its UI. Keep the existing design and extend it.

The app is a proposed feature **inside Jeeny**, not a separately branded campus service. Its home screen, menu, pink booking panels, illustrative route map, and ride status/credit screens are already implemented. Keep the visible hackathon/simulation labels: there are no live Jeeny bookings or payments.

## Get the built version

Repository: https://github.com/MohammadHezan/msa5an_overflow

Handoff branch: `jeeny-campus-connect-demo`

For a new folder:

```sh
git clone --branch jeeny-campus-connect-demo --single-branch https://github.com/MohammadHezan/msa5an_overflow.git
cd msa5an_overflow
```

For an existing clone, fetch the branch first. Before switching, merging, or copying files, inspect local work and preserve changes made by Antigravity, Claude, or the user. Do not reset their work.

This branch is based on the team's GitHub main and contains the application, not the unrelated Replit workspace scaffold. The original Flask run configuration is retained. In the source Replit workspace, a managed web artifact serves this same root-level Flask app; that artifact's unused React scaffold is not the UI.

## Run and verify

Use Python 3.11 or 3.12. Install `requirements.txt` with the environment's supported package manager, then run:

```sh
python app.py
python -m unittest discover -s tests -v
```

The app binds to `0.0.0.0` and uses `PORT`, defaulting to 5000. In Replit, configure the existing Flask app to run in Preview rather than generating a replacement frontend. Manage `SESSION_SECRET` through workspace secrets; never copy its value from another workspace or commit it. SQLite demo batches are created under `instance/` and are intentionally not included in this handoff.

## Source of the exact UI

- `templates/index.html`: Jeeny-style home, sidebar, booking, ride status, Operations, and Results.
- `static/style.css`: the complete responsive UI, pink palette, cards, desktop layout, and phone drawer.
- `static/trip.js`: live preset leave-by/fare estimates and menu interaction.
- `static/map.svg`: original illustrative route map; not a live map.
- `static/jeeny/`: official logo/icon assets and their reference sources.
- `app.py`: Flask forms, CSRF protection, per-browser batch persistence, cutoff and saved results.
- `allocation.py`: real OR-Tools CP-SAT allocation and first-come comparison.
- `tests/test_demo.py`: eight tests including reproducible generated allocation scenarios.

Do not replace this with a blank React/Vite page. Do not redesign it from memory or from screenshots.

## Demo walkthrough

1. Home → **Plan a campus ride**.
2. Start an empty batch, enter a demo student, area, arrival time, and optional full-fare consent.
3. Submit and see the pending status and suggested leave-by time.
4. Open **Operations**, choose budget/cap/drivers, and run the simulated evening cutoff.
5. Open **Results**, then click a student for their saved result.
6. Load the seven-student scenario and allocate with the default JOD 6.00 budget.

Expected default comparison:

| Metric | Campus Connect | First come |
| --- | --- | --- |
| Projected on-time students | 6/7 | 4/7 |
| Projected on-time rate | 85.7% | 57.1% |
| Credit spend | JOD 6.00 | JOD 6.00 |
| Credit per on-time arrival | JOD 1.00 | JOD 1.50 |

Two students have workable preset buses. Four credits fund four of the five students without buses; nobody claims five funded rides from four credits. Count each requester once, including unserved students. Report ties honestly.

## Scope and coordination

Read `agent.md`, `document.md`, and `design.md` before extending the app. The shared phone-to-operator JSON API and native Expo student app are planned, not implemented here. Coordinate ownership with Antigravity and Claude before changing those areas. The working web demo remains the fallback for judging.

Do not add real dispatch, payments, production accounts, or claims of trained forecasting to this simulation without a new requirement. Keep Flask, SQLite, Jinja, and OR-Tools unless the team explicitly agrees to change them.

## Prompt for the next chat

> Fetch the `jeeny-campus-connect-demo` branch from `MohammadHezan/msa5an_overflow`. Read `HANDOFF.md`, `agent.md`, and the existing app before changing anything. Preserve the exact Jeeny-style UI in `templates/index.html` and `static/`; this is a feature inside Jeeny for a hackathon MVP. Run the existing Flask app in Preview and run its eight acceptance tests. Do not rebuild it as React or overwrite other collaborators' work. Then continue with my next requested change.
