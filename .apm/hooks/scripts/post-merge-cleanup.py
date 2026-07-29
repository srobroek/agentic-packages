#!/usr/bin/env python3
"""Remove a worktree and its branch after that branch is merged (PostToolUse:Bash).

Runs only after a successful `git merge` of a `worktree-worktree-<pid>` branch --
the scheme the pre-Worktrunk session hooks created, whose orphans are still on disk.

Ported from shell, where the worktree path was recovered with
`worktree list --porcelain | grep -B1 "branch refs/heads/$BRANCH" | sed 's/worktree //'`.
`grep -B1` assumes the path line sits exactly one line above the branch line, which
holds for a plain worktree and breaks for a bare or detached entry, where an extra
field is emitted between them -- so it could return the WRONG worktree's path and
force-remove it. Parsing the porcelain records properly removes that class.

Fail open (exit 0) throughout: cleanup is convenience, and a merge must never be
followed by a hook error.
"""

from __future__ import annotations

import re
import subprocess
import sys

# The branch scheme this cleanup owns. Anchored to the full token so a branch that
# merely contains the pattern is not destroyed.
BRANCH_PATTERN = re.compile(r"\bworktree-worktree-[0-9]+\b")


def git(root: str, *arguments: str) -> subprocess.CompletedProcess[str] | None:
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


def worktree_for(root: str, branch: str) -> str:
    """Path of the worktree holding branch, or empty when there is none.

    Parses `--porcelain` as the record format it is: records are separated by blank
    lines, and each holds a `worktree <path>` line plus optional `HEAD`, `branch`,
    `bare`, and `detached` lines in no guaranteed adjacency.
    """
    result = git(root, "worktree", "list", "--porcelain")
    if result is None or result.returncode != 0:
        return ""

    target = f"refs/heads/{branch}"
    path = ""
    for line in result.stdout.splitlines():
        if not line.strip():
            path = ""
            continue
        if line.startswith("worktree "):
            path = line[len("worktree ") :].strip()
        elif line.startswith("branch ") and line[len("branch ") :].strip() == target:
            return path
    return ""


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

    # Only clean up after a merge that actually succeeded.
    tool_result = data.get("tool_result")
    if isinstance(tool_result, dict):
        exit_code = tool_result.get("exit_code", 0)
        if exit_code not in (0, None, "0"):
            return 0

    tool_input = data.get("tool_input")
    if isinstance(tool_input, str):
        command = tool_input
    elif isinstance(tool_input, dict):
        raw = tool_input.get("command")
        command = raw if isinstance(raw, str) else ""
    else:
        command = ""
    if not command:
        return 0

    match = BRANCH_PATTERN.search(command)
    if match is None:
        return 0
    branch = match.group(0)

    from pathlib import Path

    located = git(".", "rev-parse", "--show-toplevel")
    if located is None or located.returncode != 0:
        return 0
    root = located.stdout.strip()
    if not root:
        return 0

    path = worktree_for(root, branch)
    if path and Path(path).is_dir():
        git(root, "worktree", "remove", path, "--force")

    # -D is intended here: the branch was just merged, which is the precondition
    # this hook fires on, and a merged branch's commits live on in the target.
    git(root, "branch", "-D", branch)
    git(root, "worktree", "prune")
    return 0


if __name__ == "__main__":
    sys.exit(main())
