#!/usr/bin/env python3
"""Advise when a `gh pr` body would close only the first issue in a list.

A `PreToolUse` hook cannot rewrite the command it inspects, so when the `--body`
of a `gh pr create` or `gh pr edit` carries a comma-list close, this allows the
call and puts the corrected body in the advisory. The agent re-issues the command
with the fix.

Only the INLINE body form is checked. `--body-file` points at a file this will
not rewrite, and a body typed in the editor is invisible to the hook; both simply
pass, since the commit-msg layer and the author still apply.

The commit-msg hook is the tool-agnostic auto-rewrite. This layer is fast
feedback on the agent's own PR commands.
"""

from __future__ import annotations

import json
import re
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from close_keywords import normalize  # noqa: E402

# `gh pr create` / `gh pr edit`, anchored to command position so a mention inside
# a string or a different subcommand does not trigger the guard.
GH_PR = re.compile(
    r"(?:^\s*|[;&|]\s*)gh\s+pr\s+(?:create|edit)(?:\s|$)",
    re.MULTILINE,
)

ADVICE = (
    "Heads-up: this gh pr --body has a comma-list close keyword; GitHub closes "
    "only the FIRST issue, so the later issues stay open. Suggested corrected "
    "body:\n\n"
)


def extract_command(payload: str) -> str:
    """Pull the command from a hook payload.

    tool_input is an object for most callers and a bare string for some, so the
    type is checked rather than assumed.
    """
    data = json.loads(payload)
    if not isinstance(data, dict):
        return ""
    tool_input = data.get("tool_input")
    if isinstance(tool_input, str):
        return tool_input
    if isinstance(tool_input, dict):
        command = tool_input.get("command")
        return command if isinstance(command, str) else ""
    return ""


def extract_body(command: str) -> str:
    """Return the inline `--body` value, unquoted, or an empty string.

    Splitting with the shell lexer is the point of the port: the value may span
    newlines, mix quote styles, and carry backslash escapes, and every hand-rolled
    tokenizer for that is a source of misreads.
    """
    try:
        tokens = shlex.split(command)
    except ValueError:
        # Unbalanced quotes: the shell would reject this command too.
        return ""

    for index, token in enumerate(tokens):
        if token in ("--body", "-b"):
            return tokens[index + 1] if index + 1 < len(tokens) else ""
        if token.startswith("--body="):
            return token[len("--body=") :]
        if token.startswith("-b="):
            return token[len("-b=") :]
    return ""


def main() -> int:
    payload = sys.stdin.read()
    # Cheap bail on the raw bytes: this guard only acts on `gh pr`. A strict
    # superset of the real trigger, so it cannot mask a real one.
    if "gh pr" not in payload:
        return 0

    try:
        command = extract_command(payload)
    except (ValueError, TypeError):
        return 0
    if not command or not GH_PR.search(command):
        return 0

    body = extract_body(command)
    if not body:
        return 0

    fixed = normalize(body)
    if fixed == body:
        return 0

    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "additionalContext": ADVICE + fixed,
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
        # Fail open: a close-keyword nudge must never wedge a PR command.
        raise SystemExit(0)
