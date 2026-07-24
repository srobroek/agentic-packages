#!/usr/bin/env bash
# PostToolUse(Bash): refresh the GitNexus graph in the background after git
# history mutates (commit/merge/push). Repo-agnostic; worktree-safe.
#
# Resolves the PRIMARY checkout via git-common-dir, no-ops unless .gitnexus/
# exists, debounces with a 120s lock file so agents never block and
# concurrent runs never stack.
set -euo pipefail

INPUT=$(cat)
CMD=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // ""' 2>/dev/null || true)
CWD=$(printf '%s' "$INPUT" | jq -r '.cwd // ""' 2>/dev/null || true)

case "$CMD" in
  *"git commit"*|*"git merge"*|*"git push"*|*"gh pr merge"*) ;;
  *) exit 0 ;;
esac

command -v gitnexus >/dev/null 2>&1 || exit 0
[ -n "$CWD" ] && cd "$CWD" 2>/dev/null || exit 0

# Resolve the primary checkout (worktree-safe): common dir's parent.
COMMON=$(git rev-parse --git-common-dir 2>/dev/null) || exit 0
case "$COMMON" in
  /*) PRIMARY=$(dirname "$COMMON") ;;
  *)  PRIMARY=$(cd "$COMMON/.." && pwd) ;;
esac

[ -d "$PRIMARY/.gitnexus" ] || exit 0

LOCK="$PRIMARY/.gitnexus/reindex.lock"
if [ -f "$LOCK" ]; then
  # stat -f %m (macOS) or stat -c %Y (Linux)
  age=$(( $(date +%s) - $(stat -f %m "$LOCK" 2>/dev/null || stat -c %Y "$LOCK" 2>/dev/null || echo 0) ))
  [ "$age" -lt 120 ] && exit 0
fi
touch "$LOCK"

nohup sh -c "cd '$PRIMARY' && gitnexus analyze >/dev/null 2>&1; rm -f '$LOCK'" >/dev/null 2>&1 &
exit 0
