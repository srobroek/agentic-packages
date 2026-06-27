"""Tests for manifest.py — module.toml parser and validator.

Import-by-path pattern from test_contracts.py.
Run via: uv run --with pytest pytest -q packages/project-setup/tests/test_manifest.py
"""

from __future__ import annotations

import importlib.util
import sys
import textwrap
from pathlib import Path

import pytest

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


contracts = _load("contracts")
manifest_mod = _load("manifest")

parse_manifest = manifest_mod.parse_manifest
InputType = manifest_mod.InputType
ErrorCode = contracts.ErrorCode


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #
def write_toml(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "module.toml"
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


MINIMAL_VALID = """\
    [meta]
    repository = "github.com/test/repo"
    author = "test"

    [module]
    id = "test-module"
    name = "Test"
    version = "1.0.0"
    description = "A test module"
    reconcile = false
"""


# --------------------------------------------------------------------------- #
# Valid minimal manifest                                                       #
# --------------------------------------------------------------------------- #
def test_valid_minimal_manifest(tmp_path):
    p = write_toml(tmp_path, MINIMAL_VALID)
    m = parse_manifest(p)
    assert m.errors == []
    assert m.id == "test-module"
    assert m.version == "1.0.0"
    assert m.reconcile is False
    assert m.default_enabled is None  # not set → tri-state None


# --------------------------------------------------------------------------- #
# Forbidden fields                                                             #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("forbidden", [
    "priority",
    "title",
    "entrypoint",
    "required_answers",
    "produces",
    "creates",
    "optional_answers",
])
def test_forbidden_top_level_field(tmp_path, forbidden):
    toml = MINIMAL_VALID + f'\n{forbidden} = "bad"\n'
    p = write_toml(tmp_path, toml)
    m = parse_manifest(p)
    codes = [e.error_code for e in m.errors]
    assert ErrorCode.FORBIDDEN_FIELD in codes, (
        f"Expected FORBIDDEN_FIELD for '{forbidden}', got: {codes}"
    )


def test_forbidden_module_level_kind(tmp_path):
    """module-level 'kind' is forbidden — tier is step-scoped."""
    toml = MINIMAL_VALID + '\n[module]\nkind = "python"\n'
    # Appending [module] re-opens the table; write as fresh
    content = """\
        [meta]
        repository = "github.com/test/repo"
        author = "test"

        [module]
        id = "test-module"
        name = "Test"
        version = "1.0.0"
        description = "A test module"
        reconcile = false
        kind = "python"
    """
    p = write_toml(tmp_path, content)
    m = parse_manifest(p)
    codes = [e.error_code for e in m.errors]
    assert ErrorCode.FORBIDDEN_FIELD in codes


# --------------------------------------------------------------------------- #
# Unknown fields                                                               #
# --------------------------------------------------------------------------- #
def test_unknown_top_level_field(tmp_path):
    toml = MINIMAL_VALID + '\nzorblax = "surprise"\n'
    p = write_toml(tmp_path, toml)
    m = parse_manifest(p)
    codes = [e.error_code for e in m.errors]
    assert ErrorCode.UNKNOWN_FIELD in codes


# --------------------------------------------------------------------------- #
# Required meta/module fields                                                  #
# --------------------------------------------------------------------------- #
def test_missing_meta_repository(tmp_path):
    content = """\
        [meta]
        author = "test"

        [module]
        id = "x"
        name = "X"
        version = "1.0.0"
        description = "d"
        reconcile = true
    """
    m = parse_manifest(write_toml(tmp_path, content))
    codes = [e.error_code for e in m.errors]
    assert ErrorCode.MANIFEST_MALFORMED in codes


def test_missing_module_id(tmp_path):
    content = """\
        [meta]
        repository = "github.com/test/repo"
        author = "test"

        [module]
        name = "X"
        version = "1.0.0"
        description = "d"
        reconcile = true
    """
    m = parse_manifest(write_toml(tmp_path, content))
    codes = [e.error_code for e in m.errors]
    assert ErrorCode.MANIFEST_MALFORMED in codes


# --------------------------------------------------------------------------- #
# Input type validation                                                        #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("itype", [
    "string", "text", "int", "bool", "choice", "multichoice", "path", "list"
])
def test_all_valid_input_types(tmp_path, itype):
    choices = 'choices = ["a", "b"]\n' if itype in ("choice", "multichoice") else ""
    default = 'default = "a"\n' if itype == "choice" else ""
    default_mc = 'default = ["a"]\n' if itype == "multichoice" else ""
    content = MINIMAL_VALID + f"""
[[inputs]]
key = "k"
type = "{itype}"
prompt = "p"
required = false
{choices}{default}{default_mc}
"""
    m = parse_manifest(write_toml(tmp_path, content))
    assert m.errors == [], f"Unexpected errors for type '{itype}': {m.errors}"
    assert len(m.inputs) == 1
    assert m.inputs[0].type == InputType(itype)


def test_invalid_input_type(tmp_path):
    content = MINIMAL_VALID + """
[[inputs]]
key = "k"
type = "secret"
prompt = "p"
"""
    m = parse_manifest(write_toml(tmp_path, content))
    codes = [e.error_code for e in m.errors]
    assert ErrorCode.MANIFEST_MALFORMED in codes


