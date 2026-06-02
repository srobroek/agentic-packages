#!/usr/bin/env bash
set -euo pipefail

input="$(cat)"
command="$(printf '%s' "$input" | jq -r '.tool_input.command // empty' 2>/dev/null || true)"
[[ -z "$command" ]] && exit 0

deny() {
  local reason="$1"
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"}}\n' "$reason"
  exit 0
}

stripped="$(printf '%s' "$command" | sed "s/'[^']*'//g" | sed 's/"[^"]*"//g')"

printf '%s' "$stripped" | grep -qE 'gh-api\.py' && exit 0
printf '%s' "$stripped" | grep -qE '(^|[;&|]\s*)gh\s+auth\b' && exit 0

gh_count="$(printf '%s' "$stripped" | { grep -oE '(^|[;&|]\s*)gh\s+' || true; } | wc -l | tr -d ' ')"
[[ "${gh_count:-0}" -lt 3 ]] && exit 0

if printf '%s' "$stripped" | grep -qE '(^|[;&|]\s*)gh\s+(api|issue|pr|label|project|gist|release|repo|secret|variable)\b'; then
  deny "Multiple GitHub CLI operations detected -- use gh-api.py for large batch work that needs rate-limit accounting, retries, or throttling. For interactive one-off usage, plain gh is allowed."
fi

exit 0
