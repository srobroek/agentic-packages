#!/usr/bin/env bash
# pr-shepherd: deterministic merge-readiness probe.
#
# `conflicts` is a trimmed copy of packages/orchestrate/.apm/skills/orchestrate/
# scripts/conflict-probe.sh (git merge-tree prediction, no tree mutation);
# `pr` adds the gh PR state the shepherd's decision table needs.
#
# Usage:
#   merge-probe.sh conflicts <base-ref> <branch-ref>
#       -> prints conflicting paths (one per line); exit 0 clean, 1 conflicts,
#          2 error/unknown (bad refs, or old git without merge-tree --write-tree)
#   merge-probe.sh pr <pr-number>
#       -> prints gh pr view JSON: state, mergeability, review, checks; exit follows gh
#   merge-probe.sh eligibility
#       -> reads gh PR JSON on stdin; prints eligible|draft|release|closed
#
# Portability floor: bash 3.2 + BSD coreutils.
set -euo pipefail

die() { echo "merge-probe: $*" >&2; exit 2; }
command -v git >/dev/null || die "git not found"

cmd="${1:-}"; shift || true

case "$cmd" in
  eligibility)
    command -v jq >/dev/null || die "jq not found (needed for eligibility)"
    jq -er '
      if (.headRefName | startswith("release-please--branches--"))
        or any(.labels[]?; .name == "autorelease: pending") then "release"
      elif .state == "MERGED" then "merged"
      elif .state != "OPEN" then "closed"
      elif .isDraft == true then "draft"
      else "eligible"
      end
    '
    ;;

  conflicts)
    base="${1:?base ref}"; branch="${2:?branch ref}"
    base_sha="$(git rev-parse --verify "$base^{commit}" 2>/dev/null)" || die "bad base $base"
    br_sha="$(git rev-parse --verify "$branch^{commit}" 2>/dev/null)" || die "bad branch $branch"
    # Modern merge-tree predicts the merge without touching the tree.
    # --name-only output: line 1 = tree OID, then conflicted paths, then a
    # blank line and informational messages. Exit 1 = conflicts.
    set +e
    out="$(git merge-tree --write-tree --name-only "$base_sha" "$br_sha" 2>/dev/null)"
    rc=$?
    set -e
    if [ -z "$out" ]; then
      # Older git: cannot predict the merge. Exit 2 (error/unknown), NOT 0 --
      # 0 would report "clean" for a merge nobody probed. Still list the
      # branch's changed files so the caller can reason manually.
      mb="$(git merge-base "$base_sha" "$br_sha" 2>/dev/null || echo "$base_sha")"
      git diff --name-only "$mb" "$br_sha"
      echo "merge-probe: merge-tree unavailable; conflict state UNKNOWN (listed changed files only)" >&2
      exit 2
    fi
    if [ "$rc" -ne 0 ]; then
      printf '%s\n' "$out" | sed -n '2,/^$/p' | sed '/^$/d' | sort -u
      exit 1
    fi
    echo "clean"
    exit 0
    ;;

  pr)
    pr="${1:?pr number}"
    command -v gh >/dev/null || die "gh not found (needed for pr)"
    gh pr view "$pr" --json \
      number,state,isDraft,mergeable,mergeStateStatus,reviewDecision,statusCheckRollup,baseRefName,headRefName,headRefOid,mergeCommit,labels,body,url
    ;;

  *)
    die "usage: conflicts <base> <branch> | pr <number> | eligibility (got '${cmd:-}')"
    ;;
esac
