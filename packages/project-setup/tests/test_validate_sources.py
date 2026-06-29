"""Tests for the validate_sources runner validation (spec 014 FR-001/FR-002/FR-003).

Verifies:
  - SC-001: bare git locator (no ref field, no # fragment) → ORG_SOURCE_UNPINNED error
  - explicit ref= field → passes (no error)
  - #ref fragment in locator string → passes (no error)
  - local-path source → passes (exempt by FR-001)
  - empty source list → no errors
  - mixed list → only the unpinned git source errors
  - SC-006 backward-compat: every explicit-ref/local form that existing sources use passes

Run: uv run --with pytest pytest -q packages/project-setup/tests/test_validate_sources.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_PKG = Path(__file__).resolve().parents[1]
_RUNNER = _PKG / "skills" / "project-setup" / "runner"


def _load(name: str):
    """Load a runner module by name (mirrors the pattern in other test files)."""
    if name in sys.modules:
        return sys.modules[name]
    # sources/ sub-package modules (e.g. locator) are imported by bare name because
    # the runner puts both runner/ and runner/sources/ on sys.path.  Load by file.
    candidates = [
        _RUNNER / f"{name}.py",
        _RUNNER / "sources" / f"{name}.py",
    ]
    path = next((p for p in candidates if p.is_file()), None)
    assert path is not None, f"Cannot find module {name!r} in runner or runner/sources/"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Module-level setup: ensure pipeline and its deps are loadable
# ---------------------------------------------------------------------------

def _get_validate_sources():
    """Return the validate_sources function from pipeline.py."""
    # Load dependencies in order so bare imports inside pipeline.py resolve.
    for dep in (
        "contracts",
        "paths",
        "manifest",
        "answers",
        "validate",
        "plan",
        "mode",
        "executor",
        "reproduce",
        "persist",
        "enablement",
        "sdk",
        "discover",
        "fetch",
        "locator",
        "pipeline",
    ):
        _load(dep)
    pipeline = sys.modules["pipeline"]
    return pipeline.validate_sources


def _get_error_code():
    contracts = _load("contracts")
    return contracts.ErrorCode


# ---------------------------------------------------------------------------
# SC-001: bare git locator (no ref, no fragment) → ORG_SOURCE_UNPINNED
# ---------------------------------------------------------------------------

def test_sc001_bare_git_locator_rejected():
    """SC-001: git source with no ref field and no # fragment → one ORG_SOURCE_UNPINNED."""
    validate_sources = _get_validate_sources()
    ErrorCode = _get_error_code()

    errors = validate_sources([{"locator": "acme/policy"}])
    assert len(errors) == 1, f"Expected exactly one error, got: {errors}"
    assert errors[0].error_code == ErrorCode.ORG_SOURCE_UNPINNED
    assert "acme/policy" in errors[0].received


# ---------------------------------------------------------------------------
# Explicit ref= field → passes
# ---------------------------------------------------------------------------

def test_explicit_ref_field_passes():
    """A source dict with an explicit ref= field is pinned → no error."""
    validate_sources = _get_validate_sources()

    errors = validate_sources([{"locator": "acme/policy", "ref": "v1.0.0"}])
    assert errors == [], f"Expected no errors, got: {errors}"


