#!/usr/bin/env python3
"""Auto-approve a `chezmoi` command at Codex's PermissionRequest.

Dotfile work runs `chezmoi apply`, `chezmoi diff`, and `chezmoi re-add` constantly,
and each one otherwise waits on a human. Approving only when `chezmoi` is the verb
keeps that narrow: a command that merely mentions chezmoi in an argument is not
approved.

Ported from shell, where the verb test was `sed`-trimmed whitespace plus a bash
regex on the RAW command. That approved on a prefix match of the whole string, so
`chezmoi apply && rm -rf ~` was auto-approved in full -- the regex only ever saw
the head of the command, never the `&&` tail. Lexing splits on the separator, so a
compound command is approved only when every segment is itself a chezmoi call.

Emits nothing when it cannot confirm the verb, which leaves the normal permission
flow untouched.
"""

from __future__ import annotations

import sys

# Separators that begin a new command. A compound command is only safe to
# auto-approve when every segment passes, so these have to split rather than be
# swallowed into an argument.
SEPARATORS = frozenset({";", "&&", "||", "|", "&", "\n"})


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


def segments(command: str) -> list[list[str]] | None:
    """Split into command segments, or None when the command cannot be lexed.

    A newline separates commands to the shell but is only whitespace to `shlex`,
    so an unguarded lex merged `chezmoi apply\\nrm -rf ~` into one segment and
    approved it. Splitting on newlines first, then lexing each line, keeps the
    per-segment rule honest. Quoting spans lines legally, so a line that fails to
    lex on its own is treated as unverifiable rather than merged.
    """
    import shlex

    result: list[list[str]] = []
    for line in command.splitlines():
        if not line.strip():
            continue
        lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        try:
            tokens = list(lexer)
        except ValueError:
            # Unbalanced quotes. The shell would reject this too, so approve
            # nothing rather than guess where the command ends.
            return None

        current: list[str] = []
        for token in tokens:
            if token in SEPARATORS:
                result.append(current)
                current = []
                continue
            current.append(token)
        result.append(current)
    return [segment for segment in result if segment]


def is_only_chezmoi(command: str) -> bool:
    """Whether every segment of the command invokes chezmoi as its verb.

    Requiring EVERY segment is the fix for the shell version, whose prefix regex
    approved `chezmoi apply && rm -rf ~` because it matched the head and never
    looked past it.
    """
    parsed = segments(command)
    if not parsed:
        return False

    for segment in parsed:
        verb = segment[0]
        # A substitution or subshell leaves punctuation on the verb; an
        # assignment prefix means the verb is not in command position at all.
        if any(character in verb for character in "$(`{="):
            return False
        if verb != "chezmoi" and not verb.endswith("/chezmoi"):
            return False
    return True


def main() -> int:
    payload = sys.stdin.read()
    if not payload:
        return 0

    # Cheap bail before importing json or shlex.
    if "chezmoi" not in payload:
        return 0

    command = command_from(payload)
    if not command or not is_only_chezmoi(command):
        return 0

    import json

    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PermissionRequest",
                "decision": {"behavior": "allow"},
            }
        },
        sys.stdout,
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
