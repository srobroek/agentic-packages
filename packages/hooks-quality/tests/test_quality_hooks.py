"""Coverage for the two quality advisories and the module they share.

Both hooks are advisory by design, so every case asserts exit 0 and that no
denial is ever produced. What varies is whether anything is said at all, and most
of these tests pin the cases where the answer is nothing: an unrecognised project,
a repository where pre-commit already owns the checks, an edit below the
thresholds. A hook that speaks on every call is one the agent learns to skip.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
EDIT_ADVISORY = SCRIPTS / "quality-edit-advisory.py"

sys.path.insert(0, str(SCRIPTS))

import quality_common  # noqa: E402


def git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        env={
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_SYSTEM": "/dev/null",
            "HOME": str(repo),
            "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        },
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    work = tmp_path / "repo"
    work.mkdir()
    git(work, "init", "-q")
    return work


def invoke(script: Path, payload: dict, cwd: Path, env: dict | None = None) -> tuple[int, dict | None]:
    import os

    # The hook itself must not inherit the host's system git config: on a machine
    # where a corporate wrapper sets core.hooksPath, `git rev-parse --git-path
    # hooks` resolves outside the fixture and the pre-commit deferral check
    # correctly declines to fire, which would look like a hook bug.
    environment = {
        **os.environ,
        "TMPDIR": str(cwd / ".state"),
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_CONFIG_GLOBAL": "/dev/null",
    }
    (cwd / ".state").mkdir(exist_ok=True)
    if env:
        environment.update(env)
    result = subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=cwd,
        env=environment,
        timeout=120,
    )
    decision = json.loads(result.stdout)["hookSpecificOutput"] if result.stdout.strip() else None
    return result.returncode, decision


# --- quality-edit-advisory ----------------------------------------------------


def test_single_small_edit_stays_below_the_threshold(repo: Path) -> None:
    (repo / "go.mod").write_text("module x\n\ngo 1.21\n")
    payload = {"cwd": str(repo), "tool_name": "Edit", "tool_input": {"file_path": "a.go", "new_string": "x\n"}}
    code, decision = invoke(EDIT_ADVISORY, payload, repo)
    assert code == 0
    assert decision is None


def test_codex_patch_payload_is_recognised(repo: Path) -> None:
    """Codex sends the whole patch in tool_input.command rather than a file path."""
    (repo / "go.mod").write_text("module x\n\ngo 1.21\n")
    patch = "*** Update File: x.go\n@@\n-package x\n+package changed\n"
    payload = {"cwd": str(repo), "tool_name": "apply_patch", "tool_input": {"command": patch}}
    code, decision = invoke(
        EDIT_ADVISORY,
        payload,
        repo,
        env={
            "AGENTIC_QUALITY_LANGS": "go",
            "AGENTIC_QUALITY_ADVISORY_LINES": "1",
            "AGENTIC_QUALITY_ADVISORY_COOLDOWN_SECONDS": "0",
        },
    )
    assert code == 0
    assert decision is not None
    assert "QUALITY ADVISORY" in decision["additionalContext"]
    assert decision["hookEventName"] == "PostToolUse"
    assert "permissionDecision" not in decision


def test_advisory_only_names_languages_present_in_the_edits(repo: Path) -> None:
    """A Python-only change must never suggest cargo."""
    (repo / "pyproject.toml").write_text("[project]\nname='x'\n")
    payload = {"cwd": str(repo), "tool_name": "Edit", "tool_input": {"file_path": "a.py", "new_string": "x\n" * 200}}
    _, decision = invoke(
        EDIT_ADVISORY,
        payload,
        repo,
        env={
            "AGENTIC_QUALITY_LANGS": "all",
            "AGENTIC_QUALITY_ADVISORY_LINES": "1",
            "AGENTIC_QUALITY_ADVISORY_COOLDOWN_SECONDS": "0",
        },
    )
    assert decision is not None
    context = decision["additionalContext"]
    assert "ruff" in context
    assert "cargo" not in context


def test_cooldown_suppresses_a_second_advisory(repo: Path) -> None:
    (repo / "pyproject.toml").write_text("[project]\nname='x'\n")
    payload = {"cwd": str(repo), "tool_name": "Edit", "tool_input": {"file_path": "a.py", "new_string": "x\n" * 200}}
    env = {
        "AGENTIC_QUALITY_LANGS": "python",
        "AGENTIC_QUALITY_ADVISORY_LINES": "1",
        "AGENTIC_QUALITY_ADVISORY_COOLDOWN_SECONDS": "3600",
    }
    _, first = invoke(EDIT_ADVISORY, payload, repo, env=env)
    assert first is not None
    _, second = invoke(EDIT_ADVISORY, payload, repo, env=env)
    assert second is None, "a second advisory inside the cooldown is a nag"


# --- both hooks fail open ----------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param("", id="empty"),
        pytest.param("not json", id="malformed"),
        pytest.param('{"tool_input": 42}', id="wrong-type"),
        pytest.param('{"tool_input": {"file_path": null}}', id="null-field"),
    ],
)
def test_unreadable_payload_fails_open(payload: str, tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(EDIT_ADVISORY)],
        input=payload,
        capture_output=True,
        text=True,
        cwd=tmp_path,
        timeout=30,
    )
    assert result.returncode == 0
    assert not result.stdout.strip()


# --- the shared module -------------------------------------------------------


def test_selection_file_wins_over_marker_detection(tmp_path: Path) -> None:
    """An explicit selection lets a polyglot repo opt in per language."""
    (tmp_path / "go.mod").write_text("module x\n")
    (tmp_path / ".agents/hooks").mkdir(parents=True)
    (tmp_path / ".agents/hooks/quality-languages").write_text("python, rust\n")
    assert quality_common.selected_languages(tmp_path) == {"python", "rust"}


def test_markers_detect_languages_when_nothing_is_declared(tmp_path: Path) -> None:
    (tmp_path / "go.mod").write_text("module x\n")
    (tmp_path / "Cargo.toml").write_text("[package]\n")
    assert quality_common.selected_languages(tmp_path) == {"go", "rust"}


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("a.go", "go"),
        ("a.py", "python"),
        ("a.pyi", "python"),
        ("a.rs", "rust"),
        ("Cargo.toml", "rust"),
        ("a.tsx", "ts"),
        ("a.mjs", "ts"),
        ("README.md", None),
        ("Makefile", None),
    ],
)
def test_language_for_file(path: str, expected: str | None) -> None:
    assert quality_common.language_for_file(path) == expected


def test_ts_answers_for_its_aliases() -> None:
    """A repo declaring `typescript` or `javascript` still enables the ts checks."""
    assert quality_common.language_enabled("ts", {"typescript"})
    assert quality_common.language_enabled("ts", {"javascript"})
    assert quality_common.language_enabled("rust", {"all"})
    assert not quality_common.language_enabled("rust", {"python"})


# --- narrowing: do not repeat a gate pre-commit already runs -------------------


def install_precommit(repo: Path, config_body: str) -> None:
    """Give the repository a pre-commit config AND an installed framework hook."""
    (repo / ".pre-commit-config.yaml").write_text(config_body)
    hooks = repo / ".git" / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    hook = hooks / "pre-commit"
    hook.write_text("#!/bin/sh\n# File generated by pre-commit: https://pre-commit.com\n")
    hook.chmod(0o755)


def big_python_edit(repo: Path) -> dict:
    return {
        "cwd": str(repo),
        "tool_name": "Edit",
        "tool_input": {"file_path": "a.py", "new_string": "x\n" * 200},
    }


LOUD = {
    "AGENTIC_QUALITY_LANGS": "all",
    "AGENTIC_QUALITY_ADVISORY_LINES": "1",
    "AGENTIC_QUALITY_ADVISORY_COOLDOWN_SECONDS": "0",
}


def test_language_checked_by_precommit_is_not_advised(repo: Path) -> None:
    """Repeating a gate that runs on its own is the definition of a nag."""
    install_precommit(repo, "repos:\n  - repo: local\n    hooks:\n      - id: ruff\n")
    _, decision = invoke(EDIT_ADVISORY, big_python_edit(repo), repo, env=LOUD)
    assert decision is None


def test_a_gate_for_another_language_does_not_silence_this_one(repo: Path) -> None:
    """A config running rustfmt has said nothing about whether Python is formatted."""
    install_precommit(repo, "repos:\n  - repo: local\n    hooks:\n      - id: rustfmt\n")
    _, decision = invoke(EDIT_ADVISORY, big_python_edit(repo), repo, env=LOUD)
    assert decision is not None
    assert "ruff" in decision["additionalContext"]


def test_a_config_without_the_installed_hook_does_not_silence_anything(repo: Path) -> None:
    """A config alone proves nothing, because nobody may have run the install."""
    (repo / ".pre-commit-config.yaml").write_text(
        "repos:\n  - repo: local\n    hooks:\n      - id: ruff\n"
    )
    _, decision = invoke(EDIT_ADVISORY, big_python_edit(repo), repo, env=LOUD)
    assert decision is not None


def test_a_whitespace_only_config_does_not_silence_anything(repo: Path) -> None:
    """Most real configs check whitespace and YAML, not language formatting."""
    install_precommit(
        repo,
        "repos:\n  - repo: local\n    hooks:\n      - id: trailing-whitespace\n"
        "      - id: check-yaml\n",
    )
    _, decision = invoke(EDIT_ADVISORY, big_python_edit(repo), repo, env=LOUD)
    assert decision is not None
