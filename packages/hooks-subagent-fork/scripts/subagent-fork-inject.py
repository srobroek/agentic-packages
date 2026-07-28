#!/usr/bin/env python3
"""SubagentStart -- inject the fork_turns discipline so any agent that itself
spawns sub-subagents (orchestrators, pull-workers) carries the rule.

Static content; gates only on being an actual subagent (agent_id present).
Fail-open: empty stdin or malformed JSON exits 0 with no output.
"""

from __future__ import annotations

import sys


def main() -> int:
    raw = sys.stdin.read()
    if not raw.strip():
        return 0

    import json
    import os

    try:
        payload = json.loads(raw)
    except ValueError:
        return 0
    if not isinstance(payload, dict):
        return 0

    if not payload.get("agent_id"):
        return 0  # Not a subagent

    raw_max = os.environ.get("SUBAGENT_FORK_GUARD_MAX", "3")
    fork_max = raw_max if raw_max.isdigit() else "3"

    context = (
        "SUBAGENT SPAWN DISCIPLINE -- applies when this task spawns further "
        "subagents:\n"
        '- Always execute with fork_turns="none" unless recent thread context is '
        "explicitly required.\n"
        '- Format the tool call: spawn_agent(task_name="code-reviewer", '
        'fork_turns="none")\n'
        "- Put everything the subagent needs into the spawn prompt; forked turns "
        'are not a substitute for a complete brief. fork_turns="all", omitted '
        f"fork_turns, and values above {fork_max} are denied by policy.\n"
    )

    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "SubagentStart",
                "additionalContext": context,
            }
        },
        sys.stdout,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:
        # Fail open: an injection failure must never block a spawn.
        raise SystemExit(0)
