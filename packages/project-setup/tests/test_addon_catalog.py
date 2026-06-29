"""Tests for sdk.fetch_addon_catalog and sdk.addon_catalog_urls — spec 020 FR-B1/B2.

Covers:
- fetch_addon_catalog: valid JSON list, object-with-"modules"-key, object-with-"addons"-key,
  malformed JSON, opener raising, empty list, non-list/non-object shape, extra keys tolerated,
  non-dict records filtered, timeout default forwarded.
- addon_catalog_urls: env var (single, comma-separated, space-separated, mixed),
  home config [catalog].urls, home config top-level catalog_urls, both sources merged+deduped
  (env first), nothing configured → [], malformed TOML → [], missing file → [].
- No hardcoded 'srobroek' or org-specific URL present in the new functions.

Run via:
  uv run --with pytest pytest -q packages/project-setup/tests/test_addon_catalog.py

Import-by-path pattern mirrors test_detect_marketplaces.py.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_RUNNER = Path(__file__).resolve().parents[1] / "skills" / "project-setup" / "runner"


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
fetch_addon_catalog = sdk.fetch_addon_catalog
addon_catalog_urls = sdk.addon_catalog_urls


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #

def _fake_opener(payload):
    """Return an opener that returns *payload* when called."""
    def _opener(url, timeout):
        return payload
    return _opener


def _raising_opener(exc):
    """Return an opener that raises *exc*."""
    def _opener(url, timeout):
        raise exc
    return _opener


# --------------------------------------------------------------------------- #
# fetch_addon_catalog                                                          #
# --------------------------------------------------------------------------- #

class TestFetchAddonCatalog:
    """Unit tests for sdk.fetch_addon_catalog."""

    def test_valid_list_returns_records(self):
        records = [
            {"name": "foo", "description": "Foo module", "locator": "git@host:org/foo", "category": "lang"},
            {"name": "bar", "description": "Bar module", "locator": "git@host:org/bar", "category": "ci"},
        ]
        result = fetch_addon_catalog("http://example.com/catalog.json", _opener=_fake_opener(records))
        assert result == records

    def test_object_with_modules_key(self):
        modules = [{"name": "baz", "locator": "git@host:org/baz", "category": "tool"}]
        payload = {"modules": modules, "version": "1"}
        result = fetch_addon_catalog("http://example.com/catalog.json", _opener=_fake_opener(payload))
        assert result == modules

    def test_object_with_addons_key(self):
        addons = [{"name": "qux", "locator": "git@host:org/qux", "category": "ci"}]
        payload = {"addons": addons}
        result = fetch_addon_catalog("http://example.com/catalog.json", _opener=_fake_opener(payload))
        assert result == addons

    def test_modules_key_takes_precedence_over_addons(self):
        modules = [{"name": "m", "locator": "git@host:org/m", "category": "base"}]
        addons = [{"name": "a", "locator": "git@host:org/a", "category": "extra"}]
        payload = {"modules": modules, "addons": addons}
        result = fetch_addon_catalog("http://example.com/catalog.json", _opener=_fake_opener(payload))
        assert result == modules

    def test_malformed_json_returns_empty(self, monkeypatch):
        """When the opener returns something non-list/non-dict, returns []."""
        result = fetch_addon_catalog("http://example.com/catalog.json", _opener=_fake_opener("not-json-list"))
        assert result == []

    def test_opener_raising_returns_empty(self):
        result = fetch_addon_catalog(
            "http://example.com/catalog.json",
            _opener=_raising_opener(OSError("network failure")),
        )
        assert result == []

    def test_opener_raising_connection_error_returns_empty(self):
        result = fetch_addon_catalog(
            "http://example.com/catalog.json",
            _opener=_raising_opener(ConnectionError("timed out")),
        )
        assert result == []

    def test_empty_list_returns_empty(self):
        result = fetch_addon_catalog("http://example.com/catalog.json", _opener=_fake_opener([]))
        assert result == []

    def test_object_with_empty_modules_returns_empty(self):
        result = fetch_addon_catalog("http://example.com/catalog.json", _opener=_fake_opener({"modules": []}))
        assert result == []

    def test_non_list_shape_integer_returns_empty(self):
        result = fetch_addon_catalog("http://example.com/catalog.json", _opener=_fake_opener(42))
        assert result == []

    def test_non_list_shape_none_returns_empty(self):
        result = fetch_addon_catalog("http://example.com/catalog.json", _opener=_fake_opener(None))
        assert result == []

    def test_object_modules_not_a_list_returns_empty(self):
        result = fetch_addon_catalog(
            "http://example.com/catalog.json",
            _opener=_fake_opener({"modules": "should-be-a-list"}),
        )
        assert result == []

    def test_non_dict_records_filtered_out(self):
        """Non-dict items inside a valid list are silently dropped."""
        records = [
            {"name": "good", "locator": "git@host:org/good", "category": "lang"},
            "string-entry",
            None,
            42,
            {"name": "also-good", "locator": "git@host:org/ok", "category": "ci"},
        ]
        result = fetch_addon_catalog("http://example.com/catalog.json", _opener=_fake_opener(records))
        assert len(result) == 2
        assert result[0]["name"] == "good"
        assert result[1]["name"] == "also-good"

    def test_extra_keys_ignored(self):
        """Records with extra keys beyond the schema are passed through unchanged."""
        records = [{"name": "x", "locator": "git@host:org/x", "category": "tool", "extra_key": "value"}]
        result = fetch_addon_catalog("http://example.com/catalog.json", _opener=_fake_opener(records))
        assert result[0]["extra_key"] == "value"

    def test_missing_optional_keys_tolerated(self):
        """Records missing 'description' or 'category' are still returned."""
        records = [{"name": "minimal", "locator": "git@host:org/minimal"}]
        result = fetch_addon_catalog("http://example.com/catalog.json", _opener=_fake_opener(records))
        assert result == records

    def test_timeout_forwarded_to_opener(self):
        """The timeout kwarg is forwarded to the opener."""
        received = {}

        def _capturing_opener(url, timeout):
            received["timeout"] = timeout
            return []

        fetch_addon_catalog("http://example.com/catalog.json", timeout=3.5, _opener=_capturing_opener)
        assert received["timeout"] == 3.5

    def test_real_network_unreachable_returns_empty(self):
        """Without an opener, an unreachable URL must return [] not raise."""
        # 0.0.0.0:0 is a reliably unreachable address.
        result = fetch_addon_catalog("http://0.0.0.0:0/nope")
        assert result == []

    def test_never_raises_on_exception_in_opener(self):
        """Even a truly unexpected exception from the opener must not propagate."""
        result = fetch_addon_catalog(
            "http://example.com/catalog.json",
            _opener=_raising_opener(RuntimeError("unexpected")),
        )
        assert result == []


# --------------------------------------------------------------------------- #
# addon_catalog_urls                                                           #
# --------------------------------------------------------------------------- #

class TestAddonCatalogUrls:
    """Unit tests for sdk.addon_catalog_urls."""

    def test_no_config_no_env_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.delenv("PROJECT_SETUP_CATALOG_URL", raising=False)
        monkeypatch.delenv("PROJECT_SETUP_CONFIG", raising=False)
        result = addon_catalog_urls(home=tmp_path)
        assert result == []

    def test_single_env_url(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PROJECT_SETUP_CATALOG_URL", "https://example.com/catalog.json")
        result = addon_catalog_urls(home=tmp_path)
        assert result == ["https://example.com/catalog.json"]

    def test_comma_separated_env_urls(self, tmp_path, monkeypatch):
        monkeypatch.setenv(
            "PROJECT_SETUP_CATALOG_URL",
            "https://a.example.com/cat.json,https://b.example.com/cat.json",
        )
        result = addon_catalog_urls(home=tmp_path)
        assert result == [
            "https://a.example.com/cat.json",
            "https://b.example.com/cat.json",
        ]

    def test_space_separated_env_urls(self, tmp_path, monkeypatch):
        monkeypatch.setenv(
            "PROJECT_SETUP_CATALOG_URL",
            "https://a.example.com/cat.json https://b.example.com/cat.json",
        )
        result = addon_catalog_urls(home=tmp_path)
        assert result == [
            "https://a.example.com/cat.json",
            "https://b.example.com/cat.json",
        ]

    def test_mixed_comma_space_env_urls(self, tmp_path, monkeypatch):
        monkeypatch.setenv(
            "PROJECT_SETUP_CATALOG_URL",
            "https://a.example.com/cat.json, https://b.example.com/cat.json",
        )
        result = addon_catalog_urls(home=tmp_path)
        assert result == [
            "https://a.example.com/cat.json",
            "https://b.example.com/cat.json",
        ]

    def test_home_config_catalog_urls_section(self, tmp_path, monkeypatch):
        monkeypatch.delenv("PROJECT_SETUP_CATALOG_URL", raising=False)
        cfg_dir = tmp_path / ".config" / "project-setup"
        cfg_dir.mkdir(parents=True)
        (cfg_dir / "config.toml").write_text(
            '[catalog]\nurls = ["https://org.example.com/catalog.json"]\n',
            encoding="utf-8",
        )
        result = addon_catalog_urls(home=tmp_path)
        assert result == ["https://org.example.com/catalog.json"]

    def test_home_config_top_level_catalog_urls(self, tmp_path, monkeypatch):
        monkeypatch.delenv("PROJECT_SETUP_CATALOG_URL", raising=False)
        cfg_dir = tmp_path / ".config" / "project-setup"
        cfg_dir.mkdir(parents=True)
        (cfg_dir / "config.toml").write_text(
            'catalog_urls = ["https://top.example.com/catalog.json"]\n',
            encoding="utf-8",
        )
        result = addon_catalog_urls(home=tmp_path)
        assert result == ["https://top.example.com/catalog.json"]

    def test_env_and_config_merged_env_first(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PROJECT_SETUP_CATALOG_URL", "https://env.example.com/cat.json")
        cfg_dir = tmp_path / ".config" / "project-setup"
        cfg_dir.mkdir(parents=True)
        (cfg_dir / "config.toml").write_text(
            '[catalog]\nurls = ["https://cfg.example.com/catalog.json"]\n',
            encoding="utf-8",
        )
        result = addon_catalog_urls(home=tmp_path)
        assert result == [
            "https://env.example.com/cat.json",
            "https://cfg.example.com/catalog.json",
        ]

    def test_deduplication_preserves_order(self, tmp_path, monkeypatch):
        """Duplicate URLs are deduplicated; first occurrence wins."""
        monkeypatch.setenv("PROJECT_SETUP_CATALOG_URL", "https://shared.example.com/cat.json")
        cfg_dir = tmp_path / ".config" / "project-setup"
        cfg_dir.mkdir(parents=True)
        (cfg_dir / "config.toml").write_text(
            '[catalog]\nurls = ["https://shared.example.com/cat.json", "https://extra.example.com/cat.json"]\n',
            encoding="utf-8",
        )
        result = addon_catalog_urls(home=tmp_path)
        # shared URL appears only once (env), extra follows
        assert result == [
            "https://shared.example.com/cat.json",
            "https://extra.example.com/cat.json",
        ]

    def test_malformed_toml_returns_only_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PROJECT_SETUP_CATALOG_URL", "https://env.example.com/cat.json")
        cfg_dir = tmp_path / ".config" / "project-setup"
        cfg_dir.mkdir(parents=True)
        (cfg_dir / "config.toml").write_text("not valid toml [[[\n", encoding="utf-8")
        result = addon_catalog_urls(home=tmp_path)
        # malformed TOML → only env URL survives
        assert result == ["https://env.example.com/cat.json"]

    def test_malformed_toml_no_env_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.delenv("PROJECT_SETUP_CATALOG_URL", raising=False)
        cfg_dir = tmp_path / ".config" / "project-setup"
        cfg_dir.mkdir(parents=True)
        (cfg_dir / "config.toml").write_text("not valid toml [[[\n", encoding="utf-8")
        result = addon_catalog_urls(home=tmp_path)
        assert result == []

    def test_missing_config_file_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.delenv("PROJECT_SETUP_CATALOG_URL", raising=False)
        # tmp_path has no config.toml
        result = addon_catalog_urls(home=tmp_path)
        assert result == []

    def test_catalog_section_wrong_type_ignored(self, tmp_path, monkeypatch):
        """If [catalog] urls is not a list, it is skipped without raising."""
        monkeypatch.delenv("PROJECT_SETUP_CATALOG_URL", raising=False)
        cfg_dir = tmp_path / ".config" / "project-setup"
        cfg_dir.mkdir(parents=True)
        (cfg_dir / "config.toml").write_text(
            '[catalog]\nurls = "not-a-list"\n',
            encoding="utf-8",
        )
        result = addon_catalog_urls(home=tmp_path)
        assert result == []

    def test_multiple_catalog_section_urls(self, tmp_path, monkeypatch):
        monkeypatch.delenv("PROJECT_SETUP_CATALOG_URL", raising=False)
        cfg_dir = tmp_path / ".config" / "project-setup"
        cfg_dir.mkdir(parents=True)
        (cfg_dir / "config.toml").write_text(
            '[catalog]\nurls = [\n  "https://a.example.com/cat.json",\n  "https://b.example.com/cat.json",\n]\n',
            encoding="utf-8",
        )
        result = addon_catalog_urls(home=tmp_path)
        assert result == [
            "https://a.example.com/cat.json",
            "https://b.example.com/cat.json",
        ]


# --------------------------------------------------------------------------- #
# Hardcoded-URL guard (SC-X, FR-X1)                                           #
# --------------------------------------------------------------------------- #

class TestNoHardcodedUrls:
    """Assert that no org-specific / srobroek URL is hardcoded in the new code."""

    def test_no_srobroek_in_fetch_addon_catalog_source(self):
        import inspect
        src = inspect.getsource(sdk.fetch_addon_catalog)
        assert "srobroek" not in src.lower(), (
            "fetch_addon_catalog must not contain a hardcoded 'srobroek' URL"
        )

    def test_no_srobroek_in_addon_catalog_urls_source(self):
        import inspect
        src = inspect.getsource(sdk.addon_catalog_urls)
        assert "srobroek" not in src.lower(), (
            "addon_catalog_urls must not contain a hardcoded 'srobroek' URL"
        )

    def test_no_hardcoded_http_default_in_fetch_addon_catalog(self):
        import inspect
        src = inspect.getsource(sdk.fetch_addon_catalog)
        # No github.com or raw.githubusercontent.com default in the function body
        assert "github.com" not in src or "example" in src or src.count("github.com") == 0

    def test_no_hardcoded_http_default_in_addon_catalog_urls(self):
        import inspect
        src = inspect.getsource(sdk.addon_catalog_urls)
        assert "github.com" not in src
