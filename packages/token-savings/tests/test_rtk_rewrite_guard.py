"""Coverage for rtk-rewrite-guard.py, a PreToolUse:Bash rewrite hook.

The negative cases are the point. This guard makes the agent's command run
through a lossy filter, so every case it must NOT touch is a case where a
filtered rendering could change an answer rather than merely shorten it. Those
tests outnumber the positive ones deliberately.

Each refusal below was verified against rtk 0.43.0 rather than assumed:
`rtk git status --porcelain` drops the trailing newline (so `| wc -l`
under-counts), and `rtk grep` returned 25 of 400 matching lines (so `grep -c`
would be wrong). The guard cannot detect caller intent, so it refuses the whole
shape.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

GUARD = Path(__file__).resolve().parent.parent / "scripts" / "rtk-rewrite-guard.py"


def _run(payload, *, with_rtk: bool = True, tmp_path: Path | None = None) -> str:
    """Run the guard, returning the rewritten command or "" when untouched.

    A stub `rtk` goes on PATH so the suite does not depend on rtk being
    installed on the machine running it.
    """
    env = dict(os.environ)
    if with_rtk:
        if tmp_path is not None:
            stub_dir = tmp_path / "bin"
            stub_dir.mkdir(exist_ok=True)
            stub = stub_dir / "rtk"
            stub.write_text("#!/bin/sh\nexit 0\n")
            stub.chmod(0o755)
            env["PATH"] = f"{stub_dir}{os.pathsep}{env['PATH']}"
    else:
        # An empty PATH is not enough: shutil.which falls back to os.defpath.
        env["PATH"] = str(tmp_path / "empty") if tmp_path else "/nonexistent"

    raw = payload if isinstance(payload, str) else json.dumps(payload)
    proc = subprocess.run(
        [sys.executable, str(GUARD)], input=raw, capture_output=True, text=True, env=env
    )
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout.strip()
    if not out:
        return ""
    return json.loads(out)["hookSpecificOutput"]["updatedInput"]["command"]


def _bash(command: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": command}}


# --- commands that SHOULD be routed through rtk -----------------------------


@pytest.mark.parametrize(
    "command",
    [
        "git log --oneline -20",
        "git diff HEAD~1",
        "git show HEAD",
        "git blame README.md",
        "gh pr view 799",
        "gh issue list",
        "gh run view 123",
        "cargo clippy",
        "cargo test",
        "kubectl get pods",
        "kubectl describe pod x",
        "docker ps",
        "ruff check .",
        "eslint src",
        "tsc --noEmit",
    ],
)
def test_allowlisted_commands_are_routed(command, tmp_path):
    assert _run(_bash(command), tmp_path=tmp_path) == f"rtk {command}"


def test_env_assignments_keep_their_position(tmp_path):
    """`rtk FOO=1 cargo clippy` would make the assignment an argument to rtk
    rather than environment for cargo -- a different command."""
    assert _run(_bash("FOO=1 cargo clippy"), tmp_path=tmp_path) == "FOO=1 rtk cargo clippy"
    assert _run(_bash("A=1 B=2 git log -1"), tmp_path=tmp_path) == "A=1 B=2 rtk git log -1"


def test_absolute_paths_resolve_to_the_allowlisted_binary(tmp_path):
    assert _run(_bash("/usr/bin/git log -5"), tmp_path=tmp_path) == "rtk /usr/bin/git log -5"


# --- commands that must be LEFT ALONE --------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        # Verified defect: rtk drops the trailing newline on --porcelain.
        "git status --porcelain",
        # Machine-readable output whose shape is the caller's contract.
        "git log --format=%H",
        "git log --pretty=oneline",
        "git diff --name-only",
        "git diff --numstat",
        "gh pr list --json title",
        "git log --oneline --quiet",
        # Single-token output: nothing to save, always parsed.
        "git rev-parse HEAD",
        # rtk grep truncates to ~25 lines; fatal for a count.
        "grep -c foo x",
        "rg -n pattern",
        # The output IS a count.
        "wc -l file",
        # Not on the allowlist at all.
        "python3 -c 'print(1)'",
        "curl -s https://example.test",
        "ls -la",
        "make build",
    ],
)
def test_unsafe_or_unlisted_commands_are_untouched(command, tmp_path):
    assert _run(_bash(command), tmp_path=tmp_path) == ""


@pytest.mark.parametrize(
    "command",
    [
        "git log | head -5",
        "git log > /tmp/out",
        "git log >> /tmp/out",
        "git diff && cargo clippy",
        "git log; cargo test",
        "cargo clippy || true",
        "echo $(git log --oneline -1)",
        "echo `git log -1`",
        "git log < /dev/null",
    ],
)
def test_pipelines_and_redirection_are_untouched(command, tmp_path):
    """A filtered rendering feeding another process could change a result
    rather than just shorten what the model reads."""
    assert _run(_bash(command), tmp_path=tmp_path) == ""


def test_already_routed_commands_are_not_double_wrapped(tmp_path):
    assert _run(_bash("rtk git log --oneline"), tmp_path=tmp_path) == ""


def test_machine_flag_with_attached_value_is_detected(tmp_path):
    """`--format=x` attaches its value, so a plain membership test misses it."""
    assert _run(_bash("git log --format=%H -5"), tmp_path=tmp_path) == ""
    assert _run(_bash("git log --pretty=short"), tmp_path=tmp_path) == ""


# --- fail-open behavior ----------------------------------------------------


def test_missing_rtk_leaves_the_command_alone(tmp_path):
    (tmp_path / "empty").mkdir()
    assert _run(_bash("git log --oneline"), with_rtk=False, tmp_path=tmp_path) == ""


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "not json",
        '{"tool_name":"Bash","tool_input":',  # truncated mid-write
        "[]",
        "null",
        '{"tool_name":"Bash"}',
        '{"tool_name":"Bash","tool_input":{}}',
        '{"tool_name":"Bash","tool_input":{"command":""}}',
        '{"tool_name":"Bash","tool_input":{"command":null}}',
        '{"tool_name":"Bash","tool_input":42}',
    ],
)
def test_malformed_payloads_fail_open(raw, tmp_path):
    assert _run(raw, tmp_path=tmp_path) == ""


def test_string_tool_input_is_accepted(tmp_path):
    """Some callers send tool_input as a bare string; reading .command off it
    would throw and silently bypass the guard."""
    payload = {"tool_name": "Bash", "tool_input": "git log --oneline"}
    assert _run(payload, tmp_path=tmp_path) == "rtk git log --oneline"


def test_unbalanced_quotes_are_untouched(tmp_path):
    assert _run(_bash('git log --grep="unterminated'), tmp_path=tmp_path) == ""


def test_emits_allow_and_never_ask(tmp_path):
    """Constitution III: no guard emits `ask`, and Codex rejects it outright.
    `updatedInput` additionally requires permissionDecision:allow on Codex."""
    stub_dir = tmp_path / "bin"
    stub_dir.mkdir()
    stub = stub_dir / "rtk"
    stub.write_text("#!/bin/sh\nexit 0\n")
    stub.chmod(0o755)
    env = dict(os.environ)
    env["PATH"] = f"{stub_dir}{os.pathsep}{env['PATH']}"

    proc = subprocess.run(
        [sys.executable, str(GUARD)],
        input=json.dumps(_bash("git log --oneline")),
        capture_output=True,
        text=True,
        env=env,
    )
    emitted = json.loads(proc.stdout)["hookSpecificOutput"]
    assert emitted["permissionDecision"] == "allow"
    assert emitted["hookEventName"] == "PreToolUse"
    assert "ask" != emitted["permissionDecision"]
    # Claude-only fields would be silent no-ops on Codex in a target: all package.
    assert "systemMessage" not in emitted
    assert "suppressOutput" not in emitted


@pytest.mark.skipif(shutil.which("rtk") is None, reason="rtk not installed")
def test_allowlisted_rewrites_preserve_content_on_real_rtk(tmp_path):
    """Guard against the allowlist drifting ahead of what rtk actually
    preserves. `git log --oneline` must return the same commit subjects, just
    possibly fewer bytes of decoration."""
    repo = tmp_path / "repo"
    repo.mkdir()
    run = lambda *a: subprocess.run(  # noqa: E731
        ["git", "-C", str(repo), *a], capture_output=True, text=True, check=True
    )
    run("init", "-q")
    run("config", "user.email", "t@example.test")
    run("config", "user.name", "t")
    run("config", "commit.gpgsign", "false")
    (repo / "f.txt").write_text("x\n")
    run("add", "-A")
    run("commit", "-qm", "a distinctive subject line")

    native = run("log", "--oneline").stdout
    filtered = subprocess.run(
        ["rtk", "git", "log", "--oneline"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    assert "a distinctive subject line" in native
    assert "a distinctive subject line" in filtered
