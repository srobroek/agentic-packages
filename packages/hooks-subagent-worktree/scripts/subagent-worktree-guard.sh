#!/usr/bin/env bash
#
# PreToolUse:Agent advisory — non-blocking guidance on subagent worktree
# isolation. This hook NEVER denies a spawn (that was the old behavior, which
# guessed wrong too often and blocked legitimate work). It only injects a short
# reminder so the parent chooses isolation deliberately.
#
# Behavior (tool_name == "Agent"):
#   * isolation already declared (isolation key present) -> silent (the parent
#     already chose; nothing to advise).
#   * otherwise -> emit a non-blocking advisory via
#     hookSpecificOutput.additionalContext and exit 0. Always allows.
#
# Non-Agent tools and empty payloads pass straight through.
#
# Claude-only (the Agent spawn tool is Claude-specific); the Codex variant is a
# no-op.
set -euo pipefail

payload="$(cat || true)"
[[ -z "$payload" ]] && exit 0

tool="$(printf '%s' "$payload" | jq -r '.tool_name // empty' 2>/dev/null || true)"
[[ "$tool" == "Agent" ]] || exit 0

# If the parent already declared isolation, it has made the call — stay quiet.
has_iso="$(
  printf '%s' "$payload" | jq -r '
    if (.tool_input | type) == "object" and (.tool_input | has("isolation"))
    then "yes" else "no" end
  ' 2>/dev/null || printf 'no'
)"
[[ "$has_iso" == "yes" ]] && exit 0

read -r -d '' advice <<'ADVICE' || true
Subagent isolation (advisory, non-blocking): if this subagent WRITES files AND runs in parallel with other writers, pass isolation:"worktree" so they do not collide on a shared tree — Claude branches it from your current HEAD (worktree.baseRef=head) as worktree-<name>. A read-only, different-repo, or lone-writer subagent needs no isolation. If you DO run it in a worktree, instruct it to COMMIT its work before finishing: the worktree branch persists, but uncommitted changes there can be lost when the worktree is cleaned up.
ADVICE

jq -n --arg ctx "$advice" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    additionalContext: $ctx
  }
}'

exit 0
