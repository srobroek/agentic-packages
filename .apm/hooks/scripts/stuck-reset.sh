#!/usr/bin/env bash
set -euo pipefail

input="$(cat)"
exit_code="$(printf '%s' "$input" | jq -r '.tool_response.exit_code // .tool_response.exitCode // "0"' 2>/dev/null || echo "0")"
[[ "$exit_code" == "0" ]] || exit 0

key="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
state_file="/tmp/claude-stuck-$(echo "$key" | md5 2>/dev/null || echo "$key" | md5sum 2>/dev/null | cut -d' ' -f1).json"

if [[ -f "$state_file" ]]; then
  echo '{"re_edits":0,"seen_files":[],"cooldown":false}' > "$state_file"
fi

exit 0
