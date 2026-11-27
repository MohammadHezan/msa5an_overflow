# Campus Connect

Use this file to agree on the hackathon demo, record what students tell us, and guide Replit Agent as it works in this repository.

## What problem are we solving?

Students sometimes have a class they cannot reliably reach by bus. The notebook describes an Amman–Irbid commute involving multiple transport legs, the risk of being late, and the cost of taking a taxi alone. The pitch deck narrows the first demo to one Amman campus and highlights two situations: Sara's evening transport gap and Omar's crowded morning buses. The long-distance story explains the problem. The one-campus scenario gives the hackathon team a workflow it can build and test.

**Product idea.** A student requests a private ride for tomorrow and receives an answer that evening. A fixed pool of ride credits goes where it creates the most additional on-time options. A student who already has a workable bus can still receive a full-fare ride if they opted in and capacity is available.

**What the demo can establish.** Given the same requests, bus options, credit budget, and drivers, the allocator can produce more projected on-time arrivals than first come, first served in a specific scenario. Real bus reliability, willingness to pay, driver availability, and the effect on actual arrivals are pilot questions.

## Team decision form

Fill in the **Team answer** column as decisions are made. The working defaults let the team demo the app while those decisions are open.

| ID | Question | Working default in this build | Team answer |
| --- | --- | --- | --- |
| Q1 | Who is the first student we are building for, and which campus should the demo name? | One unnamed Amman campus. Use a crowded morning trip and an evening bus gap. | _Pending_ |
| Q2 | Is the first use case arriving on campus, leaving campus after class, or both? | Trips **to campus**. Sara's after-class ride home motivates the problem but needs a reverse route to appear in the app. Decide whether to adapt Sara's demo story or add outbound trips. | _Pending_ |
| Q3 | Which pickup areas and arrival windows belong in the demo? | Sweileh, University Street, Tabarbour, and Al Jubeiha. Morning 06:00–10:59, midday 11:00–15:59, and evening 16:00–22:00. | _Pending_ |
| Q4 | What makes a bus option workable for a student's deadline? | The demo uses a preset yes/no value per area and window. For a pilot, define acceptable transfers, walking, waiting, and how much schedule uncertainty is allowed. | _Pending_ |
| Q5 | What should students see before committing to a ride? | Suggested leave-by time, sample fare, and a separate full-fare opt-in. Pickup estimate uses preset travel time plus a 10-minute buffer. | _Pending_ |
| Q6 | How much credit is available and who gets priority? | Four JOD 1.50 credits from a JOD 6.00 budget, up to one per demo student. Prioritize reachable slots where the bus cannot get the student there on time. Queue order is preferred when outcomes are otherwise equal. | _Pending_ |
| Q7 | What should happen if no ride is confirmed? | Show the available preset bus when it fits. Otherwise suggest checking the next bus or trying a later arrival. | _Pending_ |
| Q8 | How will we judge success, and who will check it? | Reproduce the seeded 6/7 vs. 4/7 comparison, run a live request end to end in Preview, and record who verified it and when. | _Pending_ |
| Q9 | Who owns the Replit project, GitHub access, and demo presentation? | Team to assign. Verify shared project access before judging. | _Pending_ |

## Student interview form

Use the same questions with each student. Ask about their most recent real commute before showing the app. Use a general pickup area and skip names and exact addresses.

- **Campus, general pickup area, and trip direction** — _Answer_
- **Tell us about the last time you were late or worried about being late. Where were you going, what time did you need to arrive, and when did you actually arrive?** — _Answer_
- **What transport did you use? How many transfers or waits were involved, and how much did you pay for that trip?** — _Answer_
- **When did you realize the bus might fail you? How often has that happened in the last two weeks?** — _Answer_
- **What did you do when the bus option looked unreliable?** — _Answer_
- **If you could request a private ride the night before, what would you need to know before confirming it?** — _Answer_
- **At the sample fare and the sample fare minus JOD 1.50, what would you actually choose for that trip? Why?** — _Answer_
- **If the ride couldn't be confirmed at 9 p.m., what information would help you make another plan?** — _Answer_

**Decision log entry** — _Date · Question ID · Decision · Evidence or reason · Owner_

## MVP workflow

