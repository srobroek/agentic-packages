#!/usr/bin/env python3
"""Append one JSONL record per finished subagent (SubagentStop, async).

Ported from shell, where two `jq` spawns read two fields and the record was
assembled by string interpolation -- so an agent_type containing a quote emitted a
line that no JSONL reader could parse. `json.dump` escapes it.

Fail open (exit 0) on everything: metrics are diagnostics, and a hook that cannot
write them must not disturb the session.
"""

from __future__ import annotations

import sys


def repo_root() -> str:
    """Return the repository root, or empty when not in a work tree."""
    import subprocess

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def main() -> int:
    payload = sys.stdin.read()
    if not payload:
        return 0

    import json

    try:
        data = json.loads(payload)
    except (ValueError, TypeError):
        return 0
    if not isinstance(data, dict):
        return 0

    from datetime import datetime, timezone
    from pathlib import Path

    root = repo_root()
    directory = Path(root if root else ".") / ".claude" / "metrics"

    record = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "agent_type": data.get("agent_type") or "unknown",
        "agent_id": data.get("agent_id") or "unknown",
    }

    try:
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / "agents.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")
    except OSError:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
