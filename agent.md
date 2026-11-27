# Campus Connect

Use this file to agree on the hackathon demo, record what students tell us, and guide Replit Agent as it works in this repository.

Use [document.md](document.md) for the matching and pricing rules, the Expo and backend task split, the proposed API and repeatable scenarios.

## What problem are we solving?

Getting home from campus is expensive for students who take a taxi alone, and buses may not fit when class ends. Many students leave the same campus at about the same time, heading the same direction, but have no easy way to share a car. Some women students only feel comfortable sharing with other women. The pitch deck narrows the first demo to one Amman campus and uses Sara's ride home after a 16:00 class as the main story.

**Product idea.** A proposed Jeeny feature. A student books a ride home before class ends. Campus Connect groups students heading the same way at about the same time, picks a meeting gate and pickup time, and shows each student their share of the fare before they confirm. The price reflects how far each student rides and is never more than riding alone. Women students can choose to match only with other women students.

**What the demo can establish.** Given a batch of requests, the matcher fills as few cars as possible within the direction, timing, seat and women-only rules, and shows how much each student saves compared with riding alone. Real distances, fares, demand, willingness to share and how often riders decline are pilot questions.

## Team decision form

Fill in the **Team answer** column as decisions are made. The working defaults let the team demo the app while those decisions are open.

| ID | Question | Working default in this build | Team answer |
| --- | --- | --- | --- |
| Q1 | Who is the first student we are building for, and which campus should the demo name? | One unnamed Amman campus. Sara, a woman student going home to Dabouq after a 16:00 class. | _Pending_ |
| Q2 | Is the first use case leaving campus, arriving on campus, or both? | Rides **home from campus** after class. Trips to campus are later work. | _Pending_ |
| Q3 | Which directions, gates and drop-offs belong in the demo? | West (main gate): Sweileh, Khalda, Dabouq, Al Bayader, Wadi As-Seer. North (north gate): Al Jubeiha, Shafa Badran, Abu Nseir. South (main gate): Tla' Al Ali, Um Al Summaq, Abdoun. East (east gate): Tabarbour, Marka. Distances are simulated. | _Pending_ |
| Q4 | Who can share a car? | Same direction, class end times within 20 minutes of each other, up to 4 students per car, and women-only requests matched only with women students. | _Pending_ |
| Q5 | How is the price split? | Each car is one regular ride at the regulated app fare (468 fils + 336 fils/km over the whole route). Each student pays in proportion to their km, the shares add up to the car fare exactly, and a student only shares if they save at least 20%. | _Pending_ |
| Q6 | What should students see before confirming? | Meeting gate, pickup time (15 minutes after the latest class end, rounded up to 5 minutes), other riders' names, drop-off order, their share and the solo fare. | _Pending_ |
| Q7 | What happens when someone declines or nobody matches? | A decline removes that rider and re-plans the car. Riders who already confirmed must confirm the new plan. A student with no compatible partner is offered a solo ride at the solo fare. | _Pending_ |
| Q8 | How will we judge success, and who will check it? | Replay the sample afternoon (five cars, Sara pays JOD 1.67 instead of JOD 4.50), run a live booking end to end in Preview, and record who verified it and when. | _Pending_ |
| Q9 | Who owns the Replit project, GitHub access and demo presentation? | Team to assign. Verify shared project access before judging. | _Pending_ |

## Student interview form

Use the same questions with each student. Ask about their most recent real trip home before showing the app. Use a general drop-off area and skip names and exact addresses.

- **Campus, general drop-off area, and the time your last class usually ends** — _Answer_
- **Tell us about the last time you went home from campus. How did you get there, how long did it take, and how much did you pay?** — _Answer_
- **How often do you take a taxi or ride-hail home alone? What stops you from sharing with other students?** — _Answer_
- **Would you share a car with students you don't know from the same campus? Would you want women-only matching (if applicable)?** — _Answer_
- **How long after class would you wait for a shared ride? How far would you walk to a meeting gate?** — _Answer_
- **What would you need to see before confirming a shared ride?** — _Answer_
- **At the solo fare and at the shown shared price for your area, which would you choose? Why?** — _Answer_
- **If someone in your car cancelled and your price went up, what would you do?** — _Answer_

