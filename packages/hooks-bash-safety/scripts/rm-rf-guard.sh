#!/usr/bin/env bash
set -euo pipefail

input="$(cat)"
command="$(printf '%s' "$input" | jq -r '.tool_input.command // empty' 2>/dev/null || true)"

[[ -z "$command" ]] && exit 0

# Find an `rm` invocation whose flags include both recursive and force, in any
# form: -rf, -fr, -r -f, combined with other letters (-rfv), or the long
# options --recursive/--force.
rm_args="$(printf '%s' "$command" | grep -oE '(^|[;&|[:space:]])rm[[:space:]]+(-[^[:space:]]+[[:space:]]+)+[^;&|]*' | head -n1 || true)"
[[ -z "$rm_args" ]] && exit 0

flags="$(printf '%s' "$rm_args" | tr ' ' '\n' | grep -E '^-' || true)"
has_r=false
has_f=false
while IFS= read -r flag; do
  [[ -z "$flag" ]] && continue
  case "$flag" in
    --recursive) has_r=true ;;
    --force) has_f=true ;;
    --*) ;; # other long options carry no r/f meaning
    -*r*) has_r=true ;;&
    -*f*) has_f=true ;;
  esac
done <<<"$flags"

if [[ "$has_r" != true || "$has_f" != true ]]; then
  exit 0
fi

# Everything after `rm` that is not an option = the target paths.
targets="$(printf '%s' "$rm_args" | sed -E 's/^[;&|[:space:]]*rm[[:space:]]+//' | tr ' ' '\n' | grep -vE '^-' || true)"
display_targets="$(printf '%s' "$targets" | tr '\n' ' ' | sed 's/[[:space:]]*$//')"

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

# System-critical paths stay a hard deny — these are never legitimate. Every
# target is checked, not just the first.
while IFS= read -r target; do
  [[ -z "$target" ]] && continue
  case "$target" in
    /|//|~|"$HOME"|/Users|/Users/*|/System*|/Library*|/Applications|/bin*|/sbin*|/usr|/usr/*|/var*|/etc*|/private*)
      decide deny "rm -rf on system-critical path '$target' is blocked."
      ;;
  esac
done <<<"$targets"

# Everything else: soft confirm rather than hard block, so ordinary deletes
# (e.g. rm -rf ./build) prompt once instead of failing.
decide ask "rm -rf requested for '$display_targets'. Confirm this is the intended target before proceeding."
