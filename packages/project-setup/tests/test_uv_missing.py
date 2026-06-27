"""Guardrail test: SC-010 / spec §B2 — uv is a hard prerequisite.

The CLI preflight MUST:
  1. fail with a non-zero exit code when uv is absent from PATH, and
  2. print an install instruction mentioning "uv" to stderr, and
  3. NOT proceed to scaffold anything (no pipeline execution).

Import-by-path; hermetic (no network, no real uv required).

Run: uv run --with pytest pytest -q packages/project-setup/tests/test_uv_missing.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import pytest

_RUNNER = Path(__file__).resolve().parents[1] / "skills" / "project-setup" / "runner"
_CLI_PATH = _RUNNER / "cli.py"


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #

def _load_fresh_cli() -> ModuleType:
    """Load cli.py by file path into an isolated module name.

    cli.py calls _check_uv() at module scope.  To test the preflight we must
    reload it so the top-level call runs under our patched shutil.which.
    We use a unique module name each call so sys.modules caching doesn't
    interfere between tests.
    """
    # Each load gets a unique name to avoid hitting the cached version.
    name = f"_cli_test_{id(object())}"
    spec = importlib.util.spec_from_file_location(name, _CLI_PATH)
    assert spec and spec.loader, "Could not locate cli.py"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    return mod, spec


def _call_main_with_no_uv(tmp_path: Path, capsys) -> int:
    """Patch shutil.which to return None for 'uv', then call cli.main().

    cli.py imports shutil at the top and calls shutil.which("uv") at module
    scope via _check_uv().  Because the module-scope call fires on exec_module,
    we patch shutil.which BEFORE executing the module body.

    Returns the integer exit code (caught via SystemExit or from main()).
    """
    exit_code: int | None = None

    with patch("shutil.which", return_value=None):
        mod, spec = _load_fresh_cli()
        try:
            spec.loader.exec_module(mod)
        except SystemExit as exc:
            exit_code = int(exc.code) if exc.code is not None else 1

    return exit_code


# --------------------------------------------------------------------------- #
# Tests                                                                        #
# --------------------------------------------------------------------------- #

def test_preflight_exits_nonzero_when_uv_missing(tmp_path, capsys):
    """Exit code MUST be non-zero when uv is absent."""
    exit_code = _call_main_with_no_uv(tmp_path, capsys)
    assert exit_code is not None, "Expected SystemExit but the module ran to completion"
    assert exit_code != 0, f"Expected non-zero exit, got {exit_code}"


def test_preflight_prints_install_instruction_to_stderr_when_uv_missing(
    tmp_path, capsys
):
    """stderr output MUST mention 'uv' and include an install instruction."""
    _call_main_with_no_uv(tmp_path, capsys)
    captured = capsys.readouterr()
    stderr = captured.err

    assert stderr, "Expected error output on stderr but got nothing"
    # The contract says an install instruction mentioning uv must be printed.
    assert "uv" in stderr.lower() or "uv" in stderr, (
        f"stderr does not mention 'uv': {stderr!r}"
    )
    # At least one of the canonical install methods must appear.
    has_instruction = any(
        keyword in stderr
        for keyword in ("install", "brew", "curl", "pip", "https://")
    )
    assert has_instruction, (
        f"stderr does not contain an install instruction: {stderr!r}"
    )


def test_preflight_does_not_proceed_to_scaffold_when_uv_missing(tmp_path, capsys):
    """The pipeline MUST NOT execute when uv is missing.

    We verify this by asserting that the module-scope _check_uv() raises
    SystemExit BEFORE any pipeline imports or invocations can occur.
    The cli.py body imports pipeline and io_adapter AFTER the _check_uv()
    call, so if we get a SystemExit before exec_module returns, we know
    nothing downstream ran.
    """
    pipeline_imported = []

    original_spec_from_file = importlib.util.spec_from_file_location

    def tracking_spec(name, path, *args, **kwargs):
        if "pipeline" in str(name) or "pipeline" in str(path):
            pipeline_imported.append(name)
        return original_spec_from_file(name, path, *args, **kwargs)

    with patch("shutil.which", return_value=None):
        with patch("importlib.util.spec_from_file_location", side_effect=tracking_spec):
            mod, spec = _load_fresh_cli()
            try:
                spec.loader.exec_module(mod)
            except SystemExit:
                pass  # expected

    assert not pipeline_imported, (
        "pipeline module was imported even though uv was missing — "
        "the preflight did not abort early enough"
    )


def test_no_stdlib_fallback_path(tmp_path, capsys):
    """There is NO stdlib fallback path: the process must exit, not continue.

    If uv is absent, _check_uv() calls sys.exit(1). This means exec_module
    raises SystemExit and never returns normally. Assert that we always get
    the exit, never a clean return.
    """
    got_system_exit = False

    with patch("shutil.which", return_value=None):
        mod, spec = _load_fresh_cli()
        try:
            spec.loader.exec_module(mod)
        except SystemExit as exc:
            got_system_exit = True
            assert int(exc.code) != 0, "SystemExit code must be non-zero"

    assert got_system_exit, (
        "Expected SystemExit when uv is missing, but exec_module returned "
        "normally — the stdlib fallback path must not exist"
    )
