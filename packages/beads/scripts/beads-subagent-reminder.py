#!/usr/bin/env python3
"""Hook: SubagentStart -- slim beads contract reminder for subagents.

SessionStart (bd prime) does not fire for subagents, so without this a
spawned worker has only compiled steering. Inject the minimal contract:
where its work queues are, claim-before-work, and the close protocol.
Deliberately NOT bd prime (~1-2k tokens); this stays a few lines.

Self-gating: silent unless bd is installed AND the spawn cwd has a beads
workspace. Never blocks a spawn; any failure exits 0 with no output.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

CONTEXT = (
    "This repo tracks work in beads (bd)."
    " If the parent gave you a bead id, claim it before working: bd update <id> --claim."
    " Otherwise your queues are: bd ready --assignee <you> --json (pinned first), then bd ready --label agent:<kind> --unassigned --json."
    " Never work an issue assigned to another actor.\n"
    'Before finishing: comment residual context on your bead (bd comments add <id> "approach, tricky spots, what to check first on failure"), '
    'close it (bd close <id> --reason "..."), and file discovered follow-ups (bd create --deps discovered-from:<id>). '
    "Do not wait for CI or merges -- gates and the pr-shepherd own that."
)


def main() -> int:
    raw = sys.stdin.read()
    if not raw:
        return 0

    try:
        payload = json.loads(raw)
    except ValueError:
        return 0
    if not isinstance(payload, dict):
        return 0

    agent_id = payload.get("agent_id")
    if not agent_id:
        return 0  # Not a subagent

    if shutil.which("bd") is None:
        return 0

    cwd = payload.get("cwd") or ""
    if not cwd or not os.path.isdir(cwd):
        cwd = os.getcwd()

    # Only in repos with an active beads workspace.
    where = subprocess.run(
        ["bd", "-C", cwd, "where"],
        capture_output=True,
        timeout=5,
        check=False,
    )
    if where.returncode != 0:
        return 0

    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "SubagentStart",
                "additionalContext": CONTEXT,
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
        # Fail open: a bead-contract reminder must never wedge a spawn.
        raise SystemExit(0)
