#!/usr/bin/env python3
"""Deny agent-issued ``gh pr create`` that does not pass ``--draft``.

One rule, because one rule earns a denial: a non-draft PR has already notified
reviewers and started CI by the time anyone notices, and `gh pr ready` cannot
un-send that.

Beads linkage is intentionally not checked here. The merge queue discovers work
through `bd list --label pr:merge` and probes it through bead metadata; the
shepherd verifies its own anchors against the live PR. PR-body trailers would
duplicate that source of truth and are not required by this guard.
"""

from __future__ import annotations

import json
import os
import shlex
import sys
from typing import Any

CONTROL = {";", "&&", "||", "|", "&", "(", ")"}
SHELLS = {"bash", "sh", "zsh", "dash", "fish", "ksh"}
WRAPPERS = {"command", "env", "exec", "nice", "nohup", "sudo", "time", "timeout"}
COMMAND_KEYWORDS = {"if", "then", "elif", "else", "while", "until", "do", "!", "{"}

WRAPPER_OPTIONS_WITH_VALUE = {
    "env": {"-u", "--unset", "-C", "--chdir", "--argv0"},
    "exec": {"-a"},
    "nice": {"-n", "--adjustment"},
    "nohup": set(),
    "sudo": {
        "-u",
        "--user",
        "-g",
        "--group",
        "-h",
        "--host",
        "-p",
        "--prompt",
        "-C",
        "--close-from",
        "-D",
        "--chdir",
        "-R",
        "--chroot",
        "-T",
        "--command-timeout",
        "-r",
        "--role",
        "-t",
        "--type",
    },
    "time": {"-f", "--format", "-o", "--output"},
    "timeout": {"-k", "--kill-after", "-s", "--signal"},
}


def deny(reason: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )


def advise(context: str) -> None:
    """Allow the command but tell the model what could not be verified.

    Used for an unparsable command. Denying on an inconclusive check turns every
    parser gap into a blocked PR, which is the opposite of what a guard is for.
    """
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "additionalContext": context,
                }
            }
        )
    )


def payload_command(payload: Any) -> str:
    """Extract the command. Codex sends a bare string, Claude sends an object."""
    if isinstance(payload, str):
        return payload
    if not isinstance(payload, dict):
        return ""
    tool_input = payload.get("tool_input", "")
    command = tool_input.get("command", "") if isinstance(tool_input, dict) else tool_input
    return command if isinstance(command, str) else ""


def shell_tokens(command: str) -> list[str]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()")
    lexer.whitespace_split = True
    lexer.commenters = "#"
    normalized: list[str] = []
    for token in lexer:
        if token and all(character in ";&|()" for character in token):
            index = 0
            while index < len(token):
                pair = token[index : index + 2]
                if pair in {"&&", "||"}:
                    normalized.append(pair)
                    index += 2
                else:
                    normalized.append(token[index])
                    index += 1
        else:
            normalized.append(token)
    return normalized


def unwrap_command(tokens: list[str], index: int) -> int | None:
    """Return the executable token after command wrappers and their options."""
    while index < len(tokens):
        token = tokens[index]
        if "=" in token and not token.startswith("=") and not token.startswith("-"):
            index += 1
            continue
        wrapper = os.path.basename(token)
        if wrapper not in WRAPPERS:
            return index
        index += 1
        if wrapper == "command":
            while index < len(tokens) and tokens[index].startswith("-"):
                option = tokens[index]
                if "v" in option[1:] or "V" in option[1:]:
                    return None
                index += 1
            continue
        if (
            wrapper == "env"
            and index < len(tokens)
            and (
                tokens[index] in {"-S", "--split-string"}
                or tokens[index].startswith("-S")
                or tokens[index].startswith("--split-string=")
            )
        ):
            return index - 1
        options_with_value = WRAPPER_OPTIONS_WITH_VALUE[wrapper]
        while index < len(tokens):
            option = tokens[index]
            if option == "--":
                index += 1
                break
            if wrapper == "env" and "=" in option and not option.startswith("-"):
                index += 1
                continue
            if not option.startswith("-") or option == "-":
                break
            name = option.split("=", 1)[0]
            index += 1
            if name in options_with_value and "=" not in option:
                index += 1
        if wrapper == "timeout" and index < len(tokens):
            index += 1
        continue
    return None


