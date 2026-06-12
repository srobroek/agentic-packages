#!/usr/bin/env bash
set -euo pipefail

input="$(cat)"
stop_active="$(printf '%s' "$input" | jq -r '.stop_hook_active // false' 2>/dev/null || echo "false")"

dirty="$(git status --porcelain 2>/dev/null | grep -v '^\?' | head -5 || true)"
[[ -n "$dirty" ]] || exit 0

message="$(printf 'Uncommitted changes detected before stop:\n%s' "$dirty")"
if [[ "$stop_active" == "true" ]]; then
  message="$message"$'\n'"(Allowing stop on second attempt.)"
fi

jq -n --arg msg "$message" '{
  systemMessage: $msg
}'
