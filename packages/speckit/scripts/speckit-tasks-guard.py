#!/usr/bin/env python3
"""Cross-tool hook with several roles, branched on `tool_name`.

PreToolUse (Write|Edit|MultiEdit|apply_patch): DENY every write to
specs/*/tasks.md when the repo has an active beads workspace. tasks.md is never
authored under the beads workflow -- task state lives in beads. The deny reason
carries the full replacement workflow so the agent self-corrects without a human
(hook-guard policy: deny is agent-facing, never "ask").

PreToolUse (Bash): ADVISORY ONLY -- a command string referencing a
specs/*/tasks.md path gets a non-blocking additionalContext note (task state
lives in beads). No redirect parsing; plain substring match.

PreToolUse (Skill): ADVISORY ONLY -- invoking speckit-implement gets a
non-blocking note that /speckit.implement is deprecated in beads repos; route
through the agent-assign chain instead.

DELIBERATE DESIGN CHOICE, do not change: a bare-string `tool_input` has no path
to judge, so it ALLOWS rather than denying -- the deny needs a specific named
path. This is documented and pinned by
packages/speckit/tests/test_speckit_tasks_guard.py ("string-form tool_input allows").

Self-gating (never rely on the matcher): exits 0 silently when the payload is
empty, `bd` is missing, the target path is not specs/*/tasks.md, or the repo has
no active beads workspace (`bd where` fails).
"""

from __future__ import annotations

import sys

# Only `sys` at module scope. This hook is bound to Write/Edit/MultiEdit/Bash/
# Skill/apply_patch and runs on most tool calls in a SpecKit beads repo, so the
# cheap substring bail in main() must precede any import.


DENY_REASON = (
    "blocked by speckit (task state lives in beads, tasks.md is never "
    "authored): this repo has an active beads workspace, so specs/*/tasks.md is "
    "read-only legacy and must not be written or created. Create implementation "
    "tasks as beads under the feature molecule's implement step instead: bd "
    'create "T00N <title>" --parent <implement-step-id> --spec-id <NNN-slug> -t '
    "task; wire ordering with bd dep add <later-id> <earlier-id>; bulk-create "
    "with bd create -f <tmpfile>.md (write the temp file OUTSIDE specs/). Then "
    "work the tasks via bd ready -> bd update <id> --claim -> bd close <id> "
    '--reason "...". Find the implement step with bd mol current '
    "<molecule-root-id>."
)

BASH_ADVICE = (
    "SPECKIT: tasks.md is not authored in beads repos; task state lives "
    "in beads: bd ready / bd update <id> --claim / bd close <id> --reason. If "
    "reading legacy tasks.md for migration, that's fine."
)

IMPLEMENT_ADVICE = (
    "SPECKIT: /speckit.implement is deprecated in beads repos; route "
    "through the agent-assign chain instead (/speckit.agent-assign.assign -> "
    "validate -> execute), working the molecule steps via bd mol current / bd "
    "ready / bd update --claim / bd close."
)


def is_tasks_md(path: str) -> bool:
    """Whether `path` is a SpecKit tasks file: specs/<feature>/tasks.md at any
    depth, relative or absolute."""
    import fnmatch

    return fnmatch.fnmatchcase(path, "specs/*/tasks.md") or fnmatch.fnmatchcase(
        path, "*/specs/*/tasks.md"
    )


def beads_active(cwd: str) -> bool:
    """Whether bd resolves an active workspace for this directory."""
    import shutil
    import subprocess

    if shutil.which("bd") is None:
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


def extract(payload: str) -> dict:
    """Parse the payload; tool_input may be an object or a bare string.

    A bare-string tool_input is the historical bypass shape: `.tool_input.command
    // .tool_input` throws on a string in jq. Here it simply yields no file_path,
    skill, or command -- which, per the documented design choice, means allow.
    """
    import json

    data = json.loads(payload)
    if not isinstance(data, dict):
        return {}
    tool_input = data.get("tool_input")
    file_path = ""
    skill_name = ""
    command = ""
    if isinstance(tool_input, dict):
        raw_path = tool_input.get("file_path") or tool_input.get("path")
        file_path = raw_path if isinstance(raw_path, str) else ""
        raw_skill = tool_input.get("skill")
        skill_name = raw_skill if isinstance(raw_skill, str) else ""
        raw_cmd = tool_input.get("command")
        command = raw_cmd if isinstance(raw_cmd, str) else ""

    event = data.get("hook_event_name")
    tool_name = data.get("tool_name") or data.get("tool")
    cwd = data.get("cwd")
    return {
        "event": event if isinstance(event, str) else "",
        "tool_name": tool_name if isinstance(tool_name, str) else "",
        "file_path": file_path,
        "skill_name": skill_name,
        "cwd": cwd if isinstance(cwd, str) else "",
        "command": command,
    }


def patch_paths(patch: str) -> list[str]:
    """Every file header in a Codex apply_patch body: `*** Update/Add/Delete
    File: <path>`."""
    import re

    return re.findall(r"^\*\*\* (?:Update|Add|Delete) File: (.*)$", patch, re.MULTILINE)


def deny() -> None:
    import json

    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": DENY_REASON,
            }
        },
        sys.stdout,
    )


def advise(event: str, context: str) -> None:
    import json

    json.dump(
        {"hookSpecificOutput": {"hookEventName": event, "additionalContext": context}},
        sys.stdout,
    )


def main() -> int:
    payload = sys.stdin.read()
    if not payload:
        return 0
    # Cheap pre-parse bail: every branch below acts on a tasks.md target or a
    # speckit-implement skill invocation; anything else needs no inspection.
    if "tasks.md" not in payload and "speckit.implement" not in payload and "speckit-implement" not in payload:
        return 0

    import shutil

    if shutil.which("bd") is None:
        return 0

    try:
        data = extract(payload)
    except (ValueError, TypeError):
        return 0

    tool_name = data["tool_name"]
    if not tool_name:
        # Bare-string tool_input (legacy shape), or no tool_name at all: allow.
        return 0

    if data["event"] != "PreToolUse":
        return 0

    import os

    cwd = data["cwd"]
    if not cwd or not os.path.isdir(cwd):
        cwd = os.getcwd()

    if tool_name in ("Write", "Edit", "MultiEdit"):
        if not is_tasks_md(data["file_path"]):
            return 0
        if not beads_active(cwd):
            return 0
        deny()
        return 0

    if tool_name in ("apply_patch", "functions.apply_patch"):
        for path in patch_paths(data["command"]):
            if is_tasks_md(path):
                if not beads_active(cwd):
                    return 0
                deny()
                return 0
        return 0

    if tool_name == "Bash":
        # Advisory only (user decision): a Bash command touching a
        # specs/*/tasks.md path may be legitimate (migration reads, greps), so
        # never deny -- just remind where task state lives. Plain substring
        # match on the path pattern; no redirect parsing.
        import re

        # Mirrors the shell glob `*specs/*/tasks.md*`: "specs/" must precede
        # "/tasks.md" in the string, not merely both appear anywhere.
        if re.search(r"specs/.*/tasks\.md", data["command"], re.DOTALL):
            if not beads_active(cwd):
                return 0
            advise("PreToolUse", BASH_ADVICE)
        return 0

    if tool_name == "Skill":
        haystack = f"{data['skill_name']} {data['command']}"
        if "speckit-implement" in haystack or "speckit.implement" in haystack:
            if not beads_active(cwd):
                return 0
            advise("PreToolUse", IMPLEMENT_ADVICE)
        return 0

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:
        # Fail open: an unreadable payload or an unexpected exception allows
        # rather than blocking.
        raise SystemExit(0)
