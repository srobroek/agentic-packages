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

if ! printf '%s' "$command" | grep -Eq '(^|[[:space:]])(rm|mv|cp|touch|chmod|chown|ln|tee|cat[[:space:]]*>|sed[[:space:]].*-i|perl[[:space:]].*-pi|python[0-9]*[[:space:]].*(write|open)|printf[[:space:]].*>)'; then
  exit 0
fi

if printf '%s' "$command" | grep -Eq '(^|[[:space:]])(~/.codex|/home/sjors/.codex|~/.claude|/home/sjors/.claude|~/.config|/home/sjors/.config)'; then
  printf 'Guarded path detected: review before overwriting managed config target in shell command: %s\n' "$command" >&2
  exit 2
fi

exit 0
