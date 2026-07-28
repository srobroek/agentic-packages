"""Coverage for the speckit PR-title advisory.

The advisory is always-on: a PR title is a changelog entry after squash merge, so
it has to read for end users. This only advises, never denies, which means its
false-positive cost is a paragraph of context rather than a blocked command -- but a
hook that fires outside a SpecKit project would produce noise on every repo the
package is installed in.

The negative cases prove it stays silent on: a non-speckit project, a non-PR
command, a read-only `gh pr list`, and any malformed input.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

GUARD = Path(__file__).resolve().parent.parent / "scripts" / "speckit-pr-title.py"


@pytest.fixture
def speckit_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A directory with .specify/ so the guard recognises it as a speckit project."""
    (tmp_path / ".specify").mkdir()
    monkeypatch.chdir(tmp_path)
    return tmp_path


def run_guard(command: str) -> tuple[int, str | None]:
    payload = json.dumps({"tool_input": {"command": command}})
    result = subprocess.run(
        [sys.executable, str(GUARD)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if not result.stdout.strip():
        return result.returncode, None
    return result.returncode, json.loads(result.stdout)["hookSpecificOutput"].get(
        "additionalContext", ""
    )


def test_gh_pr_create_emits_title_guidance(speckit_project: Path) -> None:
    code, advisory = run_guard("gh pr create --fill")

    assert code == 0
    assert advisory is not None
    assert "CHANGELOG ENTRY" in advisory
    assert "feat!" in advisory  # the breaking-change example


def test_gh_pr_edit_emits_title_guidance(speckit_project: Path) -> None:
    _, advisory = run_guard('gh pr edit 5 --title "feat: x"')

    assert advisory is not None
    assert "TITLE FORMAT" in advisory


def test_gh_pr_list_stays_silent(speckit_project: Path) -> None:
    _, advisory = run_guard("gh pr list")

    assert advisory is None


def test_a_non_speckit_project_stays_silent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No .specify/ means no speckit project, so no guidance applies."""
    monkeypatch.chdir(tmp_path)  # no .specify here

    _, advisory = run_guard("gh pr create --fill")

    assert advisory is None


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param("", id="empty"),
        pytest.param("not json", id="malformed"),
        pytest.param('{"tool_input": null}', id="null"),
    ],
)
def test_an_unusable_payload_allows(payload: str, speckit_project: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(GUARD)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0
    assert not result.stdout.strip()


def test_a_string_tool_input_is_read(speckit_project: Path) -> None:
    payload = json.dumps({"tool_input": "gh pr create --fill"})
    result = subprocess.run(
        [sys.executable, str(GUARD)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0
    assert "CHANGELOG" in result.stdout


def test_the_guidance_covers_body_format(speckit_project: Path) -> None:
    """The body format section is the actionable part for the model."""
    _, advisory = run_guard("gh pr create --fill")

    assert "## Summary" in advisory
    assert "Breaking changes" in advisory