1. **Student request.** Start an empty batch, choose a preset pickup area and next-day arrival time, review the leave-by estimate and sample fare, then submit. Full-fare consent is optional. Each demo student can submit one request per batch.
2. **Evening cutoff.** Operations sets the budget, per-student cap, and available drivers per arrival window. **Run allocation** stands in for 9 p.m. in Amman. After it runs, the batch is closed to new requests.
3. **Allocation.** OR-Tools CP-SAT maximizes the number of riders who gain an on-time option within the credit and simulated driver limits. It favors using fewer credits for the same number of additional arrivals. The first-come baseline receives the same inputs and processes requests in queue order.
4. **Outcome.** Each student sees **confirmed with credit**, **confirmed at full fare**, or **ride unconfirmed** with a next option. Full-fare confirmation requires consent. The final batch is saved once so rerunning allocation cannot spend credits twice.
5. **Measurement.** Count each requester once. A requester counts as a simulated on-time arrival if they have a confirmed ride or a preset on-time bus. Display total requests, on-time arrivals, students without an on-time option, and credit spend for both methods.

The hackathon scope uses simulated bus availability, driver supply, fares, and outcomes. Live dispatch, payments, university sign-in, travel-time forecasting, and a trained overflow model belong to later work.

## Replit workflow

1. **Import the existing project.** Import [the GitHub repository](https://github.com/MohammadHezan/msa5an_overflow) once the code and this file are pushed. That push is currently blocked by write access. If the team needs to start before access is resolved, Replit also supports uploading a ZIP of the project source. Include `.replit` and `agent.md`. Leave out local data and dependencies such as `instance/` and `.venv/`. [Replit import instructions](https://docs.replit.com/build/import-from-providers)
2. **Run the baseline.** Click **Run** and open **Preview**. The existing `.replit` config installs dependencies from `requirements.txt` and starts Flask on port 5000. Run the acceptance checks below before changing implementation. [Replit Preview](https://docs.replit.com/features/editor/preview)
3. **Give Agent the file explicitly.** Paste the starter prompt below into the existing project's Agent chat. Add a question ID and the chosen team answer when asking Agent to implement a decision.
4. **Work in the existing files.** Use `app.py` for the student request, simulated cutoff, and SQLite state. Use `allocation.py` for allocation and comparison. Use `templates/index.html` and `static/` for the student, operations, and results views. Keep the single Python/Flask app for the hackathon.
5. **Verify in Preview.** After a change, rerun the affected checks and replay the seeded comparison. Record what passed, what still needs work, and any decision that changed the demo. Use a Replit checkpoint or Git commit to preserve a working version.

### Starter prompt for Replit Agent

> Read the root `agent.md` and the existing implementation. This repo already contains the Campus Connect MVP. Run it in Preview and verify the acceptance checklist, including the 6/7 vs. 4/7 comparison and the live student request flow. Use the working defaults for unanswered questions. When I give you a question ID and an agreed answer, apply that change in the existing app and rerun the affected checks. Report any mismatch between the doc and the app.

## Acceptance checklist

- [ ] **Student request.** In an empty batch, change the pickup area and arrival time. The leave-by estimate and fare update, and the submitted request shows **Awaiting cutoff**.
- [ ] **Three outcomes.** Confirm a credited ride, confirm an opted-in full-fare ride with a zero credit budget and available drivers, and show an unconfirmed ride with a next option when no ride is available.
- [ ] **Budget and capacity.** Credits stay within budget, the student cap is respected, and confirmed rides stay within each window's capacity. Zero available drivers means zero rides in that window.
- [ ] **One final result.** A repeated allocation returns the saved results without spending twice. A duplicate student request and a request after the cutoff are both rejected.
- [ ] **Seeded comparison.** Load seven students. Two have on-time buses, five need backup, and four JOD 1.50 credits can be spent. With default capacity and no full-fare opt-ins, Campus Connect shows **6/7** and first come, first served shows **4/7**, each spending **JOD 6.00**.
- [ ] **Judge walkthrough.** In Replit Preview, complete the Student → Operations → Results flow on phone and desktop widths. The judge can open an individual student's outcome from Results.

**Seeded scenario explanation.** The first four requests include the two students who already have on-time buses, so the first-come baseline helps only two more students arrive on time. Campus Connect gives all four credits to students without workable buses, and the two bus riders still count. This corrects the pitch deck's line about funding five students with four credits. These are simulated outcomes.
