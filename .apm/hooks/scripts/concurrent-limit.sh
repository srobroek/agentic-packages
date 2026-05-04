#!/usr/bin/env bash
# Hook: PreToolUse — limit concurrent agents per project
MAX_AGENTS=20
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
[ -z "$REPO_ROOT" ] && exit 0

# Prune stale worktrees before counting
git -C "$REPO_ROOT" worktree prune 2>/dev/null

# Count linked worktrees (excludes main tree — first line of worktree list)
ACTIVE_WORKTREES=$(git -C "$REPO_ROOT" worktree list 2>/dev/null | tail -n +2 | grep -c "worktree-")

if [ "$ACTIVE_WORKTREES" -ge "$MAX_AGENTS" ]; then
    echo "BLOCKED: $ACTIVE_WORKTREES active worktrees (max $MAX_AGENTS). Wait for agents to complete." >&2
    exit 2
fi
exit 0
