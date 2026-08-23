#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Deny Agent dispatch until the active-run marker is bound to a real run epic."""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from orchestrate_run_marker import (  # noqa: E402
    active_run_id,
    emit_allow,
    emit_deny,
    marker_present,
)


def require_bound_run() -> None:
    if active_run_id() == "pending":
        emit_deny(
            "Agent dispatch is blocked until the active-run marker is "
            "bound to the created run epic"
        )


def main() -> None:
    if not marker_present():
        emit_allow()
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        emit_allow()

    tool_name = str(payload.get("tool_name") or payload.get("tool") or "")
    if tool_name == "Agent":
        require_bound_run()
    emit_allow()


if __name__ == "__main__":
    main()
