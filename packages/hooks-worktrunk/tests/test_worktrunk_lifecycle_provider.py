from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1]
PROVIDER = PACKAGE / "scripts" / "worktrunk-lifecycle-provider.sh"
# Absolute: one case runs with a PATH that deliberately holds no interpreter.
BASH = shutil.which("bash") or "/bin/bash"


@pytest.fixture
def wt_stub(tmp_path: Path) -> tuple[str, Path]:
    """A `wt` on PATH that logs its argv and answers `switch` with a JSON path."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "wt.log"
    created = tmp_path / "worktrees" / "feat-auth"
    stub = bin_dir / "wt"
    stub.write_text(
        "#!/bin/sh\n"
        f'printf "%s\\n" "$*" >> "{log}"\n'
        'if [ "$1" = "switch" ]; then\n'
        f'  printf \'{{"path":"{created}"}}\\n\'\n'
        "fi\n"
    )
    stub.chmod(0o755)
    return f"{bin_dir}:{os.environ.get('PATH', '')}", log


def run_provider(payload: object, path: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [BASH, str(PROVIDER)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env={**os.environ, "PATH": path},
        check=False,
    )


def test_create_routes_through_wt_switch_and_prints_the_path(wt_stub: tuple[str, Path]) -> None:
    path, log = wt_stub
    result = run_provider(
        {"hook_event_name": "WorktreeCreate", "name": "feat/auth"},
        path,
    )
    assert result.returncode == 0, result.stderr
    assert log.read_text().strip() == "switch --create feat/auth --no-cd --format=json"
    assert result.stdout.strip().endswith("/worktrees/feat-auth")


def test_remove_routes_through_wt_remove_foreground(wt_stub: tuple[str, Path]) -> None:
    path, log = wt_stub
    result = run_provider(
        {"hook_event_name": "WorktreeRemove", "worktree_path": "/tmp/wt/feat-auth"},
        path,
    )
    assert result.returncode == 0, result.stderr
    assert log.read_text().strip() == "remove --foreground /tmp/wt/feat-auth"


def test_missing_name_aborts_without_calling_wt(wt_stub: tuple[str, Path]) -> None:
    path, log = wt_stub
    result = run_provider({"hook_event_name": "WorktreeCreate"}, path)
    assert result.returncode != 0
    assert not log.exists()


def test_other_events_are_ignored(wt_stub: tuple[str, Path]) -> None:
    path, log = wt_stub
    result = run_provider({"hook_event_name": "SessionEnd"}, path)
    assert result.returncode == 0
    assert result.stdout == ""
    assert not log.exists()


def test_absent_wt_binary_is_silent(tmp_path: Path) -> None:
    empty_bin = tmp_path / "empty"
    empty_bin.mkdir()
    result = run_provider(
        {"hook_event_name": "WorktreeCreate", "name": "feat/auth"},
        str(empty_bin),
    )
    assert result.returncode == 0
    assert result.stdout == ""
