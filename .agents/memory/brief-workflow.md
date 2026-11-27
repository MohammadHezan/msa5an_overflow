---
name: Ordered brief workflow
description: The user's required sequence and verification for the numbered project briefs
---
Follow the briefs listed in `docs/replit-briefs/README.md` in order, one phase at a time. Skip anything that already exists and passes its tests. After each phase run `python -m pytest`, check Preview at phone width, commit, and tell the user what was done before starting the next phase.

**Why:** the user explicitly requested this workflow.

**How to apply:** use the brief index as the work order, and report each phase separately rather than combining unfinished later work into an earlier phase.
