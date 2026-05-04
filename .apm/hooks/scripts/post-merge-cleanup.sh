#!/usr/bin/env bash
# Hook: PostToolUse — clean up worktree dir + branch after merge
# Triggers on: Bash(git merge*)
# After a successful merge of a worktree branch, remove the worktree directory
# and delete the branch so the concurrent-limit count stays accurate.
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
EXIT_CODE=$(echo "$INPUT" | jq -r '.tool_result.exit_code // 0')

# Only clean up after successful merges
[ "$EXIT_CODE" != "0" ] && exit 0

# Extract worktree branch name from merge command
BRANCH=$(echo "$COMMAND" | grep -oE 'worktree-worktree-[0-9]+')
[ -z "$BRANCH" ] && exit 0

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
[ -z "$REPO_ROOT" ] && exit 0

# Find and remove the worktree directory (could be in /tmp or .claude/worktrees)
WORKTREE_PATH=$(git -C "$REPO_ROOT" worktree list --porcelain 2>/dev/null | grep -B1 "branch refs/heads/$BRANCH" | head -1 | sed 's/worktree //')
if [ -n "$WORKTREE_PATH" ] && [ -d "$WORKTREE_PATH" ]; then
    git -C "$REPO_ROOT" worktree remove "$WORKTREE_PATH" --force 2>/dev/null
fi

# Delete the branch and prune
git -C "$REPO_ROOT" branch -D "$BRANCH" 2>/dev/null
git -C "$REPO_ROOT" worktree prune 2>/dev/null

exit 0
