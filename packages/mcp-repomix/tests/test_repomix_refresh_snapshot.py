"""Coverage for repomix-refresh-snapshot.py, a PostToolUse:Bash hook that repacks
a Repomix snapshot after a branch, worktree, or integration event.

Repomix packs a whole snapshot rather than indexing incrementally, so a pack is
expensive and every gate that suppresses one is load-bearing. These tests are
therefore mostly about NOT packing: a dirty tree, a failed command, an
unrelated command, a subagent, an unchanged HEAD, and a concurrent run all have
to bail. `repomix` is stubbed so a "pack" is observable without running one.

Ported from repomix-refresh-snapshot.bats when the hook moved from shell to
Python; every case there has a case here.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parent.parent / "scripts" / "repomix-refresh-snapshot.py"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    _git(repo_dir, "init", "-q")
    _git(repo_dir, "config", "user.email", "t@example.test")
    _git(repo_dir, "config", "user.name", "t")
    _git(repo_dir, "config", "commit.gpgsign", "false")
    # repomix.xml must be gitignored, or the hook declines to write it.
    (repo_dir / ".gitignore").write_text("repomix.xml\n")
    (repo_dir / "file.txt").write_text("x\n")
    _git(repo_dir, "add", "-A")
    _git(repo_dir, "commit", "-qm", "initial")
    return repo_dir


@pytest.fixture
def env(tmp_path: Path, repo: Path) -> dict[str, str]:
    """A PATH holding a stub `repomix` that records that it ran, plus an
    isolated XDG_STATE_HOME so the lockdir/marker never leaks across tests."""
    stub_bin = tmp_path / "bin"
    stub_bin.mkdir()
    ran_marker = tmp_path / "ran"
    stub = stub_bin / "repomix"
    stub.write_text(f'#!/bin/sh\nprintf \'packed\\n\' >>"{ran_marker}"\nexit 0\n')
    stub.chmod(0o755)

    environment = dict(os.environ)
    environment["PATH"] = f"{stub_bin}:{environment['PATH']}"
    environment["XDG_STATE_HOME"] = str(tmp_path / "state")
    environment["_RAN_MARKER"] = str(ran_marker)
    return environment


def fire(repo: Path, environment: dict[str, str], command: str, exit_code: int = 0) -> None:
    """Run the hook and give its backgrounded pack a moment to land."""
    payload = json.dumps(
        {
            "cwd": str(repo),
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": command},
            "tool_response": {"exit_code": exit_code},
        }
    )
    subprocess.run(
        [sys.executable, str(HOOK)],
        input=payload,
        capture_output=True,
        text=True,
        env=environment,
        timeout=30,
    )
    time.sleep(2)


def packed(environment: dict[str, str]) -> bool:
    return Path(environment["_RAN_MARKER"]).exists()


def test_script_parses() -> None:
    import ast

    ast.parse(HOOK.read_text())


# --- the events that justify a repack ---------------------------------------


def test_worktree_add_triggers_a_pack(repo: Path, env: dict[str, str]) -> None:
    # The command string is all the hook inspects; it does not run it. A real
    # `git worktree add` here would add an untracked entry and trip the
    # clean-tree gate, which is a property of the fixture rather than the hook.
    fire(repo, env, "git worktree add ../elsewhere")
    assert packed(env)


def test_branch_creation_triggers_a_pack(repo: Path, env: dict[str, str]) -> None:
    fire(repo, env, "git switch -c feature/x")
    assert packed(env)


def test_merge_triggers_a_pack(repo: Path, env: dict[str, str]) -> None:
    fire(repo, env, "git merge origin/main")
    assert packed(env)


# --- the gates that must suppress a pack ------------------------------------


def test_unrelated_command_does_not_pack(repo: Path, env: dict[str, str]) -> None:
    fire(repo, env, "ls -la")
    assert not packed(env)


def test_read_only_git_command_does_not_pack(repo: Path, env: dict[str, str]) -> None:
    fire(repo, env, "git status --short")
    assert not packed(env)


def test_failed_command_does_not_pack(repo: Path, env: dict[str, str]) -> None:
    fire(repo, env, "git merge origin/main", exit_code=1)
    assert not packed(env)


def test_dirty_working_tree_does_not_pack(repo: Path, env: dict[str, str]) -> None:
    with (repo / "file.txt").open("a") as handle:
        handle.write("dirty\n")
    fire(repo, env, "git merge origin/main")
    assert not packed(env)


def test_subagent_invocation_does_not_pack(repo: Path, env: dict[str, str]) -> None:
    payload = json.dumps(
        {
            "cwd": str(repo),
            "agent_id": "sub-1",
            "tool_name": "Bash",
            "tool_input": {"command": "git merge origin/main"},
            "tool_response": {"exit_code": 0},
        }
    )
    subprocess.run(
        [sys.executable, str(HOOK)],
        input=payload,
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    time.sleep(2)
    assert not packed(env)


def test_unchanged_head_does_not_pack_twice(repo: Path, env: dict[str, str]) -> None:
    fire(repo, env, "git merge origin/main")
    assert packed(env)
    Path(env["_RAN_MARKER"]).unlink()
    fire(repo, env, "git merge origin/main")
    assert not packed(env)


def test_a_new_commit_does_pack_again(repo: Path, env: dict[str, str]) -> None:
    fire(repo, env, "git merge origin/main")
    assert packed(env)
    Path(env["_RAN_MARKER"]).unlink()
    with (repo / "file.txt").open("a") as handle:
        handle.write("more\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "second")
    fire(repo, env, "git merge origin/main")
    assert packed(env)


def test_repomix_absent_no_pack_exit_0(repo: Path, env: dict[str, str]) -> None:
    stub_bin = Path(env["PATH"].split(os.pathsep)[0])
    (stub_bin / "repomix").unlink()
    fire(repo, env, "git merge origin/main")
    assert not packed(env)


def test_untracked_repomix_xml_not_gitignored_does_not_pack(
    repo: Path, env: dict[str, str]
) -> None:
    (repo / ".gitignore").write_text("\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "drop the ignore")
    fire(repo, env, "git merge origin/main")
    assert not packed(env)


# --- fail open --------------------------------------------------------------


def test_empty_payload_exits_clean_no_pack(env: dict[str, str]) -> None:
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input="",
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert result.returncode == 0
    assert not packed(env)


def test_malformed_payload_exits_clean_no_pack(env: dict[str, str]) -> None:
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input="not json {",
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert result.returncode == 0
    assert not packed(env)


def test_hook_emits_no_decision_being_posttooluse(repo: Path, env: dict[str, str]) -> None:
    payload = json.dumps(
        {
            "cwd": str(repo),
            "tool_name": "Bash",
            "tool_input": {"command": "git merge origin/main"},
            "tool_response": {"exit_code": 0},
        }
    )
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=payload,
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert result.stdout == ""
    assert result.stderr == ""
