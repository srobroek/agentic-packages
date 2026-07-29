#!/usr/bin/env python3
"""Deny a mutating `gh issue` command in a repository that tracks work in beads.

Where a beads workspace is active, agent task state lives in bd. Creating or
closing a GitHub issue to record it splits the record across two stores, and the
beads one is what the workflow reads. The denial carries the bd replacement so the
agent self-corrects without a human.

Read-only subcommands stay allowed: referencing a human-facing issue is ordinary
work, and only recording task state as one is not.

Ported from shell, where quoted text was stripped by a 12-line awk state machine
tracking quote style and backslash escapes by hand. `shlex` is the shell's own
lexer, so a `gh issue close` inside a commit message stays an argument rather than
becoming a command.

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


def extract(payload: str) -> tuple[str, str]:
    """Return the command and the directory it runs in."""
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


def mutates_an_issue(command: str) -> bool:
    """Whether the command runs `gh issue <mutating>` as a command, not as text.

    Lexing rather than pattern-matching the raw string is what keeps a quoted
    mention -- `git commit -m "do not gh issue close 5"` -- from tripping the
    guard: shlex resolves it to a single argument token, so the `gh` inside it is
    never in command position.

    A wrapper prefix, a command substitution, a subshell, and a separator all still
    match, because the tokens they yield put `gh` where a verb goes.
    """
    import shlex

    try:
        tokens = shlex.split(command)
    except ValueError:
        # Unbalanced quotes: the shell would reject this too, so there is nothing
        # reliable to judge.
        return False

    for index, token in enumerate(tokens):
        # A substitution, subshell, or assignment leaves punctuation attached to the
        # verb: `$(gh`, `` `gh ``, `(gh`, and `x=$(gh` are all one token to the
        # lexer. Taking the text after the last such character reduces every form to
        # `gh`, where stripping a leading run alone missed the assignment case.
        verb = token
        for separator in ("=", "$(", "`", "(", "{", ";", "&", "|"):
            if separator in verb:
                verb = verb.rsplit(separator, 1)[-1]
        if verb != "gh" and not verb.endswith("/gh"):
            continue
        rest = [word for word in tokens[index + 1 :] if not word.startswith("-")]
        if len(rest) >= 2 and rest[0] == "issue" and rest[1] in MUTATING:
            return True
    return False


def beads_active(cwd: str) -> bool:
    """Whether bd resolves a workspace for this directory."""
    import shutil
    import subprocess

    if shutil.which("bd") is None:
        return False
    directory = cwd if cwd else "."
    try:
        return (
            subprocess.run(
                ["bd", "-C", directory, "where"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=10,
            ).returncode
            == 0
        )
    except (subprocess.SubprocessError, OSError):
        return False


def main() -> int:
    payload = sys.stdin.read()
    # Cheap bail on the raw bytes: every denial needs both words. A strict superset
    # of the real trigger, so it cannot hide one the lexer would have caught.
    if "gh" not in payload or "issue" not in payload:
        return 0

    try:
        command, cwd = extract(payload)
    except (ValueError, TypeError):
        return 0
    if not command or not mutates_an_issue(command):
        return 0

    import os

    if cwd and not os.path.isdir(cwd):
        cwd = ""
    if not beads_active(cwd):
        return 0

    import json

    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": REASON,
            }
        },
        sys.stdout,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:
        # Fail open: never wedge the agent over a task-tracking convention.
        raise SystemExit(0)
