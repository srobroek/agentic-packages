#!/usr/bin/env bash
# SubagentStart hook (orchestrate skill-scoped): inject the canonical comms
# protocol into every subagent spawned while the orchestrate skill is active.
# The skill's frontmatter scopes this to run time, so no marker gate is needed.
#
# Non-blocking by design: any failure here prints a loud stderr warning and
# still exits 0 so a spawn is never blocked -- but the run then proceeds
# WITHOUT the protocol, which must not happen silently.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BLOCK_FILE="$SCRIPT_DIR/../references/comms-block.md"

if [ ! -f "$BLOCK_FILE" ] && [ -n "${CLAUDE_PROJECT_DIR:-}" ]; then
  BLOCK_FILE="${CLAUDE_PROJECT_DIR}/.claude/skills/orchestrate/references/comms-block.md"
fi

if [ ! -f "$BLOCK_FILE" ]; then
  echo "inject-comms: comms-block.md not found (checked skill dir and \$CLAUDE_PROJECT_DIR); spawning WITHOUT the comms protocol" >&2
  exit 0
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "inject-comms: jq not found; spawning WITHOUT the comms protocol" >&2
  exit 0
fi

# Command substitution strips ALL trailing newlines; append a sentinel byte
# and strip only that back off so the injected block stays byte-identical
# (including its trailing newline) to the source file.
CTX="$(cat "$BLOCK_FILE"; printf x)"
CTX="${CTX%x}"
if [ -z "$CTX" ]; then
  echo "inject-comms: comms-block.md is empty; spawning WITHOUT the comms protocol" >&2
  exit 0
fi

jq -n --arg ctx "$CTX" '{
  hookSpecificOutput: {
    hookEventName: "SubagentStart",
    additionalContext: $ctx
  }
}'
