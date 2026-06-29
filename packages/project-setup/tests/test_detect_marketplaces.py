"""Tests for sdk.detect_marketplaces() — spec 018 SC-002.

Covers:
- APM registry shape: names extracted from marketplaces[].name
- Claude Code registry shape: names = keys of the flat JSON object
- Codex registry shape: names = keys of the [marketplaces] TOML table
- Missing files (empty tmp home) → all three lists == []
- Malformed JSON / malformed TOML → affected system == [], no raise
- Empty registries (no entries) → lists == []
- All three populated in one tmp home → all three non-empty

Run via:
  uv run --with pytest pytest -q packages/project-setup/tests/test_detect_marketplaces.py
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
detect_marketplaces = sdk.detect_marketplaces


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #

def _write_apm(home: Path, data: object) -> None:
    d = home / ".apm"
    d.mkdir(parents=True, exist_ok=True)
    (d / "marketplaces.json").write_text(json.dumps(data), encoding="utf-8")


def _write_cc(home: Path, data: object) -> None:
    d = home / ".claude" / "plugins"
    d.mkdir(parents=True, exist_ok=True)
    (d / "known_marketplaces.json").write_text(json.dumps(data), encoding="utf-8")


def _write_codex(home: Path, content: str) -> None:
    d = home / ".codex"
    d.mkdir(parents=True, exist_ok=True)
    (d / "config.toml").write_text(content, encoding="utf-8")


# --------------------------------------------------------------------------- #
# APM                                                                          #
# --------------------------------------------------------------------------- #

def test_apm_names_extracted(tmp_path):
    _write_apm(tmp_path, {
        "marketplaces": [
            {"name": "mp-a", "url": "https://example.com/mp-a"},
            {"name": "mp-b"},
        ]
    })
    result = detect_marketplaces(home=tmp_path)
    assert result["apm"] == ["mp-a", "mp-b"]


def test_apm_empty_registry(tmp_path):
    _write_apm(tmp_path, {"marketplaces": []})
    result = detect_marketplaces(home=tmp_path)
    assert result["apm"] == []


def test_apm_missing_file(tmp_path):
    # No .apm directory at all
    result = detect_marketplaces(home=tmp_path)
    assert result["apm"] == []


def test_apm_malformed_json(tmp_path):
    d = tmp_path / ".apm"
    d.mkdir(parents=True)
    (d / "marketplaces.json").write_text("not valid json {{{{", encoding="utf-8")
    result = detect_marketplaces(home=tmp_path)
    assert result["apm"] == []


def test_apm_entries_without_name_skipped(tmp_path):
    _write_apm(tmp_path, {
        "marketplaces": [
            {"url": "https://example.com/no-name"},
            {"name": "good-one"},
            {"name": ""},          # empty name → falsy → skipped
        ]
    })
    result = detect_marketplaces(home=tmp_path)
    assert result["apm"] == ["good-one"]


# --------------------------------------------------------------------------- #
# Claude Code                                                                  #
# --------------------------------------------------------------------------- #

def test_cc_names_from_keys(tmp_path):
    _write_cc(tmp_path, {"official": {}, "repomix": {}})
    result = detect_marketplaces(home=tmp_path)
    assert set(result["claude-code"]) == {"official", "repomix"}


def test_cc_empty_object(tmp_path):
    _write_cc(tmp_path, {})
    result = detect_marketplaces(home=tmp_path)
    assert result["claude-code"] == []


def test_cc_missing_file(tmp_path):
    result = detect_marketplaces(home=tmp_path)
    assert result["claude-code"] == []


def test_cc_malformed_json(tmp_path):
    d = tmp_path / ".claude" / "plugins"
    d.mkdir(parents=True)
    (d / "known_marketplaces.json").write_text("[broken", encoding="utf-8")
    result = detect_marketplaces(home=tmp_path)
    assert result["claude-code"] == []


# --------------------------------------------------------------------------- #
# Codex                                                                        #
# --------------------------------------------------------------------------- #

def test_codex_names_from_toml(tmp_path):
    _write_codex(tmp_path, """
[marketplaces.alpha]
url = "https://example.com/alpha"

[marketplaces.beta]
url = "https://example.com/beta"
""")
    result = detect_marketplaces(home=tmp_path)
    assert sorted(result["codex"]) == ["alpha", "beta"]


def test_codex_no_marketplaces_key(tmp_path):
    _write_codex(tmp_path, """
[settings]
theme = "dark"
""")
    result = detect_marketplaces(home=tmp_path)
    assert result["codex"] == []


def test_codex_missing_file(tmp_path):
    result = detect_marketplaces(home=tmp_path)
    assert result["codex"] == []


def test_codex_malformed_toml(tmp_path):
    d = tmp_path / ".codex"
    d.mkdir(parents=True)
    (d / "config.toml").write_text("[[[[broken toml", encoding="utf-8")
    result = detect_marketplaces(home=tmp_path)
    assert result["codex"] == []


# --------------------------------------------------------------------------- #
# Cross-system / error isolation                                               #
# --------------------------------------------------------------------------- #

def test_all_missing_returns_empty_lists(tmp_path):
    result = detect_marketplaces(home=tmp_path)
    assert result == {"apm": [], "claude-code": [], "codex": []}


def test_malformed_apm_does_not_affect_others(tmp_path):
    # Corrupt APM but valid Claude Code + Codex
    d = tmp_path / ".apm"
    d.mkdir(parents=True)
    (d / "marketplaces.json").write_text("!!bad json!!", encoding="utf-8")
    _write_cc(tmp_path, {"my-marketplace": {}})
    _write_codex(tmp_path, "[marketplaces.x]\n")
    result = detect_marketplaces(home=tmp_path)
    assert result["apm"] == []
    assert result["claude-code"] == ["my-marketplace"]
    assert result["codex"] == ["x"]


def test_malformed_codex_does_not_affect_others(tmp_path):
    _write_apm(tmp_path, {"marketplaces": [{"name": "apm-one"}]})
    _write_cc(tmp_path, {"cc-one": {}})
    d = tmp_path / ".codex"
    d.mkdir(parents=True)
    (d / "config.toml").write_text("[[[[bad", encoding="utf-8")
    result = detect_marketplaces(home=tmp_path)
    assert result["apm"] == ["apm-one"]
    assert result["claude-code"] == ["cc-one"]
    assert result["codex"] == []


def test_all_three_populated(tmp_path):
    _write_apm(tmp_path, {
        "marketplaces": [
            {"name": "apm-mp-1"},
            {"name": "apm-mp-2"},
        ]
    })
    _write_cc(tmp_path, {"cc-official": {}, "cc-community": {}})
    _write_codex(tmp_path, """
[marketplaces.codex-store]
url = "https://example.com"

[marketplaces.codex-local]
path = "/tmp/local"
""")
    result = detect_marketplaces(home=tmp_path)
    assert result["apm"] == ["apm-mp-1", "apm-mp-2"]
    assert set(result["claude-code"]) == {"cc-official", "cc-community"}
    assert sorted(result["codex"]) == ["codex-local", "codex-store"]


def test_never_raises_on_nonexistent_home():
    # Entirely non-existent path — must not raise, return empty lists
    result = detect_marketplaces(home="/nonexistent/home/path/that/does/not/exist")
    assert result == {"apm": [], "claude-code": [], "codex": []}
