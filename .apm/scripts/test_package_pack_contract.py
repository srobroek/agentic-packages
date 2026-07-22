"""Regression tests for package dry-run and deterministic file selection."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[2]
PACKAGES = ("orchestrate", "pr-shepherd", "release-queue-watch", "beads")
PYTHON_PACKAGES = ("orchestrate", "pr-shepherd")


def _copy_package(tmp_path: Path, name: str) -> Path:
    destination = tmp_path / name
    shutil.copytree(
        ROOT / "packages" / name,
        destination,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    return destination


def _pack(package: Path) -> str:
    environment = os.environ.copy()
    environment["NO_COLOR"] = "1"
    result = subprocess.run(
        ["apm", "pack", "--dry-run", "--offline"],
        cwd=package,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout + result.stderr


@pytest.mark.parametrize("package_name", PACKAGES)
def test_supported_package_target_dry_run_succeeds(tmp_path: Path, package_name: str):
    output = _pack(_copy_package(tmp_path, package_name))
    assert "deprecated" not in output
    assert "Nothing to pack" not in output


@pytest.mark.parametrize("package_name", PYTHON_PACKAGES)
def test_python_test_residue_does_not_change_package_contents(
    tmp_path: Path, package_name: str
):
    package = _copy_package(tmp_path, package_name)
    clean_output = _pack(package)

    for scripts_dir in package.glob(".apm/**/scripts"):
        residue = scripts_dir / "__pycache__" / "residue.cpython-313.pyc"
        residue.parent.mkdir()
        residue.write_bytes(b"test residue")

    tested_output = _pack(package)
    assert tested_output == clean_output
    assert "__pycache__" not in tested_output
    assert ".pyc" not in tested_output
