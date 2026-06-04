#!/usr/bin/env bash
set -euo pipefail

payload="$(cat)"
if [[ -z "$payload" ]]; then
  exit 0
fi

command="$(
  printf '%s' "$payload" | jq -r '
    .tool_input.command // .tool_input // empty
  ' 2>/dev/null || true
)"

if [[ -z "$command" || "$command" == "null" ]]; then
  exit 0
fi

lowered="$(printf '%s' "$command" | tr '[:upper:]' '[:lower:]')"

deny() {
  jq -cn --arg reason "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$reason}}'
  exit 0
}

if [[ "$lowered" =~ git[[:space:]]+reset[[:space:]]+--hard ]]; then
  deny "refusing git reset --hard"
fi

if [[ "$lowered" =~ git[[:space:]]+checkout[[:space:]]+-- ]]; then
  deny "refusing git checkout --"
fi

if [[ "$lowered" =~ git[[:space:]]+restore([[:space:]].*)?(--staged|--worktree|--source) ]]; then
  deny "refusing git restore that can discard local changes"
fi

if [[ "$lowered" =~ git[[:space:]]+clean[[:space:]].*-f ]]; then
  deny "refusing destructive git clean"
fi

if [[ "$lowered" =~ git[[:space:]]+branch[[:space:]]+-d([[:space:]]|$) ]]; then
  deny "refusing git branch deletion from Codex"
fi

if [[ "$lowered" =~ git[[:space:]]+stash[[:space:]]+(drop|clear) ]]; then
  deny "refusing git stash drop/clear"
fi

if [[ "$lowered" =~ git[[:space:]]+tag[[:space:]]+-d[[:space:]] ]]; then
  deny "refusing git tag -d"
fi

if [[ "$lowered" =~ git[[:space:]]+push([[:space:]].*)?(--force-with-lease|--force|-f)([[:space:]]|$) ]]; then
  deny "refusing force push from Codex"
fi

if [[ "$lowered" =~ git[[:space:]]+worktree[[:space:]]+remove([[:space:]]|$) ]]; then
  deny "refusing git worktree remove from Codex"
fi

exit 0
