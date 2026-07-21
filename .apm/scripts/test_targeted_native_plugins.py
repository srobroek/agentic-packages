"""Target-aware package inventory and native plugin regression tests."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


def _load(name: str, filename: str):
    script = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build_inventory = _load("target_build_inventory", "build_inventory.py")
build_native_plugins = _load("target_build_native_plugins", "build-native-plugins.py")
build_marketplace_block = _load(
    "target_build_marketplace_block", "build-marketplace-block.py"
)
audit_codex_config = _load("target_audit_codex_config", "audit-codex-config.py")


def _manifest(path: Path, name: str, target: str) -> None:
    path.mkdir(parents=True)
    (path / "apm.yml").write_text(
        f"name: {name}\nversion: 1.0.0\ntype: hybrid\ntarget: {target}\n",
        encoding="utf-8",
    )


def test_inventory_normalizes_package_targets(tmp_path: Path, monkeypatch) -> None:
    packages = tmp_path / "packages"
    _manifest(packages / "both", "both", "all")
    _manifest(packages / "claude-only", "claude-only", "claude")
    monkeypatch.setattr(build_inventory, "PACKAGES_DIR", packages)

    context = build_inventory.build_context({"packages": []})
    records = {package["name"]: package for package in context["packages"]}

    assert records["both"]["target"] == "all"
    assert records["both"]["targets"] == ["claude", "codex"]
    assert records["claude-only"]["targets"] == ["claude"]


def test_inventory_rejects_unknown_package_target() -> None:
    with pytest.raises(ValueError, match="unsupported package target"):
        build_inventory._package_targets({"target": "future-runtime"})


def test_claude_only_package_omits_codex_native_output(
    tmp_path: Path,
    monkeypatch,
) -> None:
    packages = tmp_path / "packages"
    _manifest(packages / "lsp-rust", "lsp-rust", "claude")
    monkeypatch.setattr(build_native_plugins, "PACKAGES_DIR", packages)
    package = {
        "name": "lsp-rust",
        "dirname": "lsp-rust",
        "version": "1.0.0",
        "description": "Rust LSP",
        "classification": "bundle",
        "deps": [],
        "targets": ["claude"],
    }

    plan = build_native_plugins._plan_package(package, {}, ({}, "Apache-2.0"))

    assert plan is not None
    assert ".claude-plugin/plugin.json" in plan
    assert not any(path.startswith(".codex") for path in plan)


def test_all_target_preserves_claude_dependencies_and_codex_manifest(
    tmp_path: Path,
    monkeypatch,
) -> None:
    packages = tmp_path / "packages"
    _manifest(packages / "bundle", "bundle", "all")
    monkeypatch.setattr(build_native_plugins, "PACKAGES_DIR", packages)
    package = {
        "name": "bundle",
        "dirname": "bundle",
        "version": "1.0.0",
        "description": "Bundle",
        "classification": "bundle",
        "deps": ["srobroek/agentic-packages/packages/member#>=1.0.0 <2.0.0"],
        "targets": ["claude", "codex"],
    }

    plan = build_native_plugins._plan_package(package, {}, ({}, "Apache-2.0"))

    assert plan is not None
    claude = json.loads(plan[".claude-plugin/plugin.json"])
    codex = json.loads(plan[".codex-plugin/plugin.json"])
    assert claude["dependencies"] == [
        {"git": "srobroek/agentic-packages", "path": "packages/member"}
    ]
    assert "dependencies" not in codex


def test_codex_target_keeps_only_codex_hook_variant(
    tmp_path: Path,
    monkeypatch,
) -> None:
    packages = tmp_path / "packages"
    package_dir = packages / "codex-hook"
    _manifest(package_dir, "codex-hook", "codex")
    hooks_dir = package_dir / ".apm" / "hooks"
    hooks_dir.mkdir(parents=True)
    (hooks_dir / "hooks.json").write_text(
        '{"hooks":{"Stop":[{"hooks":[{"type":"command","command":"/bin/true"}]}]}}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(build_native_plugins, "PACKAGES_DIR", packages)
    package = {
        "name": "codex-hook",
        "dirname": "codex-hook",
        "version": "1.0.0",
        "description": "Hook",
        "classification": "hooks",
        "deps": [],
        "targets": ["codex"],
    }

    plan = build_native_plugins._plan_package(package, {}, ({}, "Apache-2.0"))

    assert plan is not None
    assert ".claude-plugin/plugin.json" not in plan
    assert "hooks/claude-hooks.json" not in plan
    assert "hooks/codex-hooks.json" in plan
    codex = json.loads(plan[".codex-plugin/plugin.json"])
    assert codex["hooks"] == "./hooks/codex-hooks.json"


def test_codex_marketplace_filter_removes_non_target_packages(
    tmp_path: Path,
) -> None:
    marketplace = tmp_path / "marketplace.json"
    marketplace.write_text(
        json.dumps(
            {
                "name": "catalog",
                "plugins": [
                    {"name": "shared", "source": {"path": "./shared"}},
                    {"name": "claude-only", "source": {"path": "./lsp"}},
                ],
            }
        ),
        encoding="utf-8",
    )

    assert build_marketplace_block.filter_codex_marketplace(
        marketplace,
        {"shared"},
        check=True,
    )
    assert len(json.loads(marketplace.read_text(encoding="utf-8"))["plugins"]) == 2

    assert build_marketplace_block.filter_codex_marketplace(marketplace, {"shared"})
    plugins = json.loads(marketplace.read_text(encoding="utf-8"))["plugins"]
    assert [plugin["name"] for plugin in plugins] == ["shared"]
    assert not build_marketplace_block.filter_codex_marketplace(
        marketplace,
        {"shared"},
        check=True,
    )


def test_claude_target_hook_is_omitted_from_codex_outputs_and_audit(
    tmp_path: Path,
    monkeypatch,
) -> None:
    packages = tmp_path / "packages"
    package_dir = packages / "claude-hook"
    _manifest(package_dir, "claude-hook", "claude")
    hooks_dir = package_dir / ".apm" / "hooks"
    hooks_dir.mkdir(parents=True)
    (hooks_dir / "hooks.json").write_text(
        '{"hooks":{"PreToolUse":[{"matcher":"Agent","hooks":[]}]}}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(build_native_plugins, "PACKAGES_DIR", packages)
    monkeypatch.setattr(audit_codex_config, "ROOT", tmp_path)
    package = {
        "name": "claude-hook",
        "dirname": "claude-hook",
        "version": "1.0.0",
        "description": "Claude hook",
        "classification": "hooks",
        "deps": [],
        "targets": ["claude"],
    }

    plan = build_native_plugins._plan_package(package, {}, ({}, "Apache-2.0"))

    assert plan is not None
    assert ".claude-plugin/plugin.json" in plan
    assert not any("codex" in path for path in plan)
    assert audit_codex_config.codex_hook_sources() == []
