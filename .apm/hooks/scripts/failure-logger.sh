#!/usr/bin/env bash
# failure-logger.sh -- PostToolUseFailure hook (async)
# Logs tool failures to ~/.claude/debug/tool-failures.log for diagnostics.
# Async -- does not block the session.

INPUT=$(cat)
TOOL=$(echo "$INPUT" | jq -r '.tool_name // "unknown"')
ERROR=$(echo "$INPUT" | jq -r '.error // .tool_error // "unknown error"' | head -c 200)
CWD=$(echo "$INPUT" | jq -r '.cwd // "unknown"')
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

LOG_DIR="$HOME/.claude/debug"
mkdir -p "$LOG_DIR"

echo "${TIMESTAMP} | ${TOOL} | ${CWD} | ${ERROR}" >> "$LOG_DIR/tool-failures.log"

# Rotate if over 1MB
LOG_FILE="$LOG_DIR/tool-failures.log"
LOG_SIZE=$(stat -c%s "$LOG_FILE" 2>/dev/null || stat -f%z "$LOG_FILE" 2>/dev/null || echo 0)
case "$LOG_SIZE" in ''|*[!0-9]*) LOG_SIZE=0 ;; esac
if [ -f "$LOG_FILE" ] && [ "$LOG_SIZE" -gt 1048576 ]; then
  mv "$LOG_FILE" "${LOG_FILE}.old"
fi

exit 0
