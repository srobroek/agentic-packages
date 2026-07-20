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

# Strip quoted values from a command string, leaving only bare tokens.
# Copied from packages/hooks-precommit-gate/scripts/precommit-gate.sh (its
# issues #4/#5 fix): quoted content is replaced by a single space so a
# `gh issue edit` mentioned inside -m '...' cannot trip the guard.
# Handles single-quoted (no escapes) and double-quoted (backslash escapes).
strip_quoted() {
  printf '%s' "$1" | awk '
  { s=$0; n=length(s); out=""; i=1
    while(i<=n){
      c=substr(s,i,1)
      if(c=="\x27"){i++;while(i<=n&&substr(s,i,1)!="\x27"){i++};i++;out=out " ";continue}
      if(c=="\""){i++;while(i<=n){c=substr(s,i,1);if(c=="\""){i++;break}
        if(c=="\\"){i++;if(i<=n)i++;continue};i++};out=out " ";continue}
      out=out c;i++
    }
    print out
  }'
}

# Match `gh issue <mutating-subcommand>` in the QUOTE-STRIPPED command. Anchor
# is a non-word class (start, whitespace, ; & | subshell-( , backtick) rather
# than strict command position: this catches command substitution `$(gh ...)`,
# backticks, subshells, and wrapper prefixes (`time gh ...`, `env FOO=1 gh
# ...`) for free, while quote-stripping removes the main false-positive source
# (mentions inside quoted arguments). Residual FP: an UNQUOTED mention like
# `echo gh issue close 5` -- accepted; deny is agent-facing self-correct.
MUTATING='(create|close|edit|comment|reopen|delete|transfer|pin|unpin|lock|unlock|develop)'
stripped="$(strip_quoted "$cmd")"
printf '%s' "$stripped" | grep -Eq "(^|[[:space:];&|(\`])gh[[:space:]]+issue[[:space:]]+${MUTATING}([[:space:]]|$)" || exit 0

reason="Task state lives in beads here (.beads/ present), not GitHub issues. Instead of gh issue: create work -> bd create \"title\" --spec-id <slug> (deps: bd dep add <later> <earlier>); pick up -> bd ready --unassigned --json + bd update <id> --claim; finish -> bd close <id> --reason \"...\"; discuss -> bd comments add <id> \"...\". If this is genuinely a human-facing GitHub issue (external users/reporting), the user must request it explicitly."

jq -n --arg reason "$reason" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    permissionDecision: "deny",
    permissionDecisionReason: $reason
  }
}'
exit 0
