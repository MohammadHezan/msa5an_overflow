# Campus Connect mobile prototype

Open **Campus Connect · Ride Booking Prototype** in Figma using the link from the project owner. Select **Present** and start the **Campus Connect student demo** flow.

The prototype uses the reference's ride-app navigation as a starting point. Campus Connect has its own visual style and uses sample profile, trip, and payment details. The navigation, account, service shortcuts, destination picker, saved places, notification, and wallet screens provide context for the two hackathon features.

## Sidebar features

| Entry | Demo flow | Implementation handoff |
| --- | --- | --- |
| **Plan a campus ride** | Select the sample Tabarbour pickup and 08:30 arrival. See a 07:48 leave-by estimate and JOD 4.25 sample fare. Choose whether a full-fare ride is acceptable and submit to see the pending state. | Use the draft quote and request endpoints in [document.md](document.md). Render backend estimates and fares from response fields. |
| **Ride status & credits** | Open an example JOD 4.25 ride with a JOD 1.50 credit and JOD 2.75 due. Follow the sample full-fare and unconfirmed outcomes to see alternate states. | Use the student's saved request status. Show full fare only with consent and show a next option when the ride is unconfirmed. |

## Prototype walkthrough

1. Start at **Home**. Open the sidebar and choose **Plan a campus ride**.
2. Select the sample pickup and arrival time. Submit with the default credit-only preference, then preview the outcome from the pending screen.
3. Reopen the request and opt into full fare to try the alternate submission path.
4. Open **Ride status & credits** from the sidebar and review all three final states.
5. Open the account from the sidebar and try the destination picker from Home.

The pickup and destination pickers show preset choices. Requests, fares, membership, referrals, and payments are sample interactions in Figma. The mobile client and shared Flask API are planned separately in [document.md](document.md).
