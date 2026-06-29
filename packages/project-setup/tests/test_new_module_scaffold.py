"""Tests for the `--new-module` scaffold (spec 020 FR-C5).

Verifies:
  - Scaffold writes module.toml + module.py + test_<id>.py under dest_dir/<id>/
  - Generated module.toml is accepted by parse_manifest with no errors
  - module.id matches the requested id
  - default_enabled is NOT present (FORBIDDEN on non-bundled modules)
  - generated module.py compiles (valid Python syntax)
  - invalid id (wrong case / non-kebab) → non-zero exit, no dir created
  - existing dest dir → non-zero exit
  - custom --new-module-dest writes to the specified directory

Run:
    uv run --with pytest pytest -q packages/project-setup/tests/test_new_module_scaffold.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_PKG = Path(__file__).resolve().parents[1]
_RUNNER = _PKG / "skills" / "project-setup" / "runner"
_CLI_PATH = _RUNNER / "cli.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load(name: str):
    if name in sys.modules:
        return sys.modules[name]
    candidates = [
        _RUNNER / f"{name}.py",
        _RUNNER / "sources" / f"{name}.py",
    ]
    path = next((p for p in candidates if p.is_file()), None)
    assert path is not None, f"Cannot find module {name!r}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _get_parse_manifest():
    for dep in ("contracts", "paths", "manifest"):
        _load(dep)
    return sys.modules["manifest"].parse_manifest


def _get_scaffold():
    """Load _scaffold_new_module from cli.py (fresh each call to avoid caching)."""
    # We load cli.py once; subsequent calls reuse the cached module.
    if "cli_for_scaffold" not in sys.modules:
        spec = importlib.util.spec_from_file_location("cli_for_scaffold", _CLI_PATH)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        sys.modules["cli_for_scaffold"] = mod
        sys.modules["cli"] = mod  # so sibling imports work
        spec.loader.exec_module(mod)
    return sys.modules["cli_for_scaffold"]._scaffold_new_module


# ---------------------------------------------------------------------------
# Happy-path: scaffold a simple module
# ---------------------------------------------------------------------------

def test_scaffold_creates_expected_files(tmp_path):
    """Scaffold writes module.toml, module.py, and test_<id>.py."""
    scaffold = _get_scaffold()
    rc = scaffold("my-addon", tmp_path)
    assert rc == 0

    mod_dir = tmp_path / "my-addon"
    assert mod_dir.is_dir()
    assert (mod_dir / "module.toml").is_file()
    assert (mod_dir / "module.py").is_file()
    assert (mod_dir / "test_my_addon.py").is_file()


def test_scaffold_module_toml_parses_cleanly(tmp_path):
    """Generated module.toml is accepted by parse_manifest with no errors."""
    scaffold = _get_scaffold()
    scaffold("my-addon", tmp_path)

    parse_manifest = _get_parse_manifest()
    manifest = parse_manifest(tmp_path / "my-addon" / "module.toml")
    assert manifest.errors == [], (
        f"module.toml has parse errors: {[e.how_to_fix for e in manifest.errors]}"
    )


def test_scaffold_module_id_matches(tmp_path):
    """parse_manifest returns the correct id."""
    scaffold = _get_scaffold()
    scaffold("my-addon", tmp_path)

    parse_manifest = _get_parse_manifest()
    manifest = parse_manifest(tmp_path / "my-addon" / "module.toml")
    assert manifest.id == "my-addon"


def test_scaffold_no_default_enabled(tmp_path):
    """Generated module.toml must NOT set default_enabled (FORBIDDEN on non-bundled).

    A comment mentioning default_enabled is fine; the key must not be assigned.
    """
    scaffold = _get_scaffold()
    scaffold("my-addon", tmp_path)

    content = (tmp_path / "my-addon" / "module.toml").read_text()
    # Look for an uncommented assignment like `default_enabled = ...`
    import re
    uncommented_lines = [
        ln for ln in content.splitlines()
        if not ln.strip().startswith("#")
    ]
    has_assignment = any(
        re.match(r"\s*default_enabled\s*=", ln)
        for ln in uncommented_lines
    )
    assert not has_assignment, (
        "Scaffold must NOT set default_enabled — it is FORBIDDEN on non-bundled modules. "
        "A comment is fine, but the key must not be assigned."
    )


def test_scaffold_module_py_compiles(tmp_path):
    """Generated module.py must be syntactically valid Python."""
    scaffold = _get_scaffold()
    scaffold("my-addon", tmp_path)

    import py_compile
    py_compile.compile(str(tmp_path / "my-addon" / "module.py"), doraise=True)


def test_scaffold_test_stub_compiles(tmp_path):
    """Generated test_<id>.py must be syntactically valid Python."""
    scaffold = _get_scaffold()
    scaffold("my-addon", tmp_path)

    import py_compile
    py_compile.compile(str(tmp_path / "my-addon" / "test_my_addon.py"), doraise=True)


# ---------------------------------------------------------------------------
# Various valid ids
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("module_id", [
    "hello",
    "my-module",
    "lang-python3",
    "a",
    "org-policy-check",
])
def test_scaffold_valid_ids(tmp_path, module_id):
    """Various valid kebab-case ids scaffold without error."""
    scaffold = _get_scaffold()
    rc = scaffold(module_id, tmp_path)
    assert rc == 0
    assert (tmp_path / module_id / "module.toml").is_file()

    parse_manifest = _get_parse_manifest()
    manifest = parse_manifest(tmp_path / module_id / "module.toml")
    assert manifest.errors == []
    assert manifest.id == module_id


# ---------------------------------------------------------------------------
# Invalid id → non-zero exit, no directory
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad_id", [
    "",
    "MyModule",          # uppercase
    "my_module",         # underscore (not kebab)
    "-starts-with-dash",
    "has spaces",
    "123-starts-with-digit",
])
def test_scaffold_invalid_id_fails(tmp_path, bad_id):
    """Invalid id → returns non-zero, no directory created."""
    scaffold = _get_scaffold()
    rc = scaffold(bad_id, tmp_path)
    assert rc != 0
    # No directory should be created for an invalid id
    # (empty string handled separately — can't be a dir name)
    if bad_id:
        assert not (tmp_path / bad_id).exists()


# ---------------------------------------------------------------------------
# Existing destination → non-zero exit
# ---------------------------------------------------------------------------

def test_scaffold_existing_dir_fails(tmp_path):
    """If <dest_dir>/<id>/ already exists, scaffold refuses and returns non-zero."""
    scaffold = _get_scaffold()
    (tmp_path / "my-addon").mkdir()
    rc = scaffold("my-addon", tmp_path)
    assert rc != 0


# ---------------------------------------------------------------------------
# CLI --new-module integration (via main())
# ---------------------------------------------------------------------------

def test_cli_new_module_flag(tmp_path):
    """--new-module via the CLI main() function writes the scaffold and exits 0."""
    from unittest.mock import patch

    # Load cli fresh to avoid pollution from other tests
    name = f"cli_nm_{id(tmp_path)}"
    spec = importlib.util.spec_from_file_location(name, _CLI_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    sys.modules["cli"] = mod
    spec.loader.exec_module(mod)

    dest = tmp_path / "modules"
    rc = mod.main([
        "--new-module", "test-addon",
        "--new-module-dest", str(dest),
        "--project-dir", str(tmp_path),
    ])
    assert rc == 0
    assert (dest / "test-addon" / "module.toml").is_file()

    parse_manifest = _get_parse_manifest()
    manifest = parse_manifest(dest / "test-addon" / "module.toml")
    assert manifest.errors == []
