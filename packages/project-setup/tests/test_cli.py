"""Tests for cli.py — entry point with uv preflight + argparse.

Key cases:
- uv missing → exit non-zero + clear install instruction on stderr
- --dry-run flag wired through to pipeline
- --project-dir normalisation
- --non-interactive flag
- missing project dir → exit 1
- help flag (basic smoke)

Import strategy: cli.py calls _check_uv() at module import time, so tests
that need to simulate uv-missing must patch shutil.which BEFORE importing cli.
We therefore load cli.py fresh per test via importlib so each test gets a
clean module with no side-effects from the top-level _check_uv() call.

Run via: uv run --with pytest pytest -q packages/project-setup/tests/test_cli.py
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_RUNNER = Path(__file__).resolve().parents[1] / "skills" / "project-setup" / "runner"
_CLI_PATH = _RUNNER / "cli.py"


def _load_cli_fresh():
    """Load cli.py into a fresh module object (bypasses caching)."""
    # Give the fresh module a unique name to avoid sys.modules caching conflicts
    name = f"cli_fresh_{id(object())}"
    spec = importlib.util.spec_from_file_location(name, _CLI_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    # Register under the fresh name and also as "cli" so sibling imports work
    sys.modules[name] = mod
    sys.modules["cli"] = mod
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------- #
# uv missing → hard fail                                                       #
# --------------------------------------------------------------------------- #
def test_uv_missing_exits_nonzero(tmp_path, capsys):
    """If uv is not on PATH, cli exits non-zero with an install instruction."""
    with patch("shutil.which", return_value=None):
        with pytest.raises(SystemExit) as exc_info:
            # Force reload under patched shutil.which
            if "cli" in sys.modules:
                del sys.modules["cli"]
            _load_cli_fresh()
    assert exc_info.value.code != 0


def test_uv_missing_prints_install_instruction(tmp_path, capsys):
    """The uv-missing message includes an install URL."""
    with patch("shutil.which", return_value=None):
        with pytest.raises(SystemExit):
            if "cli" in sys.modules:
                del sys.modules["cli"]
            _load_cli_fresh()
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "uv" in combined.lower()
    assert "install" in combined.lower() or "astral.sh" in combined.lower()


# --------------------------------------------------------------------------- #
# --project-dir                                                                #
# --------------------------------------------------------------------------- #
def test_missing_project_dir_exits_1(tmp_path, capsys):
    """A non-existent --project-dir results in exit code 1."""
    if shutil.which("uv") is None:
        pytest.skip("uv not available; this test needs uv to import cli")

    cli = _load_cli_fresh()
    nonexistent = tmp_path / "does-not-exist"
    code = cli.main(["--project-dir", str(nonexistent)])
    assert code == 1


def test_valid_project_dir_accepted(tmp_path):
    """A valid --project-dir does not raise on argparse level."""
    if shutil.which("uv") is None:
        pytest.skip("uv not available")

    cli = _load_cli_fresh()

    # We stub run_pipeline to avoid running the real pipeline
    mock_result = MagicMock()
    mock_result.success = True
    mock_result.errors = []

    with patch.object(cli, "run_pipeline", return_value=mock_result):
        code = cli.main(["--project-dir", str(tmp_path), "--non-interactive", "--dry-run"])
    assert code == 0


# --------------------------------------------------------------------------- #
# --dry-run wired through                                                      #
# --------------------------------------------------------------------------- #
def test_dry_run_flag_passed_to_pipeline(tmp_path):
    """--dry-run is forwarded as dry_run=True to run_pipeline."""
    if shutil.which("uv") is None:
        pytest.skip("uv not available")

    cli = _load_cli_fresh()
    captured_kwargs = {}

    def fake_pipeline(project_dir, io, **kwargs):
        captured_kwargs.update(kwargs)
        result = MagicMock()
        result.success = True
        result.errors = []
        return result

    with patch.object(cli, "run_pipeline", side_effect=fake_pipeline):
        cli.main(["--project-dir", str(tmp_path), "--dry-run", "--non-interactive"])

    assert captured_kwargs.get("dry_run") is True


def test_non_interactive_flag_passed_to_pipeline(tmp_path):
    """--non-interactive is forwarded as non_interactive=True to run_pipeline."""
    if shutil.which("uv") is None:
        pytest.skip("uv not available")

    cli = _load_cli_fresh()
    captured_kwargs = {}

    def fake_pipeline(project_dir, io, **kwargs):
        captured_kwargs.update(kwargs)
        result = MagicMock()
        result.success = True
        result.errors = []
        return result

    with patch.object(cli, "run_pipeline", side_effect=fake_pipeline):
        cli.main(["--project-dir", str(tmp_path), "--non-interactive"])

    assert captured_kwargs.get("non_interactive") is True


# --------------------------------------------------------------------------- #
# pipeline errors surface as exit 1                                           #
# --------------------------------------------------------------------------- #
def test_pipeline_failure_returns_exit_1(tmp_path, capsys):
    """When run_pipeline returns success=False, main() returns 1."""
    if shutil.which("uv") is None:
        pytest.skip("uv not available")

    cli = _load_cli_fresh()

    mock_result = MagicMock()
    mock_result.success = False

    # Need a SetupError-like object
    err = MagicMock()
    err.how_to_fix = "fix it"
    mock_result.errors = [err]

    with patch.object(cli, "run_pipeline", return_value=mock_result):
        code = cli.main(["--project-dir", str(tmp_path), "--non-interactive"])

    assert code == 1


# --------------------------------------------------------------------------- #
# --skill-version                                                              #
# --------------------------------------------------------------------------- #
def test_skill_version_flag_passed_to_pipeline(tmp_path):
    if shutil.which("uv") is None:
        pytest.skip("uv not available")

    cli = _load_cli_fresh()
    captured_kwargs = {}

    def fake_pipeline(project_dir, io, **kwargs):
        captured_kwargs.update(kwargs)
        result = MagicMock()
        result.success = True
        result.errors = []
        return result

    with patch.object(cli, "run_pipeline", side_effect=fake_pipeline):
        cli.main(["--project-dir", str(tmp_path), "--skill-version", "1.2.3", "--non-interactive"])

    assert captured_kwargs.get("skill_version") == "1.2.3"
