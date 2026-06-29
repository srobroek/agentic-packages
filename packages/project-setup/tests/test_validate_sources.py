"""Tests for the validate_sources runner validation (spec 014 FR-001/FR-002/FR-003,
spec 020 FR-C1).

Verifies:
  - SC-001: bare git locator (no ref field, no # fragment) → ORG_SOURCE_UNPINNED error
  - explicit ref= field → passes (no error)
  - #ref fragment in locator string → passes (no error)
  - local-path source → passes (exempt by FR-001)
  - empty source list → no errors
  - mixed list → only the unpinned git source errors
  - SC-006 backward-compat: every explicit-ref/local form that existing sources use passes
  - FR-C1 schema validation: id/git keys (no locator) → SOURCES_SCHEMA_INVALID
  - FR-C1 schema validation: missing locator → SOURCES_SCHEMA_INVALID
  - FR-C1 schema validation: correct [[source]]/locator → no schema error
  - FR-C1 schema validation (pipeline level): [[sources]] plural top-level key → error

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

def _get_pipeline():
    """Return the pipeline module, loading all dependencies first."""
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
    return sys.modules["pipeline"]


def _get_validate_sources():
    """Return the validate_sources function from pipeline.py."""
    return _get_pipeline().validate_sources


def _get_validate_sources_schema():
    """Return the validate_sources_schema function from pipeline.py."""
    return _get_pipeline().validate_sources_schema


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
# Source dict missing 'locator' key → SOURCES_SCHEMA_INVALID (FR-C1)
# ---------------------------------------------------------------------------

def test_missing_locator_key_errors():
    """Source dict without a 'locator' key → SOURCES_SCHEMA_INVALID (FR-C1 loud rejection).

    NOTE: behavior change from spec 014 (was silently skipped) — spec 020 FR-C1
    requires a loud error so mis-keyed records don't silently vanish.
    """
    validate_sources = _get_validate_sources()
    ErrorCode = _get_error_code()

    errors = validate_sources([{"ref": "v1.0.0"}])  # no 'locator' key
    assert len(errors) == 1, f"Expected one SOURCES_SCHEMA_INVALID, got: {errors}"
    assert errors[0].error_code == ErrorCode.SOURCES_SCHEMA_INVALID


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


# ---------------------------------------------------------------------------
# FR-C1: schema validation — validate_sources_schema unit tests
# ---------------------------------------------------------------------------

def test_schema_id_git_keys_rejected():
    """FR-C1: record with 'id' and 'git' keys but no 'locator' → SOURCES_SCHEMA_INVALID."""
    validate_sources_schema = _get_validate_sources_schema()
    ErrorCode = _get_error_code()

    records = [{"id": "my-org/my-modules", "git": "https://github.com/my-org/my-modules.git", "ref": "main"}]
    errors = validate_sources_schema(records)
    assert len(errors) == 1, f"Expected one schema error, got: {errors}"
    assert errors[0].error_code == ErrorCode.SOURCES_SCHEMA_INVALID
    assert "id/git" in errors[0].how_to_fix or "unknown" in errors[0].how_to_fix.lower()


def test_schema_id_key_only_rejected():
    """FR-C1: record with only 'id' key (no locator) → SOURCES_SCHEMA_INVALID."""
    validate_sources_schema = _get_validate_sources_schema()
    ErrorCode = _get_error_code()

    errors = validate_sources_schema([{"id": "my-org/my-modules"}])
    assert len(errors) == 1
    assert errors[0].error_code == ErrorCode.SOURCES_SCHEMA_INVALID


def test_schema_git_key_only_rejected():
    """FR-C1: record with only 'git' key (no locator) → SOURCES_SCHEMA_INVALID."""
    validate_sources_schema = _get_validate_sources_schema()
    ErrorCode = _get_error_code()

    errors = validate_sources_schema([{"git": "https://github.com/org/repo.git"}])
    assert len(errors) == 1
    assert errors[0].error_code == ErrorCode.SOURCES_SCHEMA_INVALID


def test_schema_missing_locator_no_id_git_rejected():
    """FR-C1: record missing 'locator' (no id/git either) → SOURCES_SCHEMA_INVALID."""
    validate_sources_schema = _get_validate_sources_schema()
    ErrorCode = _get_error_code()

    errors = validate_sources_schema([{"name": "something", "ref": "v1.0.0"}])
    assert len(errors) == 1
    assert errors[0].error_code == ErrorCode.SOURCES_SCHEMA_INVALID
    assert "missing" in errors[0].how_to_fix.lower() or "locator" in errors[0].how_to_fix


def test_schema_correct_locator_passes():
    """FR-C1: correct [[source]] record with locator → no schema error."""
    validate_sources_schema = _get_validate_sources_schema()

    errors = validate_sources_schema([{"locator": "acme/policy", "ref": "v1.0.0"}])
    assert errors == [], f"Expected no schema errors, got: {errors}"


def test_schema_correct_locator_subdir_passes():
    """FR-C1: correct [[source]] record with locator + subdir → no schema error."""
    validate_sources_schema = _get_validate_sources_schema()

    errors = validate_sources_schema([
        {"locator": "https://github.com/acme/repo", "ref": "v2.0.0", "subdir": "modules"}
    ])
    assert errors == [], f"Expected no schema errors, got: {errors}"


def test_schema_empty_list_passes():
    """FR-C1: empty list → no schema errors."""
    validate_sources_schema = _get_validate_sources_schema()

    errors = validate_sources_schema([])
    assert errors == []


def test_validate_sources_schema_first_then_pin():
    """FR-C1: validate_sources runs schema check first; schema error shown for id/git record."""
    validate_sources = _get_validate_sources()
    ErrorCode = _get_error_code()

    # A record using id/git (wrong schema) should surface a schema error, not a pin error.
    records = [{"id": "my-org/repo", "git": "https://github.com/my-org/repo.git"}]
    errors = validate_sources(records)
    assert len(errors) >= 1
    assert any(e.error_code == ErrorCode.SOURCES_SCHEMA_INVALID for e in errors)
    # Must NOT emit an ORG_SOURCE_UNPINNED error for the same record (it has no locator).
    assert not any(e.error_code == ErrorCode.ORG_SOURCE_UNPINNED for e in errors)


def test_validate_sources_valid_locator_unpinned_still_errors():
    """FR-C1 + FR-001: valid locator key but no pin → SOURCES_SCHEMA_INVALID absent,
    ORG_SOURCE_UNPINNED present (schema passes, pin fails)."""
    validate_sources = _get_validate_sources()
    ErrorCode = _get_error_code()

    errors = validate_sources([{"locator": "acme/policy"}])  # no ref, no fragment
    # Schema valid (has locator), but pin missing
    assert not any(e.error_code == ErrorCode.SOURCES_SCHEMA_INVALID for e in errors)
    assert any(e.error_code == ErrorCode.ORG_SOURCE_UNPINNED for e in errors)


# ---------------------------------------------------------------------------
# FR-C1: plural [[sources]] top-level key detection via _read_committed_sources
# ---------------------------------------------------------------------------

def test_plural_sources_key_raises(tmp_path):
    """FR-C1: sources.toml with [[sources]] (plural) → SetupError SOURCES_SCHEMA_INVALID.

    Tests the _read_committed_sources path that detects the wrong top-level key.
    """
    pipeline = _get_pipeline()
    ErrorCode = _get_error_code()
    SetupError = _load("contracts").SetupError

    # Create a fake project dir with a sources.toml using [[sources]] (plural)
    psd = tmp_path / ".project-setup"
    psd.mkdir()
    (psd / "sources.toml").write_text(
        '[[sources]]\nid = "my-org/repo"\ngit = "https://github.com/my-org/repo.git"\n',
        encoding="utf-8",
    )

    import pytest
    with pytest.raises(SetupError) as exc_info:
        pipeline._read_committed_sources(tmp_path)

    err = exc_info.value
    assert err.error_code == ErrorCode.SOURCES_SCHEMA_INVALID
    assert "sources" in err.how_to_fix.lower()
    assert "source" in err.how_to_fix  # mentions the correct key


def test_correct_source_key_reads_ok(tmp_path):
    """A sources.toml with [[source]] (singular, correct) parses without error."""
    pipeline = _get_pipeline()

    psd = tmp_path / ".project-setup"
    psd.mkdir()
    (psd / "sources.toml").write_text(
        '[[source]]\nlocator = "acme/policy"\nref = "v1.0.0"\n',
        encoding="utf-8",
    )

    records = pipeline._read_committed_sources(tmp_path)
    assert len(records) == 1
    assert records[0]["locator"] == "acme/policy"
    assert records[0]["ref"] == "v1.0.0"
