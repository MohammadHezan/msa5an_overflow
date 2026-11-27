# Campus Connect

A one-campus Amman hackathon demo for booking private rides ahead of time. Students request a ride, operations runs the evening cutoff, and every request gets an outcome. SQLite stores each browser's demo batch, and OR-Tools CP-SAT allocates the ride credits.

Campus Connect is presented as a proposed feature inside Jeeny for the hackathon pitch, not as a separate transport brand or live Jeeny service. See [document.md](document.md) for the proposed Expo/API split and [design.md](design.md) for the prototype handoff.

## Run

For another chat or a fresh clone, read [HANDOFF.md](HANDOFF.md). The `jeeny-campus-connect-demo` branch exports the exact Flask app and UI while retaining the team's simple Flask run configuration; it does not require the source workspace's unused React scaffold.

In this Replit workspace, open the **Campus Connect** web preview. Its managed workflow, `artifacts/campus-connect: web`, runs the original root-level Flask app. Python dependencies are installed from `requirements.txt`; the React files in the web artifact are unused scaffold infrastructure, not a second implementation.

Locally, use Python 3.11 or 3.12.

```sh
python -m pip install -r requirements.txt
python app.py
```

Open [http://localhost:5000](http://localhost:5000). The demo stores batches under `instance/`. Set `SESSION_SECRET` to a stable random value if you want existing browser sessions to survive an app restart.

## Judge walkthrough

1. Choose **Start empty batch**. Enter a demo name, choose a pickup area and arrival time, and review the leave-by estimate.
2. Submit the request. Open **Operations** and click **Run allocation**. Open the student's result from the Results table.
3. Choose **Load seven-student scenario** and run the allocation at the default JOD 6.00 budget. Campus Connect projects **6 of 7** on-time arrivals. First come, first served projects **4 of 7** with the same four credits and driver capacity.

Two fixture students have an on-time bus. First come, first served gives the first four eligible rides a credit, including two bus users. Campus Connect uses the four credits where they add an on-time option. Driver capacity and the per-student cap apply to each method. Full-fare rides require opt-in.

The operations button simulates the 9 p.m. cutoff. Each available driver represents one ride in the configured arrival window. Travel times, fares, bus availability and arrivals are simulated. The app makes no bookings or payments. Each student gets one request per batch.

## Acceptance checks

Run `python -m unittest discover -s tests -v`. The checks use temporary SQLite databases and do not change browser demo batches. They cover the seeded comparison, spending and driver constraints, all ride outcomes, duplicate requests, the saved cutoff, form validation, ties, zero-arrival costs, and displayed metrics. Reproducible generated scenarios check both policies against spending, consent, cap, and per-window driver limits.

Results show projected on-time rate over **all** requesters and credit spend per on-time arrival, including students who have a preset workable bus. With the default fixture the rates are 85.7% (6/7) versus 57.1% (4/7), and costs per on-time arrival are JOD 1.00 versus JOD 1.50. Zero on-time arrivals show “Not applicable”, and equal arrival counts are reported as ties. These are simulated outcomes, not measured service reliability.

## Collaboration

Use `agent.md` for product defaults and acceptance criteria. `document.md` now contains the merged plan for a shared Flask API and Expo milestone; those capabilities are proposed, not yet implemented. `design.md` was read from the Expo integration branch. Agree on ownership before overlapping changes across Replit Agent, Antigravity, and Claude. Preserve the existing Flask/SQLite/OR-Tools stack unless the team explicitly agrees otherwise.
