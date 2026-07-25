from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1]
GUARD_PATH = PACKAGE / "scripts" / "worktrunk-guard.py"
USER_CONFIG = PACKAGE / "templates" / "config.user.toml"
PROJECT_CONFIG = PACKAGE / "templates" / "config.project.toml"
SPEC = importlib.util.spec_from_file_location("worktrunk_guard", GUARD_PATH)
assert SPEC is not None and SPEC.loader is not None
guard = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = guard
SPEC.loader.exec_module(guard)


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("git worktree list", "wt list"),
        (
            "/usr/bin/git -C /repo worktree add -b feat/auth /tmp/auth origin/main",
            "wt switch --create feat/auth --base origin/main",
        ),
        ("cd /repo && git worktree remove /tmp/auth", "wt remove /tmp/auth"),
        ("FOO=bar command git worktree prune", "wt step prune --dry-run"),
        ("sudo git worktree move /tmp/old /tmp/new", "wt step relocate /tmp/old"),
        ("printf '%s\\n' \"$(git worktree list)\"", "wt list"),
        ("bash -c 'git worktree list'", "wt list"),
        ("zsh -lc 'git worktree list'", "wt list"),
        ("git-worktree lock /tmp/auth", "no general Worktrunk equivalent"),
        ("git worktree add --detach /tmp/review HEAD~1", "branch-oriented"),
        ("gh pr checkout 42", "wt switch pr:42"),
        ("gh --repo acme/repo pr checkout 42", "wt switch pr:42"),
        (
            "gh pr checkout https://github.com/acme/repo/pull/42",
            "wt switch https://github.com/acme/repo/pull/42",
        ),
        ("gh pr checkout --branch review-42 42", "wt switch pr:42"),
        (
            "claude --worktree fix-auth 'repair the login flow'",
            "wt switch --create <branch> --execute=claude",
        ),
        ("env claude -w fix-auth", "/wt-switch-create"),
    ],
)
def test_direct_worktree_management_is_denied(command: str, expected: str) -> None:
    violation = guard.scan_command(command)
    assert violation is not None
    assert expected in violation.reason


@pytest.mark.parametrize(
    "command",
    [
        "wt switch --create feat/auth --base origin/main",
        "wt switch pr:42",
        "git status --short",
        "echo 'git worktree add /tmp/example'",
        'git commit -m "docs: avoid git worktree add"',
        "printf '%s\\n' 'git worktree list'",
        "grep -R 'git worktree' docs",
        "env echo git worktree list",
        "bash -lc 'echo git worktree list'",
        "gh pr view 42",
        "claude --model opus",
        "printf '%s\\n' 'claude --worktree example'",
    ],
)
def test_non_management_commands_are_silent(command: str) -> None:
    assert guard.scan_command(command) is None


def run_guard(payload: object | str) -> subprocess.CompletedProcess[str]:
    stdin = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run(
        [sys.executable, str(GUARD_PATH)],
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )


def test_object_payload_emits_cross_runtime_deny_contract() -> None:
    result = run_guard({"tool_input": {"command": "git worktree list"}})
    assert result.returncode == 0
    output = json.loads(result.stdout)
    decision = output["hookSpecificOutput"]
    assert decision["hookEventName"] == "PreToolUse"
    assert decision["permissionDecision"] == "deny"
    assert "wt list" in decision["permissionDecisionReason"]


def test_string_payload_is_supported() -> None:
    result = run_guard({"tool_input": "git worktree prune"})
    assert result.returncode == 0
    assert json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.parametrize("payload", ["", "not-json", "[]", '{"tool_input": {}}'])
def test_unusable_payload_fails_open(payload: str) -> None:
    result = run_guard(payload)
    assert result.returncode == 0
    assert result.stdout == ""


