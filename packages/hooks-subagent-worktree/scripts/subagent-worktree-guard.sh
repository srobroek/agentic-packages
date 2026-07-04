#!/usr/bin/env bash
#
# PreToolUse:Agent advisory — non-blocking guidance on subagent worktree
# isolation and stale-worktree cleanup. This hook NEVER denies a spawn (that
# was the old behavior, which guessed wrong too often and blocked legitimate
# work). It only injects short reminders so the parent chooses isolation
# deliberately and reaps dead worktrees.
#
# Behavior (tool_name == "Agent"):
#   * isolation already declared (isolation key present) -> silent about
#     isolation (the parent already chose), but a stale-worktree notice is
#     still emitted when the repo has lingering agent worktrees.
#   * otherwise -> emit a non-blocking isolation advisory (plus the stale
#     notice when applicable) via hookSpecificOutput.additionalContext and
#     exit 0. Always allows.
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

# Has the parent already declared isolation on this spawn?
has_iso="$(
  printf '%s' "$payload" | jq -r '
    if (.tool_input | type) == "object" and (.tool_input | has("isolation"))
    then "yes" else "no" end
  ' 2>/dev/null || printf 'no'
)"

# Stale agent worktrees in the current repo: linked worktrees checked out on a
# worktree-* branch (the agent-spawn naming convention). Surfaced to the parent
# on every spawn so dead worktrees do not accumulate build artifacts and fill
# the disk. Cheap: one `git worktree list` per spawn.
cwd="$(printf '%s' "$payload" | jq -r '.cwd // empty' 2>/dev/null || true)"
stale=""
if [[ -n "$cwd" ]] && git -C "$cwd" rev-parse --git-dir >/dev/null 2>&1; then
  stale="$(git -C "$cwd" worktree list --porcelain 2>/dev/null | awk '
    /^worktree /{path=substr($0,10)}
    /^branch refs\/heads\/worktree-/{print path}
  ' | head -10 || true)"
fi

stale_notice=""
if [[ -n "$stale" ]]; then
  stale_list="$(printf '%s' "$stale" | tr '\n' ' ')"
  stale_notice="Stale worktree notice: this repo has linked agent worktrees: ${stale_list}— review whether each is still in use. For every one that is finished, first CONFIRM IT IS CLEAN: git -C <path> status --porcelain prints nothing and its branch is merged or harvested. Never discard uncommitted work to force a removal — commit, stash, or escalate instead. Once confirmed clean, delete its build artifacts (rm -rf <path>/target and similar gitignored output) and remove it: git worktree remove <path>; git worktree prune. Dead worktrees accumulate compiled output and fill the disk."
fi

# Isolation declared: the parent made the call — advise only about staleness.
if [[ "$has_iso" == "yes" ]]; then
  [[ -z "$stale_notice" ]] && exit 0
  jq -n --arg ctx "$stale_notice" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      additionalContext: $ctx
    }
  }'
  exit 0
fi

read -r -d '' advice <<'ADVICE' || true
Subagent isolation (advisory, non-blocking): if this subagent WRITES files AND runs in parallel with other writers, pass isolation:"worktree" so they do not collide on a shared tree — Claude branches it from your current HEAD (worktree.baseRef=head) as worktree-<name>. A read-only, different-repo, or lone-writer subagent needs no isolation. If you DO run it in a worktree, instruct it to COMMIT its work before finishing: the worktree branch persists, but uncommitted changes there can be lost when the worktree is cleaned up. Afterward the worktree is yours to reap: once the child's branch is merged or harvested AND the worktree is confirmed clean (git status --porcelain prints nothing — never discard uncommitted work), delete its build artifacts and remove it (rm -rf <worktree>/target; git worktree remove <worktree>) — dead worktrees accumulate compiled output and fill the disk.
ADVICE

ctx="$advice"
if [[ -n "$stale_notice" ]]; then
  ctx="${advice}

${stale_notice}"
fi

jq -n --arg ctx "$ctx" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    additionalContext: $ctx
  }
}'

exit 0
