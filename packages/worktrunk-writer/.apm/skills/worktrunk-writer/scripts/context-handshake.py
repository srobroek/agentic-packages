#!/usr/bin/env python3
"""Expose the hook-visible subagent identity before a Worktrunk lease is bound.

SubagentStart carries no allocation prompt, so this cannot tell a wait-only
allocation from ordinary delegation by reading the task. It gates instead on the
one thing it can observe -- whether the writer protocol is in play at all: an
explicit operator opt-in, or a writer lease already present in the repository.
With neither, a spawn is ordinary delegation and gets no WAIT demand, so a
repository that holds no lease never puts an unrelated child under the handshake.

The orchestration run marker alone is deliberately not a trigger. The sibling
PreToolUse guard learned (worktrunk-writer.py protocol_engaged) that the marker
by itself turned advise-not-deny into a deny for every spawn from the primary
checkout during a run, including read-only work aimed at another repository. A
run that prepared a writer checkout leaves a lease this gate finds; a run that
prepared none has nothing to hand a WAIT context to.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

WRITER = Path(__file__).with_name("worktrunk-writer.py")


def _writer():
    spec = importlib.util.spec_from_file_location("worktrunk_writer", WRITER)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load worktrunk-writer.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def protocol_engaged(payload: dict) -> bool:
    """Whether a Worktrunk writer lease is in play for this spawn.

    Fails toward NOT injecting: a missing `wt`, an unreadable inventory, or a
    non-repository cwd all read as "no protocol", because a WAIT demand the hook
    cannot back with a real lease is exactly the stall this gate removes.
    """
    if os.environ.get("WORKTRUNK_WRITER_ENFORCE") or os.environ.get("WORKTRUNK_WRITER_LEASE"):
        return True
    if shutil.which("wt") is None:
        return False
    cwd = Path(payload.get("cwd") or os.getcwd()).resolve()
    try:
        writer = _writer()
        inventory = writer.wt_inventory(cwd)
        return writer.repo_has_leases(inventory)
    except Exception:
        return False


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
    if not protocol_engaged(payload):
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
