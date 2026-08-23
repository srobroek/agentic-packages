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

# gh flags that take the next token as a value and are accepted before the command
# path. `gh -R owner/repo pr create` is valid, so dropping flag tokens without
# dropping this value reads `owner/repo` as the command group and matches nothing.
# Attached forms (`-Rowner/repo`, `--repo=owner/repo`) carry the value inside the
# flag token and need no skip.
GH_VALUE_FLAGS = frozenset({"-R", "--repo"})


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

    Returns "" when the command names a directory this cannot resolve -- a
    `cd $(cat file)`, a leading brace block, a subshell. Text cannot resolve
    those, and answering with the session directory instead is the failure that
    matters: a guard then judges a repository the command never touched. A live
    `gh pr create` for a repo with no beads workspace was blocked that way,
    demanding a merge bead the target repo could not have. Callers must treat ""
    as "unknown, do not judge" -- see `beads_active`.
    """
    # `shlex.split` does not treat `;` or a newline as a separator, so
    # `cd /x; gh` lexes the path and the semicolon as ONE token and the segment
    # loop never sees a boundary. Give the lexer punctuation awareness instead,
    # and let it emit `;` and `&&` as their own tokens.
    # A newline separates commands as surely as `;` does, but punctuation_chars
    # drops it, so a brace block's `cd` line would run on into the next command.
    # Read only the first non-empty line; a `cd` prefix never spans lines.
    first_line = next((line for line in command.splitlines() if line.strip()), "")
    lexer = shlex.shlex(first_line, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        tokens = list(lexer)
    except ValueError:
        # An unbalanced quote means the command cannot be read at all. Saying
        # "unknown" is the safe answer; naming the session directory would have a
        # caller judge a repository this never identified.
        return ""

    segment: list[str] = []
    for token in tokens:
        if token in SEPARATORS:
            break
        segment.append(token)

    # A brace block or subshell hides the `cd` behind its opener, so strip those
    # before looking for it: `{ cd /x` and `( cd /x` both mean cd /x.
    while segment[:1] in (["{"], ["("]):
        segment = segment[1:]

    if segment[:1] != ["cd"]:
        # No cd prefix at all: the command runs where the session is.
        return session_cwd

    # `--` ends option parsing for `cd`; it names no directory.
    arguments = [token for token in segment[1:] if token != "--"]
    if not arguments or arguments[0] in {"", "-"}:
        return session_cwd

    # Shell expansion the hook cannot perform: substitution, a variable, a glob.
    # The directory is real but unknowable from text, so say so rather than
    # silently answering with the session directory. `punctuation_chars` emits
    # `$` and a backtick as their own tokens, so test every argument token, not
    # just the first.
    if any(
        marker in token for token in arguments for marker in ("$", "`", "*", "?", "(")
    ):
        return ""

    if len(arguments) != 1:
        return ""
    argument = arguments[0]

    target = os.path.expanduser(argument)
    if not os.path.isabs(target):
        target = os.path.join(session_cwd or os.getcwd(), target)
    try:
        resolved = os.path.realpath(target)
    except OSError:
        return ""
    return resolved if os.path.isdir(resolved) else ""


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


def gh_command_path(arguments: list[str]) -> list[str]:
    """The group and subcommand a gh invocation names, ignoring preceding flags.

    Returns at most two tokens. Resolving the path by position in the operand list
    is what a guard must not do: any flag before the subcommand shifts that window,
    so `gh -R owner/repo pr create` would read as group `owner/repo`, and a guard
    keyed on `pr create` would pass it while refusing the unflagged form.
    """
    path: list[str] = []
    skip_value = False
    for token in arguments:
        if skip_value:
            skip_value = False
            continue
        if token.startswith("-"):
            skip_value = token in GH_VALUE_FLAGS
            continue
        path.append(token)
        if len(path) == 2:
            break
    return path


def beads_active(cwd: str) -> bool:
    """Whether bd resolves a workspace for this directory.

    Asks `bd` rather than walking for a `.beads` directory. A workspace in a
    shared ancestor -- `~/.beads` is common -- makes every repository under the
    home directory look beads-enabled.

    An empty `cwd` means `effective_cwd` could not resolve where the command
    runs. Answering for the current process would judge the session's repository
    instead, so treat unknown as not-active and let the caller stand down.
    """
    if shutil.which("bd") is None:
        return False
    if not cwd:
        return False
    try:
        return (
            subprocess.run(
                ["bd", "-C", cwd, "where"],
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
