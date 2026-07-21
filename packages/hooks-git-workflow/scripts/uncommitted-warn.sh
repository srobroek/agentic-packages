#!/usr/bin/env bash
set -euo pipefail

input="$(cat)"
stop_active="$(printf '%s' "$input" | jq -r '.stop_hook_active // false' 2>/dev/null || echo "false")"

# Tracked, uncommitted changes (ignore untracked entries starting with '?').
dirty="$(git status --porcelain 2>/dev/null | grep -v '^\?' | head -5 || true)"

# Unpushed committed work: commits on HEAD not yet on its configured upstream.
# A branch without an upstream is ambiguous: it may be an intentional local or
# ephemeral orchestration branch, so stay silent until tracking is configured.
# Best-effort and quiet: any git failure leaves $ahead empty.
ahead=""
if branch="$(git symbolic-ref --quiet --short HEAD 2>/dev/null)"; then
  if upstream="$(git rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null)"; then
    n="$(git rev-list --count "${upstream}..HEAD" 2>/dev/null || echo 0)"
    if [[ "$n" =~ ^[0-9]+$ && "$n" -gt 0 ]]; then
      ahead="${n} commit(s) not pushed to ${upstream}"
    fi
  fi
fi

# Nothing uncommitted or verifiably ahead of a configured upstream: stay silent.
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
