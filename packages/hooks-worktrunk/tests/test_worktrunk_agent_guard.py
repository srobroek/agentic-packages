from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1]
GUARD_PATH = PACKAGE / "scripts" / "worktrunk-agent-guard.py"


def run_guard(payload: object | str) -> subprocess.CompletedProcess[str]:
    stdin = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run(
        [sys.executable, str(GUARD_PATH)],
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )


def test_worktree_isolation_is_denied_with_the_worktrunk_route() -> None:
    result = run_guard(
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "Agent",
            "tool_input": {"subagent_type": "coder", "isolation": "worktree"},
        }
    )
    assert result.returncode == 0
    decision = json.loads(result.stdout)["hookSpecificOutput"]
    assert decision["hookEventName"] == "PreToolUse"
    assert decision["permissionDecision"] == "deny"
    reason = decision["permissionDecisionReason"]
    assert "WT-1" in reason
    assert "wt switch --create <branch> --base <base> --no-cd --format=json" in reason


@pytest.mark.parametrize(
    "tool_input",
    [
        {"subagent_type": "coder"},
        {"subagent_type": "Explore", "isolation": "readonly"},
        {"subagent_type": "reviewer", "isolation": "remote"},
        {"subagent_type": "coder", "isolation": None},
        {"prompt": "describe isolation: \"worktree\" in the report"},
        # The name-matching regression: only the isolation key decides.
        {"subagent_type": "worktree-specialist"},
        {"subagent_type": "hooks-subagent-worktree-auditor", "description": "worktree audit"},
    ],
)
def test_spawns_without_worktree_isolation_are_allowed(tool_input: dict) -> None:
    result = run_guard(
        {"hook_event_name": "PreToolUse", "tool_name": "Agent", "tool_input": tool_input}
    )
    assert result.returncode == 0
    assert result.stdout == ""


@pytest.mark.parametrize("payload", ["", "not-json", "[]", "{}", '{"tool_input": "worktree"}'])
def test_unusable_payload_fails_open(payload: str) -> None:
    result = run_guard(payload)
    assert result.returncode == 0
    assert result.stdout == ""


def test_guard_carries_no_name_based_classification() -> None:
    """The 1.x deny gate was reverted for classifying spawns by agent name."""
    source = GUARD_PATH.read_text(encoding="utf-8")
    body = source.split('"""', 2)[2]
    assert "subagent_type" not in body
    assert "agent_type" not in body
    assert body.count('"isolation"') == 1
