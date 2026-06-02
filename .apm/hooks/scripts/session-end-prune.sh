#!/usr/bin/env bash
# Hook: SessionEnd -- prune stale worktree metadata and orphaned branches
# async: true -- runs in background, doesn't delay exit
# NOTE: Build artifact cleanup is in SessionStart (PID-based orphan detection),
# NOT here -- cleaning on SessionEnd would nuke caches for ongoing work.
INPUT=$(cat)
AGENT_ID=$(echo "$INPUT" | jq -r '.agent_id // empty')
[ -n "$AGENT_ID" ] && exit 0  # Skip in subagents

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
[ -z "$REPO_ROOT" ] && exit 0

git -C "$REPO_ROOT" worktree prune 2>/dev/null

# Delete orphaned worktree branches (only merged ones, -d not -D)
git -C "$REPO_ROOT" branch -l 'worktree-*' --format='%(refname:short)' 2>/dev/null | while read branch; do
    if ! git -C "$REPO_ROOT" worktree list --porcelain | grep -q "branch refs/heads/$branch"; then
        git -C "$REPO_ROOT" branch -d "$branch" 2>/dev/null
    fi
done

exit 0
