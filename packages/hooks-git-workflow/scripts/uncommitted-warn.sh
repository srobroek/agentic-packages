#!/usr/bin/env bash
set -euo pipefail

input="$(cat)"
stop_active="$(printf '%s' "$input" | jq -r '.stop_hook_active // false' 2>/dev/null || echo "false")"

# Tracked, uncommitted changes (ignore untracked entries starting with '?').
dirty="$(git status --porcelain 2>/dev/null | grep -v '^\?' | head -5 || true)"

# Unpushed committed work: commits on HEAD not yet on the upstream branch.
# If an upstream is configured, count ahead commits; if none is configured but
# the branch has commits, treat the branch as unpushed. Best-effort and quiet:
# any git failure leaves $ahead empty so the hook never blocks a stop.
ahead=""
if branch="$(git symbolic-ref --quiet --short HEAD 2>/dev/null)"; then
  if upstream="$(git rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null)"; then
    n="$(git rev-list --count "${upstream}..HEAD" 2>/dev/null || echo 0)"
    if [[ "$n" =~ ^[0-9]+$ && "$n" -gt 0 ]]; then
      ahead="${n} commit(s) not pushed to ${upstream}"
    fi
  elif git rev-parse --verify --quiet HEAD >/dev/null 2>&1 \
       && [ -n "$(git remote 2>/dev/null)" ]; then
    # A remote exists but this branch tracks nothing: real unpushed work.
    # Stay silent for local-only repos with no remote (nowhere to push).
    ahead="branch '${branch}' has no upstream — commits are unpushed"
  fi
fi

# Nothing uncommitted and nothing unpushed: stay silent.
[[ -n "$dirty" || -n "$ahead" ]] || exit 0

message="Unfinished git state before stop:"
[[ -n "$dirty" ]] && message="$message"$'\n'"$(printf 'Uncommitted changes (GW-1: commit before ending):\n%s' "$dirty")"
[[ -n "$ahead" ]] && message="$message"$'\n'"Unpushed work: ${ahead} — commit and push before ending (GW-2: push before ending)."
if [[ "$stop_active" == "true" ]]; then
  message="$message"$'\n'"(Allowing stop on second attempt.)"
fi

jq -n --arg msg "$message" '{
  systemMessage: $msg
}'
