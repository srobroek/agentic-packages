#!/usr/bin/env bash
# orchestrate: remove a finished coder worktree without ever destroying live work.
#
# Gate: `git -C <wt> status --porcelain` must be empty, else refuse (exit 1).
# Only once clean does it purge known build-artifact dirs inside the worktree
# and hand the worktree back to git (`worktree remove` + `worktree prune`).
#
# Usage: worktree-sweep.sh <worktree-path>
# Exit codes: 0 swept, 1 dirty (refused, nothing deleted), 2 usage/git error.
set -euo pipefail

die() { echo "worktree-sweep: $*" >&2; exit 2; }

[ $# -ge 1 ] || die "usage: worktree-sweep.sh <worktree-path>"
wt="$1"
[ -d "$wt" ] || die "not a directory: $wt"
git -C "$wt" rev-parse --is-inside-work-tree >/dev/null 2>&1 || die "not a git worktree: $wt"

status="$(git -C "$wt" status --porcelain)"
if [ -n "$status" ]; then
  echo "worktree-sweep: dirty, refusing: $wt" >&2
  exit 1
fi

for d in target node_modules dist .venv; do
  if [ -e "$wt/$d" ]; then
    rm -rf "${wt:?}/${d:?}"
  fi
done

# Resolve the main worktree root (where `git worktree remove` must run from)
# without relying on `rev-parse --path-format` (not on all git versions).
common_dir="$(git -C "$wt" rev-parse --git-common-dir)"
case "$common_dir" in
  /*) ;;
  *) common_dir="$wt/$common_dir" ;;
esac
common_dir="$(cd "$common_dir" && pwd)"
main_root="$(dirname "$common_dir")"

git -C "$main_root" worktree remove "$wt"
git -C "$main_root" worktree prune
echo "swept: $wt"
