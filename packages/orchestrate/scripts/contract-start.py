#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""SubagentStart hook — universal claim-contract injector (matcher-less).

Injects one short paragraph into every spawned subagent: claiming a bead binds
the generic bead contract. This closes the claim<->contract net for agents that
have no per-agent rules file (built-ins, ad-hoc general-purpose spawns) — they
still learn the rule the SubagentStop net will enforce.

Contract: emits {"hookSpecificOutput": {"additionalContext": "..."}} or {} .
Never blocks. Fails open. Invoked directly via `uv run` (no bash shim).
"""

import json
import sys

NOTICE = (
    "Bead contract (bead-as-brief): if you CLAIM a bead in this workspace, you "
    "are bound by its contract until you stop. Follow the role-specific contract "
    "in your agent definition; when none exists, the generic exit requires a "
    "REPORTED comment. A genuine failure may set status=blocked and leave a "
    "FAILED/BLOCKED comment. Never close, approve, or merge a resource outside "
    "your role authority. A new claim-holder runtime starts with WAIT only; a "
    "later exact CLAIM message releases it after binding. A SubagentStop hook "
    "enforces the active contract."
)


def main():
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        sys.stdout.write("{}\n")
        return
    # Only bother injecting for real subagents (have an agent_id/agent_type).
    if not (payload.get("agent_id") or payload.get("agent_type")):
        sys.stdout.write("{}\n")
        return
    sys.stdout.write(
        json.dumps(
            {"hookSpecificOutput": {"hookEventName": "SubagentStart", "additionalContext": NOTICE}}
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