def test_explicit_ref_field_sha_passes():
    """A source dict with a SHA ref= field is pinned → no error."""
    validate_sources = _get_validate_sources()

    errors = validate_sources([{"locator": "acme/policy", "ref": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"}])
    assert errors == [], f"Expected no errors, got: {errors}"


# ---------------------------------------------------------------------------
# #ref fragment in locator string → passes
# ---------------------------------------------------------------------------

def test_hash_fragment_passes():
    """A locator with a #ref fragment is pinned → no error."""
    validate_sources = _get_validate_sources()

    errors = validate_sources([{"locator": "acme/policy#v1.0.0"}])
    assert errors == [], f"Expected no errors, got: {errors}"


def test_hash_fragment_main_passes():
    """A locator with a #main fragment is explicitly pinned → no error (spec: explicit is enough)."""
    validate_sources = _get_validate_sources()

    errors = validate_sources([{"locator": "acme/policy#main"}])
    assert errors == [], f"Expected no errors, got: {errors}"


def test_hash_fragment_sha_passes():
    """A locator with a #sha fragment is pinned → no error."""
    validate_sources = _get_validate_sources()

    errors = validate_sources([{"locator": "acme/policy#a1b2c3d"}])
    assert errors == [], f"Expected no errors, got: {errors}"


# ---------------------------------------------------------------------------
# Local-path sources → exempt
# ---------------------------------------------------------------------------

def test_local_absolute_path_exempt():
    """Absolute local-path source is exempt from pin validation → no error."""
    validate_sources = _get_validate_sources()

    errors = validate_sources([{"locator": "/tmp/some/local/path"}])
    assert errors == [], f"Expected no errors for local path, got: {errors}"


def test_local_relative_dotslash_exempt():
    """./relative local path is exempt → no error."""
    validate_sources = _get_validate_sources()

    errors = validate_sources([{"locator": "./my-modules"}])
    assert errors == [], f"Expected no errors for local path, got: {errors}"


# ---------------------------------------------------------------------------
# Empty list → no errors
# ---------------------------------------------------------------------------

def test_empty_sources_no_errors():
    """Empty source list → no errors, no crash."""
    validate_sources = _get_validate_sources()

    errors = validate_sources([])
    assert errors == []


# ---------------------------------------------------------------------------
# Mixed list → only the unpinned git source errors
# ---------------------------------------------------------------------------

def test_mixed_sources_only_unpinned_errors():
    """Mixed list: only the bare git source errors; pinned + local pass."""
    validate_sources = _get_validate_sources()
    ErrorCode = _get_error_code()

    sources = [
        {"locator": "acme/policy"},           # unpinned git → error
        {"locator": "acme/tools", "ref": "v2.0.0"},  # explicit ref → pass
        {"locator": "acme/sdk#v1.0.0"},        # fragment pin → pass
        {"locator": "/tmp/local/mods"},        # local → pass
    ]
    errors = validate_sources(sources)
    assert len(errors) == 1, f"Expected exactly one error, got: {errors}"
    assert errors[0].error_code == ErrorCode.ORG_SOURCE_UNPINNED
    assert "acme/policy" in errors[0].received


def test_multiple_unpinned_all_error():
    """Two unpinned git sources → two ORG_SOURCE_UNPINNED errors."""
    validate_sources = _get_validate_sources()
    ErrorCode = _get_error_code()

    sources = [
        {"locator": "acme/policy"},
        {"locator": "acme/infra"},
    ]
    errors = validate_sources(sources)
    assert len(errors) == 2
    for err in errors:
        assert err.error_code == ErrorCode.ORG_SOURCE_UNPINNED


# ---------------------------------------------------------------------------
# Source dict missing 'locator' key → skipped (no crash)
# ---------------------------------------------------------------------------

def test_missing_locator_key_skipped():
    """Source dict without a 'locator' key is safely skipped → no error, no crash."""
    validate_sources = _get_validate_sources()

    errors = validate_sources([{"ref": "v1.0.0"}])  # no 'locator' key
    assert errors == []


# ---------------------------------------------------------------------------
# HTTPS and SSH URL forms also checked
# ---------------------------------------------------------------------------

def test_https_url_no_ref_rejected():
    """HTTPS git URL with no # fragment and no ref field → ORG_SOURCE_UNPINNED."""
    validate_sources = _get_validate_sources()
    ErrorCode = _get_error_code()

    errors = validate_sources([{"locator": "https://github.com/acme/policy"}])
    assert len(errors) == 1
    assert errors[0].error_code == ErrorCode.ORG_SOURCE_UNPINNED


def test_https_url_with_fragment_passes():
    """HTTPS git URL with a # fragment is pinned → no error."""
    validate_sources = _get_validate_sources()

    errors = validate_sources([{"locator": "https://github.com/acme/policy#v1.0.0"}])
    assert errors == []


def test_https_url_with_ref_field_passes():
    """HTTPS git URL with a ref= field is pinned → no error."""
    validate_sources = _get_validate_sources()

    errors = validate_sources([{"locator": "https://github.com/acme/policy", "ref": "v2.1.0"}])
    assert errors == []
