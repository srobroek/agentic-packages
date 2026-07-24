#!/usr/bin/env bash
# universal-start.sh — SubagentStart hook: generic claim-contract injector.
#
# Matcher-less (fires for every subagent on both Claude and Codex runtimes).
# Injects ONE short paragraph telling the starting agent that claiming a bead
# in this workspace binds the generic completion contract. Non-blocking; any
# failure exits 0 silently.
#
# Contract (hook-io.md):
#   stdin  = SubagentStart payload JSON (agent_id, cwd, ...)
#   stdout = hookSpecificOutput JSON with additionalContext, OR empty on fail
#   exit   = 0 always
#
# Portability: bash 3.2, BSD/GNU tolerant.
set -eu

INPUT=$(cat 2>/dev/null || true)
[ -z "$INPUT" ] && exit 0
command -v jq >/dev/null 2>&1 || exit 0

# Only inject in repos with an active beads workspace.
CWD=$(printf '%s' "$INPUT" | jq -r '.cwd // empty' 2>/dev/null || true)
[ -n "$CWD" ] && [ -d "$CWD" ] || CWD="$PWD"
command -v bd >/dev/null 2>&1 || exit 0
bd -C "$CWD" where >/dev/null 2>&1 || exit 0

# Generic bead-as-brief claim contract paragraph.
# Concise by design — the full contract is in the agent definition; this is
# the minimum to orient an unlisted agent that happens to hold a claim.
CTX="Bead contract (bead-as-brief spec 002): if you hold a bead claim, you are bound by"
CTX+=" a completion contract enforced at exit. Required before stopping:"
CTX+=" (1) set metadata.push (git nodes) or metadata.output_ref (artifact nodes),"
CTX+=" (2) add an agent:* handoff label,"
CTX+=" (3) leave a REPORTED comment on your bead."
CTX+=" Always-valid exit: set bd status=blocked and leave a FAILED or BLOCKED comment."
CTX+=" No claim held? No contract applies — exit freely."

jq -n --arg ctx "$CTX" '{
  hookSpecificOutput: {
    hookEventName: "SubagentStart",
    additionalContext: $ctx
  }
}'
exit 0
