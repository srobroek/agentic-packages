"""Tests for validate.py — the validate-closed gate.

Key assertion: ALL problems (cycle + missing-requires + missing-answer +
missing-tool) are accumulated and raised together in ONE GateFailure.

Import-by-path pattern from test_contracts.py.
Run via: uv run --with pytest pytest -q packages/project-setup/tests/test_validate.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

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
validate_mod = _load("validate")

validate_closed = validate_mod.validate_closed
GateFailure = contracts.GateFailure
ErrorCode = contracts.ErrorCode


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #
def make_input(key, required=True):
    return SimpleNamespace(key=key, required=required)


def make_manifest(
    id: str,
    requires=(),
    after=(),
    before=(),
    required_inputs=(),
    required_tools=(),
):
    return SimpleNamespace(
        id=id,
        order={
            "requires": list(requires),
            "after": list(after),
            "before": list(before),
        },
        tools={"required": list(required_tools)},
        inputs=[make_input(k, required=True) for k in required_inputs],
    )


# --------------------------------------------------------------------------- #
# Happy path — returns ordered ids                                            #
# --------------------------------------------------------------------------- #
def test_validate_closed_happy_path():
    manifests = [make_manifest("a"), make_manifest("b", requires=["a"])]
    answers = {"a": {}, "b": {}}
    ordered = validate_closed(manifests, answers)
    assert ordered == ["a", "b"]


# --------------------------------------------------------------------------- #
# Missing answer                                                               #
# --------------------------------------------------------------------------- #
def test_missing_required_answer_raises():
    m = make_manifest("a", required_inputs=["name"])
    with pytest.raises(GateFailure) as exc_info:
        validate_closed([m], answers={"a": {}})
    codes = {e.error_code for e in exc_info.value.errors}
    assert ErrorCode.MISSING_ANSWER in codes


def test_present_required_answer_no_error():
    m = make_manifest("a", required_inputs=["name"])
    ordered = validate_closed([m], answers={"a": {"name": "test"}})
    assert "a" in ordered


# --------------------------------------------------------------------------- #
# Missing required tool                                                        #
# --------------------------------------------------------------------------- #
def test_missing_required_tool_raises(monkeypatch):
    """shutil.which returns None → MISSING_REQUIRED_TOOL."""
    m = make_manifest("a", required_tools=["__nonexistent_tool_xyz__"])
    with pytest.raises(GateFailure) as exc_info:
        validate_closed([m], answers={"a": {}})
    codes = {e.error_code for e in exc_info.value.errors}
    assert ErrorCode.MISSING_REQUIRED_TOOL in codes


def test_present_required_tool_no_error():
    """'python3' or 'python' is always available in test env."""
    import shutil
    tool = "python3" if shutil.which("python3") else "python"
    m = make_manifest("a", required_tools=[tool])
    ordered = validate_closed([m], answers={"a": {}})
    assert "a" in ordered


# --------------------------------------------------------------------------- #
# Dependency cycle                                                             #
# --------------------------------------------------------------------------- #
def test_cycle_raises_gate_failure():
    manifests = [
        make_manifest("a", requires=["b"]),
        make_manifest("b", requires=["a"]),
    ]
    with pytest.raises(GateFailure) as exc_info:
        validate_closed(manifests, answers={})
    codes = {e.error_code for e in exc_info.value.errors}
    assert ErrorCode.DEPENDENCY_CYCLE in codes


# --------------------------------------------------------------------------- #
# ALL problems accumulated at once                                             #
# --------------------------------------------------------------------------- #
def test_all_problems_at_once():
    """Cycle + missing-answer + missing-tool all appear in ONE GateFailure."""
    # Cycle: x requires y, y requires x
    manifests = [
        make_manifest(
            "x",
            requires=["y"],
            required_inputs=["required_key"],   # will be missing
            required_tools=["__no_such_tool_abc__"],  # will be absent
        ),
        make_manifest("y", requires=["x"]),
    ]
    answers = {}  # no answers provided

    with pytest.raises(GateFailure) as exc_info:
        validate_closed(manifests, answers)

    codes = {e.error_code for e in exc_info.value.errors}
    assert ErrorCode.DEPENDENCY_CYCLE in codes
    assert ErrorCode.MISSING_ANSWER in codes
    assert ErrorCode.MISSING_REQUIRED_TOOL in codes


# --------------------------------------------------------------------------- #
# validate.py is the ONLY raise site                                          #
# --------------------------------------------------------------------------- #
def test_validate_closed_raises_gate_failure_not_setup_error():
    """validate_closed must raise GateFailure, not SetupError."""
    m = make_manifest("a", required_inputs=["x"])
    try:
        validate_closed([m], answers={})
        assert False, "Should have raised"
    except GateFailure:
        pass
    except Exception as exc:
        assert False, f"Expected GateFailure, got {type(exc)}: {exc}"


# --------------------------------------------------------------------------- #
# Missing requires                                                             #
# --------------------------------------------------------------------------- #
def test_missing_requires_in_gate():
    manifests = [make_manifest("a", requires=["ghost"])]
    with pytest.raises(GateFailure) as exc_info:
        validate_closed(manifests, answers={})
    codes = {e.error_code for e in exc_info.value.errors}
    assert ErrorCode.MISSING_REQUIRES in codes


# --------------------------------------------------------------------------- #
# Empty input                                                                  #
# --------------------------------------------------------------------------- #
def test_empty_manifests_passes():
    ordered = validate_closed([], answers={})
    assert ordered == []
