"""Shared helpers for the beads PreToolUse Bash guards. Imported, never run directly.

Both guards in this package read the same payload, resolve the same working
directory, gate on the same `bd where` probe, and emit the same envelope. Each is
a decision the two must not make differently: a guard that resolves a different
directory than its sibling enforces a different repository's state.

Imported lazily, after the calling guard's cheap bail on the raw payload. These
hooks run on every Bash call, so a module-scope import here would cost every
command in the session.

Every helper fails toward "cannot judge": an unreadable payload, an unresolvable
directory, and an unreachable `bd` all read as no evidence, never as a violation.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys

# Separators that end the first command in a shell line. A `cd` before one of
# these applies to what follows; a `cd` without one is the whole command.
SEPARATORS = frozenset({";", "&&", "||", "&", "|"})

# Punctuation that leaves a verb glued to a token: `$(gh`, `` `gh ``, `(gh`, and
# `x=$(gh` are each one token to the lexer.
VERB_PREFIXES = ("=", "$(", "`", "(", "{", ";", "&", "|")


def payload_fields(payload: str) -> tuple[str, str]:
    """Return the command and the directory it runs in, from a hook payload."""
    try:
        data = json.loads(payload)
    except (ValueError, TypeError):
        return "", ""
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

    raw_cwd = data.get("cwd")
    cwd = raw_cwd if isinstance(raw_cwd, str) and os.path.isdir(raw_cwd) else ""
    return command, effective_cwd(command, cwd)


def effective_cwd(command: str, session_cwd: str) -> str:
    """Directory the command runs in, honouring a leading `cd <path> &&`.

    The payload `cwd` is the session's directory, but an agent harness routinely
    prefixes a Bash call with `cd <path> &&`. Resolving beads state against the
    session directory instead of the command's directory makes a guard judge the
    wrong repository, and no `cd` prefix can correct it.
    """
    try:
        tokens = shlex.split(command)
    except ValueError:
        return session_cwd

    segment: list[str] = []
    for token in tokens:
        if token in SEPARATORS:
            break
        segment.append(token)
    if segment[:1] != ["cd"]:
        return session_cwd

    # `--` ends option parsing for `cd`; it names no directory.
    arguments = [token for token in segment[1:] if token != "--"]
    if len(arguments) != 1 or arguments[0] in {"", "-"}:
        return session_cwd

    target = os.path.expanduser(arguments[0])
    if not os.path.isabs(target):
        target = os.path.join(session_cwd or os.getcwd(), target)
    try:
        resolved = os.path.realpath(target)
    except OSError:
        return session_cwd
    return resolved if os.path.isdir(resolved) else session_cwd


def gh_invocations(command: str) -> list[list[str]]:
    """Token runs following each `gh` that sits in command position.

    Lexing rather than pattern-matching the raw string is what keeps a quoted
    mention -- `git commit -m "do not gh pr create yet"` -- from tripping a
    guard: shlex resolves it to a single argument token, so the `gh` inside it is
    never in command position.

    A wrapper prefix, a command substitution, a subshell, and a separator all
    still match, because the tokens they yield put `gh` where a verb goes.
    """
    try:
        tokens = shlex.split(command)
    except ValueError:
        # Unbalanced quotes: the shell would reject this too, so there is nothing
        # reliable to judge.
        return []

    runs: list[list[str]] = []
    for index, token in enumerate(tokens):
        verb = token
        for separator in VERB_PREFIXES:
            if separator in verb:
                verb = verb.rsplit(separator, 1)[-1]
        if verb == "gh" or verb.endswith("/gh"):
            runs.append(tokens[index + 1 :])
    return runs


def beads_active(cwd: str) -> bool:
    """Whether bd resolves a workspace for this directory.

    Asks `bd` rather than walking for a `.beads` directory. A workspace in a
    shared ancestor -- `~/.beads` is common -- makes every repository under the
    home directory look beads-enabled.
    """
    if shutil.which("bd") is None:
        return False
    try:
        return (
            subprocess.run(
                ["bd", "-C", cwd or ".", "where"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=10,
            ).returncode
            == 0
        )
    except (subprocess.SubprocessError, OSError):
        return False


def deny(reason: str) -> None:
    """Emit a PreToolUse denial. The decision travels in JSON, never in the exit code."""
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        },
        sys.stdout,
    )


def advise(context: str) -> None:
    """Emit a PreToolUse advisory: the command proceeds, unverified."""
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": context,
            }
        },
        sys.stdout,
    )
