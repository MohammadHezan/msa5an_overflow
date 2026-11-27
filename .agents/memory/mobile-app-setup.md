---
name: Flask and Expo preview ownership
description: Why the existing backend and student phone preview need separate artifacts
---
Keep the existing Flask dashboard/backend in a separate web artifact from the Expo student app. Preserve the backend source and data at the repository root.

**Why:** the team requested Replit-hosted Expo Go phone previews without losing the existing Flask dashboard. Registering both backend and Metro as development services of the mobile artifact caused native manifest requests to reach Flask instead of Metro, even though browser routes worked.

**How to apply:** maintain separate artifact ownership when changing preview routing. Check native manifest URLs and their referenced bundles over the public Expo hostname; a working browser page or local manifest alone does not prove that the QR code will work.
