#!/usr/bin/env bash
# orchestrate: clean up finished worktrees created by the orchestration harness.
#
# Two modes:
#
#   worktree-sweep.sh <worktree-path>
#     Remove one specific worktree.  Gate: `git status --porcelain` must be
#     empty, else refuse (exit 1).  Purges known build-artifact dirs, then
#     removes via `wt remove` (preferred — deregisters from Worktrunk and git,
#     fires pre-remove hooks) or falls back to `git worktree remove`.
#
#   worktree-sweep.sh --prune <repo-path>
#     Reclaim orphaned physical dirs under the harness prefix
#     /private/tmp/claude-worktrees/<repo>/ that completed agents leave behind.
#     These dirs are no longer registered in git's worktree list but remain on
#     disk, consuming space.  Background: parallel Rust worktrees each grow a
#     multi-GB target/ tree; ENOSPC was observed on live runs when orphaned dirs
#     accumulated under the harness prefix after agents were dismissed (bead
#     astro-plan-ki35).  Orphaned dirs do NOT count against git's worktree cap
#     but do consume disk.
#
# Exit codes: 0 swept/pruned, 1 dirty or nothing to do (refused, nothing
# deleted), 2 usage/git error.
set -euo pipefail

die()  { echo "worktree-sweep: $*" >&2; exit 2; }
info() { echo "worktree-sweep: $*"; }

[ $# -ge 1 ] || die "usage: worktree-sweep.sh <worktree-path> | --prune <repo-path>"

# ── Mode: --prune ──────────────────────────────────────────────────────────────
if [ "$1" = "--prune" ]; then
  [ $# -ge 2 ] || die "--prune requires a repo path"
  repo="$2"
  [ -d "$repo" ] || die "not a directory: $repo"
  git -C "$repo" rev-parse --is-inside-work-tree >/dev/null 2>&1 \
    || die "not a git repo: $repo"

  # Collect dirs registered with git (main + linked worktrees).
  registered="$(git -C "$repo" worktree list --porcelain \
    | awk '/^worktree / { print $2 }')"

  # Harness prefix: /private/tmp/claude-worktrees/<repo-name>/
  repo_name="$(basename "$(git -C "$repo" rev-parse --show-toplevel)")"
  harness_prefix="/private/tmp/claude-worktrees/${repo_name}"

  if [ ! -d "$harness_prefix" ]; then
    info "no harness prefix dir found: $harness_prefix"
    exit 0
  fi

  pruned=0
  for candidate in "$harness_prefix"/*/; do
    [ -d "$candidate" ] || continue
    # Strip trailing slash for comparison.
    candidate="${candidate%/}"
    # Skip if still registered with git.
    if echo "$registered" | grep -qxF "$candidate"; then
      continue
    fi
    # Orphaned: not in git's worktree list.  Check for uncommitted work as a
    # safety gate (may already be cleaned, just a dangling dir).
    if git -C "$candidate" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
      status="$(git -C "$candidate" status --porcelain 2>/dev/null || true)"
      if [ -n "$status" ]; then
        echo "worktree-sweep: orphan has uncommitted work, skipping: $candidate" >&2
        continue
      fi
    fi
    info "removing orphaned dir: $candidate"
    rm -rf "$candidate"
    pruned=$((pruned + 1))
  done

  if [ "$pruned" -eq 0 ]; then
    info "no orphaned dirs found under $harness_prefix"
  else
    info "pruned $pruned orphaned dir(s) from $harness_prefix"
  fi
  # Also prune git's worktree metadata for any gone entries.
  git -C "$repo" worktree prune
  exit 0
fi

# ── Mode: single worktree ──────────────────────────────────────────────────────
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

# Prefer `wt remove` (Worktrunk-aware: deregisters from wt, fires pre-remove
# hooks).  Fall back to `git worktree remove` when wt is not on PATH or when
# the worktree was not created by wt.
branch="$(git -C "$wt" rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
if command -v wt >/dev/null 2>&1 && [ -n "$branch" ] && [ "$branch" != "HEAD" ]; then
  # --no-delete-branch: caller (shepherd) owns branch deletion.
  wt -C "$main_root" remove "$branch" --no-delete-branch 2>/dev/null \
    && { git -C "$main_root" worktree prune; info "swept via wt: $wt"; exit 0; } \
    || true  # fall through to git fallback on any wt error
fi

git -C "$main_root" worktree remove "$wt"
git -C "$main_root" worktree prune
info "swept: $wt"
