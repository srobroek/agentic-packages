#!/usr/bin/env python3
"""Advise using gh-api.py when a command batches several mutating `gh` calls.

Batch GitHub work needs rate-limit accounting, retries, and throttling, which
gh-api.py has and a bare `gh` loop does not. One-off interactive `gh` stays fine,
so the threshold is three or more calls in a single command.

Ported from shell, where two `sed` passes stripped quoted text and `grep -oE`
counted the calls. Both were bypassable in the same ways the repository's other
shell guards were: the quote stripper handled neither backslash escapes nor
nesting, so `gh api ... -f body="it's fine"` left an unbalanced quote that
desynchronised every later strip, and counting on `(^|[;&|]\\s*)gh\\s+` missed a
wrapper prefix (`time gh ...`), an env assignment (`GH_TOKEN=x gh ...`), and a
command substitution, while an `&&`-separated call was counted only via the `&`
in the class by accident. `shlex` is the shell's own lexer, so quoting resolves
the way the shell resolves it and the verb position is a token index, not a
regex anchor.

Fail open on anything unverifiable: an unreadable payload, an unbalanced command.
"""

from __future__ import annotations

import sys

# Only `sys` at module scope. This is a PreToolUse:Bash hook, so it runs on every
# shell command the agent issues and the bail in main() must precede any import
# that costs more than it saves.

# Subcommands that mutate or spend rate limit in bulk. `auth` is excluded by an
# earlier bail: it is interactive setup, never batch work.
BATCH_SUBCOMMANDS = frozenset(
    {
        "api",
        "issue",
        "pr",
        "label",
        "project",
        "gist",
        "release",
        "repo",
        "secret",
        "variable",
    }
)

# Three is the point where accounting starts to matter. Two `gh` calls in one
# command is ordinary interactive work (`gh pr view && gh pr checks`).
THRESHOLD = 3

REASON = (
    "Multiple GitHub CLI operations detected -- use gh-api.py for large batch work "
    "that needs rate-limit accounting, retries, or throttling. For interactive "
    "one-off usage, plain gh is allowed."
)

# Punctuation that can sit between a separator and the verb. A substitution,
# subshell, or assignment leaves it attached to the token: `$(gh`, `` `gh ``,
# `(gh`, and `GH_TOKEN=x` are each one token to the lexer, so reducing to the text
# after the last such character recovers the verb. Stripping a leading run alone
# missed the assignment form.
VERB_SEPARATORS = ("=", "$(", "`", "(", "{", ";", "&", "|")


def command_from(payload: str) -> str:
    """Return the command string, or empty when the payload does not carry one."""
    import json

    try:
        data = json.loads(payload)
    except (ValueError, TypeError):
        return ""
    if not isinstance(data, dict):
        return ""
    tool_input = data.get("tool_input")
    if isinstance(tool_input, str):
        return tool_input
    if isinstance(tool_input, dict):
        raw = tool_input.get("command")
        return raw if isinstance(raw, str) else ""
    return ""


def gh_invocations(command: str) -> list[list[str]]:
    """Return the argument list of each `gh` call in command position.

    Lexing is what keeps a quoted mention from counting: `git commit -m "gh api
    x; gh api y; gh api z"` resolves to a single argument token, so the `gh`
    inside it never reaches a verb position. A wrapper prefix, an env assignment,
    a substitution, and a separator all still count, because each yields a token
    where a verb goes.
    """
    import shlex

    try:
        tokens = shlex.split(command)
    except ValueError:
        # Unbalanced quotes: the shell would reject this too, so there is nothing
        # reliable to judge and nothing to advise about.
        return []

    calls: list[list[str]] = []
    for index, token in enumerate(tokens):
        verb = token
        for separator in VERB_SEPARATORS:
            if separator in verb:
                verb = verb.rsplit(separator, 1)[-1]
        if verb != "gh" and not verb.endswith("/gh"):
            continue
        # Arguments up to the next call boundary are this call's; a later `gh` is
        # found on its own iteration, so overrunning here is harmless.
        calls.append(tokens[index + 1 :])
    return calls


def should_advise(command: str) -> bool:
    """Whether the command batches enough mutating `gh` calls to warrant advice."""
    # gh-api.py IS the recommended tool, so a command already using it is done.
    if "gh-api.py" in command:
        return False

    # `gh auth` is interactive setup, so it does not count toward the batch. The
    # shell version bailed on the WHOLE command when it saw one, which exempted a
    # genuine four-call batch that happened to include an auth check -- and it
    # missed the bail anyway whenever the separator was a newline, because its
    # anchor class held only `;`, `&`, and `|`. Discounting the call rather than
    # the command fixes both directions.
    counted = []
    for arguments in gh_invocations(command):
        positional = [word for word in arguments if not word.startswith("-")]
        if positional and positional[0] == "auth":
            continue
        counted.append(positional)

    if len(counted) < THRESHOLD:
        return False

    return any(positional and positional[0] in BATCH_SUBCOMMANDS for positional in counted)


def main() -> int:
    payload = sys.stdin.read()
    if not payload:
        return 0

    # Cheap bail before importing json or shlex: no `gh` at all, nothing to weigh.
    if "gh" not in payload:
        return 0

    command = command_from(payload)
    if not command:
        return 0

    if not should_advise(command):
        return 0

    import json

    # allow + additionalContext, not deny: batching is a preference, and
    # constitution III reserves deny for catastrophic operations. The shell version
    # denied, which stalled legitimate one-off sequences.
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "additionalContext": REASON,
            }
        },
        sys.stdout,
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
