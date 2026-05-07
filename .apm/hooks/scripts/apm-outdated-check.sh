#!/usr/bin/env bash
# Hook: SessionStart — check for outdated APM deps (asyncRewake, exit 2 to notify agent)
INPUT=$(cat)
AGENT_ID=$(echo "$INPUT" | jq -r '.agent_id // empty')
[ -n "$AGENT_ID" ] && exit 0  # Skip in subagents

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
[ -z "$REPO_ROOT" ] && exit 0
[ ! -f "$REPO_ROOT/apm.yml" ] && exit 0

STATE_DIR="$HOME/.local/state/apm"
mkdir -p "$STATE_DIR" 2>/dev/null
LAST_CHECK="$STATE_DIR/last-outdated-$(echo "$REPO_ROOT" | md5 2>/dev/null || echo "$REPO_ROOT" | md5sum 2>/dev/null | cut -d' ' -f1)"

# Check at most once per 4 hours
if [ -f "$LAST_CHECK" ]; then
    LAST_MOD=$(stat -f %m "$LAST_CHECK" 2>/dev/null || stat -c %Y "$LAST_CHECK" 2>/dev/null || echo 0)
    NOW=$(date +%s)
    AGE=$(( NOW - LAST_MOD ))
    [ "$AGE" -lt 14400 ] && exit 0
fi

command -v apm >/dev/null 2>&1 || exit 0

OUTPUT=$(cd "$REPO_ROOT" && apm outdated 2>/dev/null)
touch "$LAST_CHECK" 2>/dev/null

if echo "$OUTPUT" | grep -qi "outdated\|stale\|behind"; then
    echo "APM dependencies are outdated. Run \`apm deps update\` to get latest packages." >&2
    echo "$OUTPUT" | head -10 >&2
    exit 2  # asyncRewake: exit 2 delivers stderr to agent as system reminder
fi

exit 0
