#!/usr/bin/env bash
# Hook: WorktreeCreate — create worktrees in /tmp to prevent nesting
# Keeps worktrees outside the repo tree (eliminates nesting bugs entirely).

INPUT=$(cat)
CWD=$(echo "$INPUT" | jq -r '.cwd // empty' 2>/dev/null)
NAME=$(echo "$INPUT" | jq -r '.worktree_name // empty' 2>/dev/null)
REF=$(echo "$INPUT" | jq -r '.git_ref // empty' 2>/dev/null)

[ -z "$CWD" ] && exit 1
[ -z "$NAME" ] && NAME="worktree-$$"
[ -z "$REF" ] && REF="HEAD"

# Sanitize the worktree name BEFORE any use. The name flows into both
# WORKTREE_PATH and BRANCH_NAME, so an unsanitized value could escape the
# managed /tmp/claude-worktrees tree (path traversal) or inject git-ref
# metacharacters.
#
# 1. Collapse all whitespace/newlines to single dashes so a multi-line payload
#    cannot smuggle a second path component through.
# 2. Strip leading/trailing dashes — this defangs a leading-dash name (e.g.
#    "-rf"), which git could otherwise treat as an option flag, and also drops
#    dashes introduced by leading/trailing whitespace.
NAME=$(printf '%s' "$NAME" | tr '\n\r\t ' '----' | tr -s '-')
NAME=$(printf '%s' "$NAME" | sed -e 's/^-*//' -e 's/-*$//')

# Hard-reject path traversal and absolute/slashed names. These cannot be safely
# rewritten without surprising the caller, so refuse outright.
case "$NAME" in
  *..*|*/*)
    echo "BLOCKED: unsafe worktree name ($NAME). Refusing to create." >&2
    exit 1
    ;;
esac

# Fall back to a process-unique name if sanitizing emptied the value.
[ -z "$NAME" ] && NAME="worktree-$$"

# GUARD: reject if CWD is inside a managed worktree path — prevents nesting.
# The actual scheme is /tmp/claude-worktrees/<repo>/<name>, so match that.
case "$CWD" in
  */claude-worktrees/*|*/.claude/worktrees/*)
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

# Create worktree with hooks disabled (avoids post-checkout hook failures in /tmp).
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
