#!/usr/bin/env bash
set -euo pipefail

# beads-gh-issue-guard.sh — PreToolUse:Bash hook (Claude + Codex).
#
# In a repo with an active beads workspace, agent task tracking lives in bd,
# not GitHub issues. DENY mutating `gh issue` subcommands with the bd
# replacement in the reason (agent-facing self-correct per hook-guard policy).
# Read-only subcommands (list, view, status) stay allowed — referencing
# human-facing issues is fine; creating/closing them as task state is not.
#
# Self-gating: matcher is Bash with no `if` filter. Fail open (allow) whenever
# state cannot be determined: no jq, no bd, no beads workspace, string payload.
#
# Portability floor: bash 3.2.57 + BSD grep. No PCRE, no \b.

payload="$(cat 2>/dev/null || true)"
[ -z "$payload" ] && exit 0
command -v jq >/dev/null 2>&1 || exit 0

# Cheap pre-jq bail: only `gh issue` commands are of interest.
case "$payload" in
  *"gh"*issue*) ;;
  *) exit 0 ;;
esac

# Single jq pass; tool_input may be an object {command:...} or a bare string.
cwd=""
cmd=""
{
  IFS= read -r cwd || true
  cmd="$(cat)"
} < <(
  printf '%s' "$payload" | jq -j '
    (.cwd // "") + "\n" +
    (if (.tool_input|type)=="string" then .tool_input
     else (.tool_input.command // "") end)
  ' 2>/dev/null
)
[ -z "$cmd" ] || [ "$cmd" = "null" ] && exit 0
[ -n "$cwd" ] && [ "$cwd" != "null" ] && [ -d "$cwd" ] || cwd="$PWD"

# Only act when the repo the command runs in has a beads workspace.
command -v bd >/dev/null 2>&1 || exit 0
bd -C "$cwd" where >/dev/null 2>&1 || exit 0

# Match `gh issue <mutating-subcommand>` anchored to command position (start,
# or after a real ; & | separator) so mentions inside quoted arguments of
# other commands do not trip the guard.
MUTATING='(create|close|edit|comment|reopen|delete|transfer|pin|unpin|lock|unlock|develop)'
printf '%s' "$cmd" | grep -Eq "(^|[;&|][[:space:]]*)gh[[:space:]]+issue[[:space:]]+${MUTATING}([[:space:]]|$)" || exit 0

reason="Task state lives in beads here (.beads/ present), not GitHub issues. Instead of gh issue: create work -> bd create \"title\" --spec-id <slug> (deps: bd dep add <later> <earlier>); pick up -> bd ready --unassigned --json + bd update <id> --claim; finish -> bd close <id> --reason \"...\"; discuss -> bd comments add <id> \"...\". If this is genuinely a human-facing GitHub issue (external users/reporting), the user must request it explicitly."

jq -n --arg reason "$reason" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    permissionDecision: "deny",
    permissionDecisionReason: $reason
  }
}'
exit 0
