#!/usr/bin/env bash
# tier-gate.sh: decide whether a style/workflow nudge should fire for the
# current session model. Frontier tiers (fable/opus) follow steering without
# per-call reminders; smaller tiers still benefit from the nudge.
#
# Sourced helper. Usage:
#   . "$(dirname "$0")/tier-gate.sh"
#   tier_gate "$payload" || exit 0    # frontier model -> stay silent
#
# Reads the model from the newest assistant entry in the transcript path the
# harness passes to every hook. Fails OPEN (nudge fires) on any parse problem.
tier_gate() {
  local transcript model
  transcript="$(printf '%s' "$1" | jq -r '.transcript_path // empty' 2>/dev/null)" || return 0
  [ -f "$transcript" ] || return 0
  # Last 40 lines, tolerate non-JSON/truncated lines, take the newest model.
  model="$(tail -n 40 "$transcript" 2>/dev/null \
    | jq -Rr 'fromjson? | .message.model? // empty' 2>/dev/null \
    | tail -n 1)" || return 0
  case "$model" in
    *fable*|*opus*) return 1 ;;
    *) return 0 ;;
  esac
}
