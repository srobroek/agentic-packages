#!/usr/bin/env bash
# Hook: WorktreeRemove — clean up worktree directory and branch after removal
INPUT=$(cat)
CWD=$(echo "$INPUT" | jq -r '.cwd // empty' 2>/dev/null)
[ -z "$CWD" ] && exit 0

# Resolve main repo root via the shared (common) git dir. Use `pwd -P` to emit
# the PHYSICAL (symlink-resolved) path so it can be compared apples-to-apples
# with `git rev-parse --show-toplevel`, which already returns a physical path.
# On macOS /tmp -> /private/tmp and /var -> /private/var are symlinks, so a
# logical (`pwd`) REPO_ROOT would never equal TOPLEVEL and the main-repo guard
# below would silently fail.
GIT_COMMON=$(git -C "$CWD" rev-parse --git-common-dir 2>/dev/null)
if [ -n "$GIT_COMMON" ]; then
  REPO_ROOT=$(cd "$CWD" && cd "$GIT_COMMON" && cd .. && pwd -P)
else
  exit 0
fi

# SAFETY: only operate on a LINKED worktree. The toplevel of a linked worktree
# differs from REPO_ROOT (the main worktree). If they match, CWD is the main
# repo itself — stashing/removing here would discard the user's real WIP, so
# bail out without touching anything.
TOPLEVEL=$(git -C "$CWD" rev-parse --show-toplevel 2>/dev/null)
[ -z "$TOPLEVEL" ] && exit 0
[ "$TOPLEVEL" = "$REPO_ROOT" ] && exit 0

BRANCH=$(git -C "$CWD" branch --show-current 2>/dev/null)

# Is this worktree inside the managed /tmp/claude-worktrees tree? Only then is
# a force removal acceptable; otherwise stay conservative.
MANAGED=0
case "$TOPLEVEL" in
  /tmp/claude-worktrees/*|/private/tmp/claude-worktrees/*)
    MANAGED=1
    ;;
esac

# Stash uncommitted changes (including untracked files via -u) so nothing is
# silently lost before the worktree directory is removed.
if [ -n "$(git -C "$CWD" status --porcelain 2>/dev/null)" ]; then
    git -C "$CWD" stash -u 2>/dev/null
fi

# Remove the worktree. Force-remove only for managed /tmp worktrees (where any
# residual untracked/modified state is disposable); otherwise non-force so git's
# own safety net protects unmanaged paths.
if [ "$MANAGED" -eq 1 ]; then
    git -C "$REPO_ROOT" worktree remove --force "$TOPLEVEL" 2>/dev/null
else
    git -C "$REPO_ROOT" worktree remove "$TOPLEVEL" 2>/dev/null
fi

# Delete worktree branch (recoverable; -d refuses unmerged work).
if [ -n "$BRANCH" ]; then
    case "$BRANCH" in
      worktree-*)
        git -C "$REPO_ROOT" branch -d "$BRANCH" 2>/dev/null
        ;;
    esac
fi

exit 0
