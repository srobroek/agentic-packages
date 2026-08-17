"""Coverage for subagent-worktree-guard.py -- the PreToolUse:Agent isolation
advisory.

Ported from tests/subagent-worktree-guard.bats (bats suite deleted per
contract rule 4: parity proven against it before porting).

The hook reads a JSON event on stdin and, for tool_name == "Agent", emits a
non-blocking advisory. It NEVER denies. Contract:
  * isolation key present  -> silent about isolation (parent already chose);
                               a stale-worktree notice may still be emitted
  * otherwise (Agent)      -> emit additionalContext advisory, exit 0
  * non-Agent / empty      -> pass through, no output, exit 0
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

GUARD = Path(__file__).resolve().parent.parent / "scripts" / "subagent-worktree-guard.py"
CODEX_HOOK = (
    Path(__file__).resolve().parent.parent
    / ".apm"
    / "hooks"
    / "hooks-subagent-worktree-codex-hooks.json"
)


def run_guard(payload: str) -> tuple[int, str]:
    result = subprocess.run(
        [sys.executable, str(GUARD)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.returncode, result.stdout


def ctx_of(payload: str) -> str:
    _, output = run_guard(payload)
    if not output.strip():
        return ""
    return json.loads(output)["hookSpecificOutput"].get("additionalContext", "")


def test_codex_hook_primitive_is_an_explicit_noop():
    assert json.loads(CODEX_HOOK.read_text()) == {"hooks": {}}


# --- pass-through (no output) --------------------------------------------------


def test_non_agent_tool_passes_through_silently():
    status, output = run_guard('{"tool_name":"Bash","tool_input":{"command":"ls"}}')
    assert status == 0
    assert output == ""


def test_empty_payload_passes_through_silently():
    status, output = run_guard("")
    assert status == 0
    assert output == ""


# --- never denies ----------------------------------------------------------------


def test_never_emits_a_deny_decision():
    _, output = run_guard('{"tool_name":"Agent","tool_input":{"description":"do work","prompt":"x"}}')
    decision = json.loads(output)["hookSpecificOutput"].get("permissionDecision", "none")
    assert decision == "none"


def test_agent_with_string_tool_input_does_not_crash():
    status, _ = run_guard('{"tool_name":"Agent","tool_input":"oops"}')
    assert status == 0


# --- isolation already chosen -> silent -------------------------------------------


def test_agent_with_isolation_worktree_is_silent():
    assert ctx_of(
        '{"tool_name":"Agent","tool_input":{"description":"w","prompt":"x","isolation":"worktree"}}'
    ) == ""


def test_agent_with_isolation_remote_is_silent():
    assert ctx_of(
        '{"tool_name":"Agent","tool_input":{"description":"w","prompt":"x","isolation":"remote"}}'
    ) == ""


# --- undeclared spawn -> advisory --------------------------------------------------


def test_agent_without_isolation_gets_an_advisory():
    ctx = ctx_of(
        '{"tool_name":"Agent","tool_input":{"description":"do work","prompt":"x",'
        '"subagent_type":"general-purpose"}}'
    )
    assert ctx != ""


def test_advisory_mentions_worktree_parallel_commit_cleanup():
    ctx = ctx_of('{"tool_name":"Agent","tool_input":{"description":"d","prompt":"x"}}')
    lowered = ctx.lower()
    assert "worktree" in lowered
    assert "commit" in lowered
    assert "parallel" in lowered
    assert "worktree remove" in lowered


def test_advisory_exits_0_non_blocking():
    status, _ = run_guard('{"tool_name":"Agent","tool_input":{"description":"d","prompt":"x"}}')
    assert status == 0


# --- stale agent worktrees -> reap notice ------------------------------------------


def make_repo_with_stale_worktree(tmp_path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo, check=True)
    (repo / "file.txt").write_text("hello\n")
    subprocess.run(["git", "add", "file.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=repo, check=True)
    subprocess.run(
        ["git", "worktree", "add", "-q", "-b", "worktree-old", str(tmp_path / "wt-old")],
        cwd=repo,
        check=True,
    )
    return repo


def test_declared_isolation_and_stale_worktree_gets_stale_notice(tmp_path):
    repo = make_repo_with_stale_worktree(tmp_path)
    ctx = ctx_of(
        json.dumps(
            {
                "tool_name": "Agent",
                "cwd": str(repo),
                "tool_input": {"description": "d", "prompt": "x", "isolation": "worktree"},
            }
        )
    )
    assert "Stale worktree notice" in ctx
    assert "wt-old" in ctx
    assert "CONFIRM IT IS CLEAN" in ctx
    assert "never discard uncommitted work" in ctx.lower()


def test_declared_isolation_no_agent_worktrees_is_silent(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    ctx = ctx_of(
        json.dumps(
            {
                "tool_name": "Agent",
                "cwd": str(repo),
                "tool_input": {"description": "d", "prompt": "x", "isolation": "worktree"},
            }
        )
    )
    assert ctx == ""


def test_undeclared_isolation_and_stale_worktree_includes_advisory_and_notice(tmp_path):
    repo = make_repo_with_stale_worktree(tmp_path)
    ctx = ctx_of(
        json.dumps(
            {
                "tool_name": "Agent",
                "cwd": str(repo),
                "tool_input": {"description": "d", "prompt": "x"},
            }
        )
    )
    assert "subagent isolation" in ctx.lower()
    assert "Stale worktree notice" in ctx
    assert "wt-old" in ctx
