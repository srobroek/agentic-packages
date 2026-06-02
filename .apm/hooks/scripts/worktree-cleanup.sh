#!/usr/bin/env bash
# Hook: WorktreeRemove -- clean up worktree directory and branch after removal
INPUT=$(cat)
CWD=$(echo "$INPUT" | jq -r '.cwd // empty')
[ -z "$CWD" ] && exit 0

# Resolve main repo root
GIT_COMMON=$(git -C "$CWD" rev-parse --git-common-dir 2>/dev/null)
if [ -n "$GIT_COMMON" ]; then
  REPO_ROOT=$(cd "$CWD" && cd "$GIT_COMMON" && cd .. && pwd)
else
  exit 0
fi

BRANCH=$(git -C "$CWD" branch --show-current 2>/dev/null)

# Stash uncommitted changes if any
if [ -n "$(git -C "$CWD" status --porcelain 2>/dev/null)" ]; then
    git -C "$CWD" stash 2>/dev/null
fi

# Remove worktree (non-force, safety-net compatible)
git -C "$REPO_ROOT" worktree remove "$CWD" 2>/dev/null

# Delete worktree branch
if [ -n "$BRANCH" ] && [[ "$BRANCH" == worktree-* ]]; then
    git -C "$REPO_ROOT" branch -d "$BRANCH" 2>/dev/null
fi

exit 0
