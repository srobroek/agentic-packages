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
    "are bound by its contract until you stop. Before stopping you must leave a "
    "REPORTED comment (or, if genuinely stuck, set the bead status=blocked and "
    "leave a FAILED/BLOCKED comment — always a valid exit). Never close, "
    "approve, or merge a node you did not own, and never write merge_sha/pr. "
    "A SubagentStop hook enforces this and will block an incomplete exit."
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
    sys.stdout.write(json.dumps({
        "hookSpecificOutput": {"hookEventName": "SubagentStart", "additionalContext": NOTICE}
    }) + "\n")


if __name__ == "__main__":
    main()
