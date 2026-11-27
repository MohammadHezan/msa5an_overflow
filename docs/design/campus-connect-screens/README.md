# Campus Connect screens (design for Replit)

Exported from the team's Figma file "Campus Connect · Jeeny-inspired Rider UI Concept", page "01 · Rider Screens & Prototype", sections "Campus Connect / 01–04". Phone screens are 390 × 873. All names, emails, plates and places are made up. Colors, font and radius follow [../jeeny-screens/README.md](../jeeny-screens/README.md).

Build the student flow in `templates/phone.html` + `static/jeeny.css` to match these screens. The rules behind them (matching, prices, ride options, friends, holds) are in [../../replit-briefs/](../../replit-briefs/README.md).

## 01 · Plan, share and ride (the main flow)

| File | Screen |
|---|---|
| `01-campus-home.png` | Campus Connect home |
| `02-student-verification.png` | Verify with university email |
| `03-verify-email-code.png` | Enter the email code |
| `04-choose-university.png` | Choose university and campus |
| `05-destination.png` | Destination |
| `06-pickup-time.png` | Pickup time (class end) |
| `07-ride-preferences.png` | Ride preferences (Anyone / Women / Men, friends) |
| `08-review-request.png` | Review the request |
| `09-matching-request.png` | Finding students going your way |
| `10-your-matched-group.png` | Your matched group |
| `11-transparent-fare.png` | Fare breakdown: one car fare, split by km (Sara JOD 1.67 of 5.844) |
| `12-seat-confirmed.png` | Seat confirmed |
| `13-captain-pickup.png` | Captain on the way, car, plate, call/message |
| `14-personal-boarding-code.png` | Personal boarding code for the captain |
| `15-shared-trip-in-progress.png` | Trip in progress |
| `16-shared-ride-receipt.png` | Receipt |

## 02 · Leave now and share (lone rider choice C)

| File | Screen |
|---|---|
| `17-leave-now-share.png` | Leave now and share on the way |
| `18-leave-now-pickup.png` | Leave-now pickup |
| `19-ride-started-sharing-on.png` | Ride started, sharing on |
| `20-approve-lina-s-pickup.png` | Approve a rider joining on the route (Lina) |
| `21-approve-noor-s-pickup.png` | Approve a second rider (Noor) |
| `22-sharing-along-the-route.png` | Sharing along the route |
| `23-live-share-receipt.png` | Receipt after sharing on the way |
| `24-no-one-joined-receipt.png` | Receipt when no one joined (solo fare) |
| `25-leg-by-leg-fare-split.png` | Leg-by-leg fare split |
| `38-two-person-shared-ride.png` | Two-person shared ride |
| `39-two-person-receipt.png` | Two-person receipt |

## 03 · Trips, controls and recovery

| File | Screen |
|---|---|
| `26-my-campus-trips.png` | My campus trips (upcoming) |
| `27-campus-trip-history.png` | Past campus rides with savings |
| `28-saved-campus-routes.png` | Saved routes |
| `29-no-group-found.png` | No group found → choices |
| `30-offer-changed.png` | Offer changed (someone left) |
| `31-updated-offer-accepted.png` | Updated offer accepted |
| `32-cancel-request-review.png` | Cancel request (review) |
| `33-request-cancelled.png` | Request cancelled |
| `34-campus-ride-help.png` | Campus ride help |
| `35-connection-lost.png` | Connection lost |
| `36-campus-not-available.png` | Campus not available |
| `37-email-verification-recovery.png` | Email verification recovery |

## 04 · Dialogs and feedback

| File | Screen |
|---|---|
| `dialog-share-your-ride.png` | Share your live trip link |
| `feedback-trip-link-copied.png` | Toast: trip link copied |
| `feedback-verification-code-sent.png` | Toast: verification code sent |
| `feedback-campus-notifications-on.png` | Toast: campus notifications on |

## Where the design and the briefs differ (follow the brief)

- **Pickup point:** some screens (e.g. 13) say "walk to the main gate, about 10 minutes". Brief 02 says each student walks at most **200 m** to the street the captain drives through. Show the student's own street and walk time from brief 02 instead of the gate.
- **Fare numbers:** screen numbers are examples. Always show the numbers the backend calculates.

## Instruction for Replit Agent

> Build the Campus Connect student flow to match the screens in this folder, in the order of the tables. Reuse the Jeeny styles from docs/design/jeeny-screens. Wire every screen to the existing backend (booking, matching, confirm/decline, ride codes) and to the rules in docs/replit-briefs. Where a screen and a brief differ, follow the brief. Use made-up names and places only.
