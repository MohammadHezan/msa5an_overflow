# Jeeny app screens (design reference for Replit)

Exported from the team's Figma file "Campus Connect · Jeeny-inspired Rider UI Concept", page "01 · Rider Screens & Prototype". Each screen is 390 × 873 (phone). Personal data (names, phone, addresses, ride destinations, invite code) is **blurred** in these exports. In the app, use made-up sample data only.

These are the **Jeeny app around the feature**, not the Campus Connect flow. Use them so the phone screen (`templates/phone.html`) looks like a feature inside Jeeny. The Campus Connect flow screens (booking, ride options, friends group, plan and price, left-alone choices, ride code) are described in [docs/replit-briefs/02-street-pickup-both-ways.md](../../replit-briefs/02-street-pickup-both-ways.md) and are not designed in Figma yet.

## Screens

| File | Screen | Use in the demo |
|---|---|---|
| `00-campus-connect-entry.png` | Campus Connect card in the side menu ("Shared rides for students · NEW") | **The entry point.** Tapping it opens the Campus Connect flow. |
| `01-home.png` | Home: services, "Where to?", recent places, promos | Start screen of the phone demo |
| `02-menu.png` | Side menu with the Campus Connect card near the bottom | How a student finds the feature |
| `03-notifications.png` | Notifications | Optional: "Your shared ride is confirmed" |
| `04-my-rides.png` | My Rides history | Optional: past shared rides with "Shared" tag |
| `05-promotions.png` | Promotions (empty) | Optional |
| `06-wallet.png` | Wallet | Optional: where the share is paid |
| `07-cards.png` | Cards | Not needed |
| `08-invite.png` | Invite & Earn | Optional: invite classmates |
| `09-about.png` | About | Not needed |
| `10-help.png` | Help Center | Not needed |

## Design tokens (from the Figma variables)

| Token | Value |
|---|---|
| Jeeny pink (primary) | `#EC008C` |
| Ink (headings) | `#101419` |
| Body text | `#424242` |
| Secondary text | `#777A82` |
| Lines and dividers | `#E7E7E7` |
| Pale background | `#F1F1F1` |
| Pink tile background | `#FDF3F9` |
| Paper | `#FFFFFF` |
| Radius | 12 and 16 |
| Soft elevation | shadow `0 1px 4px rgba(0,0,0,0.12)` |
| Font | Poppins (already used in `static/jeeny.css`) |

## Instruction for Replit Agent

> Match `templates/phone.html` and `static/jeeny.css` to these screens: the home header, service tiles, search bar, side menu and card styles. Add the side menu from `02-menu.png` with the Campus Connect card from `00-campus-connect-entry.png`; tapping it opens the Campus Connect booking flow. Use the tokens above. Do not copy the blurred personal data; use made-up names and places.
