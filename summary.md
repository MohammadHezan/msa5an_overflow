# Campus Connect project summary

Campus Connect is a one-campus Amman hackathon MVP for students who might miss class because their bus is full or unavailable. Students can request a private ride the evening before. A limited pool of credits is used where it gives more students a way to arrive on time.

## What works today

- **Student flow.** Choose a pickup area and arrival time, review the suggested leave-by time and sample fare, and decide whether a full-fare ride is acceptable. After the simulated 9 p.m. cutoff, the request shows a credited ride, a full-fare ride, or an unconfirmed ride with a next option.
- **Operations flow.** Set the credit budget, per-student cap, and driver capacity by arrival window. Run the cutoff and compare OR-Tools CP-SAT allocation with first come, first served. Flask and SQLite store the results for the demo batch.
- **Demo result.** With seven students, four JOD 1.50 credits, and identical driver capacity, the allocator produces **6/7 simulated on-time arrivals**, versus **4/7** for first come, first served. Both spend JOD 6.00. Running allocation again returns the saved outcome without spending more credit.

Bus availability, driver supply, fares, and arrival outcomes use sample data. The app does not book rides or process payments.

## Where to look in the repo

| File | What it covers |
| --- | --- |
| [README.md](README.md) | Local and Replit setup, plus the judge walkthrough. |
| [app.py](app.py) | Flask routes, trip estimates, SQLite state, and the simulated cutoff. |
| [allocation.py](allocation.py) | The credit allocator, first-come baseline, and result totals. |
| [agent.md](agent.md) | Team decisions, student interview questions, and acceptance checks. |
| [document.md](document.md) | Expo and Flask work split, proposed API, task estimates, and simulation plan. |

## What remains

Build the React Native app with Expo and the shared Flask JSON API. The first integration milestone is a student submitting from a physical phone, an operator running the cutoff in the web dashboard, and the same phone showing the saved outcome. The expanded synthetic scenario runner and optional overflow forecast are also planned.
