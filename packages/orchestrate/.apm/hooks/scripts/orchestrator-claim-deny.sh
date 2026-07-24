#!/usr/bin/env bash
# orchestrator-claim-deny.sh — PreToolUse hook: orchestrator claim prohibition.
#
# T0 (the orchestrator session) NEVER claims beads. This hook intercepts any
# `bd ... --claim` command issued in the orchestrator session and denies it
# with a self-correction message.
#
# RUN-MARKER GATE: the hook fires only when a run is active. Two probes (OR):
#   1. Env var ORCHESTRATE_RUN is set and non-empty.
#   2. Marker file exists: ${ORCHESTRATE_MARKER_FILE} (override) or default
#      ./.orchestration/.active-run (in cwd).
#
# Without the run marker: silently allow (do not interfere with non-run sessions).
#
# Contract (hook-io.md):
#   stdin  = PreToolUse payload JSON (tool_name, tool_input.command, ...)
#   stdout = {} (allow) | {"decision":"deny","reason":"..."} (deny)
#   exit   = 0 always (fail open on malformed input)
#
# Portability: bash 3.2, BSD/GNU tolerant.
set -uo pipefail   # NOT -e: must fail open.

emit_allow() { printf '{}\n'; exit 0; }
emit_deny() {
  jq -cn --arg r "$1" '{decision:"deny", reason:$r}' 2>/dev/null \
    || printf '{"decision":"deny","reason":"orchestrators do not claim beads"}\n'
  exit 0
}

# --- Run-marker gate ---
run_active=0
if [ -n "${ORCHESTRATE_RUN:-}" ]; then
  run_active=1
fi
if [ "$run_active" = "0" ]; then
  _marker="${ORCHESTRATE_MARKER_FILE:-}"
  if [ -n "$_marker" ] && [ -f "$_marker" ]; then
    run_active=1
  fi
  if [ "$run_active" = "0" ] && [ -f "./.orchestration/.active-run" ]; then
    run_active=1
  fi
fi
[ "$run_active" = "0" ] && emit_allow

# --- Parse the tool input ---
payload="$(cat 2>/dev/null || true)"
[ -z "$payload" ] && emit_allow

command -v jq >/dev/null 2>&1 || emit_allow

cmd="$(printf '%s' "$payload" | jq -r '
  .tool_input.command // .tool_input.cmd // .input.command // empty
' 2>/dev/null || true)"

[ -z "$cmd" ] && emit_allow

# Check whether this is a bd --claim invocation.
first_word="$(printf '%s' "$cmd" | awk '{print $1}')"
case "$first_word" in
  bd|*/bd) : ;;
  *)        emit_allow ;;
esac

printf '%s' "$cmd" | grep -qE '(^| )--claim( |$)' || emit_allow

emit_deny "orchestrators route work, they never claim beads; dispatch to a worker agent instead (T0 authority: create, close, dismiss, unclaim, deps, gates, shells, BRIEF)"
