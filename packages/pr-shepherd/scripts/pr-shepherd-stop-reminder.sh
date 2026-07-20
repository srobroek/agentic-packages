#!/usr/bin/env bash
# Stop hook: advisory reminder when merge beads are ready or GitHub gates are
# unchecked. Never blocks — emits {continue:true,systemMessage} only (the
# advisory Stop-hook shape; Stop has no additionalContext field), exits 0
# always.
#
# Portability floor: bash 3.2 + BSD coreutils.
set -euo pipefail

# Self-gate: inert without bd, gh, jq, or a beads repo.
command -v bd >/dev/null 2>&1 || exit 0
command -v gh >/dev/null 2>&1 || exit 0
command -v jq >/dev/null 2>&1 || exit 0
bd where >/dev/null 2>&1 || exit 0

export BD_NO_PAGER=1 BD_NON_INTERACTIVE=1

ready_count="$(bd ready --label agent:integrator --unassigned --json 2>/dev/null \
  | jq -r 'if type=="array" then length else 0 end' 2>/dev/null || echo 0)"
# gh:pr / gh:run gates left open may just be stale — bd gate check is cheap.
gate_count="$(bd gate list --json 2>/dev/null \
  | jq -r '[(. // []) | .[] | select(.status=="open")
            | select((.await_type // "") | startswith("gh:"))] | length' \
    2>/dev/null || echo 0)"

case "$ready_count" in (''|*[!0-9]*) ready_count=0 ;; esac
case "$gate_count"  in (''|*[!0-9]*) gate_count=0  ;; esac

[ "$ready_count" -gt 0 ] || [ "$gate_count" -gt 0 ] || exit 0

msg="PR SHEPHERD: $ready_count merge bead(s) ready / $gate_count GitHub gate(s) unchecked — run /pr-shepherd to drain the queue."

jq -cn --arg msg "$msg" '{continue: true, systemMessage: $msg}' 2>/dev/null \
  || printf '%s\n' "$msg" >&2

exit 0