# --------------------------------------------------------------------------- #
# choice / multichoice: default ∈ choices                                     #
# --------------------------------------------------------------------------- #
def test_choice_default_not_in_choices(tmp_path):
    content = MINIMAL_VALID + """
[[inputs]]
key = "k"
type = "choice"
prompt = "p"
choices = ["a", "b"]
default = "c"
"""
    m = parse_manifest(write_toml(tmp_path, content))
    codes = [e.error_code for e in m.errors]
    assert ErrorCode.MANIFEST_MALFORMED in codes


def test_choice_default_in_choices(tmp_path):
    content = MINIMAL_VALID + """
[[inputs]]
key = "k"
type = "choice"
prompt = "p"
choices = ["a", "b"]
default = "a"
"""
    m = parse_manifest(write_toml(tmp_path, content))
    assert m.errors == []


def test_multichoice_default_not_all_in_choices(tmp_path):
    content = MINIMAL_VALID + """
[[inputs]]
key = "k"
type = "multichoice"
prompt = "p"
choices = ["a", "b"]
default = ["a", "z"]
"""
    m = parse_manifest(write_toml(tmp_path, content))
    codes = [e.error_code for e in m.errors]
    assert ErrorCode.MANIFEST_MALFORMED in codes


def test_multichoice_default_all_in_choices(tmp_path):
    content = MINIMAL_VALID + """
[[inputs]]
key = "k"
type = "multichoice"
prompt = "p"
choices = ["a", "b"]
default = ["a", "b"]
"""
    m = parse_manifest(write_toml(tmp_path, content))
    assert m.errors == []


def test_choice_missing_choices_list(tmp_path):
    content = MINIMAL_VALID + """
[[inputs]]
key = "k"
type = "choice"
prompt = "p"
"""
    m = parse_manifest(write_toml(tmp_path, content))
    codes = [e.error_code for e in m.errors]
    assert ErrorCode.MANIFEST_MALFORMED in codes


# --------------------------------------------------------------------------- #
# Step validation                                                              #
# --------------------------------------------------------------------------- #
def test_valid_python_step(tmp_path):
    content = MINIMAL_VALID + """
[[steps]]
id = "run"
kind = "python"
"""
    m = parse_manifest(write_toml(tmp_path, content))
    assert m.errors == []
    assert len(m.steps) == 1
    assert m.steps[0].kind == "python"


def test_agent_step_requires_steering(tmp_path):
    content = MINIMAL_VALID + """
[[steps]]
id = "ask"
kind = "agent"
"""
    m = parse_manifest(write_toml(tmp_path, content))
    codes = [e.error_code for e in m.errors]
    assert ErrorCode.MANIFEST_MALFORMED in codes


def test_agent_step_with_steering(tmp_path):
    content = MINIMAL_VALID + """
[[steps]]
id = "ask"
kind = "agent"
steering = "steering/ask.md"
"""
    m = parse_manifest(write_toml(tmp_path, content))
    assert m.errors == []


def test_gate_step_requires_message(tmp_path):
    content = MINIMAL_VALID + """
[[steps]]
id = "confirm"
kind = "gate"
"""
    m = parse_manifest(write_toml(tmp_path, content))
    codes = [e.error_code for e in m.errors]
    assert ErrorCode.MANIFEST_MALFORMED in codes


def test_gate_step_with_message(tmp_path):
    content = MINIMAL_VALID + """
[[steps]]
id = "confirm"
kind = "gate"
message = "Are you sure?"
"""
    m = parse_manifest(write_toml(tmp_path, content))
    assert m.errors == []


def test_invalid_step_kind(tmp_path):
    content = MINIMAL_VALID + """
[[steps]]
id = "run"
kind = "shell"
"""
    m = parse_manifest(write_toml(tmp_path, content))
    codes = [e.error_code for e in m.errors]
    assert ErrorCode.MANIFEST_MALFORMED in codes


# --------------------------------------------------------------------------- #
# default_enabled tri-state                                                    #
# --------------------------------------------------------------------------- #
def test_default_enabled_true(tmp_path):
    content = """\
        [meta]
        repository = "github.com/test/repo"
        author = "test"

        [module]
        id = "test-mod"
        name = "Test"
        version = "1.0.0"
        description = "d"
        reconcile = false
        default_enabled = true
    """
    m = parse_manifest(write_toml(tmp_path, content))
    assert m.errors == []
    assert m.default_enabled is True


def test_default_enabled_false(tmp_path):
    content = """\
        [meta]
        repository = "github.com/test/repo"
        author = "test"

        [module]
        id = "test-mod"
        name = "Test"
        version = "1.0.0"
        description = "d"
        reconcile = false
        default_enabled = false
    """
    m = parse_manifest(write_toml(tmp_path, content))
    assert m.errors == []
    assert m.default_enabled is False


def test_default_enabled_absent(tmp_path):
    m = parse_manifest(write_toml(tmp_path, MINIMAL_VALID))
    assert m.default_enabled is None


# --------------------------------------------------------------------------- #
# Multiple errors accumulate                                                   #
# --------------------------------------------------------------------------- #
def test_multiple_errors_accumulate(tmp_path):
    """Both FORBIDDEN_FIELD and UNKNOWN_FIELD appear in the same parse."""
    content = """\
        [meta]
        repository = "github.com/test/repo"
        author = "test"

        [module]
        id = "test-mod"
        name = "Test"
        version = "1.0.0"
        description = "d"
        reconcile = false

        priority = 1
        zorblax = "surprise"
    """
    m = parse_manifest(write_toml(tmp_path, content))
    codes = {e.error_code for e in m.errors}
    assert ErrorCode.FORBIDDEN_FIELD in codes
    assert ErrorCode.UNKNOWN_FIELD in codes
