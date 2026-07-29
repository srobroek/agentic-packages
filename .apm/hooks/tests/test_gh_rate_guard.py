"""Tests for gh-rate-guard.py.

The shell predecessor had no tests at all, so these are written against the
behaviour it intended rather than the behaviour it had -- and several cases below
are ones it got wrong. Each such case says so, because they are the reason the
port exists.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "gh-rate-guard.py"


def load():
    """Import the hyphenated script as a module."""
    spec = importlib.util.spec_from_file_location("gh_rate_guard", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = load()


def run(command, monkeypatch, capsys, *, raw=None):
    """Drive main() with a payload and return (exit code, parsed output or None)."""
    payload = raw if raw is not None else json.dumps({"tool_input": {"command": command}})
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO(payload))
    code = guard.main()
    out = capsys.readouterr().out
    return code, (json.loads(out) if out.strip() else None)


# --- the advisory fires ----------------------------------------------------


def test_three_mutating_calls_advise(monkeypatch, capsys):
    code, out = run("gh issue create -t a; gh issue create -t b; gh issue create -t c", monkeypatch, capsys)
    assert code == 0
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"
    assert "gh-api.py" in out["hookSpecificOutput"]["additionalContext"]


def test_and_separated_calls_advise(monkeypatch, capsys):
    code, out = run("gh pr view 1 && gh pr view 2 && gh pr view 3", monkeypatch, capsys)
    assert out is not None


@pytest.mark.parametrize(
    "command",
    [
        # Each of these was MISSED by the shell version: its count anchored on
        # `(^|[;&|]\s*)gh\s+`, which a wrapper prefix, an env assignment, and a
        # command substitution all defeat.
        pytest.param("time gh api a; time gh api b; time gh api c", id="wrapper-prefix"),
        pytest.param("GH_TOKEN=x gh api a; GH_TOKEN=x gh api b; GH_TOKEN=x gh api c", id="env-assignment"),
        pytest.param("x=$(gh api a); y=$(gh api b); z=$(gh api c)", id="command-substitution"),
        pytest.param("(gh api a); (gh api b); (gh api c)", id="subshell"),
        pytest.param("/opt/homebrew/bin/gh api a; gh api b; gh api c", id="absolute-path"),
    ],
)
def test_shell_version_bypasses_are_caught(command, monkeypatch, capsys):
    _, out = run(command, monkeypatch, capsys)
    assert out is not None, "this form bypassed the shell guard's counter"


# --- the advisory stays quiet ---------------------------------------------


def test_two_calls_are_interactive(monkeypatch, capsys):
    _, out = run("gh pr view 1 && gh pr checks 1", monkeypatch, capsys)
    assert out is None


def test_gh_api_py_is_the_recommendation(monkeypatch, capsys):
    _, out = run("python3 gh-api.py gh issue list; gh-api.py gh pr list; gh-api.py gh api x", monkeypatch, capsys)
    assert out is None


def test_auth_does_not_count_toward_the_batch(monkeypatch, capsys):
    """Two real calls plus an auth check is interactive work, not a batch."""
    _, out = run("gh auth status; gh api a; gh api b", monkeypatch, capsys)
    assert out is None


def test_auth_does_not_exempt_a_real_batch(monkeypatch, capsys):
    """Found by differential fuzzing against the shell version, which bailed on the
    whole command when it saw `gh auth` -- and missed even that bail when the
    separator was a newline, since its anchor class held only ; & |."""
    _, out = run("gh auth status\ngh api a\ngh api b\ngh api c", monkeypatch, capsys)
    assert out is not None


def test_read_only_subcommands_do_not_advise(monkeypatch, capsys):
    _, out = run("gh status; gh version; gh help", monkeypatch, capsys)
    assert out is None


def test_quoted_mention_does_not_count(monkeypatch, capsys):
    """The shell version's sed strippers were defeated by an inner apostrophe."""
    _, out = run(
        "git commit -m \"gh api a; gh api b; gh api c -- it's batch work\"",
        monkeypatch,
        capsys,
    )
    assert out is None


def test_substring_match_is_not_a_call(monkeypatch, capsys):
    _, out = run("ghost api a; highlight api b; gh-other api c", monkeypatch, capsys)
    assert out is None


# --- fail open ------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param("", id="empty"),
        pytest.param("not json at all", id="unparseable"),
        pytest.param("[]", id="not-an-object"),
        pytest.param("{}", id="no-tool-input"),
        pytest.param('{"tool_input": {}}', id="no-command"),
        pytest.param('{"tool_input": null}', id="null-tool-input"),
        pytest.param('{"tool_input": 42}', id="numeric-tool-input"),
    ],
)
def test_unverifiable_payloads_fail_open(raw, monkeypatch, capsys):
    code, out = run(None, monkeypatch, capsys, raw=raw)
    assert code == 0
    assert out is None


def test_bare_string_tool_input_is_read(monkeypatch, capsys):
    """Codex sends tool_input as a string; the guard must still see the command."""
    raw = json.dumps({"tool_input": "gh api a; gh api b; gh api c"})
    _, out = run(None, monkeypatch, capsys, raw=raw)
    assert out is not None


def test_unbalanced_quotes_fail_open(monkeypatch, capsys):
    """shlex raises; the shell would reject this too, so judge nothing."""
    code, out = run("gh api 'unterminated; gh api b; gh api c", monkeypatch, capsys)
    assert code == 0
    assert out is None


def test_never_emits_ask(monkeypatch, capsys):
    """Constitution III: no guard may emit ask, which stalls an autonomous agent."""
    _, out = run("gh api a; gh api b; gh api c", monkeypatch, capsys)
    assert out["hookSpecificOutput"]["permissionDecision"] != "ask"