**Decision log entry** — _Date · Question ID · Decision · Evidence or reason · Owner_

## MVP workflow

1. **Book.** On the Book view, a student enters a name, class end time (08:00–21:00), drop-off, and whether she is a woman student who wants women-only matching. The page shows the solo fare and a sample shared price for each drop-off. Each name can book once per batch.
2. **Match.** On the Matching view, the operator runs matching for the batch. OR-Tools CP-SAT groups students into as few cars as possible under the direction, time gap, seat and women-only rules. After it runs, the batch is closed to new requests and repeating it returns the saved cars.
3. **Review.** Each student sees their plan: gate, pickup time, riders, drop-off order, their share and the solo fare. A student with no match is offered a solo ride.
4. **Confirm or decline.** A confirmation applies only to the plan the student saw. A decline removes the rider and re-plans the car; anyone who already confirmed sees **plan changed** and confirms again.
5. **Trips.** The Trips view lists every car with its pickup, riders, shares and statuses, plus totals for requests, students sharing, cars, total paid and the solo total.

The hackathon scope uses simulated distances, fares and gates. Live dispatch, payments, university sign-in, real routing and driver supply belong to later work.

## Replit workflow

1. **Import the existing project.** Import [the GitHub repository](https://github.com/MohammadHezan/msa5an_overflow). Replit also supports uploading a ZIP of the project source. Include `.replit` and `agent.md`. Leave out local settings, data and dependencies such as `.env`, `instance/` and `.venv/`. [Replit import instructions](https://docs.replit.com/build/import-from-providers)
2. **Run the baseline.** Click **Run** and open **Preview**. The `.replit` config installs dependencies from `requirements.txt` and starts Flask on port 5000. Run the acceptance checks below before changing implementation. [Replit Preview](https://docs.replit.com/features/editor/preview)
3. **Give Agent the file explicitly.** Paste the starter prompt below into the project's Agent chat. Add a question ID and the chosen team answer when asking Agent to implement a decision.
4. **Work in the existing files.** Use `app.py` for booking, matching, confirm/decline and SQLite state. Use `sharing.py` for corridors, fares, grouping and the price split. Use `templates/index.html` and `static/` for the Book, Matching and Trips views. Keep the single Python/Flask app for the hackathon.
5. **Verify in Preview.** After a change, rerun the affected checks and replay the sample afternoon. Record what passed, what still needs work, and any decision that changed the demo. Use a Replit checkpoint or Git commit to preserve a working version.

### Starter prompt for Replit Agent

> Read the root `agent.md` and the existing implementation. This repo contains the Campus Connect shared-ride MVP. Run it in Preview and verify the acceptance checklist, including Sara's women-only car and the decline flow. Use the working defaults for unanswered questions. When I give you a question ID and an agreed answer, apply that change in the existing app and rerun the affected checks. Report any mismatch between the doc and the app.

## Acceptance checklist

- [ ] **Book.** In an empty batch, change the drop-off. The solo fare and sample share update, and the submitted request shows **waiting** until matching runs. A man cannot choose women-only matching.
- [ ] **Match.** Matching groups only students in the same direction with class end times at most 20 minutes apart, at most 4 per car. A women-only student is never matched with a man. Repeating matching returns the same cars, and a request after matching is rejected.
- [ ] **Prices.** Each share is at least JOD 0.50, a multiple of JOD 0.05, never more than the student's solo fare, and larger for students who ride farther in the same car.
- [ ] **Confirm and decline.** Confirm Sara's plan, then decline as Rama. Sara sees **plan changed** with a new share and confirms again. A confirmation of an outdated plan is rejected.
- [ ] **Sample afternoon.** Load the ten students and match. There are five cars. Sara, Rama and Huda share a women-only West car from the main gate at 16:15, and Sara pays **JOD 1.67** instead of **JOD 4.50**. Kareem is offered a solo ride. Zaid rides alone east.
- [ ] **Judge walkthrough.** In Replit Preview, complete the Book → Matching → Trips flow on phone and desktop widths. The judge can open an individual student's plan from Trips.
