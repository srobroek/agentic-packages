"""Unit tests for enablement.py — resolve_enabled_modules.

Tests cover:
  - base-only when no selection is given
  - selection ∪ base
  - requires-closure auto-pull
  - UNKNOWN_MODULE on bad id in selection
  - UNKNOWN_MODULE on bad id in requires
  - reproduce uses committed, init uses proposed
  - proposed=None → base-only (FR-007 safe default)

Run: uv run --with pytest pytest -q packages/project-setup/tests/test_enablement.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

_RUNNER = Path(__file__).resolve().parents[1] / "skills" / "project-setup" / "runner"


def _load(name: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _RUNNER / f"{name}.py")
    assert spec and spec.loader, name
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


contracts = _load("contracts")
enablement_mod = _load("enablement")

resolve_enabled_modules = enablement_mod.resolve_enabled_modules
ErrorCode = contracts.ErrorCode


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #

def _manifest(id: str, *, default_enabled: bool | None = None, requires: list[str] | None = None) -> SimpleNamespace:
    """Build a minimal fake ModuleManifest with the fields enablement.py uses."""
    return SimpleNamespace(
        id=id,
        default_enabled=default_enabled,
        order={"requires": requires or [], "after": [], "before": []},
    )


# --------------------------------------------------------------------------- #
# Base-only behaviour                                                          #
# --------------------------------------------------------------------------- #

def test_base_only_when_no_selection():
    """No selection → only default_enabled=True modules are enabled."""
    manifests = [
        _manifest("core-identity", default_enabled=True),
        _manifest("dirs-scaffold", default_enabled=True),
        _manifest("lang-python", default_enabled=False),
        _manifest("apm-install", default_enabled=False),
    ]
    enabled, errors = resolve_enabled_modules(
        manifests,
        committed_enabled=None,
        proposed_enabled=None,
        mode="init",
    )
    assert errors == []
    assert enabled == {"core-identity", "dirs-scaffold"}


def test_base_only_when_proposed_is_empty_list():
    """proposed_enabled=[] (empty) → base-only (FR-007)."""
    manifests = [
        _manifest("core-identity", default_enabled=True),
        _manifest("lang-python", default_enabled=False),
    ]
    enabled, errors = resolve_enabled_modules(
        manifests,
        committed_enabled=None,
        proposed_enabled=[],
        mode="init",
    )
    assert errors == []
    assert enabled == {"core-identity"}


def test_all_false_default_enabled_no_selection_gives_empty():
    """If no module is default_enabled and no selection, result is empty."""
    manifests = [
        _manifest("lang-python", default_enabled=False),
        _manifest("lang-ts", default_enabled=False),
    ]
    enabled, errors = resolve_enabled_modules(
        manifests,
        committed_enabled=None,
        proposed_enabled=None,
        mode="init",
    )
    assert errors == []
    assert enabled == set()


# --------------------------------------------------------------------------- #
# Selection ∪ base                                                             #
# --------------------------------------------------------------------------- #

def test_proposed_adds_to_base():
    """proposed_enabled adds to base (base is always included)."""
    manifests = [
        _manifest("core-identity", default_enabled=True),
        _manifest("dirs-scaffold", default_enabled=True),
        _manifest("lang-python", default_enabled=False),
        _manifest("apm-install", default_enabled=False),
    ]
    enabled, errors = resolve_enabled_modules(
        manifests,
        committed_enabled=None,
        proposed_enabled=["lang-python"],
        mode="init",
    )
    assert errors == []
    assert enabled == {"core-identity", "dirs-scaffold", "lang-python"}


def test_proposed_base_already_included():
    """A base module in proposed_enabled is a no-op (idempotent)."""
    manifests = [
        _manifest("core-identity", default_enabled=True),
        _manifest("lang-python", default_enabled=False),
    ]
    enabled, errors = resolve_enabled_modules(
        manifests,
        committed_enabled=None,
        proposed_enabled=["core-identity", "lang-python"],
        mode="init",
    )
    assert errors == []
    assert enabled == {"core-identity", "lang-python"}


# --------------------------------------------------------------------------- #
# requires-closure                                                             #
# --------------------------------------------------------------------------- #

def test_requires_closure_auto_pull():
    """Enabling a module pulls its requires target even if not in selection."""
    manifests = [
        _manifest("core-identity", default_enabled=True),
        _manifest("precommit-setup", default_enabled=False, requires=["quality-hooks"]),
        _manifest("quality-hooks", default_enabled=False),
    ]
    enabled, errors = resolve_enabled_modules(
        manifests,
        committed_enabled=None,
        proposed_enabled=["precommit-setup"],
        mode="init",
    )
    assert errors == []
    # quality-hooks must be auto-included as a requires dep of precommit-setup
    assert "quality-hooks" in enabled
    assert "precommit-setup" in enabled
    assert "core-identity" in enabled


def test_requires_closure_transitive():
    """Requires-closure is transitive: A requires B requires C → all three included."""
    manifests = [
        _manifest("a", default_enabled=False, requires=["b"]),
        _manifest("b", default_enabled=False, requires=["c"]),
        _manifest("c", default_enabled=False),
    ]
    enabled, errors = resolve_enabled_modules(
        manifests,
        committed_enabled=None,
        proposed_enabled=["a"],
        mode="init",
    )
    assert errors == []
    assert enabled == {"a", "b", "c"}


def test_requires_closure_base_already_present():
    """If a requires target is already in base, no duplicate error is produced."""
    manifests = [
        _manifest("core-identity", default_enabled=True),
        _manifest("agents-md", default_enabled=False, requires=["core-identity"]),
    ]
    enabled, errors = resolve_enabled_modules(
        manifests,
        committed_enabled=None,
        proposed_enabled=["agents-md"],
        mode="init",
    )
    assert errors == []
    assert enabled == {"core-identity", "agents-md"}


# --------------------------------------------------------------------------- #
# UNKNOWN_MODULE errors                                                        #
# --------------------------------------------------------------------------- #

def test_unknown_module_in_selection_errors():
    """An id in proposed_enabled that is not a discovered module → UNKNOWN_MODULE."""
    manifests = [
        _manifest("core-identity", default_enabled=True),
    ]
    enabled, errors = resolve_enabled_modules(
        manifests,
        committed_enabled=None,
        proposed_enabled=["typo-module"],
        mode="init",
    )
    assert len(errors) == 1
    assert errors[0].error_code == ErrorCode.UNKNOWN_MODULE
    assert "typo-module" in errors[0].how_to_fix
    # base still enabled even with errors
    assert "core-identity" in enabled


def test_unknown_module_in_committed_errors():
    """An id in committed_enabled that is not discovered → UNKNOWN_MODULE (reproduce)."""
    manifests = [
        _manifest("core-identity", default_enabled=True),
    ]
    enabled, errors = resolve_enabled_modules(
        manifests,
        committed_enabled=["ghost-module"],
        proposed_enabled=None,
        mode="reproduce",
    )
    assert len(errors) == 1
    assert errors[0].error_code == ErrorCode.UNKNOWN_MODULE
    assert "ghost-module" in errors[0].how_to_fix


def test_unknown_module_in_requires_errors():
    """A requires target not in discovered modules → UNKNOWN_MODULE from closure."""
    manifests = [
        _manifest("core-identity", default_enabled=True),
        _manifest("lang-python", default_enabled=False, requires=["missing-dep"]),
    ]
    enabled, errors = resolve_enabled_modules(
        manifests,
        committed_enabled=None,
        proposed_enabled=["lang-python"],
        mode="init",
    )
    assert len(errors) == 1
    assert errors[0].error_code == ErrorCode.UNKNOWN_MODULE
    assert "missing-dep" in errors[0].received


def test_multiple_unknown_modules_all_reported():
    """All unknown ids in the selection are reported (not just the first)."""
    manifests = [_manifest("core-identity", default_enabled=True)]
    enabled, errors = resolve_enabled_modules(
        manifests,
        committed_enabled=None,
        proposed_enabled=["bad-a", "bad-b"],
        mode="init",
    )
    assert len(errors) == 2
    codes = {e.error_code for e in errors}
    assert codes == {ErrorCode.UNKNOWN_MODULE}


# --------------------------------------------------------------------------- #
# Mode behaviour: reproduce vs init                                            #
# --------------------------------------------------------------------------- #

def test_reproduce_uses_committed_not_proposed():
    """In reproduce mode, committed_enabled is authoritative; proposed is ignored."""
    manifests = [
        _manifest("core-identity", default_enabled=True),
        _manifest("lang-python", default_enabled=False),
        _manifest("lang-ts", default_enabled=False),
    ]
    # committed says lang-python; proposed says lang-ts
    enabled, errors = resolve_enabled_modules(
        manifests,
        committed_enabled=["lang-python"],
        proposed_enabled=["lang-ts"],
        mode="reproduce",
    )
    assert errors == []
    assert "lang-python" in enabled
    assert "lang-ts" not in enabled


def test_init_uses_proposed_not_committed():
    """In init mode, proposed_enabled is used; committed_enabled is ignored."""
    manifests = [
        _manifest("core-identity", default_enabled=True),
        _manifest("lang-python", default_enabled=False),
        _manifest("lang-ts", default_enabled=False),
    ]
    # committed says lang-python (from a prior run that somehow exists);
    # proposed says lang-ts — init should use proposed only.
    enabled, errors = resolve_enabled_modules(
        manifests,
        committed_enabled=["lang-python"],
        proposed_enabled=["lang-ts"],
        mode="init",
    )
    assert errors == []
    assert "lang-ts" in enabled
    assert "lang-python" not in enabled


def test_reproduce_none_committed_falls_back_to_base():
    """In reproduce mode with committed_enabled=None, base defaults apply."""
    manifests = [
        _manifest("core-identity", default_enabled=True),
        _manifest("lang-python", default_enabled=False),
    ]
    enabled, errors = resolve_enabled_modules(
        manifests,
        committed_enabled=None,
        proposed_enabled=None,
        mode="reproduce",
    )
    assert errors == []
    assert enabled == {"core-identity"}


# --------------------------------------------------------------------------- #
# Edge: default_enabled=None (absent from manifest)                            #
# --------------------------------------------------------------------------- #

def test_none_default_enabled_not_in_base():
    """A module with default_enabled=None (absent) is NOT in base."""
    manifests = [
        _manifest("core-identity", default_enabled=True),
        _manifest("no-default", default_enabled=None),
    ]
    enabled, errors = resolve_enabled_modules(
        manifests,
        committed_enabled=None,
        proposed_enabled=None,
        mode="init",
    )
    assert errors == []
    assert enabled == {"core-identity"}
