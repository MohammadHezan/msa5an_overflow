# Campus Connect

A one-campus Amman hackathon demo for booking private rides ahead of time. Students request a ride, operations runs the evening cutoff, and every request gets an outcome. SQLite stores each browser's demo batch, and OR-Tools CP-SAT allocates the ride credits.

See [document.md](document.md) for the Expo and backend split, proposed API, task estimates, and simulation plan. Team questions and the original demo checklist are in [agent.md](agent.md).

## Run

On Replit, import the project and click **Run**. The included configuration installs dependencies and starts the app. Open **Preview** to use it.

Locally, use Python 3.11 or 3.12.

```sh
python -m pip install -r requirements.txt
python app.py
```

Open [http://localhost:5000](http://localhost:5000). The demo stores batches under `instance/`. For local settings, copy `.env.example` to `.env`. Set `SESSION_SECRET` to a stable random value if you want existing browser sessions to survive an app restart. On Replit, set it in Secrets.

## Judge walkthrough

1. Choose **Start empty batch**. Enter a demo name, choose a pickup area and arrival time, and review the leave-by estimate.
2. Submit the request. Open **Operations** and click **Run allocation**. Open the student's result from the Results table.
3. Choose **Load seven-student scenario** and run the allocation at the default JOD 6.00 budget. Campus Connect projects **6 of 7** on-time arrivals. First come, first served projects **4 of 7** with the same four credits and driver capacity.

Two fixture students have an on-time bus. First come, first served gives the first four eligible rides a credit, including two bus users. Campus Connect uses the four credits where they add an on-time option. Driver capacity and the per-student cap apply to each method. Full-fare rides require opt-in.

The operations button simulates the 9 p.m. cutoff. Each available driver represents one ride in the configured arrival window. Travel times, fares, bus availability and arrivals are simulated. The app makes no bookings or payments. Each student gets one request per batch.
