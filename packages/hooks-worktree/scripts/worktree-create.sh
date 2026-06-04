#!/usr/bin/env bash
# Hook: WorktreeCreate — create worktrees in /tmp to prevent nesting
# Keeps worktrees outside the repo tree (eliminates nesting bugs entirely).

INPUT=$(cat)
CWD=$(echo "$INPUT" | jq -r '.cwd // empty')
NAME=$(echo "$INPUT" | jq -r '.worktree_name // empty')
REF=$(echo "$INPUT" | jq -r '.git_ref // empty')

[ -z "$CWD" ] && exit 1
[ -z "$NAME" ] && NAME="worktree-$$"
[ -z "$REF" ] && REF="HEAD"

# GUARD: reject if CWD is inside a worktree path — prevents nesting
case "$CWD" in
  */worktrees/*|*/.claude/worktrees/*)
    echo "BLOCKED: CWD is inside a worktree ($CWD). Refusing to nest." >&2
    exit 1
    ;;
esac

# Resolve to the MAIN worktree (not a linked worktree)
# git rev-parse --git-common-dir points to the shared .git dir of the main worktree
GIT_COMMON=$(git -C "$CWD" rev-parse --git-common-dir 2>/dev/null)
if [ -n "$GIT_COMMON" ]; then
  REPO_ROOT=$(cd "$CWD" && cd "$GIT_COMMON" && cd .. && pwd)
else
  REPO_ROOT="$CWD"
fi

# Create worktrees in /tmp — outside repo tree, auto-cleaned on reboot
REPO_NAME=$(basename "$REPO_ROOT")
WORKTREE_PATH="/tmp/claude-worktrees/${REPO_NAME}/${NAME}"
BRANCH_NAME="worktree-${NAME}"

mkdir -p "$(dirname "$WORKTREE_PATH")"

# Create worktree with hooks disabled (avoids post-checkout hook failures in /tmp)
if git -C "$REPO_ROOT" -c core.hooksPath=/dev/null worktree add "$WORKTREE_PATH" -b "$BRANCH_NAME" "$REF" >/dev/null 2>/dev/null; then
  echo "$WORKTREE_PATH"
  exit 0
else
  # Fallback: try without -b (branch may already exist)
  if git -C "$REPO_ROOT" -c core.hooksPath=/dev/null worktree add "$WORKTREE_PATH" "$REF" >/dev/null 2>/dev/null; then
    echo "$WORKTREE_PATH"
    exit 0
  fi
  exit 1
fi
