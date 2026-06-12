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

# Matches `git` followed by any global options (-C <path>, -c <k=v>,
# --git-dir=<p>, --work-tree=<p>, --no-pager, ...) before the subcommand,
# so prefixed invocations cannot slip past the subcommand patterns.
git='git([[:space:]]+-[^[:space:]]+([[:space:]]+[^[:space:]]+)?)*[[:space:]]+'

deny() {
  jq -cn --arg reason "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$reason}}'
  exit 0
}

if [[ "$lowered" =~ ${git}reset[[:space:]]+--hard ]]; then
  deny "refusing git reset --hard"
fi

if [[ "$lowered" =~ ${git}checkout[[:space:]]+--([[:space:]]|$) ]]; then
  deny "refusing git checkout -- (discards local changes)"
fi

if [[ "$lowered" =~ ${git}restore([[:space:]].*)?(--staged|--worktree|--source) ]]; then
  deny "refusing git restore that can discard local changes"
fi

if [[ "$lowered" =~ ${git}clean[[:space:]].*-f ]]; then
  deny "refusing destructive git clean"
fi

if [[ "$lowered" =~ ${git}branch[[:space:]]+(-d|--delete)([[:space:]]|$) ]]; then
  deny "refusing git branch deletion"
fi

if [[ "$lowered" =~ ${git}stash[[:space:]]+(drop|clear) ]]; then
  deny "refusing git stash drop/clear"
fi

if [[ "$lowered" =~ ${git}tag[[:space:]]+(-d|--delete)[[:space:]] ]]; then
  deny "refusing git tag deletion"
fi

if [[ "$lowered" =~ ${git}push([[:space:]].*)?(--force-with-lease|--force|-f)([[:space:]]|$) ]]; then
  deny "refusing git force push"
fi

if [[ "$lowered" =~ ${git}worktree[[:space:]]+remove([[:space:]]|$) ]]; then
  deny "refusing git worktree remove"
fi

exit 0
