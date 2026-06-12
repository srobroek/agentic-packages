#!/usr/bin/env bash
# stuck-reset.sh
# PostToolUse -> Bash (git commit / test runners). Resets stuck-detector state
# when the command succeeded (exit 0): a commit or a passing test run means the
# loop is making progress, so the re-edit streak starts over.
# Key derivation must stay identical to debug-stuck-detector.sh.
set -euo pipefail

input="$(cat)"
exit_code="$(printf '%s' "$input" | jq -r '.tool_response.exit_code // .tool_response.exitCode // "0"' 2>/dev/null || echo "0")"
[[ "$exit_code" == "0" ]] || exit 0

repo="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
session="$(printf '%s' "$input" | jq -r '.session_id // empty' 2>/dev/null || true)"
key="${repo}:${session}"
state_file="/tmp/claude-stuck-$(echo "$key" | md5 2>/dev/null || echo "$key" | md5sum 2>/dev/null | cut -d' ' -f1).json"

if [[ -f "$state_file" ]]; then
  echo '{"edit_counts":{},"re_edits":0,"last_fired":0}' > "$state_file"
fi

exit 0
