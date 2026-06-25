#!/usr/bin/env bash
# Hook: PreToolUse -- advisory steering toward codebase-memory and repomix
# Injects additionalContext when agent uses plain Grep/Glob/Read for code discovery.
# Never blocks -- always exit 0.

INPUT=$(cat)

# Fire at most once per session. Key the gate on the hook payload's
# session_id; $PPID is a transient shell that changes per invocation and
# would re-fire the advisory on every tool call.
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty')

# Keep the gate inside a per-user private directory so other users on a
# shared host cannot read or pre-create our gate files.
GATE_DIR="${XDG_RUNTIME_DIR:-${TMPDIR:-/tmp}}/code-discovery-steer"
mkdir -p "$GATE_DIR" 2>/dev/null || exit 0
GATE="$GATE_DIR/${SESSION_ID:-$PPID}"

# Prune stale gates only within our own private directory.
find "$GATE_DIR" -maxdepth 1 -type f -mtime +1 -delete 2>/dev/null

if [ -f "$GATE" ]; then
    exit 0
fi

# Only emit the advisory if we could actually create the gate. If the touch
# fails (read-only dir, full disk), staying silent prevents the advisory from
# re-firing on every subsequent tool call.
touch "$GATE" 2>/dev/null
[ -f "$GATE" ] || exit 0

CTX="CODE DISCOVERY: Prefer codebase-memory-mcp (search_graph, trace_path, get_code_snippet) for symbol and call-path exploration. Use Repomix only when broad repository snapshot context is useful; it is a packer, not an incremental index. Grep/Glob/Read are fine for text content, config values, and non-code files."

jq -n --arg ctx "$CTX" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    additionalContext: $ctx
  }
}'
exit 0