def env_split_invocation(
    tokens: list[str], index: int, depth: int
) -> tuple[list[list[str]], int] | None:
    """Expand env -S/--split-string into the command it executes."""
    while index < len(tokens):
        token = tokens[index]
        if "=" in token and not token.startswith("=") and not token.startswith("-"):
            index += 1
            continue
        break
    if index >= len(tokens) or os.path.basename(tokens[index]) != "env":
        return None
    cursor = index + 1
    while cursor < len(tokens) and tokens[cursor] not in CONTROL:
        option = tokens[cursor]
        split_command: str | None = None
        if option in {"-S", "--split-string"} and cursor + 1 < len(tokens):
            split_command = tokens[cursor + 1]
            cursor += 2
        elif option.startswith("-S") and len(option) > 2:
            split_command = option[2:]
            cursor += 1
        elif option.startswith("--split-string="):
            split_command = option.split("=", 1)[1]
            cursor += 1
        if split_command is not None:
            end = cursor
            while end < len(tokens) and tokens[end] not in CONTROL:
                end += 1
            if cursor < end:
                split_command = f"{split_command} {shlex.join(tokens[cursor:end])}"
            return invocation_spans(split_command, depth + 1), end
        if option in {"-u", "--unset", "-C", "--chdir", "--argv0"}:
            cursor += 2
            continue
        if option == "--" or not option.startswith("-"):
            return None
        cursor += 1
    return None


def gh_create_arguments(tokens: list[str], index: int) -> tuple[list[str], int] | None:
    """Normalize a gh PR create invocation, including gh global repo options."""
    cursor = index + 1
    while cursor < len(tokens) and tokens[cursor] not in CONTROL:
        option = tokens[cursor]
        if option in {"-R", "--repo", "--hostname"}:
            cursor += 2
            continue
        if option.startswith("-R") and len(option) > 2:
            cursor += 1
            continue
        if option.startswith("--repo=") or option.startswith("--hostname="):
            cursor += 1
            continue
        break
    if tokens[cursor : cursor + 2] != ["pr", "create"]:
        return None
    end = cursor + 2
    while end < len(tokens) and tokens[end] not in CONTROL:
        end += 1
    return [tokens[index], "pr", "create", *tokens[cursor + 2 : end]], end


def invocation_spans(command: str, depth: int = 0) -> list[list[str]]:
    if depth > 4:
        raise ValueError("nested shell command depth exceeds policy limit")
    tokens = shell_tokens(command)
    found: list[list[str]] = []

    index = 0
    command_start = True
    while index < len(tokens):
        token = tokens[index]
        if token in CONTROL or token in COMMAND_KEYWORDS:
            command_start = True
            index += 1
            continue
        if not command_start:
            index += 1
            continue
        if split := env_split_invocation(tokens, index, depth):
            nested, end = split
            found.extend(nested)
            command_start = False
            index = end
            continue
        executable = unwrap_command(tokens, index)
        if executable is None:
            command_start = False
            index += 1
            continue
        index = executable
        if split := env_split_invocation(tokens, index, depth):
            nested, end = split
            found.extend(nested)
            command_start = False
            index = end
            continue
        basename = os.path.basename(tokens[index])
        if basename in SHELLS:
            option_index = index + 1
            while option_index < len(tokens) and tokens[option_index] not in CONTROL:
                option = tokens[option_index]
                if option.startswith("-") and "c" in option[1:]:
                    if option_index + 1 < len(tokens):
                        found.extend(
                            invocation_spans(tokens[option_index + 1], depth + 1)
                        )
                    break
                option_index += 1
            command_start = False
            index = option_index + 2
            continue
        if basename == "gh" and (parsed := gh_create_arguments(tokens, index)):
            invocation, end = parsed
            found.append(invocation)
            command_start = False
            index = end
            continue
        command_start = False
        index += 1
    return found


def draft_enabled(invocation: list[str]) -> bool:
    enabled = False
    true_values = {"1", "t", "true", "yes", "y", "on"}
    for token in invocation[3:]:
        if token in {"--draft", "-d"}:
            enabled = True
        if token.startswith("--draft=") or token.startswith("-d="):
            enabled = token.split("=", 1)[1].lower() in true_values
    return enabled


def main() -> int:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        payload = raw
    command = payload_command(payload)
    if not command:
        return 0
    # Cheap bail before tokenizing. This hook is registered on every Bash call,
    # and the shell wrapper that used to do this filtering is gone. A strict
    # superset of the real trigger, so it cannot hide a command the parser would
    # have flagged.
    if not all(word in command for word in ("gh", "pr", "create")):
        return 0
    try:
        invocations = invocation_spans(command)
    except ValueError as error:
        # Allow, do not deny. PR bodies carry markdown: apostrophes, backticks,
        # and nested quotes all make the tokenizer give up, and a command this
        # guard cannot read is not evidence of a policy breach.
        advise(
            f"PR policy not verified: this command could not be parsed ({error}). "
            "Ensure the invocation uses --draft."
        )
        return 0
    if any(not draft_enabled(invocation) for invocation in invocations):
        deny(
            "Agent-authored PRs must start as drafts. Re-run every gh pr create "
            "invocation with --draft; use gh pr ready only after implementation, "
            "local validation, and required review are complete."
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:
        # Fail open, per the hook contract: an unexpected exception allows rather
        # than blocking. Without this, a payload whose `cwd` was not a string raised
        # TypeError and exited 1 instead of exiting 0 quietly.
        raise SystemExit(0)
