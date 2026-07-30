"""Coverage for speckit-tasks-guard.py, which has three roles branched on
the tool: a DENY on writes to specs/*/tasks.md, and advisories on a Bash
command or a Skill invocation that touches the same ground.

The deny is the part worth pinning hardest in both directions. tasks.md is
never authored under the beads workflow, so writing one must be refused with
the replacement workflow in the reason; but a write to any OTHER tasks.md, or
to a spec file that is not tasks.md, is ordinary work and must pass. So must
everything in a repository with no beads workspace.

`bd` is stubbed on PATH so these tests describe the guard's logic rather than
the machine's beads state.

Ported from the retired speckit-beads-tasks-guard.bats; every bats case has a matching
test here.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

GUARD = Path(__file__).resolve().parent.parent / "scripts" / "speckit-tasks-guard.py"


@pytest.fixture
def work(tmp_path: Path) -> Path:
    root = tmp_path / "work"
    (root / "specs" / "001-feature").mkdir(parents=True)
    return root


def _stub_bd(tmp_path: Path, *, active: bool) -> dict[str, str]:
    stub_dir = tmp_path / "bin"
    stub_dir.mkdir(exist_ok=True)
    stub = stub_dir / "bd"
    stub.write_text(f"#!/bin/sh\nexit {0 if active else 1}\n")
    stub.chmod(0o755)
    environment = dict(os.environ)
    environment["PATH"] = f"{stub_dir}:{environment['PATH']}"
    return environment


@pytest.fixture
def bd_active(tmp_path: Path) -> dict[str, str]:
    return _stub_bd(tmp_path, active=True)


@pytest.fixture
def bd_inactive(tmp_path: Path) -> dict[str, str]:
    return _stub_bd(tmp_path, active=False)


@pytest.fixture
def bd_absent(tmp_path: Path) -> dict[str, str]:
    stub_dir = tmp_path / "empty-bin"
    stub_dir.mkdir(exist_ok=True)
    environment = dict(os.environ)
    environment["PATH"] = str(stub_dir)
    return environment


def run_guard(payload: object, environment: dict[str, str]) -> tuple[int, str]:
    body = payload if isinstance(payload, str) else json.dumps(payload)
    result = subprocess.run(
        [sys.executable, str(GUARD)],
        input=body,
        capture_output=True,
        text=True,
        env=environment,
        timeout=30,
    )
    return result.returncode, result.stdout.strip()


def write_payload(work: Path, tool: str, file_path: str) -> dict:
    return {
        "cwd": str(work),
        "hook_event_name": "PreToolUse",
        "tool_name": tool,
        "tool_input": {"file_path": file_path},
    }


def bash_payload(work: Path, command: str) -> dict:
    return {
        "cwd": str(work),
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }


def decision(output: str) -> str:
    if not output:
        return "allow"
    return json.loads(output)["hookSpecificOutput"].get("permissionDecision", "allow")


def test_script_parses() -> None:
    subprocess.run([sys.executable, "-c", f"compile(open({str(GUARD)!r}).read(), 'g', 'exec')"], check=True)


# --- the deny ----------------------------------------------------------------


def test_write_to_tasks_md_is_denied(work: Path, bd_active: dict[str, str]) -> None:
    _, output = run_guard(write_payload(work, "Write", str(work / "specs/001-feature/tasks.md")), bd_active)
    assert decision(output) == "deny"


def test_edit_to_tasks_md_is_denied(work: Path, bd_active: dict[str, str]) -> None:
    _, output = run_guard(write_payload(work, "Edit", str(work / "specs/001-feature/tasks.md")), bd_active)
    assert decision(output) == "deny"


def test_apply_patch_to_tasks_md_is_denied(work: Path, bd_active: dict[str, str]) -> None:
    # Codex sends the patch in tool_input.command, not file_path.
    payload = {
        "cwd": str(work),
        "hook_event_name": "PreToolUse",
        "tool_name": "apply_patch",
        "tool_input": {"command": f"*** Update File: {work / 'specs/001-feature/tasks.md'}"},
    }
    _, output = run_guard(payload, bd_active)
    assert decision(output) == "deny"


def test_the_denial_carries_the_replacement_workflow(work: Path, bd_active: dict[str, str]) -> None:
    _, output = run_guard(write_payload(work, "Write", str(work / "specs/001-feature/tasks.md")), bd_active)
    reason = json.loads(output)["hookSpecificOutput"]["permissionDecisionReason"]
    assert "bd" in reason


# --- what must pass ---------------------------------------------------------


def test_a_spec_file_that_is_not_tasks_md_is_allowed(work: Path, bd_active: dict[str, str]) -> None:
    _, output = run_guard(write_payload(work, "Write", str(work / "specs/001-feature/spec.md")), bd_active)
    assert decision(output) == "allow"


def test_a_tasks_md_outside_specs_is_allowed(work: Path, bd_active: dict[str, str]) -> None:
    _, output = run_guard(write_payload(work, "Write", str(work / "docs/tasks.md")), bd_active)
    assert decision(output) == "allow"


def test_an_ordinary_source_file_is_allowed_and_silent(work: Path, bd_active: dict[str, str]) -> None:
    _, output = run_guard(write_payload(work, "Write", str(work / "src/main.py")), bd_active)
    assert decision(output) == "allow"
    assert not output


def test_no_beads_workspace_allows(work: Path, bd_inactive: dict[str, str]) -> None:
    _, output = run_guard(write_payload(work, "Write", str(work / "specs/001-feature/tasks.md")), bd_inactive)
    assert decision(output) == "allow"


def test_bd_absent_allows(work: Path, bd_absent: dict[str, str]) -> None:
    _, output = run_guard(write_payload(work, "Write", str(work / "specs/001-feature/tasks.md")), bd_absent)
    assert decision(output) == "allow"


# --- the Bash advisory is never a block -------------------------------------


def test_a_bash_command_touching_tasks_md_advises_without_blocking(
    work: Path, bd_active: dict[str, str]
) -> None:
    _, output = run_guard(bash_payload(work, f"cat {work / 'specs/001-feature/tasks.md'}"), bd_active)
    assert decision(output) == "allow"


def test_an_unrelated_bash_command_is_silent(work: Path, bd_active: dict[str, str]) -> None:
    _, output = run_guard(bash_payload(work, "git status --short"), bd_active)
    assert decision(output) == "allow"
    assert not output


# --- fail open --------------------------------------------------------------


def test_empty_payload_exits_0_no_output(bd_active: dict[str, str]) -> None:
    code, output = run_guard("", bd_active)
    assert code == 0
    assert not output


def test_malformed_payload_exits_0_no_output(bd_active: dict[str, str]) -> None:
    code, output = run_guard("not json {", bd_active)
    assert code == 0
    assert not output


def test_string_form_tool_input_allows_by_documented_choice(work: Path, bd_active: dict[str, str]) -> None:
    # A bare-string tool_input carries no path to judge, so this guard allows
    # rather than guessing -- a narrower stance than the contract's general
    # advice to read a string input, and deliberate here because the deny needs
    # a specific path.
    payload = {
        "cwd": str(work),
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "tool_input": str(work / "specs/001-feature/tasks.md"),
    }
    code, output = run_guard(payload, bd_active)
    assert code == 0
    assert decision(output) == "allow"


def test_never_emits_ask(work: Path, bd_active: dict[str, str]) -> None:
    _, output = run_guard(write_payload(work, "Write", str(work / "specs/001-feature/tasks.md")), bd_active)
    assert decision(output) != "ask"
    _, output = run_guard(write_payload(work, "Write", str(work / "src/main.py")), bd_active)
    assert decision(output) != "ask"
