#!/usr/bin/env python3
"""Deny a `gh pr create` whose merge bead cannot serve the merge queue.

In a beads repository the merge queue discovers a pull request through its merge
bead, and reads the bead's anchors to decide what to land. A merge bead that is
closed, mislabelled, already assigned, or missing an anchor is discovered and then
skipped, so the pull request waits for a queue that will never take it. Refusing
at creation puts the failure where the author can still fix it.

The merge bead is resolved by BRANCH, never by a pull-request-body trailer. A
trailer requirement is circular: it demands a line in every pull request body in
order to check that line, and nothing else reads it. `metadata.branch` is the join
key the merge queue itself uses, so the guard and the queue read one record.

A missing merge bead is refused wherever the convention is in use, which is any
repository holding at least one bead with a merge-queue label. A repository that
tracks work in beads and has no merge queue holds none, and the guard stays quiet
there rather than demanding a bead the workflow never uses.

Fail open on everything unverifiable: no bd, no beads workspace, an unreadable
payload, an unparsable command, a lookup that cannot complete. A guard that cannot
confirm the state has nothing to enforce.
"""

from __future__ import annotations

import sys

# Only `sys` at module scope. This is a PreToolUse:Bash hook, so it runs on every
# shell command and the bail in main() must precede any costly import.

# Labels a merge bead carries. Both are required; either one makes a bead a
# candidate, so a bead that dropped one is found and refused rather than missed.
REQUIRED_LABELS = ("pr:merge", "agent:integrator")

# Anchors the merge queue reads to match a bead against a live pull request.
# `branch` is absent because it is enforced earlier and more strongly: a bead whose
# branch metadata is missing or wrong matches no branch, and a branch with no match
# is refused outright where the convention is in use.
REQUIRED_METADATA = ("repo", "origin_actor")

# `bd` is Dolt-backed: a healthy call still takes about a second, and load pushes
# it well past that. One retry absorbs a transient stall.
BD_TIMEOUT = 30
BD_ATTEMPTS = 2


class BeadsUnavailable(Exception):
    """`bd` could not answer, so the absence of a record proves nothing."""


