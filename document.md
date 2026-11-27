# Campus Connect project document

## Product and first milestone

Campus Connect gives students a backup when their bus may miss a class deadline. A student enters their pickup area and next-day arrival time, sees when to leave and what a private ride could cost, and gets an answer after the evening cutoff. Operations uses a limited credit budget to help as many students as possible gain an on-time option. Students who opt in can pay full fare if a ride is available.

The notebook's Amman–Irbid commute explains the effect of multiple transport legs, delays, and a taxi fare paid alone. The pitch deck's first pilot covers one Amman campus. Keep that scope for the first Expo demo with **trips to campus**. Sara's ride home after class remains an open direction decision in [agent.md](agent.md). Keep interviews, campus selection, and business assumptions in that form.

The first mobile milestone is one demo student submitting a request from a physical phone, an operator running the cutoff in the web dashboard, and the same phone seeing the saved result. The seven-student scenario remains the repeatable demonstration.

## Current implementation and proposed split

| Component | Today | First Expo milestone |
| --- | --- | --- |
| Student experience | Flask renders the request form, estimates, and status in `templates/index.html` and `static/`. | Add a TypeScript React Native app under `mobile/`. It owns navigation, form input, loading, and result presentation. It reads estimates and outcomes from the backend. |
| Backend | `app.py` serves HTML routes and stores demo batches in SQLite. A browser session currently owns its own batch. | Add a versioned JSON API and shared domain functions. The phone and the operator must use the same batch. Keep Flask and SQLite for the single-instance demo. |
| Operations | The web dashboard configures budget, cap, and drivers, then runs the simulated cutoff. | Keep the dashboard on Replit. Connect it to the same backend batch and rules as the Expo app. |
| Allocation | `allocation.py` serves the OR-Tools CP-SAT allocator and first-come comparison using preset bus availability. | Reuse those policies. Add an optional scenario runner to compare results on repeatable simulated inputs. |

Keep one repository. `mobile/` will be a separate Expo project with its own dependencies. Keep the Flask files at the repo root during the first integration so the Replit Run command stays usable. Moving Flask to `backend/` can be a separate mechanical change after the phone-to-dashboard flow works. Any move also updates `.replit`, Python paths, environment loading, and run instructions.

## Task ownership and build order

These are proposed owners and estimates in focused person-hours. The first demo is **12–18 person-hours**, or roughly **7–11 working hours on the critical path** if the mobile, backend, and simulation tasks run in parallel. Expo account setup, device access, and deployment delays can extend that estimate.

| Task | Proposed owner | Estimate | Depends on | Done when |
| --- | --- | ---: | --- | --- |
| T0. Agree on the contract and demo scenario | All, with Mohammad coordinating | 1–2 h | — | Agree on trip direction, demo roles, request fields, API errors, seeded scenario, and device for rehearsal. |
| B1. Build the shared Flask API | Mohammad | 3–4 h | T0 | Health, session join, quote, request creation, and status endpoints work. The operator can allocate the same batch and repeating the cutoff returns the saved result. |
| M1. Build the Expo student app | Laith | 3–4 h | T0 | Join, request, and result screens work with sample API responses. Handle delayed responses, offline errors, and retries. |
| S1. Build the repeatable simulation | Abdallatif | 2–3 h | T0 | Replay the seven-student comparison and run seeded scenarios with zero drivers, higher demand, and tighter credit budgets. Show both methods' totals in the dashboard. |
| I1. Connect the phone to Replit | Mohammad and Laith | 2–3 h | B1, M1 | A physical phone calls the Replit backend over HTTPS. A web operation changes the status seen on that phone. |
| T1. Rehearse the judging flow | All, with Abdallatif coordinating | 1–2 h | I1, S1 | Run the mobile and web flow, replay the seeded demo, and record the device, branch, scenario seed, and expected screenshots or outputs. |
| S2. Optional learning experiment | Abdallatif and Mohammad | 3–5 h, separate from the core demo | S1 | Evaluate a simple overflow classifier against a rule and a naïve baseline on held-out synthetic dates. |

