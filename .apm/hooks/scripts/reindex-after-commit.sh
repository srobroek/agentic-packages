#!/usr/bin/env bash
# Hook: PostToolUse — refresh code intelligence indexes after git commit
# Fires on git commit. Async, non-blocking — does not delay the workflow.
# Refreshes both codebase-memory (fast reindex) and repomix (repack XML).

INPUT=$(cat)
AGENT_ID=$(echo "$INPUT" | jq -r '.agent_id // empty')
[ -n "$AGENT_ID" ] && exit 0  # Skip in subagents

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
[ -z "$REPO_ROOT" ] && exit 0

# codebase-memory fast reindex
if command -v codebase-memory-mcp >/dev/null 2>&1; then
    codebase-memory-mcp cli index_repository "{\"repo_path\":\"$REPO_ROOT\",\"mode\":\"fast\"}" 2>/dev/null
fi

# Update staleness marker
STATE_DIR="$HOME/.local/state/codebase-memory"
mkdir -p "$STATE_DIR" 2>/dev/null
REPO_HASH=$(echo "$REPO_ROOT" | md5sum 2>/dev/null | cut -d' ' -f1 || echo "$REPO_ROOT" | md5 -q 2>/dev/null)
touch "$STATE_DIR/last-index-$REPO_HASH" 2>/dev/null

# Repomix repack (async — runs in background, can be slow for large repos)
if command -v repomix >/dev/null 2>&1; then
    PROJ=$(basename "$REPO_ROOT")
    OUTPUT="/tmp/repomix-${PROJ}.xml"
    repomix --directory "$REPO_ROOT" --style xml --output "$OUTPUT" --no-security-check 2>/dev/null &
elif command -v npx >/dev/null 2>&1; then
    PROJ=$(basename "$REPO_ROOT")
    OUTPUT="/tmp/repomix-${PROJ}.xml"
    timeout 120 npx --yes repomix --directory "$REPO_ROOT" --style xml --output "$OUTPUT" --no-security-check 2>/dev/null &
fi

exit 0
