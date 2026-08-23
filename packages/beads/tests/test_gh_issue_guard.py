"""Coverage for the beads gh-issue deny gate.

The guard refuses a mutating `gh issue` command where a beads workspace is active,
because task state belongs in one store and beads is the one the workflow reads.

It denies, so the cases that matter most are the ones it must let through: a
read-only subcommand, a `gh pr` command, a mention quoted inside a commit message,
and anything at all in a repository with no beads workspace.

`bd` is stubbed on PATH so these describe the guard's logic rather than the
machine's beads state.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

GUARD = Path(__file__).resolve().parent.parent / "scripts" / "beads-gh-issue-guard.py"


@pytest.fixture
def workspace(tmp_path: Path) -> dict:
    """A directory the guard accepts as beads-enabled, plus a stubbed `bd`."""
    work = tmp_path / "work"
    (work / ".beads").mkdir(parents=True)

    binary = tmp_path / "bin"
    binary.mkdir()
    stub = binary / "bd"
    stub.write_text("#!/bin/sh\nexit 0\n")
    stub.chmod(0o755)

    environment = dict(os.environ)
    environment["PATH"] = f"{binary}:{environment['PATH']}"
    return {"cwd": str(work), "env": environment, "bin": binary}


def run_guard(command: str, workspace: dict) -> tuple[int, str | None, str]:
    payload = json.dumps({"cwd": workspace["cwd"], "tool_input": {"command": command}})
    result = subprocess.run(
        [sys.executable, str(GUARD)],
        input=payload,
        capture_output=True,
        text=True,
        env=workspace["env"],
        timeout=30,
    )
    if not result.stdout.strip():
        return result.returncode, None, ""
    out = json.loads(result.stdout)["hookSpecificOutput"]
    return result.returncode, out["permissionDecision"], out.get("permissionDecisionReason", "")


# --- a mutating subcommand is refused ----------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        pytest.param("gh issue create --title x --body y", id="create"),
        pytest.param("gh issue close 42", id="close"),
        pytest.param("gh issue comment 42 --body hi", id="comment"),
        pytest.param("gh issue edit 42 --add-label bug", id="edit"),
        pytest.param("gh issue reopen 42", id="reopen"),
        pytest.param("gh issue develop 42", id="develop"),
        # The verb still sits in command position behind each of these.
        pytest.param("env FOO=1 gh issue close 42", id="behind-an-env-assignment"),
        pytest.param("sudo gh issue close 42", id="behind-a-wrapper"),
        pytest.param("git status && gh issue close 7", id="after-a-separator"),
        pytest.param("x=$(gh issue create --title y)", id="inside-a-substitution"),
        pytest.param("(gh issue close 5)", id="inside-a-subshell"),
        pytest.param("/opt/homebrew/bin/gh issue close 5", id="by-absolute-path"),
        # A flag before the subcommand shifts the operand window: unless the value
        # of `-R` is skipped, `acme/widget` reads as the command group.
        pytest.param("gh -R acme/widget issue close 42", id="behind-a-repo-flag"),
        pytest.param("gh --repo acme/widget issue close 42", id="behind-a-long-repo-flag"),
        pytest.param("gh --repo=acme/widget issue close 42", id="behind-an-attached-value"),
    ],
)
def test_a_mutating_issue_command_is_denied(command: str, workspace: dict) -> None:
    code, decision, reason = run_guard(command, workspace)

    assert code == 0, "the decision travels in JSON, never in the exit code"
    assert decision == "deny"
    assert "bd create" in reason, "a denial must name the replacement, not just refuse"


# --- what must pass ----------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        pytest.param("gh issue list --state open", id="list"),
        pytest.param("gh issue view 42", id="view"),
        pytest.param("gh issue status", id="status"),
        pytest.param("gh pr create --title x --body y", id="pr-not-issue"),
        pytest.param("ls -la", id="unrelated"),
        # Quoted prose is an argument, not a command. Lexing is what separates the
        # two; matching the raw string flagged both.
        pytest.param(
            "git commit -m 'do not gh issue close 42 by hand'", id="single-quoted-mention"
        ),
        pytest.param(
            'git commit -m "gh issue create is banned here"', id="double-quoted-mention"
        ),
        pytest.param('echo "gh issue close 1"', id="echoed-mention"),
    ],
)
def test_ordinary_work_is_allowed(command: str, workspace: dict) -> None:
    code, decision, _ = run_guard(command, workspace)

    assert code == 0
    assert decision is None, f"unexpected denial for: {command}"


# --- fail open ---------------------------------------------------------------


def test_without_a_beads_workspace_nothing_is_denied(workspace: dict) -> None:
    """No workspace means no convention to enforce."""
    stub = workspace["bin"] / "bd"
    stub.write_text("#!/bin/sh\nexit 1\n")
    stub.chmod(0o755)

    _, decision, _ = run_guard("gh issue create --title x", workspace)

    assert decision is None


def test_without_bd_nothing_is_denied(workspace: dict) -> None:
    (workspace["bin"] / "bd").unlink()

    _, decision, _ = run_guard("gh issue create --title x", workspace)

    assert decision is None


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param("", id="empty"),
        pytest.param("not json {", id="malformed"),
        pytest.param("[]", id="not-an-object"),
        pytest.param('{"tool_input": null}', id="null-tool-input"),
        # Unbalanced quotes: the shell would reject this command too.
        pytest.param('{"tool_input":{"command":"gh issue close \'42"}}', id="unbalanced-quotes"),
    ],
)
def test_an_unusable_payload_allows(payload: str, workspace: dict) -> None:
    result = subprocess.run(
        [sys.executable, str(GUARD)],
        input=payload,
        capture_output=True,
        text=True,
        env=workspace["env"],
        timeout=30,
    )

    assert result.returncode == 0
    assert not result.stdout.strip()


def test_a_bare_string_tool_input_is_read(workspace: dict) -> None:
    """The jq idiom this replaced threw on a string and skipped the guard."""
    payload = json.dumps(
        {"cwd": workspace["cwd"], "tool_input": "gh issue create --title x"}
    )
    result = subprocess.run(
        [sys.executable, str(GUARD)],
        input=payload,
        capture_output=True,
        text=True,
        env=workspace["env"],
        timeout=30,
    )

    assert result.returncode == 0
    decision = json.loads(result.stdout)["hookSpecificOutput"]
    assert decision["permissionDecision"] == "deny"


def test_never_emits_ask(workspace: dict) -> None:
    """`ask` waits for a human, which stalls an autonomous run."""
    for command in ("gh issue create --title x", "gh issue list", "ls"):
        _, decision, _ = run_guard(command, workspace)
        assert decision != "ask"
