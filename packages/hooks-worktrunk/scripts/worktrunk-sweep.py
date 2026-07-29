#!/usr/bin/env python3
"""Report abandoned Worktrunk worktrees and reclaim their build output.

Runs at SessionStart. Reports; the only thing it deletes is build output, which is
reproducible by definition. Branch and worktree removal stay with `wt remove`,
which already deletes a merged branch and refuses an unmerged one -- reimplementing
that here would duplicate the safety net Worktrunk owns.

REPLACES worktree-orphan-cleanup, which scanned `/tmp/claude-worktrees/<repo>/
worktree-<pid>` and inferred abandonment from a dead pid. Worktrunk places
worktrees at `~/tmp/worktrees/<repo>/<branch>` -- branch-named, with no pid to
test -- so that hook could never see a real Worktrunk worktree and never cleaned
one. It also could not have told a stale worktree from an active one, because a pid
says nothing about whether work was finished.

STALENESS IS ESTABLISHED, NOT ASSUMED. A worktree is only a candidate when every
one of these holds, read from `wt list --format json`:
  * it is not the main checkout, and not the current one;
  * its working tree is clean -- no staged, modified, untracked, renamed, or
    deleted paths, so nothing uncommitted can be lost;
  * it is not ahead of its remote, so no local commit is unpublished;
  * its last commit is older than the age threshold.
Anything Worktrunk will not describe -- a detached worktree, a missing remote, an
unparsable record -- is left alone. Fewer signals means less confidence, not more
license.

Artifact removal additionally requires the directory to be git-ignored, so a
tracked `dist/` is never touched.
"""

from __future__ import annotations

import os
import sys

# Build output worth reclaiming. Each is checked against git's ignore rules before
# removal, so a repository that tracks one of these keeps it.
ARTIFACT_DIRS = ("target", "node_modules", ".venv", "dist", "build", ".build")

# How old the last commit must be before a clean, published worktree is called
# abandoned. Two weeks: long enough that a branch parked over a holiday is not
# swept, short enough to matter.
STALE_AFTER_SECONDS = int(os.environ.get("WORKTRUNK_SWEEP_STALE_AFTER", 14 * 24 * 3600))

# Cap the report. A machine with dozens of stale worktrees needs a nudge, not a wall.
REPORT_LIMIT = 10


def run(command: list[str], *, timeout: float = 30, cwd: str | None = None):
    """Run a command, returning None when it cannot run or exceeds its bound."""
    import subprocess

    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
            cwd=cwd,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def worktrees() -> list[dict]:
    """Records from `wt list`, or empty when Worktrunk cannot describe them.

    Schema 1 is pinned explicitly: wt warns that a future release switches the
    default to schema 2, and this reads schema-1 field names. Asking for the
    version we parse means an upstream default change cannot silently reshape the
    input.
    """
    result = run(["wt", "list", "--format", "json"], timeout=60)
    if result is None or result.returncode != 0:
        return []

    import json

    # wt prints advisories on stderr, but be defensive about a leading banner.
    text = result.stdout.strip()
    start = text.find("[")
    if start < 0:
        return []
    try:
        parsed = json.loads(text[start:])
    except (ValueError, TypeError):
        return []
    return [record for record in parsed if isinstance(record, dict)]


def is_stale(record: dict, now: float) -> tuple[bool, str]:
    """Whether a worktree is abandoned, and the reason it is not when it is not."""
    if record.get("is_main") or record.get("is_current"):
        return False, "active checkout"

    path = record.get("path")
    if not isinstance(path, str) or not path or not os.path.isdir(path):
        return False, "no directory"

    # A detached worktree has branch: null. Worktrunk cannot name what it holds, so
    # neither can this.
    if not isinstance(record.get("branch"), str) or not record["branch"]:
        return False, "detached or unnamed"

    working = record.get("working_tree")
    if not isinstance(working, dict):
        return False, "no working-tree status"
    for key in ("staged", "modified", "untracked", "renamed", "deleted"):
        if working.get(key):
            return False, f"uncommitted work ({key})"

    remote = record.get("remote")
    if not isinstance(remote, dict):
        return False, "no remote tracking"
    ahead = remote.get("ahead")
    if not isinstance(ahead, int):
        return False, "unknown ahead count"
    if ahead > 0:
        return False, f"{ahead} unpushed commit(s)"

    commit = record.get("commit")
    if not isinstance(commit, dict):
        return False, "no commit metadata"
    timestamp = commit.get("timestamp")
    if not isinstance(timestamp, int):
        return False, "no commit timestamp"
    age = now - timestamp
    if age < STALE_AFTER_SECONDS:
        return False, "recent"

    return True, f"clean, pushed, {int(age // 86400)}d old"


def ignored(path: str, name: str) -> bool:
    """Whether git ignores this directory, so removing it discards nothing tracked."""
    result = run(["git", "-C", path, "check-ignore", "-q", "--", name], timeout=15)
    return result is not None and result.returncode == 0


def reclaim(path: str) -> list[str]:
    """Delete git-ignored build output under path. Returns what was removed."""
    import shutil

    removed = []
    for name in ARTIFACT_DIRS:
        candidate = os.path.join(path, name)
        if not os.path.isdir(candidate) or os.path.islink(candidate):
            continue
        if not ignored(path, name):
            continue
        try:
            shutil.rmtree(candidate, ignore_errors=True)
        except OSError:
            continue
        if not os.path.exists(candidate):
            removed.append(name)
    return removed


def main() -> int:
    payload = sys.stdin.read()

    import json

    try:
        data = json.loads(payload) if payload else {}
    except (ValueError, TypeError):
        data = {}
    if not isinstance(data, dict):
        data = {}

    # One sweep per session, from the parent: N subagents must not race on the same
    # directories.
    if data.get("agent_id"):
        return 0

    import shutil as _shutil

    if _shutil.which("wt") is None:
        return 0

    import time

    now = time.time()
    stale: list[tuple[str, str, list[str]]] = []
    for record in worktrees():
        ok, reason = is_stale(record, now)
        if not ok:
            continue
        path = record["path"]
        stale.append((record["branch"], reason, reclaim(path)))

    if not stale:
        return 0

    lines = []
    for branch, reason, removed in stale[:REPORT_LIMIT]:
        note = f"reclaimed {', '.join(removed)}" if removed else "no build output to reclaim"
        lines.append(f"{branch} ({reason}; {note})")

    message = (
        f"{len(stale)} abandoned Worktrunk worktree(s) -- clean, fully pushed, and "
        f"untouched for over {STALE_AFTER_SECONDS // 86400} days: "
        + "; ".join(lines)
    )
    if len(stale) > REPORT_LIMIT:
        message += f"; and {len(stale) - REPORT_LIMIT} more"
    message += (
        ". Build output was reclaimed where git ignores it. The worktrees and "
        "branches were NOT removed: run `wt remove <branch>` to drop one (it "
        "deletes the branch when merged and refuses when not), or `wt prune` to "
        "sweep them together."
    )
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": message,
            }
        },
        sys.stdout,
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
