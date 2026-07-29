#!/usr/bin/env python3
"""Nudge the agent to investigate a dependency before adding it.

`PreToolUse` on `Bash`. When the agent is about to ADD/INSTALL a dependency,
this advises (non-blocking, additionalContext) a supply-chain screen --
typosquat/abandonment/deprecation -- checked against current facts via
registry/web/context7 rather than training memory, which can predate a
compromise. Maintenance-quality and alternatives judgement is already
always-loaded steering (steering-pragmatic's code-economy table); this hook
adds only what a frontier model's training data cannot supply. For
update/upgrade/remove, a lighter nudge (review the change; no discovery).

WHY a command hook (not a prompt/agent hook): agent/prompt hooks BLOCK the turn
and cannot run async (only `command` hooks support async). A command hook is
near-instant and lets the MAIN agent -- which has web/context7/full context --
do the actual investigation, instead of a blind 50-turn subagent.

Only `sys` is imported at module scope: this hook runs on every Bash command,
and the dominant case (no package manager token present) never needs `re` or
`json`. Both are imported inside the functions that use them, per the
contract's hot-path rule and the ~9ms/~4.5ms cost pr-close-guard.py measured
for `re`/`pathlib` at module scope.
"""

from __future__ import annotations

import sys

# Cheap pre-parse bail: this guard only acts on package-manager commands, so a
# payload containing none of these tokens has nothing to inspect. Every manager
# name is listed verbatim, deliberately overlapping (npm/pnpm), so the superset
# stays auditable -- it must remain a strict superset of the structured match
# below, since a payload lacking every token here cannot contain a real trigger.
MANAGER_TOKENS = (
    "pnpm", "npm", "yarn", "bun", "uv", "pip", "poetry",
    "cargo", "go", "gem", "bundle", "composer",
)

# Command-position boundary: start of string, or after a real shell separator
# (; & | newline, incl. && / ||) plus optional spaces. Deliberately NOT plain
# whitespace -- that misfires on `echo 'run pnpm add later'`, where the package
# command sits inside a quoted argument rather than at a command position.
_BOUNDARY = r"(^|[;&|]&?&?\s*|\s*[;&|]+\s*)"

ADD_SUFFIX = (
    r"(pnpm\s+(add|install)|npm\s+(install|i|add)|yarn\s+add|bun\s+add|"
    r"uv\s+(add|pip\s+install)|pip3?\s+install|poetry\s+add|cargo\s+add|"
    r"go\s+get|go\s+install|gem\s+install|bundle\s+add|composer\s+require)"
    r"(\s|$)"
)

CHANGE_SUFFIX = (
    r"(pnpm\s+(update|up|remove)|npm\s+(update|upgrade|uninstall|remove|rm)|"
    r"yarn\s+(up|upgrade|remove)|bun\s+(update|remove)|uv\s+(remove|lock|sync)|"
    r"pip3?\s+uninstall|poetry\s+(update|remove)|cargo\s+(update|upgrade|remove)|"
    r"go\s+mod\s+tidy|bundle\s+(update|remove)|composer\s+(update|remove))"
    r"(\s|$)"
)

ADD_ADVICE = (
    "Before adding this dependency, screen it: reputable author/org, no "
    "typosquat, not abandoned/deprecated. Use the package registry / web / "
    "context7 to check current facts -- training data can predate a compromise "
    "or deprecation. If it's clearly fine, say so in one line and proceed; if "
    "there's a concern, raise it before installing."
)

CHANGE_ADVICE = (
    "Dependency change (update/upgrade/remove): confirm it's intended and check "
    "for breaking changes / changelog notes for the new version, and that "
    "nothing still depends on anything being removed. Prefer the latest "
    "compatible version. No need to re-vet a package already in use unless the "
    "major version changes."
)


def extract_command(payload: str) -> str:
    """Pull the command from a hook payload; empty string on any shape miss."""
    import json

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


def emit(context: str) -> None:
    import json

    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "additionalContext": context,
            }
        },
        sys.stdout,
    )


def main() -> int:
    payload = sys.stdin.read()
    if not payload:
        return 0

    if not any(token in payload for token in MANAGER_TOKENS):
        return 0

    try:
        command = extract_command(payload)
    except (ValueError, TypeError):
        return 0
    if not command:
        return 0

    import re

    lc = command.lower()

    if re.search(_BOUNDARY + ADD_SUFFIX, lc):
        emit(ADD_ADVICE)
        return 0

    if re.search(_BOUNDARY + CHANGE_SUFFIX, lc):
        emit(CHANGE_ADVICE)
        return 0

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:
        # Fail open: a supply-chain nudge must never wedge a package command.
        raise SystemExit(0)
