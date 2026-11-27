# Replit briefs

Work orders for the Replit Agent, written by the planning side of the team. Do them in number order, one phase at a time. After each phase: run `python -m pytest`, check Preview, commit.

| # | Brief | What it builds |
|---|---|---|
| 02 | [02-street-pickup-both-ways.md](02-street-pickup-both-ways.md) | Street pickup within 200 m, both directions, ride options, friends groups, captains, confirm holds, lone-rider choices, simulation tab. Phase 0 (engine fixes) and part of Phase 3/5 may already be done; check the code and tests, skip what exists. |
| 03 | [03-ride-option-in-list.md](03-ride-option-in-list.md) | Campus Connect as a row in the Jeeny ride list (Economy · Taxi · Comfort · Campus Connect · Box) with a details sheet |

| 04 | [../design/campus-connect-screens/README.md](../design/campus-connect-screens/README.md) | Build the 43 designed Campus Connect screens (plan and ride, leave now and share, trips and recovery, dialogs) on top of briefs 02 and 03. Where a screen and a brief differ, follow the brief. |
| 05 | [05-friends-car-after-matching.md](05-friends-car-after-matching.md) | Friends (2–4) always get one car, also after matching ran: lobby, open/closed group, Men only / Women only by passenger gender, demo user is a man. |

Design reference: [docs/design/jeeny-screens/README.md](../design/jeeny-screens/README.md) (Jeeny app around the feature) and [docs/design/campus-connect-screens/README.md](../design/campus-connect-screens/README.md) (the feature).
