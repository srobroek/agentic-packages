#!/usr/bin/env bash
set -euo pipefail

# pr-close-guard.sh — PreToolUse:Bash hook (Claude + Codex).
#
# Catches the GitHub comma-list close quirk in a PR body before the PR is
# created/edited. A PreToolUse hook CANNOT rewrite the command, so when the
# `--body` of a `gh pr create` / `gh pr edit` contains a malformed multi-issue
# close, this DENIES with the corrected body in the message — the agent re-issues
# the command with the fix. (The commit-msg layer is the tool-agnostic
# auto-rewrite; this layer is fast feedback for our agent's PR commands.)
#
# Self-gating: matcher is Bash, no `if` filter (the repo's `if`-alternation is
# unreliable), so the script decides whether it applies.
#
# Portability floor: bash 3.2.57 + BSD grep/awk.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NORMALIZE="${SCRIPT_DIR}/normalize-closes.sh"

payload="$(cat 2>/dev/null || true)"
[ -z "$payload" ] && exit 0
command -v jq >/dev/null 2>&1 || exit 0
[ -x "$NORMALIZE" ] || exit 0

# Cheap pre-jq bail: this guard only acts on `gh pr create`/`gh pr edit`. The
# pattern matches the RAW payload string (a superset of real triggers), so the
# vast majority of Bash calls skip the jq + awk pipeline below entirely.
case "$payload" in
  *"gh pr"*) ;;
  *) exit 0 ;;
esac

# tool_input may be an object {command:"..."} OR a bare string. Type-check so a
# string-form input is read, not dropped (the naive jq idiom throws on a string).
cmd="$(
  printf '%s' "$payload" | jq -r '
    if (.tool_input|type)=="string" then .tool_input
    else (.tool_input.command // empty) end
  ' 2>/dev/null || true
)"
[ -z "$cmd" ] || [ "$cmd" = "null" ] && exit 0

# Only gate `gh pr create` / `gh pr edit`, anchored to command position.
printf '%s' "$cmd" \
  | grep -Eq '(^|[;&|][[:space:]]*)gh[[:space:]]+pr[[:space:]]+(create|edit)([[:space:]]|$)' \
  || exit 0

deny() {
  jq -cn --arg reason "$1" \
    '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$reason}}'
  exit 0
}

# Extract the --body / -b value (quote-aware). We only handle the INLINE body
# form here; --body-file/-F point at a file we will not rewrite, and a body typed
# in the editor is invisible — those simply pass (the commit-msg layer and the
# author still apply). Pull the value with a small awk tokenizer that respects
# single/double quotes.
body="$(
  printf '%s' "$cmd" | awk '
  {
    s = $0; n = length(s); i = 1
    # tokenize quote-aware into TOK[] preserving the unquoted value
    tc = 0
    while (i <= n) {
      c = substr(s,i,1)
      if (c == " " || c == "\t") { i++; continue }
      tok = ""
      while (i <= n) {
        c = substr(s,i,1)
        if (c == " " || c == "\t") break
        if (c == "\x27") { # single quote
          i++
          while (i <= n && substr(s,i,1) != "\x27") { tok = tok substr(s,i,1); i++ }
          i++  # closing quote
          continue
        }
        if (c == "\"") {
          i++
          while (i <= n && substr(s,i,1) != "\"") { tok = tok substr(s,i,1); i++ }
          i++
          continue
        }
        tok = tok c; i++
      }
      tc++; TOK[tc] = tok
    }
    # find --body / -b / --body=... ; print its value and stop
    for (k = 1; k <= tc; k++) {
      t = TOK[k]
      if (t == "--body" || t == "-b") { if (k < tc) { print TOK[k+1]; exit } }
      if (substr(t,1,7) == "--body=") { print substr(t,8); exit }
      if (substr(t,1,3) == "-b=")     { print substr(t,4); exit }
    }
  }'
)"

# No inline body -> nothing we can check here.
[ -z "$body" ] && exit 0

fixed="$(printf '%s' "$body" | "$NORMALIZE" 2>/dev/null || true)"

# Unchanged -> the body is already correct (or has no malformed close) -> allow.
[ "$fixed" = "$body" ] && exit 0

deny "$(printf 'This PR body has a comma-list close that GitHub will only apply to the FIRST issue (e.g. "Closes #1, #2" leaves #2 open). Re-run gh pr %s with this corrected --body so every issue closes:\n\n%s' "create-or-edit" "$fixed")"
