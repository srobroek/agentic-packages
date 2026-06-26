#!/usr/bin/env bash
#
# PreToolUse:Agent guard — enforce an explicit worktree-isolation decision on
# every subagent spawn. Claude-only (the Agent spawn tool is Claude-specific).
#
# Decision table (tool_name == "Agent"):
#   * isolation key already present      -> allow untouched (caller chose
#     "worktree" or "remote", or a frontmatter default applied)
#   * description contains [iso:skip]    -> allow, stripping the sentinel from
#     the description via updatedInput (caller declared: no worktree needed —
#     read-only, different repo, or must edit the parent tree directly)
#   * otherwise                          -> deny, instructing the caller to make
#     one of those two choices and re-issue
#
# Non-Agent tools and empty payloads pass straight through.
set -euo pipefail

SENTINEL='[iso:skip]'

payload="$(cat)"
[[ -z "$payload" ]] && exit 0

tool="$(printf '%s' "$payload" | jq -r '.tool_name // empty' 2>/dev/null || true)"
[[ "$tool" == "Agent" ]] || exit 0

# tool_input is normally an object; guard against a string shape so jq never throws.
has_iso="$(
  printf '%s' "$payload" | jq -r '
    if (.tool_input | type) == "object" and (.tool_input | has("isolation"))
    then "yes" else "no" end
  ' 2>/dev/null || printf 'no'
)"
[[ "$has_iso" == "yes" ]] && exit 0

desc="$(printf '%s' "$payload" | jq -r '
  if (.tool_input | type) == "object" then (.tool_input.description // "") else "" end
' 2>/dev/null || true)"

case "$desc" in
  *"$SENTINEL"*)
    # Allow, but strip the sentinel (and any surrounding whitespace) from the
    # description so it does not leak into the child's task label. Emit the FULL
    # rewritten tool_input via updatedInput.
    updated="$(
      printf '%s' "$payload" | jq -c '
        .tool_input
        | .description = (
            (.description // "")
            | gsub("\\s*\\[iso:skip\\]\\s*"; " ")
            | gsub("^\\s+|\\s+$"; "")
          )
      ' 2>/dev/null || true
    )"
    if [[ -n "$updated" && "$updated" != "null" ]]; then
      jq -cn --argjson ti "$updated" \
        '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"allow",updatedInput:$ti}}'
    fi
    exit 0
    ;;
esac

reason='Declare worktree isolation for this subagent before it spawns. If it WRITES files into THIS repository, re-issue the Agent call with "isolation":"worktree". If it is read-only, operates on a DIFFERENT repository, or must edit the parent working tree directly, re-issue the SAME call with the exact token [iso:skip] appended to the description field (do NOT add an isolation field — the schema has no "none" value). Choose one and re-spawn.'
jq -cn --arg r "$reason" \
  '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
exit 0
