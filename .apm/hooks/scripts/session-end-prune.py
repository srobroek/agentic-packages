#!/usr/bin/env python3
"""Prune worktree metadata and delete merged orphan branches (SessionEnd, async).

Only `worktree-*` branches are considered, and only with `git branch -d`, so an
unmerged branch survives -- losing work here would be silent and unrecoverable.

Ported from shell, where the branch list was piped into a `while read` loop and
each iteration ran `git worktree list --porcelain | grep -q`, so N branches cost
2N git spawns. One porcelain read up front collects the checked-out set instead.

Fail open (exit 0) throughout, and skip inside subagents so N finishing agents do
not each prune the same repository.
"""

from __future__ import annotations

import subprocess
import sys


def git(root: str, *arguments: str) -> subprocess.CompletedProcess[str] | None:
    """Run a git command in root, or return None when it cannot run."""
    try:
        return subprocess.run(
            ["git", "-C", root, *arguments],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def checked_out_branches(root: str) -> set[str] | None:
    """Branches currently checked out in a worktree, or None when unknown.

    None matters: on failure the caller must delete nothing, because an empty set
    would read as "no branch is checked out" and make every orphan a candidate.
    """
    result = git(root, "worktree", "list", "--porcelain")
    if result is None or result.returncode != 0:
        return None
    prefix = "branch refs/heads/"
    return {
        line[len(prefix) :].strip()
        for line in result.stdout.splitlines()
        if line.startswith(prefix)
    }


def main() -> int:
    payload = sys.stdin.read()
    if not payload:
        return 0

    import json

    try:
        data = json.loads(payload)
    except (ValueError, TypeError):
        return 0
    if not isinstance(data, dict):
        return 0

    # Subagents share the repository with the parent session; let the parent prune.
    if data.get("agent_id"):
        return 0

    try:
        located = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return 0
    if located.returncode != 0:
        return 0
    root = located.stdout.strip()
    if not root:
        return 0

    git(root, "worktree", "prune")

    in_use = checked_out_branches(root)
    if in_use is None:
        return 0

    listed = git(root, "branch", "-l", "worktree-*", "--format=%(refname:short)")
    if listed is None or listed.returncode != 0:
        return 0

    for branch in listed.stdout.split():
        if branch in in_use:
            continue
        # -d, never -D: git refuses when the branch holds unmerged commits, which
        # is exactly the safety this cleanup depends on.
        git(root, "branch", "-d", branch)

    git(root, "worktree", "prune")
    return 0


if __name__ == "__main__":
    sys.exit(main())
