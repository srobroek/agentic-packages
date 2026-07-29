#!/usr/bin/env python3
"""Append one line per tool failure to ~/.claude/debug (PostToolUseFailure, async).

Ported from shell, where three `jq` spawns read three fields and `stat -c`/`stat -f`
were tried in sequence to size the log for rotation. `Path.stat()` is one call and
needs no per-platform fallback.

Fail open (exit 0) on everything: this is diagnostics, so a failure to log must not
surface as a second failure.
"""

from __future__ import annotations

import sys

# Truncate the error text: a stack trace or a wall of compiler output would make
# the log unreadable and is not what this record is for.
ERROR_LIMIT = 200

# Rotate at 1 MiB, keeping exactly one previous generation.
ROTATE_BYTES = 1048576


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

    error = data.get("error") or data.get("tool_error") or "unknown error"
    if not isinstance(error, str):
        error = str(error)

    # Newlines would break the one-record-per-line format the log promises.
    error = " ".join(error.split())[:ERROR_LIMIT]

    fields = [
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        str(data.get("tool_name") or "unknown"),
        str(data.get("cwd") or "unknown"),
        error,
    ]

    directory = Path.home() / ".claude" / "debug"
    log = directory / "tool-failures.log"
    try:
        directory.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as handle:
            handle.write(" | ".join(fields) + "\n")
        # Rotate after writing, so the current record is never the one lost.
        if log.stat().st_size > ROTATE_BYTES:
            log.replace(log.with_suffix(log.suffix + ".old"))
    except OSError:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
