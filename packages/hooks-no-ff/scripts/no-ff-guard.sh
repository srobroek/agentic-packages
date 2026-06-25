#!/usr/bin/env bash
set -euo pipefail

# PreToolUse hook: advise --no-ff on real `git merge` invocations.
#
# Portability floor: bash 3.2.57 + BSD sed/grep (stock macOS). Only POSIX
# parameter expansion, `case` globbing, and bash `[[ =~ ]]` ERE are used — no
# bash-4 features, no GNU-only regex.
#
# Contract: read a Claude PreToolUse event on stdin, emit a decision on stdout
#   {hookSpecificOutput:{hookEventName,permissionDecision,permissionDecisionReason}}
# and ALWAYS exit 0 (the decision lives in the JSON, not the exit code). When no
# guard fires, emit nothing and exit 0 ("allow" by omission).
#
# Locked severity policy: a merge lacking --no-ff is recoverable, so this is an
# advisory "ask", never a hard deny.

payload="$(cat)"
if [[ -z "$payload" ]]; then
  exit 0
fi

# tool_input is either an object ({command:"..."}) OR a bare string. The naive
# `.tool_input.command // .tool_input` form THROWS on a string and silently
# leaves $command empty (bypass). Type-check first so both shapes are read.
command="$(
  printf '%s' "$payload" | jq -r '
    if (.tool_input | type) == "string" then .tool_input
    else (.tool_input.command // empty)
    end
  ' 2>/dev/null || true
)"

if [[ -z "$command" || "$command" == "null" ]]; then
  exit 0
fi

# Soft block: surface the reason and require the user to confirm.
ask() {
  jq -cn --arg reason "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"ask",permissionDecisionReason:$reason}}'
  exit 0
}

# Strip a trailing shell comment so a `--no-ff` living only inside a comment
# does NOT satisfy the requirement. A comment starts at a `#` that follows
# whitespace (or at the very start). We do not model `#` inside quotes; the
# advisory-only severity makes a rare over-strip harmless.
strip_comment() {
  local s="$1"
  case "$s" in
    \#*) printf '%s' "" ; return 0 ;;        # whole line is a comment
  esac
  # Drop from the first " #" (space then hash) onward.
  case "$s" in
    *[[:space:]]\#*) printf '%s' "${s%%[[:space:]]\#*}" ; return 0 ;;
  esac
  printf '%s' "$s"
}

lowered="$(printf '%s' "$command" | tr '[:upper:]' '[:lower:]')"
code="$(strip_comment "$lowered")"

# Leading `git` plus global options (unquoted-arg form), mirroring the
# git-safety guard: zero-or-more `-flag [arg]` pairs before the subcommand.
git_prefix='git([[:space:]]+-[^[:space:]]+([[:space:]]+[^[:space:]]+)?)*[[:space:]]+'

# A REAL merge subcommand is `merge` followed by a word boundary (space or
# EOL). This anchored form already excludes `merge-base`, `mergetool`,
# `merge-file`, and `merge-tree` because none has a boundary right after
# `merge`. Not a real merge -> allow.
if ! [[ "$code" =~ ${git_prefix}merge([[:space:]]|$) ]]; then
  exit 0
fi

# Explicitly exclude non-merging / read-only argument forms even when a real
# `merge` token is present: --abort, --continue, --quit, --ff-only. These are
# recovery/inspection operations, not new merges, so they must NOT be flagged.
if [[ "$code" =~ (^|[[:space:]])--(abort|continue|quit|ff-only)([[:space:]=]|$) ]]; then
  exit 0
fi

# --no-ff must appear as a REAL token (boundary on both sides), not as a
# substring or inside the trailing comment (already stripped above).
if [[ "$code" =~ (^|[[:space:]])--no-ff([[:space:]=]|$) ]]; then
  exit 0
fi

# Real merge, no --no-ff token: advisory only.
ask "git merge without --no-ff: a fast-forward may erase the feature branch's merge point. Add --no-ff to preserve history, or confirm to proceed."

# Unreachable (ask exits), kept for clarity.
exit 0
