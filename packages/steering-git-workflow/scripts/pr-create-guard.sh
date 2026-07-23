#!/usr/bin/env bash
set -euo pipefail

# Fail closed for possible PR creation when the structured checker is absent
# or fails. Unrelated Bash calls remain unaffected.
payload="$(cat 2>/dev/null || true)"
case "$payload" in
  *gh*pr*create*) ;;
  *) exit 0 ;;
esac

deny_fallback() {
  printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"PR creation policy could not be verified. Ensure python3 is available, then create the PR with --draft and a valid Tracks-Bead trailer in Beads repositories."}}'
}

command -v python3 >/dev/null 2>&1 || { deny_fallback; exit 0; }
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
output="$(printf '%s' "$payload" | python3 "$script_dir/pr-create-guard.py")" || {
  deny_fallback
  exit 0
}
printf '%s' "$output"
