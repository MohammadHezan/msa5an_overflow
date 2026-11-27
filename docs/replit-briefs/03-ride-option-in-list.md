# Replit brief 03: Campus Connect as a Jeeny ride option

Do not change pooling/ or any pricing rule. Run `python -m pytest` before and after.

## Goal
After the student picks a destination, the ride list shows Campus Connect like any other Jeeny option:
Economy · Taxi · Jeeny Comfort · Campus Connect · Box. Picking it feels like picking Comfort: one tap on a row, then a short details sheet, then confirm.

## 1. The row (ride list in templates/phone.html)
- Order: Economy, Taxi, Jeeny Comfort, Campus Connect, Box. Default selection: Economy.
- Campus Connect row has the same height and layout as the others: car image (static/rides/campus.webp), name "Campus Connect", pink "Students" tag, subtitle "Share with students going your way".
- Right side: "from JOD 1.67" (the sample share for this destination from fare_estimates) with the Economy price struck through, plus "save ~60%" in green. Use real numbers from the backend.
- Remove the inline form from the list (name, gender, preference, friends). The list shows rows only.
- Prices come from the backend estimate for the chosen destination: Economy = solo fare, Taxi = 390 + 280/km, Comfort = solo fare × 1.3, Box = solo fare. Only Campus Connect books for real. The others show "Demo only" when confirmed.

## 2. The button
The confirm button label follows the selected row: "Confirm Economy", "Confirm Comfort", "Choose Campus Connect".

## 3. Campus Connect details sheet
Opens on "Choose Campus Connect". A back arrow returns to the list. In this order:
- Direction: [To campus] [From campus]
- Time: "Class ends at" (from campus) or "Class starts at" (to campus)
- Street pickup: "Walk 1 min to <street>" (brief 02, Phase 1)
- Ride with: [Anyone] [Women only] [Men only]. Women only is enabled only for women, Men only only for men (gender from the profile; in the demo, a small "I am" toggle at the top). Under women/men: "Matching may take longer."
- Book with friends: [Just me] [Start a group] [Join a group], with "Let others fill empty seats" when starting a group.
- Price box: "Your share about JOD 1.67 · alone JOD 4.50", with small text "Exact share shown before you confirm. You never pay more than riding alone."
- Button: "Find my shared ride" → the existing "Finding students going your way" screen.

## 4. Student check
Campus Connect shows only for verified students. In the demo, the profile shows "Verified student · <campus>". If not verified, the row shows a lock and "Verify your university email", which opens a one-field demo form. No real email is sent.

## 5. Entry points
- The side-menu card "Campus Connect · Shared rides for students" (docs/design/jeeny-screens/02-menu.png) opens the ride list with Campus Connect selected.
- The Home service tiles stay Ride · Comfort · Airport · Box.

## 6. Look
Match rows, sheet, radius (12/16), shadow and colors to docs/design/jeeny-screens (pink #EC008C, ink #101419, line #E7E7E7, Poppins). Mobile first, 390 px wide. Made-up names and places only.

## Done when (check in Preview at phone width)
- After picking a destination, the list shows 5 rows with real prices. Campus Connect shows "from JOD x", the struck Economy price and "save %".
- Tapping Campus Connect, then "Choose Campus Connect", opens the details sheet. Back returns to the list.
- Women only/Men only follow gender. Friends group works. "Find my shared ride" books and shows searching.
- Economy/Taxi/Comfort/Box confirm shows "Demo only".
- The side-menu card opens the list with Campus Connect selected.
- `python -m pytest` passes. Update replit.md.
