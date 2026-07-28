"""Tests for subagent-context-inject.py.

Ported from tests/code-intel.bats (contract rule 4: keep the existing suite
as the oracle when porting a guard to Python). The Python port resolves the
repo root by an in-process parent walk (contract performance rule 3) rather
than shelling out to `git rev-parse --show-toplevel`, so fixtures need a real
`.git` entry on disk instead of a stubbed answer for that one call; the git
stub still covers branch/symbolic-ref/diff, which remain subprocess calls.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "scripts" / "subagent-context-inject.py"

# A repo root containing a backslash and a double quote -- the exact
# adversarial path that broke the old sed/tr JSON escaping.
ODD_NAME = 're\\po"odd'

GIT_STUB = """#!/usr/bin/env bash
case "$*" in
  *"branch --show-current"*) printf '%s\\n' 'feat/x"y' ;;
  *"symbolic-ref"*) exit 1 ;;
  *"diff --name-only"*) printf 'a.txt\\nb.txt\\n' ;;
  *) exit 0 ;;
esac
"""


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    odd = tmp_path / ODD_NAME
    (odd / ".git").mkdir(parents=True)
    stubbin = tmp_path / "bin"
    stubbin.mkdir()
    git_stub = stubbin / "git"
    git_stub.write_text(GIT_STUB)
    git_stub.chmod(0o755)
    return odd


def run_hook(stdin: str, repo: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PATH"] = f"{repo.parent / 'bin'}:{env['PATH']}"
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=stdin,
        capture_output=True,
        text=True,
        env=env,
    )


def test_backslash_quote_repo_name_yields_valid_json(repo):
    payload = json.dumps({"agent_id": "a1", "agent_type": "speckit-implement-task", "cwd": str(repo)})
    result = run_hook(payload, repo)
    assert result.returncode == 0
    json.loads(result.stdout)


def test_backslash_path_round_trips_through_json_field(repo):
    payload = json.dumps({"agent_id": "a1", "agent_type": "x", "cwd": str(repo)})
    result = run_hook(payload, repo)
    assert result.returncode == 0
    ctx = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert ODD_NAME in ctx


def test_base_block_carries_routing_not_working_style(repo):
    payload = json.dumps({"agent_id": "a1", "agent_type": "coder", "cwd": str(repo)})
    result = run_hook(payload, repo)
    assert result.returncode == 0
    ctx = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "Serena" in ctx
    assert "rg for exact text" in ctx
    # Working-style discipline moved to steering-pragmatic; it MUST NOT appear here.
    for gone in ("MANDATORY RULES", "MUST Code economy", "MUST YAGNI", "MUST Comments", "MUST Reports"):
        assert gone not in ctx


def test_non_subagent_exits_silently(repo):
    payload = json.dumps({"cwd": str(repo)})
    result = run_hook(payload, repo)
    assert result.returncode == 0
    assert result.stdout == ""


def test_malformed_empty_stdin_does_not_crash(repo):
    result = run_hook("", repo)
    assert result.returncode == 0
