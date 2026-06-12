#!/usr/bin/env bash
# debug-stuck-detector.sh
# PostToolUse -> Edit|Write|MultiEdit (Claude) and apply_patch (Codex)
# Counts re-edits (same source file edited again with no intervening commit or
# passing test run -- stuck-reset.sh clears state on those). At the threshold it
# injects an advisory via hookSpecificOutput.additionalContext (plain stdout or
# stderr on PostToolUse is invisible to the model). Fires once, then backs off
# until another full threshold of churn accumulates.
# Separate state from test-state-tracker -- no coupling.

INPUT=$(cat)

TOOL=$(echo "$INPUT" | jq -r '.tool_name // .tool // empty')

# Collect edited file paths. Claude Edit/Write/MultiEdit carry
# .tool_input.file_path; Codex apply_patch carries a patch body with
# "*** Update File:" / "*** Add File:" lines (may touch several files).
case "$TOOL" in
  apply_patch|functions.apply_patch)
    PATCH=$(echo "$INPUT" | jq -r 'if (.tool_input | type) == "string" then .tool_input else .tool_input.patch // .tool_input.input // .input // empty end')
    FILES=$(printf '%s\n' "$PATCH" | sed -nE 's/^\*\*\* (Update|Add) File: (.*)$/\2/p')
    ;;
  *)
    FILES=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
    ;;
esac
[ -z "$FILES" ] && exit 0

# State keyed by git toplevel + hook session_id, so state never leaks across
# sessions or concurrent agents in the same repo. Sweep stale files from
# abandoned sessions so they cannot fire spuriously later.
REPO=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
SESSION=$(echo "$INPUT" | jq -r '.session_id // empty')
KEY="${REPO}:${SESSION}"
STATE_FILE="/tmp/claude-stuck-$(echo "$KEY" | md5 2>/dev/null || echo "$KEY" | md5sum 2>/dev/null | cut -d' ' -f1).json"
find /tmp -maxdepth 1 -name 'claude-stuck-*.json' -mtime +1 -delete 2>/dev/null

# Initialize if missing or corrupt
if [ ! -f "$STATE_FILE" ] || ! jq -e type "$STATE_FILE" >/dev/null 2>&1; then
  echo '{"edit_counts":{},"re_edits":0,"last_fired":0}' > "$STATE_FILE"
fi

STATE=$(cat "$STATE_FILE")

# Count edits per source file; a re-edit is any edit after the first.
COUNTED=0
while IFS= read -r FILE; do
  [ -n "$FILE" ] || continue
  # Only count source file edits
  if ! echo "$FILE" | grep -qE '\.(py|ts|tsx|js|jsx|go|rs|c|cpp|h|hpp|cs|java|rb|swift|vue|svelte|zig|hs|ex|exs|kt|scala)$'; then
    continue
  fi
  COUNTED=1
  STATE=$(echo "$STATE" | jq --arg f "$FILE" '
    .edit_counts[$f] = ((.edit_counts[$f] // 0) + 1)
    | if .edit_counts[$f] > 1 then .re_edits = ((.re_edits // 0) + 1) else . end')
done <<EOF
$FILES
EOF
[ "$COUNTED" -eq 1 ] || exit 0

echo "$STATE" > "${STATE_FILE}.tmp" && mv "${STATE_FILE}.tmp" "$STATE_FILE"

REEDITS=$(echo "$STATE" | jq '.re_edits // 0')
LAST_FIRED=$(echo "$STATE" | jq '.last_fired // 0')
HOT_FILE=$(echo "$STATE" | jq -r '(.edit_counts | to_entries | max_by(.value) | .key) // empty')
HOT_COUNT=$(echo "$STATE" | jq '(.edit_counts | to_entries | max_by(.value) | .value) // 0')
HOT_REEDITS=$((HOT_COUNT > 0 ? HOT_COUNT - 1 : 0))

# Thresholds (configurable via env): total re-edits across files, and re-edits
# concentrated on a single file (the classic stuck signature, fires earlier).
THRESHOLD=${UNSTUCK_THRESHOLD:-8}
FILE_THRESHOLD=${UNSTUCK_FILE_THRESHOLD:-4}

TRIGGERED=false
[ "$REEDITS" -ge "$THRESHOLD" ] && TRIGGERED=true
[ "$HOT_REEDITS" -ge "$FILE_THRESHOLD" ] && TRIGGERED=true

# Fire once at the trigger, then back off; re-arm after another full
# threshold of re-edits accumulates without a reset.
if [ "$TRIGGERED" = "true" ]; then
  if [ "$LAST_FIRED" -eq 0 ] || [ "$REEDITS" -ge $((LAST_FIRED + THRESHOLD)) ]; then
    echo "$STATE" | jq --argjson n "$REEDITS" '.last_fired = (if $n > 0 then $n else 1 end)' \
      > "${STATE_FILE}.tmp" && mv "${STATE_FILE}.tmp" "$STATE_FILE"

    NFILES=$(echo "$STATE" | jq '.edit_counts | length')
    FILELIST=$(echo "$STATE" | jq -r '[.edit_counts | to_entries | sort_by(-.value) | .[] | "\(.key) (\(.value)x)"] | join(", ")' | head -c 300)

    MSG="STUCK DETECTOR: ${HOT_FILE} edited ${HOT_COUNT} times (${REEDITS} re-edits across ${NFILES} source files) with no commit or passing test run in between. Edit counts: ${FILELIST}. If the next step is another variation of the same fix, stop: use the unstuck skill to challenge the leading assumption (it can escalate to the adversarial-challenger agent), or the diagnose skill first if there is no trusted reproduction or fast feedback loop yet. This advisory backs off after firing -- act on it now rather than waiting for it to repeat."

    jq -n --arg ctx "$MSG" '{
      hookSpecificOutput: {
        hookEventName: "PostToolUse",
        additionalContext: $ctx
      }
    }'
  fi
fi

exit 0
