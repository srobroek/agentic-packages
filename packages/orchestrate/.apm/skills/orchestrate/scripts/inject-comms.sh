#!/usr/bin/env bash
# SubagentStart hook (orchestrate skill-scoped): inject the canonical comms
# protocol into every subagent spawned while the orchestrate skill is active.
# The skill's frontmatter scopes this to run time, so no marker gate is needed.
# Emits nothing (exit 0) if the block is missing, so a spawn is never blocked.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BLOCK_FILE="$SCRIPT_DIR/../references/comms-block.md"

[ -f "$BLOCK_FILE" ] || exit 0
command -v jq >/dev/null 2>&1 || exit 0

CTX="$(cat "$BLOCK_FILE")"
[ -n "$CTX" ] || exit 0

jq -n --arg ctx "$CTX" '{
  hookSpecificOutput: {
    hookEventName: "SubagentStart",
    additionalContext: $ctx
  }
}'
