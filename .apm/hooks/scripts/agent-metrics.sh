#!/usr/bin/env bash
# Hook: SubagentStop — log agent metrics (async, non-blocking)
INPUT=$(cat)
AGENT_TYPE=$(echo "$INPUT" | jq -r '.agent_type // "unknown"')
AGENT_ID=$(echo "$INPUT" | jq -r '.agent_id // "unknown"')
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
METRICS_DIR="${REPO_ROOT:-.}/.claude/metrics"
mkdir -p "$METRICS_DIR" 2>/dev/null

TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "{\"timestamp\":\"$TIMESTAMP\",\"agent_type\":\"$AGENT_TYPE\",\"agent_id\":\"$AGENT_ID\"}" >> "$METRICS_DIR/agents.jsonl"

exit 0
