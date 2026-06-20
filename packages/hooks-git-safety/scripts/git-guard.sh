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

# Hard reject: the operation is refused outright.
deny() {
  jq -cn --arg reason "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$reason}}'
  exit 0
}

# Soft block: surface the reason and require the user to confirm before running.
ask() {
  jq -cn --arg reason "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"ask",permissionDecisionReason:$reason}}'
  exit 0
}

# Soft warn: let the command proceed but surface a caution in the transcript.
warn() {
  jq -cn --arg reason "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"allow",permissionDecisionReason:$reason}}'
  exit 0
}

# reset --hard stays a HARD reject — it silently destroys uncommitted work with
# no per-file confirmation and is the easiest way to lose hours of changes.
if [[ "$lowered" =~ ${git}reset[[:space:]]+--hard ]]; then
  deny "refusing git reset --hard (hard block: destroys uncommitted work)"
fi

# Everything below is a SOFT guard: confirm (ask) or proceed-with-caution (warn),
# not a hard reject.

if [[ "$lowered" =~ ${git}checkout[[:space:]]+--([[:space:]]|$) ]]; then
  ask "git checkout -- discards local changes to the named paths — confirm to proceed."
fi

if [[ "$lowered" =~ ${git}restore([[:space:]].*)?(--staged|--worktree|--source) ]]; then
  ask "git restore can discard local changes — confirm to proceed."
fi

if [[ "$lowered" =~ ${git}clean[[:space:]].*-f ]]; then
  ask "destructive git clean removes untracked files — confirm to proceed."
fi

if [[ "$lowered" =~ ${git}branch[[:space:]]+(-d|--delete)([[:space:]]|$) ]]; then
  ask "git branch deletion — confirm to proceed."
fi

if [[ "$lowered" =~ ${git}stash[[:space:]]+(drop|clear) ]]; then
  ask "git stash drop/clear permanently discards stashed work — confirm to proceed."
fi

if [[ "$lowered" =~ ${git}tag[[:space:]]+(-d|--delete)[[:space:]] ]]; then
  ask "git tag deletion — confirm to proceed."
fi

if [[ "$lowered" =~ ${git}push([[:space:]].*)?(--force-with-lease|--force|-f)([[:space:]]|$) ]]; then
  warn "⚠ git force push rewrites remote history (--force/--force-with-lease) — proceeding (soft warn)."
fi

if [[ "$lowered" =~ ${git}worktree[[:space:]]+remove([[:space:]]|$) ]]; then
  ask "git worktree remove deletes the worktree checkout — confirm to proceed."
fi

exit 0
