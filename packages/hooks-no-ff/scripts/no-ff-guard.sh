#!/usr/bin/env bash
set -euo pipefail

input="$(cat)"
command="$(printf '%s' "$input" | jq -r '.tool_input.command // empty' 2>/dev/null || true)"

if printf '%s' "$command" | grep -q "git merge" && ! printf '%s' "$command" | grep -q "\-\-no-ff"; then
  echo "BLOCKED: Feature branch merges require --no-ff to preserve history. Add --no-ff flag." >&2
  exit 2
fi

exit 0
