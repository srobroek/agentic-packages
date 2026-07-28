"""Coverage for the chezmoi write advisory.

The guard exists for a silent failure: a chezmoi-managed target is a real file, not
a symlink to its source, so a direct edit succeeds and is then reverted by the next
`chezmoi apply` with no error and no diff.

Membership is faked here rather than shelling out to chezmoi, so the tests describe
the guard's logic instead of the machine's dotfile state.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

GUARD = Path(__file__).resolve().parent.parent / "scripts" / "chezmoi-guard.py"

MANAGED = "/home/tester/.claude/settings.json"
UNMANAGED = "/home/tester/projects/notes.md"


@pytest.fixture
def fake_chezmoi(tmp_path: Path) -> dict[str, str]:
    """A PATH holding a `chezmoi` that reports one managed file."""
    binary = tmp_path / "bin"
    binary.mkdir()
    stub = binary / "chezmoi"
    stub.write_text(f'#!/bin/sh\nprintf "%s\\n" "{MANAGED}"\n')
    stub.chmod(0o755)

    environment = dict(os.environ)
    environment["PATH"] = f"{binary}:{environment['PATH']}"
    # A fresh cache directory per test, so one test's membership list cannot be read
    # by the next and the TTL never leaks across cases.
    cache = tmp_path / "cache"
    cache.mkdir()
    environment["TMPDIR"] = str(cache)
    environment["HOME"] = "/home/tester"
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


def advisory(output: str) -> str:
    if not output:
        return ""
    return json.loads(output)["hookSpecificOutput"]["additionalContext"]


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({"tool_name": "Edit", "tool_input": {"file_path": MANAGED}}, id="edit"),
        pytest.param({"tool_name": "Write", "tool_input": {"file_path": MANAGED}}, id="write"),
        pytest.param(
            {"tool_name": "MultiEdit", "tool_input": {"file_path": MANAGED}}, id="multiedit"
        ),
        pytest.param({"tool_name": "Edit", "tool_input": {"path": MANAGED}}, id="path-key"),
        # A bare string tool_input is ambiguous, and the contract calls out that it
        # must not silently bypass the guard.
        pytest.param({"tool_name": "Edit", "tool_input": MANAGED}, id="string-tool-input"),
        # `~` and `..` must resolve, or a managed path dodges an exact comparison.
        pytest.param(
            {"tool_name": "Edit", "tool_input": {"file_path": "~/.claude/settings.json"}},
            id="tilde",
        ),
        pytest.param(
            {
                "tool_name": "Edit",
                "tool_input": {"file_path": "/home/tester/.claude/../.claude/settings.json"},
            },
            id="traversal",
        ),
        # Codex sends the whole patch, so the file headers are parsed directly.
        pytest.param(
            {
                "tool_name": "apply_patch",
                "tool_input": {"command": f"*** Update File: {MANAGED}\n@@\n-a\n+b\n"},
            },
            id="apply-patch",
        ),
    ],
)
def test_a_managed_target_is_advised(payload: dict, fake_chezmoi: dict[str, str]) -> None:
    code, output = run_guard(payload, fake_chezmoi)

    assert code == 0
    assert output, "a managed write must produce an advisory"
    decision = json.loads(output)["hookSpecificOutput"]
    assert decision["permissionDecision"] == "allow", "the advisory must never block"
    assert "chezmoi apply" in advisory(output)


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({"tool_name": "Edit", "tool_input": {"file_path": UNMANAGED}}, id="unmanaged"),
        pytest.param({"tool_name": "Edit", "tool_input": {}}, id="no-path"),
        pytest.param({"tool_name": "Edit"}, id="no-tool-input"),
        pytest.param({}, id="empty-object"),
        # A managed path INSIDE a patch body, but not as a file header, is not a
        # write target.
        pytest.param(
            {
                "tool_name": "apply_patch",
                "tool_input": {"command": f"*** Update File: /tmp/x\n@@\n-see {MANAGED}\n"},
            },
            id="managed-path-in-patch-body",
        ),
        # A parent directory of a managed file is not itself a managed target.
        # Walking parents flagged every file beneath a managed directory.
        pytest.param(
            {"tool_name": "Edit", "tool_input": {"file_path": "/home/tester/.claude/other.json"}},
            id="sibling-under-a-managed-dir",
        ),
    ],
)
def test_ordinary_writes_are_silent(payload: dict, fake_chezmoi: dict[str, str]) -> None:
    code, output = run_guard(payload, fake_chezmoi)

    assert code == 0
    assert not output, f"unexpected advisory for: {payload}"


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param("", id="empty"),
        pytest.param("not json", id="malformed"),
        pytest.param("[]", id="not-an-object"),
        pytest.param('{"tool_input": null}', id="null-tool-input"),
        pytest.param('{"tool_input": 5}', id="numeric-tool-input"),
    ],
)
def test_an_unusable_payload_fails_open(payload: str, fake_chezmoi: dict[str, str]) -> None:
    code, output = run_guard(payload, fake_chezmoi)

    assert code == 0
    assert not output


def test_without_chezmoi_the_guard_is_silent(tmp_path: Path) -> None:
    """Membership is undecidable, so the guard says nothing rather than guessing."""
    empty = tmp_path / "bin"
    empty.mkdir()
    environment = dict(os.environ)
    environment["PATH"] = str(empty)
    environment["HOME"] = "/home/tester"

    code, output = run_guard(
        {"tool_name": "Edit", "tool_input": {"file_path": MANAGED}}, environment
    )

    assert code == 0
    assert not output


def test_the_membership_list_is_cached(fake_chezmoi: dict[str, str], tmp_path: Path) -> None:
    """`chezmoi managed` costs about 220ms, too much to pay per tool call."""
    payload = {"tool_name": "Edit", "tool_input": {"file_path": MANAGED}}
    run_guard(payload, fake_chezmoi)

    caches = list(Path(fake_chezmoi["TMPDIR"]).glob("chezmoi-managed-cache.*"))
    assert len(caches) == 1, "the managed list should be cached on disk"
    assert MANAGED in caches[0].read_text()

    # A second call still advises, now from the cache rather than a fresh spawn.
    _, output = run_guard(payload, fake_chezmoi)
    assert output
