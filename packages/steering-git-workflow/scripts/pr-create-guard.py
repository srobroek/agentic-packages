#!/usr/bin/env python3
"""Block non-draft or unlinked agent-issued ``gh pr create`` commands."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
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


def payload_command(payload: Any) -> tuple[str, Path]:
    if isinstance(payload, str):
        return payload, Path.cwd()
    if not isinstance(payload, dict):
        return "", Path.cwd()
    tool_input = payload.get("tool_input", "")
    if isinstance(tool_input, dict):
        command = tool_input.get("command", "")
    else:
        command = tool_input
    raw_cwd = payload.get("cwd") or os.getcwd()
    cwd = Path(raw_cwd)
    return command if isinstance(
        command, str
    ) else "", cwd if cwd.is_dir() else Path.cwd()


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


def argument(invocation: list[str], long: str, short: str) -> str | None:
    args = invocation[3:]
    for index, token in enumerate(args):
        if token in {long, short}:
            return args[index + 1] if index + 1 < len(args) else None
        if token.startswith(f"{long}=") or token.startswith(f"{short}="):
            return token.split("=", 1)[1]
    return None


def draft_enabled(invocation: list[str]) -> bool:
    enabled = False
    true_values = {"1", "t", "true", "yes", "y", "on"}
    for token in invocation[3:]:
        if token in {"--draft", "-d"}:
            enabled = True
        if token.startswith("--draft=") or token.startswith("-d="):
            enabled = token.split("=", 1)[1].lower() in true_values
    return enabled


def beads_workspace(cwd: Path) -> bool:
    return any((parent / ".beads").is_dir() for parent in (cwd, *cwd.parents))


def trailer_ids(body: str, name: str) -> list[str]:
    prefix = f"{name}:"
    ids: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped.startswith(prefix):
            continue
        value = stripped[len(prefix) :].strip()
        if value and all(
            character.isalnum() or character in "._-" for character in value
        ):
            ids.append(value)
    return ids


def bead_record(cwd: Path, bead_id: str) -> dict[str, Any] | None:
    if not shutil.which("bd"):
        return None
    try:
        result = subprocess.run(
            ["bd", "-C", str(cwd), "show", bead_id, "--json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, list) or not payload or not isinstance(payload[0], dict):
        return None
    return payload[0]


def validate(invocation: list[str], cwd: Path) -> str | None:
    if not draft_enabled(invocation):
        return (
            "Agent-authored PRs must start as drafts. Re-run every gh pr create "
            "invocation with --draft; use gh pr ready only after implementation, "
            "local validation, and required review are complete."
        )
    if not beads_workspace(cwd):
        return None

    body = argument(invocation, "--body", "-b")
    body_file = argument(invocation, "--body-file", "-F")
    if body_file:
        body_path = Path(body_file)
        if not body_path.is_absolute():
            body_path = cwd / body_path
        try:
            body = body_path.read_text(encoding="utf-8")
        except OSError:
            return (
                f"Cannot verify PR body file '{body_file}'. Supply a readable "
                "--body-file containing Tracks-Bead: <id>."
            )
    if not body:
        return (
            "PRs created in a Beads repository must supply --body or --body-file "
            "with Tracks-Bead: <id>; implicit --fill/editor bodies cannot be verified."
        )

    tracks = trailer_ids(body, "Tracks-Bead")
    closes = trailer_ids(body, "Closes-Bead")
    merges = trailer_ids(body, "Merge-Bead")
    if not tracks:
        return "PR body must include at least one exact Tracks-Bead: <id> line."
    if len(merges) != 1:
        return "PR body must include exactly one Merge-Bead: <id> line."
    merge_id = merges[0]
    merge_record = bead_record(cwd, merge_id)
    if merge_record is None:
        return f"Merge-Bead '{merge_id}' is not resolvable from this repository."
    labels = set(merge_record.get("labels", []))
    if merge_record.get("status") != "open" or not {
        "pr:merge",
        "agent:integrator",
    }.issubset(labels):
        return (
            f"Merge-Bead '{merge_id}' must be open and labeled pr:merge "
            "and agent:integrator."
        )
    if merge_record.get("assignee"):
        return f"Merge-Bead '{merge_id}' must be unassigned for PR Shepherd discovery."
    metadata = merge_record.get("metadata")
    required_metadata = {"branch", "repo", "origin_actor"}
    if not isinstance(metadata, dict) or any(
        not metadata.get(name) for name in required_metadata
    ):
        return (
            f"Merge-Bead '{merge_id}' must have branch, repo, and origin_actor "
            "metadata before PR creation."
        )
    for bead_id in tracks:
        if bead_record(cwd, bead_id) is None:
            return f"Tracks-Bead '{bead_id}' is not resolvable from this repository."
    for bead_id in closes:
        if bead_id not in tracks:
            return f"Closes-Bead '{bead_id}' must also appear as Tracks-Bead."
        work_record = bead_record(cwd, bead_id)
        if work_record is None:
            return f"Closes-Bead '{bead_id}' is not resolvable from this repository."
        if work_record.get("status") == "closed":
            return f"Closes-Bead '{bead_id}' is already closed; late closing edges are denied."
        dependencies = work_record.get("dependencies", [])
        edge_exists = any(
            dependency.get("id") == merge_id
            and dependency.get("dependency_type") == "blocks"
            for dependency in dependencies
            if isinstance(dependency, dict)
        )
        if not edge_exists:
            return (
                f"Closes-Bead '{bead_id}' must already depend on Merge-Bead "
                f"'{merge_id}' before PR creation."
            )
    if set(metadata.get("tracks_beads", [])) != set(tracks) or set(
        metadata.get("closes_beads", [])
    ) != set(closes):
        return (
            f"Merge-Bead '{merge_id}' tracked/closing metadata must match the "
            "PR body trailers."
        )
    return None


def main() -> int:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        payload = raw
    command, cwd = payload_command(payload)
    if not command:
        return 0
    likely_pr_create = all(word in command for word in ("gh", "pr", "create"))
    try:
        invocations = invocation_spans(command)
    except ValueError as error:
        if likely_pr_create:
            deny(f"PR creation command could not be safely parsed: {error}.")
        return 0
    for invocation in invocations:
        reason = validate(invocation, cwd)
        if reason:
            deny(reason)
            return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