def head_branch(arguments: list[str], cwd: str) -> str:
    """Branch the pull request would be opened from.

    `--head` wins when given, because it names the branch being proposed even when
    the command runs from a different checkout. A cross-fork value arrives as
    `owner:branch`, and the merge bead records the branch alone.
    """
    import subprocess

    for index, token in enumerate(arguments):
        value = ""
        if token in {"--head", "-H"} and index + 1 < len(arguments):
            value = arguments[index + 1]
        elif token.startswith("--head="):
            value = token.split("=", 1)[1]
        if value:
            return value.rsplit(":", 1)[-1]

    # `symbolic-ref` rather than `rev-parse --abbrev-ref`: it names a branch that
    # has no commit yet, and fails on a detached HEAD instead of returning the
    # literal "HEAD" as a branch name.
    try:
        result = subprocess.run(
            ["git", "-C", cwd or ".", "symbolic-ref", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (subprocess.SubprocessError, OSError):
        return ""
    return "" if result.returncode != 0 else result.stdout.strip()


def candidate_beads(cwd: str) -> list[dict]:
    """Every open or closed bead carrying a merge-bead label.

    Queries on `--label-any` rather than requiring both labels, so a bead that lost
    one is still found and can be refused for losing it. Requiring both in the
    query would make that defect indistinguishable from absence.
    """
    import json
    import shutil
    import subprocess

    if shutil.which("bd") is None:
        raise BeadsUnavailable("bd is not installed")

    command = [
        "bd",
        "-C",
        cwd or ".",
        "list",
        "--label-any",
        ",".join(REQUIRED_LABELS),
        "--all",
        "--limit",
        "0",
        "--json",
    ]
    last_error = "unknown error"
    for _ in range(BD_ATTEMPTS):
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, check=False, timeout=BD_TIMEOUT
            )
        except subprocess.TimeoutExpired:
            last_error = "bd list timed out"
            continue
        except OSError as error:
            raise BeadsUnavailable(f"could not run bd: {error}") from error

        if result.returncode != 0:
            last_error = (result.stderr.strip().splitlines() or ["bd list failed"])[0]
            continue
        output = result.stdout.strip()
        if not output:
            return []
        try:
            payload = json.loads(output)
        except json.JSONDecodeError:
            last_error = "bd returned unparsable JSON"
            continue
        # bd wraps output as {"data": [...]} under BD_JSON_ENVELOPE and returns the
        # bare list without it, so both shapes have to be accepted.
        if isinstance(payload, dict):
            payload = payload.get("data")
        if not isinstance(payload, list):
            return []
        return [record for record in payload if isinstance(record, dict)]
    raise BeadsUnavailable(last_error)


def matches_branch(record: dict, branch: str) -> bool:
    """Whether this bead anchors exactly this branch.

    Equality, never a prefix: `feat/thing` and `feat/thing-extra` are different
    branches with different pull requests, and a prefix match would let either
    one's bead answer for the other.
    """
    metadata = record.get("metadata")
    return isinstance(metadata, dict) and metadata.get("branch") == branch


def defect(record: dict) -> str | None:
    """Why this merge bead cannot serve the queue, None when it can."""
    bead_id = record.get("id") or "<unknown>"
    labels = record.get("labels")
    missing_labels = [
        label
        for label in REQUIRED_LABELS
        if not isinstance(labels, list) or label not in labels
    ]
    if missing_labels:
        return (
            f"Merge bead {bead_id} is missing the {' and '.join(missing_labels)} "
            f"label. The merge queue selects on {' and '.join(REQUIRED_LABELS)}, so a "
            "bead without both is never picked up."
        )
    if record.get("status") != "open":
        return (
            f"Merge bead {bead_id} for this branch is {record.get('status')}, not open. "
            "A closed merge bead is already spent; open a new one for this pull request."
        )
    if record.get("assignee"):
        return (
            f"Merge bead {bead_id} is assigned to {record['assignee']}. The queue claims "
            "an unassigned bead, so leave the assignee empty until it is picked up."
        )
    metadata = record.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    missing = [name for name in REQUIRED_METADATA if not metadata.get(name)]
    if missing:
        return (
            f"Merge bead {bead_id} is missing {', '.join(missing)} metadata. The queue "
            "matches the bead against the live pull request on branch, repo, and "
            "origin_actor, and cannot match on an absent anchor. Write them with "
            "bd update <id> --metadata '<json>'."
        )
    return None


def main() -> int:
    payload = sys.stdin.read()
    # Cheap bail on the raw bytes: every denial needs all three words. A strict
    # superset of the real trigger, so it cannot hide one the lexer would catch.
    if not all(word in payload for word in ("gh", "pr", "create")):
        return 0

    import os.path

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import beads_hooks

    command, cwd = beads_hooks.payload_fields(payload)
    if not command:
        return 0

    runs = [
        arguments
        for arguments in beads_hooks.gh_invocations(command)
        if beads_hooks.gh_command_path(arguments) == ["pr", "create"]
    ]
    if not runs:
        return 0
    if not beads_hooks.beads_active(cwd):
        return 0

    for arguments in runs:
        branch = head_branch(arguments, cwd)
        if not branch:
            beads_hooks.advise(
                "Merge-bead policy not verified: the branch this pull request would be "
                "opened from could not be determined. Confirm the merge bead is open, "
                "unassigned, and carries branch, repo, and origin_actor metadata."
            )
            return 0
        try:
            candidates = candidate_beads(cwd)
        except BeadsUnavailable as error:
            beads_hooks.advise(
                f"Merge-bead policy not verified: the bead lookup could not complete "
                f"({error}). The merge bead must still be open, unassigned, labelled "
                f"{' and '.join(REQUIRED_LABELS)}, and carry branch, repo, and "
                "origin_actor metadata."
            )
            return 0

        matching = [record for record in candidates if matches_branch(record, branch)]
        if not matching:
            if not candidates:
                # No bead in this repository has ever carried a merge-queue label,
                # so the convention is not in use here and there is nothing to
                # enforce. Tracking work in beads does not imply a merge queue.
                continue
            beads_hooks.deny(
                f"No merge bead anchors branch {branch}. This repository routes pull "
                f"requests through a merge queue, which finds the bead by matching "
                f"metadata.branch, so a pull request without one is never picked up. "
                f"Create a bead labelled {' and '.join(REQUIRED_LABELS)} with "
                f"metadata.branch set to {branch}, or correct the branch metadata on "
                f"the bead that was meant to anchor it."
            )
            return 0
        if len(matching) > 1:
            ids = ", ".join(sorted(str(record.get("id")) for record in matching))
            beads_hooks.deny(
                f"Branch {branch} has more than one merge bead ({ids}). The queue "
                "resolves a pull request by branch, so it cannot choose between them. "
                "Close or re-anchor all but one."
            )
            return 0
        reason = defect(matching[0])
        if reason:
            beads_hooks.deny(reason)
            return 0
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:
        # Fail open: this hook is registered on every Bash call, so exiting non-zero
        # over an internal defect fails every command in the session, including the
        # ones needed to diagnose it. The breadcrumb keeps a crash from reading as a
        # pass.
        import traceback

        traceback.print_exc(file=sys.stderr)
        raise SystemExit(0)
