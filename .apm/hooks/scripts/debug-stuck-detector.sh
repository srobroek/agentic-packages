#!/usr/bin/env bash
# debug-stuck-detector.sh
# PostToolUse → Edit|Write|MultiEdit (async)
# Counts re-edits (same file edited again in current cycle), suggests diagnose/unstuck at threshold.
# Separate state from test-state-tracker — no coupling.

INPUT=$(cat)

# Extract file path from tool input
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
[ -z "$FILE" ] && exit 0

# Only count source file edits
if ! echo "$FILE" | grep -qE '\.(py|ts|tsx|js|jsx|go|rs|c|cpp|h|hpp|cs|java|rb|swift|vue|svelte|zig|hs|ex|exs|kt|scala)$'; then
  exit 0
fi

# State file keyed by git toplevel
KEY=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
STATE_FILE="/tmp/claude-stuck-$(echo "$KEY" | md5 2>/dev/null || echo "$KEY" | md5sum 2>/dev/null | cut -d' ' -f1).json"

# Initialize if missing
if [ ! -f "$STATE_FILE" ]; then
  echo '{"re_edits":0,"seen_files":[],"cooldown":false}' > "$STATE_FILE"
fi

STATE=$(cat "$STATE_FILE")

# Check if this file was already edited in this cycle
ALREADY_SEEN=$(echo "$STATE" | jq --arg f "$FILE" '[.seen_files // [] | .[] | select(. == $f)] | length > 0')

if [ "$ALREADY_SEEN" = "true" ]; then
  # Re-edit — increment counter
  echo "$STATE" | jq '.re_edits += 1' \
    > "${STATE_FILE}.tmp" && mv "${STATE_FILE}.tmp" "$STATE_FILE"
else
  # First edit to this file — track it, don't increment
  echo "$STATE" | jq --arg f "$FILE" '.seen_files = (.seen_files // [] | . + [$f])' \
    > "${STATE_FILE}.tmp" && mv "${STATE_FILE}.tmp" "$STATE_FILE"
fi

# Re-read after update
STATE=$(cat "$STATE_FILE")
REEDITS=$(echo "$STATE" | jq '.re_edits // 0')
COOLDOWN=$(echo "$STATE" | jq -r '.cooldown // false')

# Check threshold (configurable via env, default 8)
THRESHOLD=${UNSTUCK_THRESHOLD:-8}
if [ "$REEDITS" -ge "$THRESHOLD" ] && [ "$COOLDOWN" != "true" ]; then
  # Set cooldown to avoid repeated suggestions
  echo "$STATE" | jq '.cooldown = true' \
    > "${STATE_FILE}.tmp" && mv "${STATE_FILE}.tmp" "$STATE_FILE"

  # Get list of re-edited files for context
  FILES=$(echo "$STATE" | jq -r '.seen_files // [] | join(", ")' | head -c 200)

  # Emit suggestion via stderr (appears as system message to agent)
  cat >&2 <<EOF
STUCK DETECTOR: ${REEDITS} re-edits to previously-edited source files without committing.
Files in cycle: ${FILES}
Use diagnose first if there is no trusted reproduction or fast feedback loop.
Use unstuck when diagnosis is looping and you need an adversarial assumption check.
EOF
fi

exit 0
