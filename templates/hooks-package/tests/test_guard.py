#!/usr/bin/env python3
"""Example guard test suite. Copy alongside scripts/guard.py.

Contract authoring rule 3 requires a suite per guard, and says a guard's NEGATIVE
cases matter more than its positive ones: the expensive failure is a guard that
denies benign work, or one that silently allows the thing it exists to catch.
Roughly two thirds of the cases below are negative for that reason.

Run with: python3 -m pytest templates/hooks-package/tests/test_guard.py
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

GUARD = Path(__file__).resolve().parents[1] / "scripts" / "guard.py"


def _load():
    spec = importlib.util.spec_from_file_location("guard_under_test", GUARD)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = _load()


def run(payload: str | None) -> tuple[int, str]:
    result = subprocess.run(
        [sys.executable, str(GUARD)],
        input="" if payload is None else payload,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.returncode, result.stdout.strip()


def decide(command: str | None, *, as_string: bool = False) -> str:
    """The guard's permissionDecision for a command, or "" when it allows."""
    if command is None:
        payload = ""
    else:
        tool_input = command if as_string else {"command": command}
        payload = json.dumps({"tool_name": "Bash", "tool_input": tool_input})
    code, output = run(payload)
    assert code == 0, "a guard must always exit 0; nonzero is a hook error"
    if not output:
        return ""
    return (
        json.loads(output)
        .get("hookSpecificOutput", {})
        .get("permissionDecision", "")
    )


# --- shipped contract -------------------------------------------------------


def test_guard_is_committed_executable():
    """The hook JSON invokes it by bare path, so the kernel needs the bit."""
    assert GUARD.stat().st_mode & 0o111


def test_shebang_is_python3():
    assert GUARD.read_text(encoding="utf-8").startswith("#!/usr/bin/env python3\n")


@pytest.mark.parametrize(
    "command",
    ["git push", "git status", 'echo "git push"', "sudo git push"],
)
def test_guard_never_emits_ask(command):
    """`ask` waits for a human, stalling an autonomous run; Codex ignores it and
    runs the call anyway. Asserted over the OUTPUT, not the source text, so the
    docstring can still name the rule it teaches.
    """
    assert decide(command) in ("", "deny", "allow")


# --- positive cases ---------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "git push",
        "git push origin main",
        "git push --force-with-lease",
        "git -c user.name=x push",
    ],
)
def test_gated_command_is_denied(command):
    assert decide(command) == "deny"


@pytest.mark.parametrize(
    "command",
    [
        "env GIT_SSH_COMMAND=ssh git push",
        "sudo git push",
        "sudo -u git git push",
        "nice -n 19 git push",
        "timeout 5 git push",
        "timeout -s KILL 5 git push",
        "command git push",
    ],
)
def test_wrapped_and_prefixed_forms_are_still_denied(command):
    """Each of these bypassed a hand-rolled matcher in this repo's history."""
    assert decide(command) == "deny"


def test_string_tool_input_is_still_judged():
    """`.tool_input.command // .tool_input` THROWS on a string in jq, which
    silently allows the call. The Python type check is the fix.
    """
    assert decide("git push", as_string=True) == "deny"


# --- negative cases ---------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "git status",
        "git pull",
        "git commit -m wip",
        "npm run build",
        "ls -la",
    ],
)
def test_unrelated_commands_are_allowed_silently(command):
    assert decide(command) == ""


@pytest.mark.parametrize(
    "command",
    [
        'echo "git push"',
        'git commit -m "do not git push yet"',
        "grep -r 'git push' docs/",
        'printf "run git push after review\\n"',
    ],
)
def test_quoted_prose_mentioning_the_command_is_allowed(command):
    """A `*"git push"*` glob denied every one of these. The verb is what counts,
    not a substring of the line.
    """
    assert decide(command) == ""


@pytest.mark.parametrize("command", ["git pushx", "gitk push", "mygit push", "pushd /tmp"])
def test_lookalike_verbs_are_allowed(command):
    assert decide(command) == ""


def test_wrapper_option_value_is_not_read_as_the_verb():
    """`nice -n 19 git status` must stay allowed: 19 is an option value, and
    reading it as the verb would make the guard judge the wrong word.
    """
    assert decide("nice -n 19 git status") == ""


# --- fail-open cases --------------------------------------------------------


def test_empty_payload_is_allowed():
    assert decide(None) == ""


@pytest.mark.parametrize(
    "payload",
    [
        "{not json",
        "[]",
        "null",
        '{"tool_input": null}',
        '{"tool_input": 7}',
        '{"tool_input": {}}',
        '{"tool_input": {"command": null}}',
        '{"tool_input": {"command": ""}}',
    ],
)
def test_unusable_payloads_allow_rather_than_crash(payload):
    """Fail open: an unreadable payload loses one check, not the whole run."""
    code, output = run(payload)
    assert code == 0
    assert output == ""


def test_unbalanced_quotes_fail_open():
    """shlex cannot tokenize this, so the guard declines to guess."""
    assert decide('git push "unterminated') == ""


# --- helpers ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("git push", ["git", "push"]),
        ("env FOO=1 git push", ["git", "push"]),
        ("FOO=1 BAR=2 git push", ["git", "push"]),
        ("sudo -u git git push", ["git", "push"]),
        ("timeout 5 git push", ["git", "push"]),
        ("git push", ["git", "push"]),
        ("", []),
    ],
)
def test_strip_prefix_reaches_the_real_verb(command, expected):
    commands = guard.expand_commands(command)
    assert [guard.strip_prefix(words) for words in commands] == ([expected] if expected else [])
