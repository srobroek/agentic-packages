#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""PreToolUse hook — orchestrator claim prohibition (run-marker gated).

T0 (the orchestrator session) never claims beads; it routes. This hook denies
any `bd ... --claim` issued while an orchestrate run is active. The run marker
(env ORCHESTRATE_RUN or ./.orchestration/.active-run) scopes it so ordinary
interactive sessions are untouched.

Decision: deny with a self-correction message (diagnosis only). Fails open on
malformed input. Invoked directly via `uv run`.
Contract: specs/002-bead-as-brief/contracts/hook-io.md
"""
import json
import os
import re
import sys

DENY_MSG = ("orchestrators route work, they never claim beads; dispatch to a "
            "worker agent instead (T0 authority: create, close, dismiss, "
            "unclaim, deps, gates, shells, BRIEF)")


def emit_allow():
    sys.stdout.write("{}\n")
    sys.exit(0)


def run_active() -> bool:
    if os.environ.get("ORCHESTRATE_RUN"):
        return True
    marker = os.environ.get("ORCHESTRATE_MARKER_FILE", "")
    if marker and os.path.isfile(marker):
        return True
    return os.path.isfile("./.orchestration/.active-run")


def main():
    if not run_active():
        emit_allow()  # not in a run -> never interfere
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        emit_allow()

    ti = payload.get("tool_input") or {}
    cmd = ti.get("command") if isinstance(ti, dict) else None
    cmd = cmd or (ti if isinstance(ti, str) else "") or payload.get("input", {}).get("command", "")
    if not cmd:
        emit_allow()

    first = cmd.strip().split()[0] if cmd.strip() else ""
    if os.path.basename(first) != "bd":
        emit_allow()

    # --claim as a standalone flag anywhere in the command.
    if not re.search(r"(^|\s)--claim(\s|$)", cmd):
        emit_allow()

    sys.stdout.write(json.dumps({"decision": "deny", "reason": DENY_MSG}) + "\n")


if __name__ == "__main__":
    main()
