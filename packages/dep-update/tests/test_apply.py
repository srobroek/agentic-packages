#!/usr/bin/env python3
"""Tests for dep-update's apply.py post-apply verification.

tests/dep-update.bats drives apply.py end to end with stub package managers and
remains the integration oracle. This module covers the two verification defects
the port fixed, which that suite does not pin, plus the manifest shapes each
check has to read.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / ".apm/skills/dep-update/scripts/apply.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("apply_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


apply_mod = _load()


def test_script_is_committed_executable():
    assert SCRIPT.stat().st_mode & 0o111


# --- check_python_version ---------------------------------------------------


def test_python_check_confirms_exact_pep621_pin(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "d"\ndependencies = ["requests==2.32.3"]\n'
    )
    assert apply_mod.check_python_version(tmp_path, "requests", "2.32.3")


def test_python_check_rejects_a_different_version(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "d"\ndependencies = ["requests==2.31.0"]\n'
    )
    assert not apply_mod.check_python_version(tmp_path, "requests", "2.32.3")


def test_python_check_does_not_treat_the_name_as_a_regex(tmp_path):
    """DEFECT: `grep -qiE "\\"${name}==${ver}\\""` left the name unescaped, so
    every `.` was a wildcard and `ruamel.yaml` confirmed against `ruamelXyaml`.
    """
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "d"\ndependencies = ["ruamelXyaml==0.18.6"]\n'
    )
    assert not apply_mod.check_python_version(tmp_path, "ruamel.yaml", "0.18.6")


def test_python_check_does_not_treat_the_version_as_a_regex(tmp_path):
    """DEFECT: the version was unescaped too, so `1.2.3` matched `1x2x3`."""
    (tmp_path / "requirements.txt").write_text("pkg==1x2x3\n")
    assert not apply_mod.check_python_version(tmp_path, "pkg", "1.2.3")


@pytest.mark.parametrize("spelling", ["ruamel-yaml", "ruamel_yaml", "Ruamel.YAML"])
def test_python_check_folds_pep503_equivalent_names(tmp_path, spelling):
    """`.`, `-`, `_` and case all fold to one project name on PyPI, so a
    manifest that spells it differently is still the package that was bumped.
    """
    (tmp_path / "requirements.txt").write_text(f"{spelling}==0.18.6\n")
    assert apply_mod.check_python_version(tmp_path, "ruamel.yaml", "0.18.6")


def test_python_check_reads_optional_and_group_dependencies(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "d"\n'
        '[project.optional-dependencies]\ndev = ["pytest==8.3.2"]\n'
    )
    assert apply_mod.check_python_version(tmp_path, "pytest", "8.3.2")


def test_python_check_ignores_extras_and_markers_on_the_pin(tmp_path):
    (tmp_path / "requirements.txt").write_text(
        'uvicorn[standard]==0.30.6; python_version >= "3.9"\n'
    )
    assert apply_mod.check_python_version(tmp_path, "uvicorn", "0.30.6")


def test_python_check_reads_uv_lock(tmp_path):
    (tmp_path / "uv.lock").write_text(
        '[[package]]\nname = "fastapi"\nversion = "0.111.0"\n'
    )
    assert apply_mod.check_python_version(tmp_path, "fastapi", "0.111.0")
    assert not apply_mod.check_python_version(tmp_path, "fastapi", "0.112.0")


def test_python_check_without_any_manifest_is_unconfirmed(tmp_path):
    assert not apply_mod.check_python_version(tmp_path, "requests", "2.32.3")


def test_python_check_on_malformed_toml_is_unconfirmed(tmp_path):
    """Fail closed on the VERDICT, not on the process: an unreadable manifest
    cannot confirm a bump, and the caller reports a mismatch rather than crashing.
    """
    (tmp_path / "pyproject.toml").write_text("[project\nbroken")
    assert not apply_mod.check_python_version(tmp_path, "requests", "2.32.3")


# --- check_node_version -----------------------------------------------------


@pytest.mark.parametrize("prefix", ["", "^", "~", "="])
def test_node_check_accepts_exact_caret_tilde_and_equals(tmp_path, prefix):
    (tmp_path / "package.json").write_text(
        json.dumps({"dependencies": {"express": f"{prefix}4.18.3"}})
    )
    assert apply_mod.check_node_version(tmp_path, "express", "4.18.3")


def test_node_check_rejects_a_substring_version_match(tmp_path):
    """DEFECT: the check accepted `ver in v`, so bumping to `1.2` "confirmed"
    against an unchanged `^1.20.0`.
    """
    (tmp_path / "package.json").write_text(
        json.dumps({"dependencies": {"express": "^1.20.0"}})
    )
    assert not apply_mod.check_node_version(tmp_path, "express", "1.2")


def test_node_check_rejects_a_longer_version_sharing_a_prefix(tmp_path):
    (tmp_path / "package.json").write_text(
        json.dumps({"dependencies": {"express": "^1.2.3"}})
    )
    assert not apply_mod.check_node_version(tmp_path, "express", "1.2")


def test_node_check_reads_every_dependency_section(tmp_path):
    (tmp_path / "package.json").write_text(
        json.dumps({"optionalDependencies": {"fsevents": "2.3.3"}})
    )
    assert apply_mod.check_node_version(tmp_path, "fsevents", "2.3.3")


def test_node_check_on_malformed_json_is_unconfirmed(tmp_path):
    (tmp_path / "package.json").write_text("{not json")
    assert not apply_mod.check_node_version(tmp_path, "express", "4.18.3")


# --- node package manager detection -----------------------------------------


def test_pm_env_override_wins(tmp_path, monkeypatch):
    monkeypatch.setenv("DEP_UPDATE_PKG_MANAGER", "bun")
    (tmp_path / "pnpm-lock.yaml").write_text("")
    assert apply_mod.detect_node_pm(tmp_path) == "bun"


def test_pm_from_answers_toml_strips_a_version_pin(tmp_path, monkeypatch):
    monkeypatch.delenv("DEP_UPDATE_PKG_MANAGER", raising=False)
    setup = tmp_path / ".project-setup"
    setup.mkdir()
    (setup / "answers.toml").write_text(
        '[module.lang-ts]\npackage_manager = "pnpm@9.1.0"\n'
    )
    assert apply_mod.detect_node_pm(tmp_path) == "pnpm"


def test_pm_falls_back_to_lockfile_when_answers_is_malformed(tmp_path, monkeypatch):
    monkeypatch.delenv("DEP_UPDATE_PKG_MANAGER", raising=False)
    setup = tmp_path / ".project-setup"
    setup.mkdir()
    (setup / "answers.toml").write_text("[module\nbroken")
    (tmp_path / "yarn.lock").write_text("")
    assert apply_mod.detect_node_pm(tmp_path) == "yarn"


@pytest.mark.parametrize(
    ("lockfile", "expected"),
    [
        ("pnpm-lock.yaml", "pnpm"),
        ("bun.lock", "bun"),
        ("bun.lockb", "bun"),
        ("yarn.lock", "yarn"),
    ],
)
def test_pm_from_lockfile(tmp_path, monkeypatch, lockfile, expected):
    monkeypatch.delenv("DEP_UPDATE_PKG_MANAGER", raising=False)
    (tmp_path / lockfile).write_text("")
    assert apply_mod.detect_node_pm(tmp_path) == expected


def test_pm_defaults_to_npm(tmp_path, monkeypatch):
    monkeypatch.delenv("DEP_UPDATE_PKG_MANAGER", raising=False)
    assert apply_mod.detect_node_pm(tmp_path) == "npm"


# --- argument guards --------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [".project-setup/x", "answers.toml", "a/sources.toml"],
)
def test_project_setup_paths_are_refused(tmp_path, name):
    assert apply_mod.main(["apply.py", "pypi", name, "1.0", str(tmp_path)]) == 2


def test_missing_arguments_exit_two(tmp_path):
    assert apply_mod.main(["apply.py", "pypi", "requests"]) == 2


def test_missing_target_directory_exits_two(tmp_path):
    assert (
        apply_mod.main(["apply.py", "pypi", "requests", "1.0", str(tmp_path / "nope")])
        == 2
    )


@pytest.mark.parametrize("ecosystem", ["cargo", "rust", "go"])
def test_advisory_only_ecosystems_exit_zero_without_applying(tmp_path, ecosystem):
    assert (
        apply_mod.main(["apply.py", ecosystem, "serde", "1.0.0", str(tmp_path)]) == 0
    )
    assert list(tmp_path.iterdir()) == []


def test_unknown_ecosystem_exits_zero(tmp_path):
    assert apply_mod.main(["apply.py", "bogus", "x", "1.0", str(tmp_path)]) == 0