def test_user_config_uses_sequential_blocking_setup() -> None:
    config = tomllib.loads(USER_CONFIG.read_text())
    pre_start = config["pre-start"]
    assert pre_start[0] == {"mise-trust": "mise trust --yes"}
    cargo_target = pre_start[1]["cargo-target"]
    assert '[ -f "{{ worktree_path }}/Cargo.toml" ]' in cargo_target
    assert "refusing to overwrite existing" in cargo_target
    assert "/.cargo/config.toml" in cargo_target
    assert '"{{ primary_worktree_path }}/target"' in cargo_target
    assert 'cargo_config="{{ worktree_path }}/.cargo/config.toml"' in cargo_target
    assert config["post-start"] == {"copy-ignored": "wt step copy-ignored --require-include"}
    assert {"target/", ".venv/", "venv/", ".cargo/config.toml"} <= set(
        config["step"]["copy-ignored"]["exclude"]
    )
    commit_command = config["commit"]["generation"]["command"]
    assert commit_command.startswith("CLAUDECODE= ")
    assert "--safe-mode" in commit_command


def test_cargo_hook_materializes_an_ignored_repository_target() -> None:
    config = tomllib.loads(USER_CONFIG.read_text())
    template = config["pre-start"][1]["cargo-target"]
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        worktree = root / "worktree"
        primary = root / "primary"
        common = root / "common.git"
        bin_dir = root / "bin"
        worktree.mkdir()
        primary.mkdir()
        common.mkdir()
        bin_dir.mkdir()
        (worktree / "Cargo.toml").write_text("[workspace]\nmembers = []\n")
        fake_git = bin_dir / "git"
        fake_git.write_text(f"#!/bin/sh\nprintf '%s\\n' '{common}'\n")
        fake_git.chmod(0o755)
        command = template.replace("{{ worktree_path }}", str(worktree)).replace(
            "{{ primary_worktree_path }}", str(primary)
        )

        result = subprocess.run(
            ["bash", "-c", command],
            capture_output=True,
            text=True,
            env={**os.environ, "PATH": f"{bin_dir}:{os.environ.get('PATH', '')}"},
            check=False,
        )

        assert result.returncode == 0, result.stderr
        cargo_config = worktree / ".cargo" / "config.toml"
        assert cargo_config.read_text() == (
            "# Generated by the Worktrunk user pre-start hook.\n"
            "[build]\n"
            f'target-dir = "{primary}/target"\n'
        )
        assert "/.cargo/config.toml" in (common / "info" / "exclude").read_text()


def test_cargo_hook_preserves_an_existing_config() -> None:
    config = tomllib.loads(USER_CONFIG.read_text())
    template = config["pre-start"][1]["cargo-target"]
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        worktree = root / "worktree"
        primary = root / "primary"
        (worktree / ".cargo").mkdir(parents=True)
        primary.mkdir()
        (worktree / "Cargo.toml").write_text("[workspace]\nmembers = []\n")
        cargo_config = worktree / ".cargo" / "config.toml"
        cargo_config.write_text("[net]\noffline = true\n")
        command = template.replace("{{ worktree_path }}", str(worktree)).replace(
            "{{ primary_worktree_path }}", str(primary)
        )

        result = subprocess.run(
            ["bash", "-c", command],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 1
        assert "refusing to overwrite existing" in result.stderr
        assert cargo_config.read_text() == "[net]\noffline = true\n"


def test_cargo_hook_is_a_noop_outside_rust_repositories() -> None:
    config = tomllib.loads(USER_CONFIG.read_text())
    template = config["pre-start"][1]["cargo-target"]
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        worktree = root / "worktree"
        primary = root / "primary"
        worktree.mkdir()
        primary.mkdir()
        command = template.replace("{{ worktree_path }}", str(worktree)).replace(
            "{{ primary_worktree_path }}", str(primary)
        )

        result = subprocess.run(
            ["bash", "-c", command],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0, result.stderr
        assert not (worktree / ".cargo").exists()


def test_project_config_keeps_operational_hooks_project_owned() -> None:
    config = tomllib.loads(PROJECT_CONFIG.read_text())
    assert set(config) == {"commit", "aliases"}
    assert "template-append" in config["commit"]["generation"]
    assert config["aliases"]["copy"].startswith("wt step copy-ignored")
