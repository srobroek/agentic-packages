#!/usr/bin/env bash
set -euo pipefail

payload="$(cat)"
if [[ -z "$payload" ]]; then
  exit 0
fi

command="$(
  printf '%s' "$payload" | jq -r '
    .tool_input.command // .tool_input // empty
  ' 2>/dev/null || true
)"

if [[ -z "$command" || "$command" == "null" ]]; then
  exit 0
fi

trimmed="$(printf '%s' "$command" | sed -E 's/^[[:space:]]+//; s/[[:space:]]+$//')"

if [[ "$trimmed" =~ ^chezmoi($|[[:space:]]) ]]; then
  jq -cn '{
    hookSpecificOutput: {
      hookEventName: "PermissionRequest",
      decision: {
        behavior: "allow"
      }
    }
  }'
fi
