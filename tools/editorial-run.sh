#!/usr/bin/env bash
set -euo pipefail
# Dedicated checkout; never reset the legacy blog-sync worktree.
editorial_state="${JOURNAL_EDITORIAL_STATE:-$HOME/.local/state/journal-editorial}"
editorial_runtime="$editorial_state/runtime"
mkdir -p "$editorial_state"
exec 9>"$editorial_state/runtime.lock"
flock -w 300 9
if [[ ! -d "$editorial_runtime/.git" ]]; then
  git clone --quiet --branch main --single-branch https://github.com/swchoi1994/swchoi1994.github.io.git "$editorial_runtime"
fi
cd "$editorial_runtime"
if [[ -n "$(git status --porcelain)" ]]; then
  echo 'Runtime has local edits; preserve and inspect them before continuing.' >&2
  exit 1
fi
git fetch --quiet origin main
git merge --ff-only --quiet origin/main
export JOURNAL_EDITORIAL_STATE="$editorial_state"
export NODE_PATH="$editorial_runtime/tools/browser/node_modules${NODE_PATH:+:$NODE_PATH}"
# Pin and cache the browser dependency. npm ci is needed only after lock changes.
if [[ ! -d "$editorial_runtime/tools/browser/node_modules/playwright" ]] || [[ ! -f "$editorial_state/browser-lock.sha256" ]] || ! sha256sum -c --status "$editorial_state/browser-lock.sha256"; then
  npm ci --prefix tools/browser >&2
  tools/browser/node_modules/.bin/playwright install chromium >&2
  sha256sum tools/browser/package-lock.json > "$editorial_state/browser-lock.sha256"
fi
exec python3 tools/editorial.py "$@"
