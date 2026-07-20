#!/usr/bin/env bash
# Hook: SubagentStart -- slim beads contract reminder for subagents.
#
# SessionStart (bd prime) does not fire for subagents, so without this a
# spawned worker has only compiled steering. Inject the minimal contract:
# where its work queues are, claim-before-work, and the close protocol.
# Deliberately NOT bd prime (~1-2k tokens); this stays a few lines.
#
# Self-gating: silent unless bd is installed AND the spawn cwd has a beads
# workspace. Never blocks a spawn; any failure exits 0 with no output.
# Portability floor: bash 3.2.57 + BSD coreutils.
set -eu

INPUT=$(cat 2>/dev/null || true)
[ -z "$INPUT" ] && exit 0
command -v jq >/dev/null 2>&1 || exit 0
command -v bd >/dev/null 2>&1 || exit 0

AGENT_ID=$(printf '%s' "$INPUT" | jq -r '.agent_id // empty' 2>/dev/null)
CWD=$(printf '%s' "$INPUT" | jq -r '.cwd // empty' 2>/dev/null)
[ -z "$AGENT_ID" ] && exit 0  # Not a subagent
[ -n "$CWD" ] && [ -d "$CWD" ] || CWD="$PWD"

# Only in repos with an active beads workspace.
bd -C "$CWD" where >/dev/null 2>&1 || exit 0

NL=$'\n'
CTX="This repo tracks work in beads (bd)."
CTX+=" If the parent gave you a bead id, claim it before working: bd update <id> --claim."
CTX+=" Otherwise your queues are: bd ready --assignee <you> --json (pinned first), then bd ready --label agent:<kind> --unassigned --json."
CTX+=" Never work an issue assigned to another actor.${NL}"
CTX+="Before finishing: comment residual context on your bead (bd comments add <id> \"approach, tricky spots, what to check first on failure\"), close it (bd close <id> --reason \"...\"), and file discovered follow-ups (bd create --deps discovered-from:<id>). Do not wait for CI or merges -- gates and the pr-shepherd own that."

jq -n --arg ctx "$CTX" '{
  hookSpecificOutput: {
    hookEventName: "SubagentStart",
    additionalContext: $ctx
  }
}'
exit 0
