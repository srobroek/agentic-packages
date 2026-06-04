#!/usr/bin/env bash
set -euo pipefail

input="$(cat)"
command="$(printf '%s' "$input" | jq -r '.tool_input.command // empty' 2>/dev/null || true)"

if ! printf '%s' "$command" | grep -qE '(^|[[:space:]])rm[[:space:]]+(-rf|-fr|-r[[:space:]]+-f|-f[[:space:]]+-r)[[:space:]]'; then
  exit 0
fi

path_arg="$(printf '%s' "$command" | sed -E 's/^.*rm[[:space:]]+(-rf|-fr|-r[[:space:]]+-f|-f[[:space:]]+-r)[[:space:]]+//' | sed 's/[[:space:]]*$//')"

decide() {
  # $1 = permissionDecision (deny|ask), $2 = reason
  jq -cn --arg decision "$1" --arg reason "$2" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: $decision,
      permissionDecisionReason: $reason
    }
  }'
  exit 0
}

# System-critical paths stay a hard deny — these are never legitimate.
case "$path_arg" in
  /|//|~|"$HOME"|/Users|/Users/*|/System*|/Library*|/Applications|/bin*|/sbin*|/usr|/usr/*|/var*|/etc*|/private*)
    decide deny "rm -rf on system-critical path '$path_arg' is blocked."
    ;;
esac

# Everything else: soft confirm rather than hard block, so ordinary deletes
# (e.g. rm -rf ./build) prompt once instead of failing.
decide ask "rm -rf requested for '$path_arg'. Confirm this is the intended target before proceeding."
