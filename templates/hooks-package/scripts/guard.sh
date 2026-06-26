#!/usr/bin/env bash
# CRITICAL: this script lives at the PACKAGE ROOT (scripts/guard.sh), NOT
# nested under .apm/. Hook JSON references it as
#   ${PLUGIN_ROOT}/scripts/guard.sh
# which resolves from the installed plugin root, so root-level scripts/ is the
# correct location for HOOK scripts. (Skills are the opposite -- their scripts
# nest under the skill dir because SKILL.md uses file-relative paths.)
#
# SELF-GATING, no `if` filter.
# The hook JSON above intentionally does NOT use the `"if": "Bash(git push*)"`
# matcher filter. That pipe/glob `if` filter has been observed to SILENTLY
# no-match (the hook never fires, with no error), so guards that rely on it
# can be bypassed. Instead the matcher is the broad tool name ("Bash") and this
# script decides for itself whether the command is in scope, then exits 0
# (allow) early when it is not. Make the gating logic live in the script.
set -euo pipefail

# Read the hook payload from stdin. tool_input may be an object
# ({command: "..."}) OR a bare string; `.tool_input.command // .tool_input`
# THROWS on a string (jq cannot index a string) and would silently bypass the
# guard, so branch on type.
payload="$(cat)"
[[ -z "$payload" ]] && exit 0

command="$(
  printf '%s' "$payload" | jq -r '
    if (.tool_input|type)=="string" then .tool_input
    else (.tool_input.command // empty) end
  ' 2>/dev/null || true
)"
[[ -z "$command" || "$command" == "null" ]] && exit 0

# --- Self-gate: only act on the commands this guard cares about. -------------
# Replace this pattern with your own scope. Here we gate on `git push` as an
# example. Everything else falls through to the allow at the bottom.
case "$command" in
  *"git push"*) ;;   # in scope -- continue to the decision below
  *) exit 0 ;;       # out of scope -- allow without comment
esac

# --- Decision: deny (or "ask") with a reason. --------------------------------
# Emit the PreToolUse decision as JSON on stdout, then exit 0. (Exiting 0 with a
# decision payload is the contract; a nonzero exit is treated as a hook error.)
jq -cn --arg reason "example guard: git push is gated by this template" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    permissionDecision: "deny",
    permissionDecisionReason: $reason
  }
}'
exit 0
