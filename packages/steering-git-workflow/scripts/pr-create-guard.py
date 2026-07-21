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
WRAPPERS = {"command", "env", "nohup", "time"}
COMMAND_KEYWORDS = {"if", "then", "elif", "else", "while", "until", "do", "!", "{"}


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
        if "=" in token and not token.startswith("="):
            index += 1
            continue

        basename = os.path.basename(token)
        if basename in WRAPPERS:
            index += 1
            continue
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
        if basename == "gh" and tokens[index + 1 : index + 3] == ["pr", "create"]:
            end = index + 3
            while end < len(tokens) and tokens[end] not in CONTROL:
                end += 1
            found.append(tokens[index:end])
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
    if "--draft" not in invocation[3:]:
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
    if merge_record.get("status") == "closed" or "pr:merge" not in merge_record.get(
        "labels", []
    ):
        return f"Merge-Bead '{merge_id}' must be open and labeled pr:merge."
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
