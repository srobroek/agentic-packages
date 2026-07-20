#!/usr/bin/env bash
# orchestrate: deterministic merge-conflict + CI probe for the Integration Gatekeeper.
#
# Predicts whether a branch merges cleanly into a base WITHOUT mutating any tree
# (git merge-tree), and reports CI status for its PR if one exists. The Gatekeeper
# reasons about FCFS order and pushback from these facts instead of guessing.
#
# Sibling: packages/pr-shepherd/.apm/skills/pr-shepherd/scripts/merge-probe.sh
# carries a trimmed copy of `conflicts`; keep the extraction logic in sync.
#
# Usage:
#   conflict-probe.sh conflicts <base-ref> <branch-ref>
#       -> prints conflicting paths (one per line); exit 0 clean, 1 conflicts, 2 error
#   conflict-probe.sh pairwise <base-ref> <branch-a> <branch-b>
#       -> do A and B touch overlapping files vs base? exit 0 disjoint, 1 overlap
#   conflict-probe.sh ci <pr-number|branch>
#       -> prints `gh pr checks` summary; exit follows gh (needs gh + network)
set -euo pipefail

die() { echo "conflict-probe: $*" >&2; exit 2; }
command -v git >/dev/null || die "git not found"

cmd="${1:-}"; shift || true

case "$cmd" in
  conflicts)
    base="${1:?base ref}"; branch="${2:?branch ref}"
    base_sha="$(git rev-parse --verify "$base^{commit}" 2>/dev/null)" || die "bad base $base"
    br_sha="$(git rev-parse --verify "$branch^{commit}" 2>/dev/null)" || die "bad branch $branch"
    # Modern merge-tree predicts the merge without touching the tree.
    # --name-only output: line 1 = tree OID, then conflicted paths, then a
    # blank line and informational messages. Exit 1 = conflicts. (Backported
    # from merge-probe.sh: the old grep '[^ ]+/[^ ]+' extractor dropped
    # root-level conflict files that contain no slash.)
    set +e
    out="$(git merge-tree --write-tree --name-only "$base_sha" "$br_sha" 2>/dev/null)"
    rc=$?
    set -e
    # Fallback for older git: three-dot diff name-only against merge base.
    if [ -z "$out" ]; then
      mb="$(git merge-base "$base_sha" "$br_sha" 2>/dev/null || echo "$base_sha")"
      git diff --name-only "$mb" "$br_sha"
      echo "conflict-probe: merge-tree unavailable; listed changed files only" >&2
      exit 0
    fi
    if [ "$rc" -ne 0 ]; then
      printf '%s\n' "$out" | sed -n '2,/^$/p' | sed '/^$/d' | sort -u
      exit 1
    fi
    echo "clean"
    exit 0
    ;;

  pairwise)
    base="${1:?base}"; a="${2:?branch a}"; b="${3:?branch b}"
    mba="$(git merge-base "$base" "$a")"; mbb="$(git merge-base "$base" "$b")"
    fa="$(git diff --name-only "$mba" "$a" | sort -u)"
    fb="$(git diff --name-only "$mbb" "$b" | sort -u)"
    overlap="$(comm -12 <(printf '%s\n' "$fa") <(printf '%s\n' "$fb") || true)"
    if [ -n "$overlap" ]; then
      echo "overlap:"; printf '%s\n' "$overlap"
      exit 1
    fi
    echo "disjoint"
    exit 0
    ;;

  ci)
    ref="${1:?pr number or branch}"
    command -v gh >/dev/null || die "gh not found (needed for ci)"
    gh pr checks "$ref"
    ;;

  *)
    die "usage: conflicts|pairwise|ci (got '${cmd:-}')"
    ;;
esac