First agree on T0, then work in parallel from the same example responses. Use the current web demo as a rehearsal fallback while integrating Expo. If time is tight, finish the phone-to-dashboard loop and run the rule-based simulation before starting S2.

## Proposed API contract

This is the implementation target. The current app still uses web forms and browser sessions.

| Endpoint | Used by | Expected behavior |
| --- | --- | --- |
| `GET /api/v1/health` | Device and operators | Reports whether the backend can respond. The phone calls this first to verify the configured origin. |
| `POST /api/v1/demo-sessions/join` | Student app | Exchanges an operator-issued, short-lived code for a student token scoped to a batch and synthetic student identity. |
| `GET /api/v1/routes` | Student app | Returns the demo campus, preset pickup IDs and names, and allowed arrival windows. |
| `POST /api/v1/quotes` | Student app | Returns a suggested leave-by time and fare for a pickup ID and arrival deadline. A quote does not reserve a ride. |
| `POST /api/v1/requests` | Student app | Saves one request with `pickupId`, `arriveBy`, `allowFullFare`, and a client-generated `clientRequestId`. Returns the server request ID and `pending`. |
| `GET /api/v1/requests/{id}` | Student app | Returns the student's own result, including pickup time, payable amount, or next option as applicable. |
| `POST /api/v1/batches/{id}/allocation` | Authorized operations | Runs the cutoff for that batch and returns the already-saved result on repeat. The web form and any API handler must share the same allocation service. |
| `GET /api/v1/batches/{id}/results` | Authorized operations | Returns comparison metrics and per-student outcomes for that batch. |

- Return dates with an ISO 8601 offset and show times in `Asia/Amman`. Send money in integer fils, with explicit `JOD` currency. Four 1,500-fils credits cost 6,000 fils.
- Use `pending`, `confirmed_with_credit`, `confirmed_full_fare`, and `unconfirmed` for request states. A full-fare ride requires opt-in. Mobile refreshes from the server after the operator acts and after reopening the result screen.
- A network retry with the same `clientRequestId` and payload returns the original request. Reusing that ID for a different payload or submitting a second request for the same student and batch returns `409`. Include a stable JSON error code for a closed batch, duplicate request, bad input, or failed authorization.
- The operator's session creates the shared batch. Its student join code connects the phone to that exact batch. The mobile token grants access to that student's status. Allocation and results require the operator role. Keep credentials out of query strings and logs.
- Keep transport rules and counts on the backend. Validate input and finalize the batch, ride assignments, and credit spend in one transaction so a retry or concurrent action cannot assign twice.

## Simulation and AI experiment

