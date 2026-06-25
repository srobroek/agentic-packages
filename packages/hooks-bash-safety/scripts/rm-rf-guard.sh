#!/usr/bin/env bash
set -euo pipefail

input="$(cat)"
# tool_input may be an object ({command: "..."}) OR a bare string. The naive
# `.tool_input.command // .tool_input` form THROWS on a string input (jq cannot
# index a string), which would silently bypass this guard. Branch on type.
command="$(printf '%s' "$input" | jq -r 'if (.tool_input|type)=="string" then .tool_input else (.tool_input.command // empty) end' 2>/dev/null || true)"

[[ -z "$command" || "$command" == "null" ]] && exit 0

# Find an `rm` invocation whose flags include both recursive and force, in any
# form: -rf, -fr, -r -f, combined with other letters (-rfv), or the long
# options --recursive/--force.
rm_args="$(printf '%s' "$command" | grep -oE '(^|[;&|[:space:]])rm[[:space:]]+(-[^[:space:]]+[[:space:]]+)+[^;&|]*' | head -n1 || true)"
[[ -z "$rm_args" ]] && exit 0

flags="$(printf '%s' "$rm_args" | tr ' ' '\n' | grep -E '^-' || true)"
has_r=false
has_f=false
# bash 3.2 has no `;;&` case fallthrough, so detect r and f with independent
# tests. Short flags may be bundled (-rf, -fr, -rfv); long flags are spelled out.
while IFS= read -r flag; do
  [[ -z "$flag" ]] && continue
  case "$flag" in
    --recursive) has_r=true ;;
    --force) has_f=true ;;
    --*) ;; # other long options carry no r/f meaning
    -*)
      # Bundled short option group, e.g. -rf or -rfv. Test each letter
      # independently — a single flag can supply both r and f.
      [[ "$flag" == *r* ]] && has_r=true
      [[ "$flag" == *f* ]] && has_f=true
      ;;
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
#
# The command string is read from JSON and never shell-expanded here, so the
# target tokens are literal. That means `rm -rf /*` arrives as the two-char
# token `/*` (NOT a glob), and the home dir may arrive as the un-expanded
# `$HOME`/`${HOME}`/`~` tokens. The root forms (`/`, `//`, literal `/*`) and the
# enumerated system directories are unrecoverable and stay hard deny; deeper
# absolute paths (e.g. /tmp/build, a project's node_modules) are recoverable and
# fall through to the soft-ask below per the severity policy.
while IFS= read -r target; do
  [[ -z "$target" ]] && continue
  # The quoted '~' / '~/' patterns intentionally match the LITERAL tilde token
  # from the unexpanded command string; expanding it (SC2088's suggestion) would
  # break the match, so the warning is suppressed deliberately.
  # shellcheck disable=SC2088
  case "$target" in
    /|//|'/*'|'~'|'~/'|'$HOME'|'${HOME}'|"$HOME"|/Users|/System*|/Library*|/Applications*|/bin*|/sbin*|/usr|/usr/*|/var*|/etc*|/private*)
      decide deny "rm -rf on system-critical path '$target' is blocked."
      ;;
  esac
done <<<"$targets"

# Everything else: soft confirm rather than hard block, so ordinary deletes
# (e.g. rm -rf ./build) prompt once instead of failing.
decide ask "rm -rf requested for '$display_targets'. Confirm this is the intended target before proceeding."
