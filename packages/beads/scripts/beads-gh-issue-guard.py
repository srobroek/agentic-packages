#!/usr/bin/env python3
"""Deny a mutating `gh issue` command in a repository that tracks work in beads.

Where a beads workspace is active, agent task state lives in bd. Creating or
closing a GitHub issue to record it splits the record across two stores, and the
beads one is what the workflow reads. The denial carries the bd replacement so the
agent self-corrects without a human.

Read-only subcommands stay allowed: referencing a human-facing issue is ordinary
work, and only recording task state as one is not.

Payload reading, working-directory resolution, lexing, and the beads-workspace
probe live in `beads_hooks`, shared with the other guard in this package.

Fail open on everything unverifiable: no bd, no beads workspace, an unreadable
payload. A guard that cannot confirm the workspace has nothing to enforce.
"""

from __future__ import annotations

import sys

# Only `sys` at module scope. This is a PreToolUse:Bash hook, so it runs on every
# shell command and the bail in main() must precede any costly import.

# Subcommands that write. `develop` creates a branch and links it, which is task
# state; `list`, `view`, and `status` only read.
MUTATING = frozenset(
    {
        "create",
        "close",
        "edit",
        "comment",
        "reopen",
        "delete",
        "transfer",
        "pin",
        "unpin",
        "lock",
        "unlock",
        "develop",
    }
)

REASON = (
    "Task state lives in beads here (.beads/ present), not GitHub issues. Instead "
    'of gh issue: create work -> bd create "title" --spec-id <slug> (deps: bd dep '
    "add <later> <earlier>); pick up -> bd ready --unassigned --json + bd update "
    '<id> --claim; finish -> bd close <id> --reason "..."; discuss -> bd comments '
    'add <id> "...". If this is genuinely a human-facing GitHub issue (external '
    "users/reporting), the user must request it explicitly."
)


def mutates_an_issue(command: str) -> bool:
    """Whether the command runs `gh issue <mutating>` as a command, not as text."""
    import beads_hooks

    for arguments in beads_hooks.gh_invocations(command):
        rest = [word for word in arguments if not word.startswith("-")]
        if len(rest) >= 2 and rest[0] == "issue" and rest[1] in MUTATING:
            return True
    return False


def main() -> int:
    payload = sys.stdin.read()
    # Cheap bail on the raw bytes: every denial needs both words. A strict superset
    # of the real trigger, so it cannot hide one the lexer would have caught.
    if "gh" not in payload or "issue" not in payload:
        return 0

    import os.path

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import beads_hooks

    command, cwd = beads_hooks.payload_fields(payload)
    if not command or not mutates_an_issue(command):
        return 0
    if not beads_hooks.beads_active(cwd):
        return 0

    beads_hooks.deny(REASON)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:
        # Fail open: never wedge the agent over a task-tracking convention.
        raise SystemExit(0)
