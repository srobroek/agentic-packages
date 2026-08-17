"""Coverage for the package-investigate PreToolUse nudge hook.

Asserts the add/install path emits the deep-investigation context,
update/remove emits the lighter review, unrelated commands stay silent, and
malformed stdin never crashes. Ported from package-investigate.bats when the
hook moved from shell to Python; every case there has a case here.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parent.parent / "scripts" / "package-investigate.py"


def run_hook(payload: str) -> tuple[int, str]:
    """Run the hook on raw stdin; return exit code and additionalContext (or "")."""
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=30,
    )
    ctx = ""
    if result.stdout.strip():
        try:
            ctx = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
        except (ValueError, KeyError, TypeError):
            ctx = ""
    return result.returncode, ctx


def mk_obj(command: str) -> str:
    return json.dumps({"tool_input": {"command": command}})


def mk_str(command: str) -> str:
    return json.dumps({"tool_input": command})


@pytest.mark.parametrize(
    "command",
    [
        "pnpm add foo",
        "npm install left-pad",
        "pip install requests",
        "cargo add serde",
        "go get example.com/pkg",
        "cd app && pnpm add foo",
        "cd app\npnpm add foo",
    ],
)
def test_add_install_emits_investigate_nudge(command: str) -> None:
    status, ctx = run_hook(mk_obj(command))
    assert status == 0
    assert "Before adding this dependency" in ctx


@pytest.mark.parametrize(
    "command",
    [
        "npm remove bar",
        "pnpm update",
        "cargo update",
        "go mod tidy",
    ],
)
def test_update_remove_emits_lighter_review(command: str) -> None:
    status, ctx = run_hook(mk_obj(command))
    assert status == 0
    assert "Dependency change (update/upgrade/remove)" in ctx


def test_unrelated_command_is_silent() -> None:
    status, ctx = run_hook(mk_obj("ls"))
    assert status == 0
    assert ctx == ""


def test_quoted_pnpm_add_inside_echo_is_not_command_position() -> None:
    status, ctx = run_hook(mk_obj("echo 'run pnpm add later'"))
    assert status == 0
    assert ctx == ""


def test_quoted_multiline_pnpm_add_inside_echo_is_not_command_position() -> None:
    status, ctx = run_hook(mk_obj("echo 'run\npnpm add later'"))
    assert status == 0
    assert ctx == ""


def test_string_form_tool_input_still_gates() -> None:
    status, ctx = run_hook(mk_str("pnpm add foo"))
    assert status == 0
    assert "Before adding this dependency" in ctx


def test_empty_stdin_exits_clean() -> None:
    status, ctx = run_hook("")
    assert status == 0
    assert ctx == ""


def test_invalid_json_stdin_never_crashes() -> None:
    status, ctx = run_hook("this is not json {")
    assert status == 0
    assert ctx == ""


def test_tool_input_absent_is_silent() -> None:
    status, ctx = run_hook(json.dumps({"foo": "bar"}))
    assert status == 0
    assert ctx == ""
