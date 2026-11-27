---
name: Expo app is standalone, not a Replit artifact
description: Why mobile/ is its own Expo project instead of a Replit-managed Expo app
---
mobile/ is a standalone Expo project, not a Replit multi-artifact Expo app.
**Why:** the team plan keeps Flask at the repo root with mobile/ as a separate project; becoming an artifact would mean restructuring the whole repo into a pnpm workspace.
**How to apply:** don't convert mobile/ to an artifact unless the user asks for Replit-hosted phone previews.
