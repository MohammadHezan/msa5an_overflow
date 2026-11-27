# Yalla Ride

For the current concept, core matching and pricing rules, completed features and known limitations, see the [Yalla Ride project guide](docs/yalla-ride-project-guide.html). The older overview below contains historical demo assumptions; use the guide and current configuration for the implemented rules.

A proposed Jeeny feature that helps students pay less by sharing rides home with other students going the same way. A student books before class ends. Campus Connect groups students leaving the same campus in the same direction at about the same time, sets one meeting point and pickup time, and shows each student's share before they confirm. The price reflects how far each student rides. Women students can choose to match only with other women students.

The demo is a Flask app. SQLite stores each browser's demo batch, and OR-Tools CP-SAT groups students into as few cars as possible.

## Run

On Replit, click **Run** to start the existing Flask dashboard and managed Expo student app. Open **Campus Connect Dashboard** to use the dashboard. Select **Campus Connect** and scan the **Expo Go** QR code from the preview URL-bar menu to open the student app on a phone, with no local setup. See the [student app guide](artifacts/campus-connect/README.md). The dashboard and `/api/v1` stay on port 5000.

Locally, use Python 3.11 or 3.12.

```sh
python -m pip install -r requirements.txt
python app.py
```

Open [http://localhost:5000](http://localhost:5000). The demo stores batches under `instance/`. For local settings, copy `.env.example` to `.env`. Set `SESSION_SECRET` to a stable random value if you want existing browser sessions to survive an app restart. On Replit, set it in Secrets.

## Judge walkthrough

1. The app opens with a sample afternoon of ten students. Open **Matching** and click **Match 10 students**.
2. On **Trips**, see the five cars, each pickup time and gate, and each student's share compared with riding alone.
3. Open **Sara**. Her class ends at 16:00. She meets Rama and Huda at the main gate at 16:02, shares one women-only car, and pays JOD 1.46 instead of JOD 4.34.
4. Click **Decline** as Rama. Sara and Huda now see an updated plan and are asked to confirm again.
5. Kareem finishes at the same time and heads the same way, but the car is women-only, so he is offered a solo ride.
6. Choose **Start empty batch** to book your own requests from the **Book** page.

Distances, fares and gates are simulated. Each car is one regular ride at the regulated Jeeny app fare (JOD 0.468 + JOD 0.336/km over the whole route, LTRC tariff of 11 May 2026). Each student pays in proportion to their own distance, the shares add up to exactly that fare, and a student only shares if they save at least 20%. Matching and pricing come from the `pooling/` engine; `sharing.py` adapts it to this app. The app makes no bookings or payments.
