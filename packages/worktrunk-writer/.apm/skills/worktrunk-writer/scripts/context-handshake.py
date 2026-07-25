#!/usr/bin/env python3
"""Expose the hook-visible subagent identity before a Worktrunk lease is bound."""

from __future__ import annotations

import json
import sys


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return 0
    context = next(
        (
            value
            for key in ("agent_id", "subagent_id")
            if isinstance((value := payload.get(key)), str) and value
        ),
        "",
    )
    if not context:
        return 0
    notice = (
        "When your allocation prompt begins with WAIT, reply without invoking any "
        "tool. Your entire first response must be exactly:\n"
        f"WAIT context={context}\n"
        "This exact response becomes a completion notification to the controlling "
        "parent. The parent must bind this hook context, not the spawn handle, then "
        "resume you. "
        "Ignore this instruction when the allocation prompt does not begin with WAIT."
    )
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "SubagentStart",
                    "additionalContext": notice,
                }
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
