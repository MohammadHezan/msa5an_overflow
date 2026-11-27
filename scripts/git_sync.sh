#!/usr/bin/env bash
# Pull from and push to GitHub (origin/main) every 3 minutes. Local changes are committed first.
# Run from the agent shell: workflows have no GitHub credentials.
# Stops merging (and leaves the tree untouched) if a pull would conflict, so nothing is overwritten.
cd "$(dirname "$0")/.." || exit 1
export DANGEROUSLY_ALLOW_GIT=1
export GIT_TERMINAL_PROMPT=0  # Fail instead of hanging if GitHub credentials are unavailable
INTERVAL="${SYNC_INTERVAL:-180}"

while true; do
  ts=$(date '+%H:%M:%S')
  if [ -e .git/MERGE_HEAD ]; then
    echo "[$ts] A merge is in progress; skipping until it is resolved."
  elif ! git fetch -q origin main; then
    echo "[$ts] Fetch failed."
  else
    if [ -n "$(git status --porcelain)" ]; then
      git add -A && git commit -qm "Auto-sync: work in progress" && echo "[$ts] Committed local changes."
    fi
    if [ "$(git rev-list --count HEAD..origin/main)" -gt 0 ]; then
      if git merge -q --no-edit origin/main; then
        echo "[$ts] Pulled $(git log -1 --format=%h origin/main) from GitHub."
      else
        git merge --abort
        echo "[$ts] CONFLICT pulling origin/main; merge aborted. Needs a manual merge."
      fi
    fi
    if [ ! -e .git/MERGE_HEAD ] && [ "$(git rev-list --count origin/main..HEAD)" -gt 0 ]; then
      if git push -q origin HEAD:main; then
        echo "[$ts] Pushed $(git log -1 --format=%h) to GitHub."
      else
        echo "[$ts] Push failed."
      fi
    else
      echo "[$ts] Up to date."
    fi
  fi
  sleep "$INTERVAL"
done
