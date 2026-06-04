#!/usr/bin/env bash
set -euo pipefail

input="$(cat)"
command="$(printf '%s' "$input" | jq -r '.tool_input.command // empty' 2>/dev/null || true)"

printf '%s' "$command" | grep -q "gh pr merge" || exit 0
printf '%s' "$command" | grep -qE '\-\-(squash|merge|rebase)' && exit 0

echo "BLOCKED: PR merge requires explicit strategy. Use --squash for feature PRs, --merge for release PRs." >&2
exit 2
