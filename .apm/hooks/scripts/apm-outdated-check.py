#!/usr/bin/env python3
"""Tell the agent when APM dependencies are stale (SessionStart, asyncRewake).

Throttled to once per four hours per repository, because `apm outdated` reaches the
network and session starts are frequent.

Ported from shell, where freshness came from `stat -c %Y || stat -f %m || echo 0`
-- a per-platform fallback chain whose own comment records that getting the order
wrong made `stat -f` print a filesystem dump on Linux and feed garbage into the
arithmetic. `Path.stat().st_mtime` is one portable call. The state filename also
came from `md5 || md5sum | cut`, which produced a DIFFERENT filename on macOS than
on Linux for the same repository; `hashlib` is stable across both.

Exit 2 is deliberate and is the contract for asyncRewake: it delivers stderr to the
agent as a system reminder. Every other path exits 0.
"""

from __future__ import annotations

import subprocess
import sys

# Four hours. Frequent enough to notice a stale pin within a working day, rare
# enough that a burst of session starts does not hammer the network.
INTERVAL_SECONDS = 14400

# Words in `apm outdated` output that mean action is needed.
STALE_MARKERS = ("outdated", "stale", "behind")

# Cap the excerpt: the reminder is a nudge, not a report.
EXCERPT_LINES = 10


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

    # One check per session, from the parent only.
    if data.get("agent_id"):
        return 0

    import hashlib
    import shutil
    import time
    from pathlib import Path

    try:
        located = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return 0
    if located.returncode != 0:
        return 0
    root = located.stdout.strip()
    if not root or not (Path(root) / "apm.yml").is_file():
        return 0

    if shutil.which("apm") is None:
        return 0

    digest = hashlib.md5(root.encode("utf-8"), usedforsecurity=False).hexdigest()
    state = Path.home() / ".local" / "state" / "apm"
    stamp = state / f"last-outdated-{digest}"

    try:
        if stamp.is_file() and (time.time() - stamp.stat().st_mtime) < INTERVAL_SECONDS:
            return 0
    except OSError:
        pass

    try:
        result = subprocess.run(
            ["apm", "outdated"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError):
        return 0

    # Stamp regardless of the verdict, so a failing or slow `apm outdated` is not
    # retried on every session start.
    try:
        state.mkdir(parents=True, exist_ok=True)
        stamp.touch()
    except OSError:
        pass

    output = result.stdout
    lowered = output.lower()
    if not any(marker in lowered for marker in STALE_MARKERS):
        return 0

    print(
        "APM dependencies are outdated. Run `apm deps update` to get latest packages.",
        file=sys.stderr,
    )
    for line in output.splitlines()[:EXCERPT_LINES]:
        print(line, file=sys.stderr)
    # asyncRewake contract: exit 2 delivers stderr to the agent.
    return 2


if __name__ == "__main__":
    sys.exit(main())
