"""Tests for mode.py — detect_mode (init vs reproduce).

Run via: uv run --with pytest pytest -q packages/project-setup/tests/test_mode.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_RUNNER = Path(__file__).resolve().parents[1] / "skills" / "project-setup" / "runner"


def _load(name: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _RUNNER / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


mode_mod = _load("mode")
detect_mode = mode_mod.detect_mode


# --------------------------------------------------------------------------- #
# init mode                                                                    #
# --------------------------------------------------------------------------- #
def test_detect_mode_returns_init_when_no_sources_toml(tmp_path):
    assert detect_mode(tmp_path) == "init"


def test_detect_mode_returns_init_when_project_setup_dir_missing(tmp_path):
    # .project-setup/ dir doesn't exist at all
    assert detect_mode(tmp_path) == "init"


def test_detect_mode_returns_init_when_project_setup_dir_exists_but_no_sources_toml(tmp_path):
    (tmp_path / ".project-setup").mkdir()
    assert detect_mode(tmp_path) == "init"


def test_detect_mode_returns_init_for_empty_directory(tmp_path):
    assert detect_mode(tmp_path) == "init"


# --------------------------------------------------------------------------- #
# reproduce mode                                                               #
# --------------------------------------------------------------------------- #
def test_detect_mode_returns_reproduce_when_sources_toml_present(tmp_path):
    psd = tmp_path / ".project-setup"
    psd.mkdir()
    (psd / "sources.toml").write_text("[meta]\nskill_version = '0.1.0'\n")
    assert detect_mode(tmp_path) == "reproduce"


def test_detect_mode_reproduce_with_empty_sources_toml(tmp_path):
    psd = tmp_path / ".project-setup"
    psd.mkdir()
    (psd / "sources.toml").write_bytes(b"")
    assert detect_mode(tmp_path) == "reproduce"


def test_detect_mode_returns_reproduce_regardless_of_answers_toml(tmp_path):
    psd = tmp_path / ".project-setup"
    psd.mkdir()
    (psd / "sources.toml").write_text("[meta]\n")
    (psd / "answers.toml").write_text("[module.foo]\nbar = 'baz'\n")
    assert detect_mode(tmp_path) == "reproduce"


# --------------------------------------------------------------------------- #
# accepts str and Path                                                         #
# --------------------------------------------------------------------------- #
def test_detect_mode_accepts_str_path(tmp_path):
    assert detect_mode(str(tmp_path)) == "init"


def test_detect_mode_accepts_path_object(tmp_path):
    psd = tmp_path / ".project-setup"
    psd.mkdir()
    (psd / "sources.toml").write_text("")
    assert detect_mode(Path(tmp_path)) == "reproduce"
