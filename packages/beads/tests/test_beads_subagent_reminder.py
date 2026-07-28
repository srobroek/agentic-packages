"""Tests for beads-subagent-reminder.py.

Ported from the reminder cases in tests/beads-hooks.bats (contract rule 4:
keep the existing suite as the oracle when porting to Python). The guard
cases in that file (beads-gh-issue-guard.sh) are being ported separately and
stay in bats untouched.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "scripts" / "beads-subagent-reminder.py"


def run_hook(stdin: str, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=stdin,
        capture_output=True,
        text=True,
        env=env if env is not None else os.environ.copy(),
    )


def test_exits_0_on_empty_payload():
    result = run_hook("")
    assert result.returncode == 0


def test_exits_0_on_malformed_json():
    result = run_hook("{oops")
    assert result.returncode == 0


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    work = tmp_path / "work"
    (work / ".beads").mkdir(parents=True)
    stubbin = tmp_path / "bin"
    stubbin.mkdir()
    bd_stub = stubbin / "bd"
    bd_stub.write_text("#!/bin/sh\nexit 0\n")
    bd_stub.chmod(0o755)
    return work


def stub_env(tmp_path: Path) -> dict:
    env = os.environ.copy()
    env["PATH"] = f"{tmp_path / 'bin'}:{env['PATH']}"
    return env


def test_injects_contract_when_bd_and_workspace_present(workspace, tmp_path):
    payload = json.dumps({"agent_id": "a1", "cwd": str(workspace)})
    result = run_hook(payload, stub_env(tmp_path))
    assert result.returncode == 0
    ctx = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "bd create" in ctx
    assert "bd close" in ctx


def test_no_agent_id_is_silent(workspace, tmp_path):
    payload = json.dumps({"cwd": str(workspace)})
    result = run_hook(payload, stub_env(tmp_path))
    assert result.returncode == 0
    assert result.stdout == ""


def test_no_beads_workspace_is_silent(tmp_path):
    no_workspace = tmp_path / "plain"
    no_workspace.mkdir()
    stubbin = tmp_path / "bin"
    stubbin.mkdir()
    bd_stub = stubbin / "bd"
    bd_stub.write_text("#!/bin/sh\nexit 1\n")
    bd_stub.chmod(0o755)
    payload = json.dumps({"agent_id": "a1", "cwd": str(no_workspace)})
    result = run_hook(payload, stub_env(tmp_path))
    assert result.returncode == 0
    assert result.stdout == ""


def test_bd_absent_is_silent(workspace):
    env = os.environ.copy()
    env["PATH"] = "/usr/bin:/bin"
    payload = json.dumps({"agent_id": "a1", "cwd": str(workspace)})
    result = run_hook(payload, env)
    assert result.returncode == 0
    assert result.stdout == ""
