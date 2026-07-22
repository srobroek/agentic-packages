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
PACKABLE_PREFIXES = tuple(
    f".apm/{directory}/"
    for directory in (
        "agents",
        "commands",
        "extensions",
        "hooks",
        "instructions",
        "prompts",
        "rules",
        "skills",
        "steering",
    )
)


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


def _manifest_includes(package_name: str) -> tuple[str, ...]:
    manifest = (ROOT / "packages" / package_name / "apm.yml").read_text(
        encoding="utf-8"
    )
    includes: list[str] = []
    in_includes = False
    for line in manifest.splitlines():
        if line == "includes:":
            in_includes = True
            continue
        if in_includes and line.startswith("  - "):
            includes.append(line.removeprefix("  - "))
            continue
        if in_includes and line and not line.startswith(" "):
            break
    return tuple(includes)


def _tracked_packable_files(package_name: str) -> tuple[str, ...]:
    package_prefix = f"packages/{package_name}/"
    result = subprocess.run(
        ["git", "ls-files", "--", f"{package_prefix}.apm"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    relative = (
        path.removeprefix(package_prefix)
        for path in result.stdout.splitlines()
    )
    return tuple(
        path for path in relative if path.startswith(PACKABLE_PREFIXES)
    )


def _is_covered(path: str, includes: tuple[str, ...]) -> bool:
    return any(
        path == include or path.startswith(f"{include.rstrip('/')}/")
        for include in includes
    )


@pytest.mark.parametrize("package_name", PACKAGES)
def test_supported_package_target_dry_run_succeeds(tmp_path: Path, package_name: str):
    output = _pack(_copy_package(tmp_path, package_name))
    assert "deprecated" not in output
    assert "Nothing to pack" not in output


@pytest.mark.parametrize("package_name", PYTHON_PACKAGES)
def test_explicit_includes_cover_every_tracked_packable_file(package_name: str):
    includes = _manifest_includes(package_name)
    missing = [
        path
        for path in _tracked_packable_files(package_name)
        if not _is_covered(path, includes)
    ]
    assert not missing, (
        f"{package_name}/apm.yml omits tracked packable files:\n  "
        + "\n  ".join(missing)
        + "\nAdd each file to includes or include its intentional source directory."
    )


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
