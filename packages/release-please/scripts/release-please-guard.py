#!/usr/bin/env python3
"""Warn -- never block -- on manual release-please operations.

On a repo managed by release-please, manually cutting a release, tagging a
version, pushing tags, or hand-merging a release branch to a protected branch is
the way to botch the release loop indefinitely: release-please then sees an
untagged/mislabeled release and stops auto-tagging. This hook does not block --
it injects an advisory (`additionalContext`) so the model reconsiders and reads
the release-please skill. The command still runs.

Never emits `permissionDecision: "deny"` or `"ask"`: per the repo hook policy,
blocking decisions stall autonomous runs, and these operations are legitimate in
recovery scenarios. The note is the whole point.

Ported from shell almost line-for-line; the regexes are the load-bearing part and
are kept as close to the original ERE as re.IGNORECASE + word-boundary substitutes
allow, so behaviour matches the existing bats oracle.
"""

from __future__ import annotations

import sys

# Only `sys` at module scope. This is a PreToolUse:Bash hook, so it runs on every
# shell command; everything else is imported inside the functions that need it.


def extract(payload: str) -> tuple[str, str]:
    """Return (command, cwd). `tool_input` may be an object or a bare string."""
    import json

    data = json.loads(payload)
    if not isinstance(data, dict):
        return "", ""
    tool_input = data.get("tool_input")
    if isinstance(tool_input, str):
        command = tool_input
    elif isinstance(tool_input, dict):
        raw = tool_input.get("command")
        command = raw if isinstance(raw, str) else ""
    else:
        command = ""
    cwd = data.get("cwd")
    return command, cwd if isinstance(cwd, str) else ""


def is_release_please_repo(cwd: str) -> bool:
    """Whether this repo is release-please managed, at `cwd`.

    Prefers the detector script shipped with the skill (same package); falls back
    to a cheap inline config-file check when the detector cannot be found, so the
    guard still works when co-location differs (e.g. installed layout).
    """
    import os
    import subprocess

    here = os.path.dirname(os.path.abspath(__file__))
    candidates = (
        os.path.join(here, "..", ".apm", "skills", "release-please", "scripts", "detect-release-please.sh"),
        os.path.join(here, "..", "skills", "release-please", "scripts", "detect-release-please.sh"),
        os.path.join(here, "detect-release-please.sh"),
    )
    detect = next((c for c in candidates if os.path.isfile(c)), None)
    if detect is not None:
        try:
            completed = subprocess.run(
                ["bash", detect],
                cwd=cwd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=10,
            )
            return completed.returncode == 0
        except (subprocess.SubprocessError, OSError):
            return False
    return os.path.isfile(os.path.join(cwd, "release-please-config.json")) or os.path.isfile(
        os.path.join(cwd, ".release-please-manifest.json")
    )


def violation(command: str, cwd: str) -> str | None:
    """Return the advisory text for `command`, or None to allow silently."""
    import re

    lowered = command.lower()

    # --- 1. Manual GitHub Release creation ----------------------------------
    if re.search(r"(^|\s)gh\s+release\s+create(\s|$)", lowered):
        return (
            "RELEASE-PLEASE REPO: this repo is managed by release-please, which "
            "creates GitHub Releases automatically when the release PR merges. "
            "Running 'gh release create' manually cuts a release release-please "
            "did not author -- it will not flip the autorelease:pending label to "
            "autorelease:tagged, which can stall auto-tagging on every future "
            "release. Prefer merging the release PR. Only cut a manual release as "
            "a deliberate, documented fallback. See the release-please skill "
            "(references/pitfalls-recovery.md)."
        )

    # --- 2. Manual version tag creation -------------------------------------
    if re.search(
        r"(^|\s)git(\s+-\S+(\s+\S+)?)*\s+tag(\s+-[a-z]+)*\s+v?\d+\.\d+\.\d+",
        lowered,
    ):
        return (
            "RELEASE-PLEASE REPO: release-please owns version tags and cuts them "
            "automatically when the release PR merges. Creating a version tag by "
            "hand can collide with the tag release-please will create "
            "(duplicate-tag failure) or desync the manifest from the tags. Let the "
            "release PR do it. See the release-please skill."
        )

    # Also catch pushing tags explicitly.
    if re.search(
        r"(^|\s)git(\s+-\S+)*\s+push(\s+\S+)*\s+(--tags|--follow-tags)(\s|$)",
        lowered,
    ):
        return (
            "RELEASE-PLEASE REPO: pushing tags manually (git push "
            "--tags/--follow-tags) can publish a version tag that collides with "
            "the one release-please cuts on release-PR merge. release-please "
            "pushes its own tags. See the release-please skill."
        )

    # --- 3. Manual merge to a protected branch (bypassing the release PR) ---
    git_prefix = r"git(\s+-\S+(\s+\S+)?)*\s+"
    if re.search(git_prefix + r"merge(\s|$)", lowered):
        if not re.search(r"(^|\s)--(abort|continue|quit)(\s|=|$)", lowered):
            cur_branch = _current_branch(cwd)
            if cur_branch in ("main", "master"):
                return (
                    f"RELEASE-PLEASE REPO + PROTECTED BRANCH: you are on "
                    f"'{cur_branch}'. Releases must flow through release-please's "
                    "release PR (merge it via the PR, which triggers the tag + "
                    "GitHub Release). Do NOT hand-merge a release branch "
                    f"(release-please--branches--*) into '{cur_branch}' -- that "
                    "bypasses the tagging step and can leave an untagged, merged "
                    "release PR that stalls the loop. Ordinary feature merges are "
                    "fine; releases are not. See the release-please skill."
                )
    return None


def _current_branch(cwd: str) -> str:
    import subprocess

    try:
        completed = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=10,
            text=True,
        )
    except (subprocess.SubprocessError, OSError):
        return ""
    return completed.stdout.strip()


def main() -> int:
    payload = sys.stdin.read()
    if not payload:
        return 0
    # Cheap bail on the raw bytes: every rule below fires on a `git` or `gh`
    # invocation. A strict superset of the real trigger, so it cannot hide one the
    # regex checks would have caught.
    if "git" not in payload and "gh" not in payload:
        return 0

    try:
        command, cwd = extract(payload)
    except (ValueError, TypeError):
        return 0
    if not command:
        return 0

    import os

    if not cwd or not os.path.isdir(cwd):
        cwd = os.getcwd()

    if not is_release_please_repo(cwd):
        return 0

    context = violation(command, cwd)
    if context is None:
        return 0

    import json

    json.dump(
        {"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": context}},
        sys.stdout,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:
        # Fail open: an advisory-only guard must never turn an unexpected
        # exception into a stalled command.
        raise SystemExit(0)
