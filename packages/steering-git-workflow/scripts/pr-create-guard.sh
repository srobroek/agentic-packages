#!/usr/bin/env bash
set -euo pipefail

# Advise on possible PR creation when the structured checker is absent or fails.
# Unrelated Bash calls remain unaffected.
payload="$(cat 2>/dev/null || true)"
case "$payload" in
  *gh*pr*create*) ;;
  *) exit 0 ;;
esac

# Policy: missing python3 / checker error is not catastrophic — emit advisory
# allow so the agent is not hard-blocked by a missing runtime dependency.
deny_fallback() {
  printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow","additionalContext":"PR creation policy checker unavailable (python3 absent or errored). Proceed with --draft and a valid Tracks-Bead trailer in Beads repositories. Install python3 to enable automated verification."}}'
}

# PR_CREATE_GUARD_PYTHON lets tests inject /nonexistent without touching PATH.
_python3="${PR_CREATE_GUARD_PYTHON:-python3}"
command -v "$_python3" >/dev/null 2>&1 || { deny_fallback; exit 0; }
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
output="$(printf '%s' "$payload" | "$_python3" "$script_dir/pr-create-guard.py")" || {
  deny_fallback
  exit 0
}
printf '%s' "$output"
