#!/usr/bin/env bash
#
# PreToolUse:Agent guard — enforce an explicit worktree-isolation decision on
# every subagent spawn, AND refuse to delegate parent-tree writes from a
# non-isolated primary checkout. Claude-only (the Agent spawn tool is
# Claude-specific).
#
# A subagent's relationship to the filesystem falls into one of four cases. The
# caller declares which one applies; an undeclared spawn is denied.
#
#   isolation:"worktree" / "remote"   child is isolated by the runtime.
#                                     -> allow untouched.
#
#   [iso:readonly]   child only inspects; never writes.            -> allow.
#   [iso:extern]     child writes a DIFFERENT repo on an           -> allow.
#                    agent-private path (its own clone), never a
#                    shared checkout.
#   [iso:direct]     child writes THIS repo's working tree         -> allow ONLY
#                    directly (the result must land in the           if the spawn
#                    current checkout, so a throwaway worktree        runs from a
#                    would strip it).                                 linked
#                                                                     worktree;
#                                                                     DENY if the
#                                                                     parent sits
#                                                                     on the
#                                                                     primary
#                                                                     checkout.
#
# The matched sentinel is stripped from the description (via updatedInput) so it
# never leaks into the child's task label. Non-Agent tools and empty payloads
# pass straight through.
set -euo pipefail

payload="$(cat)"
[[ -z "$payload" ]] && exit 0

tool="$(printf '%s' "$payload" | jq -r '.tool_name // empty' 2>/dev/null || true)"
[[ "$tool" == "Agent" ]] || exit 0

# isolation key already chosen by the caller (or a frontmatter default) -> allow.
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

# emit_allow_stripping <sentinel-regex>
# Allow the spawn, rewriting tool_input to drop the matched sentinel (and the
# whitespace around it) from the description. Emits the FULL updatedInput.
emit_allow_stripping() {
  local re="$1" updated
  updated="$(
    printf '%s' "$payload" | jq -c --arg re "$re" '
      .tool_input
      | .description = (
          (.description // "")
          | gsub("\\s*" + $re + "\\s*"; " ")
          | gsub("^\\s+|\\s+$"; "")
        )
    ' 2>/dev/null || true
  )"
  if [[ -n "$updated" && "$updated" != "null" ]]; then
    jq -cn --argjson ti "$updated" \
      '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"allow",updatedInput:$ti}}'
  fi
}

# emit_deny <reason>
emit_deny() {
  jq -cn --arg r "$1" \
    '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
}

# on_primary_checkout — true when the spawn's cwd is the repo's PRIMARY checkout
# (not a linked worktree). Compares the absolute git dir against the absolutized
# common dir: they are equal only on the primary checkout. Fails OPEN (returns
# false) outside a git repo or when git cannot answer, so a non-repo spawn is
# never blocked by a gate that cannot reason about it.
on_primary_checkout() {
  local cwd agd gcd
  cwd="$(printf '%s' "$payload" | jq -r '.cwd // empty' 2>/dev/null || true)"
  [[ -n "$cwd" && -d "$cwd" ]] || cwd="$PWD"
  agd="$(git -C "$cwd" rev-parse --absolute-git-dir 2>/dev/null || true)"
  [[ -n "$agd" ]] || return 1            # not a git repo -> not "primary"
  gcd="$(git -C "$cwd" rev-parse --git-common-dir 2>/dev/null || true)"
  [[ -n "$gcd" ]] || return 1
  case "$gcd" in
    /*) : ;;
    *)  gcd="$(cd "$cwd" 2>/dev/null && cd "$gcd" 2>/dev/null && pwd -P)" || return 1 ;;
  esac
  [[ "$agd" == "$gcd" ]]
}

case "$desc" in
  *"[iso:readonly]"*)
    emit_allow_stripping '\[iso:readonly\]'
    exit 0
    ;;
  *"[iso:extern]"*)
    emit_allow_stripping '\[iso:extern\]'
    exit 0
    ;;
  *"[iso:direct]"*)
    if on_primary_checkout; then
      # shellcheck disable=SC2016  # backticks are literal text in a user-facing message, not command substitution
      emit_deny 'This subagent writes the CURRENT repo'"'"'s working tree directly ([iso:direct]), but the spawn is running on the PRIMARY checkout — its writes would land on the shared primary tree where they can collide with other work. Move into a git worktree first (e.g. `claude --worktree <name>`, or `git worktree add`), then re-issue the spawn from there. If the child does NOT actually write this repo, re-tag it: [iso:readonly] (inspects only) or [iso:extern] (writes its OWN clone of a different repo).'
      exit 0
    fi
    emit_allow_stripping '\[iso:direct\]'
    exit 0
    ;;
esac

emit_deny 'Declare worktree isolation for this subagent before it spawns. Pick ONE:
  • "isolation":"worktree" — child WRITES this repo and its changes should stay isolated (runs in its own worktree).
  • [iso:direct]   — child WRITES this repo'"'"'s tree directly (result must land in the current checkout). Allowed only from a worktree, not the primary checkout.
  • [iso:extern]   — child WRITES a DIFFERENT repo on its OWN private clone path (never a shared external checkout).
  • [iso:readonly] — child only inspects; never writes.
Append the chosen [iso:*] token to the description (do NOT add an isolation field other than "worktree"/"remote" — the schema has no "none"), then re-issue.'
exit 0
