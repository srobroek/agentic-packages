#!/usr/bin/env python3
"""Hook: SubagentStart -- inject project context + MCP guidance into subagents.

Fires for all subagent types. Injects additionalContext into the agent's
system prompt.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def find_repo_root(start: Path) -> Path | None:
    """Walk parents for a `.git` entry, exact and far cheaper than spawning
    `git rev-parse --show-toplevel`. `.git` is a file in linked worktrees, so
    check existence rather than requiring a directory.
    """
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def main() -> int:
    payload = json.loads(sys.stdin.read())
    if not isinstance(payload, dict):
        return 0

    agent_id = payload.get("agent_id")
    if not agent_id:
        return 0  # Not a subagent

    agent_type = payload.get("agent_type") or ""
    cwd = payload.get("cwd") or "."

    repo_root = find_repo_root(Path(cwd))
    if repo_root is None:
        return 0

    # One git call to resolve the branch; the root itself came from the
    # in-process parent walk above rather than a `rev-parse` spawn.
    branch_result = subprocess.run(
        ["git", "-C", str(repo_root), "branch", "--show-current"],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    branch = branch_result.stdout.strip()
    project = repo_root.name

    # Base context for ALL subagents: project identity + code-discovery routing.
    # Working-style discipline (code economy, comments, report format) lives in
    # the steering-pragmatic package's SubagentStart hook, not here -- this
    # package owns only the code-intelligence routing concern.
    ctx = f"Project: {project}. Branch: {branch}. "
    ctx += (
        "For code discovery use Serena for semantic symbols, references, and "
        "edits; use rg for exact text and paths; use context7 for library "
        "documentation. Fall back to direct file inspection when semantic "
        "tools cannot answer.\n"
    )

    if agent_type == "adversarial-challenger":
        ctx += (
            "IMPORTANT: You are investigating independently. "
            "Do NOT read spec files, conversation history, or CLAUDE.md reasoning sections. "
            "Work ONLY from the Problem Brief provided in your prompt. "
            "You may read source code, run tests, and grep -- but form your own hypotheses. "
        )

    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "SubagentStart",
                "additionalContext": ctx,
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
        # Fail open: context injection must never block a spawn.
        raise SystemExit(0)
