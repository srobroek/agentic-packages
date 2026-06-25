#!/usr/bin/env bash
set -euo pipefail

# Branch awareness hook (UserPromptSubmit). Advisory only — never blocks.
# On a protected branch (main/master) it injects branch facts as
# additionalContext and lets the model decide whether to branch. It performs
# no prompt parsing and emits no judgment.

# Consume stdin so the producer never gets SIGPIPE; the payload is unused.
cat >/dev/null 2>&1 || true

git rev-parse --git-dir >/dev/null 2>&1 || exit 0

# Empty when detached HEAD or no commits yet: exit cleanly, no context.
current_branch="$(git branch --show-current 2>/dev/null || true)"
[ -n "$current_branch" ] || exit 0

case "$current_branch" in
  main|master) ;;
  *) exit 0 ;;
esac

# Existing local feature branches (everything except protected ones).
feature_branches="$(git branch --list 2>/dev/null \
  | sed -E 's/^[*+ ]+//' \
  | grep -vxE '(main|master)' \
  | head -10 \
  | tr '\n' ' ' \
  | sed 's/ *$//' || true)"
[ -n "$feature_branches" ] || feature_branches="(none)"

# Linked worktrees with their checked-out branch (skip the current dir).
# git worktree --porcelain reports physical paths, so compare against pwd -P.
current_pwd="$(pwd -P 2>/dev/null || pwd)"
worktree_lines=""
worktree_path=""
while IFS= read -r line; do
  case "$line" in
    "worktree "*)
      worktree_path="${line#worktree }"
      ;;
    "branch refs/heads/"*)
      wt_branch="${line#branch refs/heads/}"
      if [ "$worktree_path" != "$current_pwd" ] && [ -n "$wt_branch" ]; then
        worktree_lines="${worktree_lines}  - ${wt_branch} (${worktree_path})
"
      fi
      ;;
  esac
done <<EOF
$(git worktree list --porcelain 2>/dev/null || true)
EOF
[ -n "$worktree_lines" ] || worktree_lines="  (none)
"

context="BRANCH_CONTEXT: You are on protected branch '${current_branch}'.

Existing feature branches: ${feature_branches}
Linked worktrees:
${worktree_lines}If this prompt starts new work, consider a feature branch (git checkout -b feat/<desc>) or an existing branch/worktree above. If the request is a question, a quick fix, or explicitly belongs on '${current_branch}', just proceed."

jq -n --arg ctx "$context" '{
  hookSpecificOutput: {
    hookEventName: "UserPromptSubmit",
    additionalContext: $ctx
  }
}'

exit 0