Treat the simulation, forecasting, and allocation as separate steps. The simulator generates hypothetical days and actual bus outcomes. A forecast estimates overflow risk using only information available by the cutoff. OR-Tools applies the allocation policy within budget, driver supply, and full-fare consent. CP-SAT is the optimization method already implemented. [Google OR-Tools CP-SAT](https://developers.google.com/optimization/cp)

### Reproducible demo

1. Keep the seven-student fixture as a fixed regression check. Two students have workable buses, five need backup, four credits are available, and nobody opts in to full fare. Under the default driver capacity, the optimizer yields **6/7** and first come, first served yields **4/7** with **JOD 6.00** spent by each.
2. Generate additional synthetic scenarios from a recorded random seed. Vary request volume, bus schedules, realized bus capacity or delays, and driver availability by area, day, and window. Start with normal demand, a peak morning, an evening gap, zero drivers, and a tight credit budget.
3. Replay each scenario against both policies with the same student requests, credit budget, and driver supply. Evaluate both against the same simulated outcomes. Record the seed, policy, cutoff inputs, and version so the result can be reproduced.
4. Report projected on-time students divided by **all** requesters, students without an on-time option, and total credit spent. For multi-day runs also report additional arrivals versus first come, first served. When that gain is positive, report the difference in spend divided by the additional arrivals. Report ties as ties.

### Optional forecast

- Define the forecast target as whether a request will lack a workable bus for its arrival deadline. Build the label from the simulator's realized bus service, delay, and capacity. Inputs can include the area, window, weekday, published timetable, past simulated overflow and requests received by the cutoff. Keep realized capacity, delays and tomorrow's labels out of features.
- Start with a timetable and demand rule. If time permits, compare logistic regression to that rule and a naïve prior baseline. Split by date with complete days held out for evaluation, keeping older examples for training. Report precision and recall for bus overflow and the downstream allocation results on the same held-out scenarios. Label these results **synthetic**. A real pilot needs observed transport data and a separate evaluation. [Scikit-learn time series split](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html) · [Logistic regression](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html) · [Dummy classifier](https://scikit-learn.org/stable/modules/generated/sklearn.dummy.DummyClassifier.html)
- Keep the allocator's existing fixed-fixture path for the scripted demo. Wire a forecast into a separate scenario run so its mistakes can be measured against simulated outcomes. The seven-student result demonstrates allocation and does not measure forecast accuracy.

## Environment and running the project

| Location | Name | Purpose |
| --- | --- | --- |
| Backend root `.env` | `PORT` | Flask port. The Replit config currently maps port 5000. |
| Backend root `.env` or Replit Secrets | `SESSION_SECRET` | Signs Flask browser sessions. Set a unique value for your deployment. The actual local file is ignored by Git. |
| Future `mobile/.env` | `EXPO_PUBLIC_API_URL` | Public HTTPS origin used by the Expo app, with no API path. Copy `mobile/.env.example` when the Expo project is scaffolded. |

**Current backend.** Copy [the backend template](.env.example) to `.env` on a new checkout. Run `python -m pip install -r requirements.txt` and then `python app.py`, or click **Run** in Replit. The app loads `.env` at startup and existing process variables take precedence. Configure backend secrets via Replit Secrets. [Replit Secrets](https://docs.replit.com/core-concepts/project-editor/app-setup/secrets)

**Expo after M1.** Scaffold a TypeScript Expo app under `mobile/` with an SDK compatible with the test device. Start Metro from that directory with `npx expo start`. Use Expo Go if the chosen modules are supported on the test device, or use a development build. A Metro tunnel can help the phone load the development bundle. Set the backend origin separately and verify the phone can reach `/api/v1/health` over HTTPS before testing the flow. A phone's `localhost` points to the phone. [Expo setup](https://docs.expo.dev/get-started/create-a-project/) · [Expo development workflows](https://docs.expo.dev/develop/development-builds/development-workflows/) · [React Native networking](https://reactnative.dev/docs/network.html)

**Client settings are visible.** Expo reads `process.env.EXPO_PUBLIC_API_URL` from its project environment and embeds that value in the bundle. Keep server secrets out of all `EXPO_PUBLIC_*` variables. Use the committed templates to share variable names. [Expo environment variables](https://docs.expo.dev/guides/environment-variables/)

## Expo milestone acceptance

- [ ] Open the app on a physical device and connect to the backend at its HTTPS origin.
- [ ] Join a batch, see a server quote, submit once, and retain the same request after a network retry.
- [ ] Run the simulated cutoff in the web dashboard. Refresh or reopen the phone app and see the saved result for that request.
- [ ] Check all three outcomes, full-fare consent, a closed batch, and no access to another student's result.
- [ ] Replay the seven-student comparison and confirm **6/7 vs. 4/7** and identical credit spend.
- [ ] Demonstrate a second seeded scenario and describe which values were simulated.

Record agreed product decisions in [agent.md](agent.md). Update this document when the API, simulation assumptions, estimates, or repository layout changes.
