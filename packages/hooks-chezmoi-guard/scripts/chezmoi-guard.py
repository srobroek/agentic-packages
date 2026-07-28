#!/usr/bin/env python3
"""Warn when a write targets a file chezmoi actually manages.

A chezmoi-managed target is a real file, not a symlink to its source, so a direct
edit succeeds, looks correct, and is then silently reverted by the next
`chezmoi apply`. Nothing errors and no diff appears, which is why this is worth a
hook rather than steering alone: the skill only fires when the model recognises a
task as a chezmoi task, and editing `~/.claude/settings.json` to add a permission
does not announce itself as one.

Advisory only. The operation proceeds, chezmoi remains the source of truth, and
recovery is `chezmoi edit` on the source.

Scoped to write TOOLS -- apply_patch, Edit, Write, MultiEdit -- rather than also
every Bash call. A redirect-based write (`echo x > ~/.claude/settings.json`) is
therefore not covered, which is the deliberate trade for keeping this off the
per-shell-command path.

Membership is exact against `chezmoi managed`, never a parent-directory walk.
`chezmoi managed` lists managed targets, so walking parents flagged every file
under a managed directory -- including the plain committed files in an
external-managed tree, which you edit at source.
"""

from __future__ import annotations

import sys

# Only `sys` at module scope. This runs on every write the agent makes, and the
# common case is an unmanaged path, so the imports live in the functions that need
# them: `re` costs about 9ms and `pathlib` another 4.5ms on this host.

CACHE_TTL_SECONDS = 60

# `*** Update File: <path>` headers in a Codex patch. Feeding a whole patch to a
# path check silently misses every target, so the headers are parsed directly.
PATCH_HEADER = r"^\*\*\* (?:Update|Add|Delete) File: (.*)$"

ADVICE = (
    "heads-up: '{path}' is chezmoi-managed, so this edit will be overwritten by "
    "the next 'chezmoi apply' and the change will be silently lost. Edit the "
    "source instead: chezmoi edit '{path}' (source: chezmoi source-path "
    "'{path}'). Proceeding."
)


def emit(path: str) -> None:
    """Print one non-blocking advisory."""
    import json

    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "additionalContext": ADVICE.format(path=path),
            }
        },
        sys.stdout,
    )


def normalize(target: str) -> str:
    """Resolve to an absolute path and collapse `.` and `..` lexically.

    Lexical on purpose: the target may not exist yet, and resolving symlinks could
    land somewhere the path does not point. Collapsing matters because the managed
    list holds canonical paths, so `~/.claude/../.claude/settings.json` must not
    dodge an exact comparison.
    """
    import os

    expanded = os.path.expanduser(target)
    if not os.path.isabs(expanded):
        expanded = os.path.join(os.getcwd(), expanded)

    parts: list[str] = []
    for segment in expanded.split("/"):
        if segment in ("", "."):
            continue
        if segment == "..":
            if parts:
                parts.pop()
            continue
        parts.append(segment)
    return "/" + "/".join(parts) if parts else "/"


def managed_paths() -> frozenset[str]:
    """The set of paths chezmoi manages, cached briefly on disk.

    `chezmoi managed` costs about 220ms, far too much per tool call, so the list is
    cached for a minute. The cache is per-user rather than a predictable shared
    name, so one user on a host cannot pre-create or poison another's.
    """
    import os
    import subprocess
    import tempfile

    cache = os.path.join(tempfile.gettempdir(), f"chezmoi-managed-cache.{os.getuid()}")
    try:
        if os.path.getmtime(cache) + CACHE_TTL_SECONDS > _now():
            with open(cache, encoding="utf-8", errors="surrogateescape") as handle:
                return frozenset(line.rstrip("\n") for line in handle if line.strip())
    except OSError:
        pass

    try:
        completed = subprocess.run(
            ["chezmoi", "managed", "--path-style=absolute", "--include=files,symlinks"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (subprocess.SubprocessError, OSError):
        return frozenset()
    if completed.returncode != 0:
        return frozenset()

    entries = frozenset(
        line.rstrip("\n") for line in completed.stdout.splitlines() if line.strip()
    )
    # Written to a temporary name and renamed, so a concurrent hook never reads a
    # half-written list. Matching hooks launch concurrently by design.
    try:
        handle, temporary = tempfile.mkstemp(dir=os.path.dirname(cache))
        with os.fdopen(handle, "w", encoding="utf-8", errors="surrogateescape") as stream:
            stream.write("\n".join(sorted(entries)))
        os.replace(temporary, cache)
    except OSError:
        pass
    return entries


def _now() -> float:
    import time

    return time.time()


def candidate_paths(payload: dict) -> list[str]:
    """Every path this tool call would write."""
    import re

    tool_input = payload.get("tool_input")
    tool_name = payload.get("tool_name") or payload.get("tool") or ""

    # A bare-string tool_input is ambiguous: some callers send a path, some a
    # command. It is checked as both, since neither check does anything unless the
    # value is an exact managed path.
    if isinstance(tool_input, str):
        text, path = tool_input, tool_input
    elif isinstance(tool_input, dict):
        text = tool_input.get("command") or ""
        path = tool_input.get("file_path") or tool_input.get("path") or ""
        if not isinstance(text, str):
            text = ""
        if not isinstance(path, str):
            path = ""
    else:
        return []

    if tool_name in ("apply_patch", "functions.apply_patch") and text:
        return re.findall(PATCH_HEADER, text, re.MULTILINE)
    return [path] if path else []


def main() -> int:
    raw = sys.stdin.read()
    if not raw.strip():
        return 0
    # Bail before parsing on the raw bytes. Every advisory this guard emits names a
    # path under a dot-directory chezmoi manages, and a payload mentioning none
    # cannot produce one. A strict superset of the real trigger.
    if "." not in raw:
        return 0

    import json

    try:
        payload = json.loads(raw)
    except (ValueError, TypeError):
        return 0
    if not isinstance(payload, dict):
        return 0

    paths = candidate_paths(payload)
    if not paths:
        return 0

    import shutil

    # Undecidable without chezmoi, so the guard says nothing rather than guessing.
    if shutil.which("chezmoi") is None:
        return 0

    managed = managed_paths()
    if not managed:
        return 0

    for path in paths:
        if normalize(path) in managed:
            emit(path)
            return 0
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:
        # Fail open: an advisory must never wedge a write.
        raise SystemExit(0)
