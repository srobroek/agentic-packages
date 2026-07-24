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

# Guardrail: if ANY gitnexus analyze is already running for this repo, hold
# off rather than start a second one — concurrent writers corrupt/quarantine
# the LadybugDB. Never cancel a running analyze (mid-write kill risks
# corruption). The background runner waits up to 15min for the running one to
# finish, then reindexes once, so the tail merge of a train is still captured.
LOCK="$PRIMARY/.gitnexus/reindex.lock"
if [ -f "$LOCK" ]; then
  # stat -f %m (macOS) or stat -c %Y (Linux)
  age=$(( $(date +%s) - $(stat -f %m "$LOCK" 2>/dev/null || stat -c %Y "$LOCK" 2>/dev/null || echo 0) ))
  [ "$age" -lt 1800 ] && exit 0
fi
touch "$LOCK"

nohup sh -c "
  for _i in \$(seq 1 90); do
    pgrep -f 'gitnexus analyze' >/dev/null 2>&1 || break
    sleep 10
  done
  cd '$PRIMARY' && gitnexus analyze >/dev/null 2>&1
  rm -f '$LOCK'
" >/dev/null 2>&1 &
exit 0
