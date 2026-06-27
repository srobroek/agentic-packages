"""Tests for order.py — pure, non-raising topological sort.

Import-by-path pattern from test_contracts.py.
Run via: uv run --with pytest pytest -q packages/project-setup/tests/test_order.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

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
order_mod = _load("order")

resolve_order = order_mod.resolve_order
ErrorCode = contracts.ErrorCode


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #
def make_manifest(id: str, requires=(), after=(), before=()):
    """Create a minimal manifest-like object for order tests."""
    return SimpleNamespace(
        id=id,
        order={"requires": list(requires), "after": list(after), "before": list(before)},
    )


# --------------------------------------------------------------------------- #
# Basic ordering                                                               #
# --------------------------------------------------------------------------- #
def test_no_deps_stable_alphabetical_order():
    """Without edges, modules are sorted alphabetically (tie-break)."""
    manifests = [
        make_manifest("z-mod"),
        make_manifest("a-mod"),
        make_manifest("m-mod"),
    ]
    ordered, errors = resolve_order(manifests)
    assert errors == []
    assert ordered == ["a-mod", "m-mod", "z-mod"]


def test_requires_hard_dep_ordering():
    """B requires A → A must come before B."""
    manifests = [
        make_manifest("b-mod", requires=["a-mod"]),
        make_manifest("a-mod"),
    ]
    ordered, errors = resolve_order(manifests)
    assert errors == []
    assert ordered.index("a-mod") < ordered.index("b-mod")


def test_after_soft_dep_ordering():
    """B after A → A must come before B (soft edge)."""
    manifests = [
        make_manifest("b-mod", after=["a-mod"]),
        make_manifest("a-mod"),
    ]
    ordered, errors = resolve_order(manifests)
    assert errors == []
    assert ordered.index("a-mod") < ordered.index("b-mod")


def test_before_soft_dep_ordering():
    """A before B → A must come before B (soft edge, expressed as 'a before b')."""
    manifests = [
        make_manifest("b-mod"),
        make_manifest("a-mod", before=["b-mod"]),
    ]
    ordered, errors = resolve_order(manifests)
    assert errors == []
    assert ordered.index("a-mod") < ordered.index("b-mod")


def test_chain_ordering():
    """C requires B, B requires A → A before B before C."""
    manifests = [
        make_manifest("c-mod", requires=["b-mod"]),
        make_manifest("b-mod", requires=["a-mod"]),
        make_manifest("a-mod"),
    ]
    ordered, errors = resolve_order(manifests)
    assert errors == []
    assert ordered.index("a-mod") < ordered.index("b-mod") < ordered.index("c-mod")


# --------------------------------------------------------------------------- #
# Determinism                                                                  #
# --------------------------------------------------------------------------- #
def test_order_is_stable_across_runs():
    """The same set of modules always produces the same order."""
    manifests = [
        make_manifest("delta"),
        make_manifest("alpha"),
        make_manifest("gamma", after=["beta"]),
        make_manifest("beta", requires=["alpha"]),
    ]
    ordered1, _ = resolve_order(manifests)
    ordered2, _ = resolve_order(manifests)
    assert ordered1 == ordered2


def test_order_tie_break_alphabetical():
    """When multiple nodes are ready simultaneously, alphabetical order wins."""
    # A and B both depend on Z (root). After Z is done, A and B are both ready.
    manifests = [
        make_manifest("z-root"),
        make_manifest("b-leaf", requires=["z-root"]),
        make_manifest("a-leaf", requires=["z-root"]),
    ]
    ordered, errors = resolve_order(manifests)
    assert errors == []
    assert ordered[0] == "z-root"
    assert ordered[1] == "a-leaf"
    assert ordered[2] == "b-leaf"


# --------------------------------------------------------------------------- #
# Cycle detection → DEPENDENCY_CYCLE                                           #
# --------------------------------------------------------------------------- #
def test_simple_cycle_returns_dependency_cycle_error():
    """A → B → A produces DEPENDENCY_CYCLE."""
    manifests = [
        make_manifest("a-mod", requires=["b-mod"]),
        make_manifest("b-mod", requires=["a-mod"]),
    ]
    ordered, errors = resolve_order(manifests)
    assert ordered == []
    assert any(e.error_code == ErrorCode.DEPENDENCY_CYCLE for e in errors)


def test_cycle_error_has_module_ids():
    """DEPENDENCY_CYCLE error includes the cycle path in module_ids."""
    manifests = [
        make_manifest("x", requires=["y"]),
        make_manifest("y", requires=["x"]),
    ]
    _, errors = resolve_order(manifests)
    cycle_errors = [e for e in errors if e.error_code == ErrorCode.DEPENDENCY_CYCLE]
    assert len(cycle_errors) == 1
    # module_ids carries the cycle path
    assert len(cycle_errors[0].module_ids) >= 2


def test_three_node_cycle():
    """A → B → C → A is detected."""
    manifests = [
        make_manifest("a", requires=["c"]),
        make_manifest("b", requires=["a"]),
        make_manifest("c", requires=["b"]),
    ]
    _, errors = resolve_order(manifests)
    assert any(e.error_code == ErrorCode.DEPENDENCY_CYCLE for e in errors)


# --------------------------------------------------------------------------- #
# Missing requires → MISSING_REQUIRES                                         #
# --------------------------------------------------------------------------- #
def test_missing_requires_target_produces_error():
    """requires pointing at a non-existent module → MISSING_REQUIRES."""
    manifests = [
        make_manifest("a-mod", requires=["nonexistent"]),
    ]
    ordered, errors = resolve_order(manifests)
    assert any(e.error_code == ErrorCode.MISSING_REQUIRES for e in errors)


def test_missing_requires_carries_module_ids():
    """MISSING_REQUIRES error names both the requirer and the missing dep."""
    manifests = [
        make_manifest("a-mod", requires=["ghost-dep"]),
    ]
    _, errors = resolve_order(manifests)
    mr_errors = [e for e in errors if e.error_code == ErrorCode.MISSING_REQUIRES]
    assert len(mr_errors) >= 1
    assert "a-mod" in mr_errors[0].module_ids or mr_errors[0].module_id == "a-mod"
    assert "ghost-dep" in mr_errors[0].module_ids or "ghost-dep" in mr_errors[0].received


# --------------------------------------------------------------------------- #
# Soft edges to absent/disabled modules → silently dropped                    #
# --------------------------------------------------------------------------- #
def test_after_absent_module_silently_dropped():
    """after pointing at a missing module is a soft edge — NOT an error."""
    manifests = [
        make_manifest("a-mod", after=["missing-mod"]),
    ]
    ordered, errors = resolve_order(manifests)
    assert not any(e.error_code == ErrorCode.MISSING_REQUIRES for e in errors)
    assert "a-mod" in ordered


def test_before_absent_module_silently_dropped():
    """before pointing at a missing module is a soft edge — NOT an error."""
    manifests = [
        make_manifest("a-mod", before=["missing-mod"]),
    ]
    ordered, errors = resolve_order(manifests)
    assert not any(e.error_code == ErrorCode.MISSING_REQUIRES for e in errors)
    assert "a-mod" in ordered


# --------------------------------------------------------------------------- #
# order.py never raises                                                        #
# --------------------------------------------------------------------------- #
def test_resolve_order_never_raises_on_cycle():
    """Even a cycle must not raise — errors are returned, not raised."""
    manifests = [
        make_manifest("a", requires=["b"]),
        make_manifest("b", requires=["a"]),
    ]
    # Must not raise
    ordered, errors = resolve_order(manifests)
    assert isinstance(ordered, list)
    assert isinstance(errors, list)


def test_resolve_order_never_raises_on_missing_requires():
    """Missing requires must not raise."""
    manifests = [make_manifest("a", requires=["nope"])]
    ordered, errors = resolve_order(manifests)
    assert isinstance(ordered, list)
    assert isinstance(errors, list)


# --------------------------------------------------------------------------- #
# Empty / single module                                                        #
# --------------------------------------------------------------------------- #
def test_empty_manifests():
    ordered, errors = resolve_order([])
    assert ordered == []
    assert errors == []


def test_single_module_no_deps():
    ordered, errors = resolve_order([make_manifest("solo")])
    assert errors == []
    assert ordered == ["solo"]
