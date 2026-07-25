#!/usr/bin/env python3
"""Deny harness-native worktree isolation on agent spawns.

Gates on `tool_input.isolation == "worktree"` alone. Never on the agent's name or
`subagent_type`: those are free-form strings a hook cannot resolve to read-or-write,
and classifying by them is the defect that got the 1.x deny gate reverted.
"""

from __future__ import annotations

import json
import sys

REASON = (
    "Blocked by WT-1: harness `isolation:\"worktree\"` creates a native git worktree "
    "outside the Worktrunk lifecycle, so this spawn has no durable pre-spawn anchor. "
    "Prepare the checkout in the parent with "
    "`wt switch --create <branch> --base <base> --no-cd --format=json`, record the "
    "returned branch and path in durable task state, and pass them to the child. "
    "Inside Claude Code, `/wt-switch-create` does the same. Spawn without an "
    "`isolation` key to share the current checkout."
)


def denies(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return False
    return tool_input.get("isolation") == "worktree"


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return 0
    if not denies(payload):
        return 0
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": REASON,
                }
            },
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
