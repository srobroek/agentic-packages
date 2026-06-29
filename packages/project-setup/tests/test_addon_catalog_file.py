"""Tests for the first-party addon catalog file and PLUGIN_ROOT/CLAUDE_PLUGIN_ROOT env fix.

Spec 020 FR-D2, FR-E1, FR-E3.

Covers:
- catalog.json exists, parses as valid JSON
- schema/note top-level fields present
- modules list has exactly 18 entries
- each record has name, description, locator, category (and ref)
- the 6 base modules are NOT present
- all 18 addon modules ARE present
- fetch_addon_catalog parses an in-memory equivalent of the catalog shape
- paths.plugin_root() resolves when only CLAUDE_PLUGIN_ROOT is set in env
- a module's _load_sdk fallback accepts CLAUDE_PLUGIN_ROOT when PLUGIN_ROOT absent

Run via:
  uv run --with pytest pytest -q packages/project-setup/tests/test_addon_catalog_file.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

_SKILL_DIR = Path(__file__).resolve().parents[1] / "skills" / "project-setup"
_RUNNER = _SKILL_DIR / "runner"
_CATALOG_PATH = _SKILL_DIR / "addons" / "catalog.json"

# ── Load runner modules via importlib (mirrors other test files) ──────────── #

def _load(name: str):
    if name in sys.modules:
        return sys.modules[name]
    for p in (str(_RUNNER), str(_RUNNER / "sources")):
        if p not in sys.path:
            sys.path.insert(0, p)
    spec = importlib.util.spec_from_file_location(name, _RUNNER / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


sdk = _load("sdk")
paths = _load("paths")

# The 6 base (bundled) modules that must NOT appear in the addon catalog.
BASE_MODULES = {
    "core-identity",
    "dirs-scaffold",
    "gitignore-generate",
    "license-write",
    "agents-md",
    "git-init",
}

# The 18 addon modules that MUST appear in the catalog.
ADDON_MODULES = {
    "lang-python",
    "lang-ts",
    "lang-go",
    "lang-rust",
    "precommit-setup",
    "quality-hooks",
    "justfile-write",
    "ci-github-actions",
    "env-example",
    "stack-adr",
    "readme-draft",
    "apm-install",
    "mcp-config",
    "speckit-bridge",
    "codex-config",
    "github-repo",
    "org-policy",
    "package-add",
}

REQUIRED_RECORD_KEYS = {"name", "description", "locator", "category"}


# --------------------------------------------------------------------------- #
# Catalog file structure                                                       #
# --------------------------------------------------------------------------- #

class TestCatalogFileStructure:
    """Validate catalog.json on disk — shape, count, required fields."""

    @pytest.fixture(scope="class")
    def catalog(self):
        assert _CATALOG_PATH.is_file(), f"catalog.json not found at {_CATALOG_PATH}"
        return json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))

    def test_catalog_file_exists(self):
        assert _CATALOG_PATH.is_file(), f"addons/catalog.json missing at {_CATALOG_PATH}"

    def test_top_level_schema_field(self, catalog):
        assert "schema" in catalog, "catalog.json must have a top-level 'schema' field"
        assert catalog["schema"] == "project-setup-addon-catalog/v1"

    def test_top_level_note_field(self, catalog):
        assert "note" in catalog, "catalog.json must have a top-level 'note' field"
        assert "pending" in catalog["note"].lower() or "placeholder" in catalog["note"].lower(), (
            "note field should reference placeholder/pending status"
        )

    def test_modules_key_is_list(self, catalog):
        assert "modules" in catalog, "catalog.json must have a 'modules' key"
        assert isinstance(catalog["modules"], list), "'modules' must be a list"

    def test_exactly_18_modules(self, catalog):
        count = len(catalog["modules"])
        assert count == 18, f"Expected 18 addon modules, found {count}"

    def test_no_base_modules_present(self, catalog):
        names = {m["name"] for m in catalog["modules"] if isinstance(m, dict)}
        overlap = names & BASE_MODULES
        assert not overlap, f"Base modules must not be in addon catalog: {overlap}"

    def test_all_addon_modules_present(self, catalog):
        names = {m["name"] for m in catalog["modules"] if isinstance(m, dict)}
        missing = ADDON_MODULES - names
        assert not missing, f"These addon modules are missing from catalog: {missing}"

    def test_each_record_has_required_keys(self, catalog):
        for record in catalog["modules"]:
            assert isinstance(record, dict), f"Non-dict record: {record!r}"
            missing = REQUIRED_RECORD_KEYS - record.keys()
            assert not missing, f"Record {record.get('name', '?')} missing keys: {missing}"

    def test_each_record_has_nonempty_name(self, catalog):
        for record in catalog["modules"]:
            assert record.get("name", "").strip(), f"Empty name in record: {record!r}"

    def test_each_record_has_nonempty_description(self, catalog):
        for record in catalog["modules"]:
            assert record.get("description", "").strip(), (
                f"Empty description for module {record.get('name', '?')}"
            )

    def test_each_record_has_nonempty_locator(self, catalog):
        for record in catalog["modules"]:
            assert record.get("locator", "").strip(), (
                f"Empty locator for module {record.get('name', '?')}"
            )

    def test_each_record_has_valid_category(self, catalog):
        valid_categories = {"language", "quality", "tooling", "docs", "agentic", "integration", "monorepo"}
        for record in catalog["modules"]:
            cat = record.get("category", "")
            assert cat in valid_categories, (
                f"Module {record.get('name', '?')} has invalid category {cat!r}. "
                f"Expected one of {valid_categories}"
            )

    def test_language_modules_have_language_category(self, catalog):
        lang_modules = {"lang-python", "lang-ts", "lang-go", "lang-rust"}
        by_name = {m["name"]: m for m in catalog["modules"]}
        for name in lang_modules:
            assert by_name[name]["category"] == "language", (
                f"{name} must have category 'language', got {by_name[name]['category']!r}"
            )

    def test_no_hardcoded_srobroek_in_catalog(self, catalog):
        raw = _CATALOG_PATH.read_text(encoding="utf-8")
        assert "srobroek" not in raw.lower(), (
            "catalog.json must not contain a hardcoded 'srobroek' org reference"
        )


# --------------------------------------------------------------------------- #
# fetch_addon_catalog parses the catalog shape                                 #
# --------------------------------------------------------------------------- #

class TestFetchAddonCatalogParsesFileShape:
    """Verify sdk.fetch_addon_catalog handles the object-with-modules-key shape used by catalog.json."""

    def test_fetch_addon_catalog_parses_object_shape(self):
        """fetch_addon_catalog must return 18 records when given a catalog-file-shaped payload."""
        catalog_data = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
        # Use the _opener seam to feed the file contents directly (no network).
        result = sdk.fetch_addon_catalog(
            "file://unused",
            _opener=lambda url, timeout: catalog_data,
        )
        assert isinstance(result, list)
        assert len(result) == 18

    def test_fetch_addon_catalog_records_have_required_keys(self):
        catalog_data = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
        result = sdk.fetch_addon_catalog(
            "file://unused",
            _opener=lambda url, timeout: catalog_data,
        )
        for record in result:
            for key in ("name", "description", "locator", "category"):
                assert key in record, f"Record {record.get('name', '?')} missing '{key}'"

    def test_fetch_addon_catalog_returns_list_of_dicts(self):
        catalog_data = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
        result = sdk.fetch_addon_catalog(
            "file://unused",
            _opener=lambda url, timeout: catalog_data,
        )
        assert all(isinstance(r, dict) for r in result)

    def test_fetch_addon_catalog_no_base_modules_in_file(self):
        catalog_data = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
        result = sdk.fetch_addon_catalog(
            "file://unused",
            _opener=lambda url, timeout: catalog_data,
        )
        names = {r["name"] for r in result}
        overlap = names & BASE_MODULES
        assert not overlap, f"Base modules must not appear in catalog: {overlap}"


# --------------------------------------------------------------------------- #
# CLAUDE_PLUGIN_ROOT env-var fix (spec 020 FR-E1/E3)                          #
# --------------------------------------------------------------------------- #

class TestClaudePluginRootFallback:
    """paths.plugin_root() and executor env must accept CLAUDE_PLUGIN_ROOT."""

    def test_plugin_root_resolves_from_claude_plugin_root(self, tmp_path, monkeypatch):
        """plugin_root() uses CLAUDE_PLUGIN_ROOT when PLUGIN_ROOT is absent."""
        # Create a fake skill dir structure that plugin_root() recognises.
        fake_plugin = tmp_path / "fake-skill"
        (fake_plugin / "runner").mkdir(parents=True)

        monkeypatch.delenv("PLUGIN_ROOT", raising=False)
        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(fake_plugin))

        # Reload paths module in an isolated fashion to pick up the new env.
        import importlib
        paths_spec = importlib.util.spec_from_file_location(
            "paths_fresh", _RUNNER / "paths.py"
        )
        paths_fresh = importlib.util.module_from_spec(paths_spec)
        paths_spec.loader.exec_module(paths_fresh)

        result = paths_fresh.plugin_root()
        assert result == fake_plugin, (
            f"plugin_root() should return {fake_plugin} when CLAUDE_PLUGIN_ROOT is set, got {result}"
        )

    def test_plugin_root_plugin_root_env_takes_precedence(self, tmp_path, monkeypatch):
        """When both are set, PLUGIN_ROOT wins."""
        fake_pr = tmp_path / "by-plugin-root"
        (fake_pr / "runner").mkdir(parents=True)
        fake_cpr = tmp_path / "by-claude-plugin-root"
        (fake_cpr / "runner").mkdir(parents=True)

        monkeypatch.setenv("PLUGIN_ROOT", str(fake_pr))
        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(fake_cpr))

        import importlib
        paths_spec = importlib.util.spec_from_file_location(
            "paths_fresh2", _RUNNER / "paths.py"
        )
        paths_fresh2 = importlib.util.module_from_spec(paths_spec)
        paths_spec.loader.exec_module(paths_fresh2)

        result = paths_fresh2.plugin_root()
        assert result == fake_pr, (
            f"PLUGIN_ROOT must take precedence over CLAUDE_PLUGIN_ROOT, got {result}"
        )

    def test_module_load_sdk_accepts_claude_plugin_root(self, tmp_path, monkeypatch):
        """A module's _load_sdk fallback resolves sdk.py via CLAUDE_PLUGIN_ROOT."""
        # Verify that at least one patched module now uses the `or os.environ.get("CLAUDE_PLUGIN_ROOT")` pattern.
        import ast

        # Check a representative set of patched modules.
        patched_modules = [
            "core-identity", "lang-python", "github-repo", "codex-config",
            "speckit-bridge", "apm-install", "justfile-write", "ci-github-actions",
        ]
        modules_dir = _SKILL_DIR / "modules"
        for mod_id in patched_modules:
            source = (modules_dir / mod_id / "module.py").read_text(encoding="utf-8")
            assert 'os.environ.get("CLAUDE_PLUGIN_ROOT")' in source, (
                f"modules/{mod_id}/module.py missing CLAUDE_PLUGIN_ROOT fallback"
            )
            # Ensure PLUGIN_ROOT is still checked first (the `or` pattern).
            assert 'os.environ.get("PLUGIN_ROOT") or os.environ.get("CLAUDE_PLUGIN_ROOT")' in source, (
                f"modules/{mod_id}/module.py must keep PLUGIN_ROOT as primary with CLAUDE_PLUGIN_ROOT as fallback"
            )
