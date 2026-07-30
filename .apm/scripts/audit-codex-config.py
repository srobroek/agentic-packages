#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6"]
# ///
"""Validate Codex-specific package manifests, hooks, and MCP files."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SUPPORTED_EVENTS = {
    "SessionStart",
    "SubagentStart",
    "PreToolUse",
    "PermissionRequest",
    "PostToolUse",
    "PreCompact",
    "PostCompact",
    "UserPromptSubmit",
    "SubagentStop",
    "Stop",
}
CLAUDE_EVENTS = {
    "SessionStart",
    "Setup",
    "InstructionsLoaded",
    "UserPromptSubmit",
    "UserPromptExpansion",
    "MessageDisplay",
    "PreToolUse",
    "PermissionRequest",
    "PostToolUse",
    "PostToolUseFailure",
    "PostToolBatch",
    "PermissionDenied",
    "Notification",
    "SubagentStart",
    "SubagentStop",
    "TaskCreated",
    "TaskCompleted",
    "Stop",
    "StopFailure",
    "TeammateIdle",
    "ConfigChange",
    "CwdChanged",
    "FileChanged",
    "WorktreeCreate",
    "WorktreeRemove",
    "PreCompact",
    "PostCompact",
    "SessionEnd",
    "Elicitation",
    "ElicitationResult",
}
CODEX_DIFFERENCE_PACKAGES = {
    "adr-as-beads",
    "agent-builder",
    "hooks-attribution-guard",
    "hooks-bash-safety",
    "hooks-chezmoi-guard",
    "hooks-close-keywords",
    "hooks-git-safety",
    "hooks-package-investigate",
    "hooks-quality",
    "hooks-worktrunk",
    "language-go",
    "language-python",
    "language-rust",
    "language-shell",
    "language-terraform",
    "language-typescript",
    "lsp-go",
    "lsp-python",
    "lsp-rust",
    "lsp-shell",
    "lsp-terraform",
    "lsp-typescript",
    "orchestrate",
    "release-please",
    "speckit",
    "worktrunk-writer",
}
SUPPORTED_PACKAGE_TARGETS = {"all", "claude", "codex"}
HOOK_MANIFEST_CLASSIFICATION = {
    "packages/adr-as-beads/.apm/hooks/hooks.json": "native-required",
    "packages/beads/.apm/hooks/beads-claude-hooks.json": "target-specific compatibility",
    "packages/beads/.apm/hooks/beads-codex-hooks.json": "target-specific compatibility",
    "packages/code-intelligence/.apm/hooks/hooks.json": "native-required",
    "packages/hooks-attribution-guard/.apm/hooks/hooks.json": "native-required",
    "packages/hooks-bash-safety/.apm/hooks/hooks.json": "native-required",
    "packages/hooks-chezmoi-guard/.apm/hooks/hooks.json": "native-required",
    "packages/hooks-close-keywords/.apm/hooks/hooks.json": "native-required",
    "packages/hooks-git-safety/.apm/hooks/hooks.json": "native-required",
    "packages/hooks-package-investigate/.apm/hooks/hooks.json": "native-required",
    "packages/hooks-quality/.apm/hooks/hooks.json": "native-required",
    "packages/hooks-serena/.apm/hooks/hooks-serena-claude-hooks.json": "target-specific compatibility",
    "packages/hooks-serena/.apm/hooks/hooks-serena-codex-hooks.json": "target-specific compatibility",
    "packages/hooks-subagent-fork/.apm/hooks/hooks.json": "native-required",
    "packages/hooks-subagent-model/.apm/hooks/hooks.json": "excluded-policy",
    "packages/hooks-subagent-worktree/.apm/hooks/hooks-subagent-worktree-claude-hooks.json": "excluded-policy",
    "packages/hooks-worktrunk/.apm/hooks/hooks-worktrunk-claude-hooks.json": "target-specific compatibility",
    "packages/hooks-worktrunk/.apm/hooks/hooks-worktrunk-codex-hooks.json": "target-specific compatibility",
    "packages/orchestrate/.apm/hooks/orchestrate-claude-hooks.json": "target-specific compatibility",
    "packages/orchestrate/.apm/hooks/orchestrate-codex-hooks.json": "target-specific compatibility",
    "packages/token-savings/.apm/hooks/token-savings-claude-hooks.json": "target-specific compatibility",
    "packages/token-savings/.apm/hooks/token-savings-codex-hooks.json": "target-specific compatibility",
    "packages/toolchain-cache-policy/.apm/hooks/toolchain-cache-policy-claude-hooks.json": "target-specific compatibility",
    "packages/toolchain-cache-policy/.apm/hooks/toolchain-cache-policy-codex-hooks.json": "target-specific compatibility",
    "packages/release-please/.apm/hooks/hooks.json": "native-required",
    "packages/speckit/.apm/hooks/speckit-workflow-claude-hooks.json": "target-specific compatibility",
    "packages/speckit/.apm/hooks/speckit-workflow-codex-hooks.json": "target-specific compatibility",
    "packages/steering-pragmatic/.apm/hooks/hooks.json": "native-required",
    "packages/steering-git-workflow/.apm/hooks/git-workflow-claude-hooks.json": "target-specific compatibility",
    "packages/steering-git-workflow/.apm/hooks/git-workflow-codex-hooks.json": "target-specific compatibility",
    "packages/worktrunk-writer/.apm/hooks/worktrunk-writer-claude-hooks.json": "target-specific compatibility",
    "packages/worktrunk-writer/.apm/hooks/worktrunk-writer-codex-hooks.json": "target-specific compatibility",
}
OBSOLETE_HOOK_MANIFESTS = {
    "packages/agent-builder/.apm/hooks/agent-builder-claude-hooks.json",
    # speckit absorbed speckit-beads; its guard now rides the speckit-workflow
    # manifests. Only one *-claude-hooks.json per package is read
    # (build-native-plugins._hook_sources takes claude[0]), so a second manifest
    # here would deploy nothing while looking wired.
    "packages/speckit-beads/.apm/hooks/speckit-beads-claude-hooks.json",
    "packages/speckit-beads/.apm/hooks/speckit-beads-codex-hooks.json",
}
COLLAPSED_DUPLICATE_HOOK_MANIFESTS = {
    "packages/pr-shepherd/.apm/hooks/pr-shepherd-claude-hooks.json",
    "packages/pr-shepherd/.apm/hooks/pr-shepherd-codex-hooks.json",
}
APPROVAL_POLICIES = {
    "untrusted",
    "on-failure",
    "on-request",
    "granular",
    "never",
}
PLUGIN_SCRIPT_RE = re.compile(r"\$\{PLUGIN_ROOT\}/([A-Za-z0-9_./-]+)")
PROJECT_SCRIPT_RE = re.compile(r"\$\(git rev-parse --show-toplevel\)/\./([A-Za-z0-9_./-]+)")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def markdown_table_ids(text: str, start: str, end: str) -> list[str]:
    """Return backticked first-column values between two Markdown headings."""
    if start not in text or end not in text:
        return []
    section = text.split(start, 1)[1].split(end, 1)[0]
    return re.findall(r"^\| `([^`]+)` \|", section, flags=re.MULTILINE)


def codex_hook_sources() -> list[Path]:
    paths = list((ROOT / ".apm" / "hooks").glob("*-codex-hooks.json"))
    for hooks_dir in (ROOT / "packages").glob("*/.apm/hooks"):
        manifest_path = hooks_dir.parents[1] / "apm.yml"
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        if manifest.get("target") == "claude":
            continue
        universal = hooks_dir / "hooks.json"
        if universal.is_file():
            paths.append(universal)
        paths.extend(hooks_dir.glob("*-codex-hooks.json"))
        paths.extend(hooks_dir.glob("codex-hooks.json"))
    return sorted(set(paths))


def validate_hook_command(path: Path, command: object) -> list[str]:
    if not isinstance(command, str) or not command.strip():
        return [f"{path}: command hook must define a non-empty command"]

    errors: list[str] = []
    is_project_source = path.parent == ROOT / ".apm" / "hooks"
    if is_project_source:
        if "${PLUGIN_ROOT}" in command:
            errors.append(
                f"{path}: project hooks must use APM's /./ source marker, not PLUGIN_ROOT"
            )
        for rel in PROJECT_SCRIPT_RE.findall(command):
            target = ROOT / ".apm" / "hooks" / rel
            if not target.is_file():
                errors.append(f"{path}: missing project hook target {rel}")
        if "/scripts/" in command and not PROJECT_SCRIPT_RE.search(command):
            errors.append(
                f"{path}: project hook script must use "
                "'$(git rev-parse --show-toplevel)/./scripts/...'"
            )
        return errors

    if "git rev-parse" in command:
        errors.append(f"{path}: plugin hook startup must not discover the Git root")
    plugin_root = path.parents[2]
    script_refs = PLUGIN_SCRIPT_RE.findall(command)
    if "/scripts/" in command and not script_refs:
        errors.append(f"{path}: plugin hook scripts must resolve through PLUGIN_ROOT")
    for rel in script_refs:
        target = plugin_root / rel
        # A ${PLUGIN_ROOT}/... reference is usually a script file, but may also
        # be a resource directory passed to the hook (e.g. RULES_DIR=.apm/rules
        # for the bead-contract evaluator). Accept either; only a reference that
        # resolves to nothing is a real missing-target error.
        if not target.is_file() and not target.is_dir():
            errors.append(f"{path}: missing plugin hook target {rel}")
    return errors


def main() -> int:
    errors: list[str] = []
    marketplace = load_json(ROOT / ".agents" / "plugins" / "marketplace.json")
    root_manifest = yaml.safe_load((ROOT / "apm.yml").read_text(encoding="utf-8")) or {}
    catalog_entries = (root_manifest.get("marketplace") or {}).get("packages") or []
    marketplace_entries = marketplace.get("plugins") or []
    checked_manifests = 0
    checked_mcp = 0
    checked_hooks = 0
    checked_agents = 0

    codex_catalog_entries = []
    for entry in catalog_entries:
        if not isinstance(entry, dict) or not entry.get("name"):
            codex_catalog_entries.append(entry)
            continue
        source = entry.get("source")
        target = "all"
        if isinstance(source, str) and source.startswith("./packages/"):
            package_manifest_path = ROOT / source.removeprefix("./") / "apm.yml"
            package_manifest = (
                yaml.safe_load(package_manifest_path.read_text(encoding="utf-8")) or {}
            )
            target = package_manifest.get("target", "all")
            if target not in SUPPORTED_PACKAGE_TARGETS:
                errors.append(f"{entry['name']}: unsupported package target {target!r}")
        else:
            # External entries (git-source, not ./packages/) are packed by their
            # own upstream repo and are never present in this repo's marketplace.json.
            # Skip them from the Codex catalog cross-check.
            continue
        if target != "claude":
            codex_catalog_entries.append(entry)

    catalog_by_name = {
        str(entry["name"]): entry
        for entry in codex_catalog_entries
        if isinstance(entry, dict) and entry.get("name")
    }
    marketplace_by_name = {
        str(entry["name"]): entry
        for entry in marketplace_entries
        if isinstance(entry, dict) and entry.get("name")
    }
    all_catalog_names = {
        str(entry["name"])
        for entry in catalog_entries
        if isinstance(entry, dict) and entry.get("name")
    }
    if len(catalog_by_name) != len(codex_catalog_entries):
        errors.append("apm.yml marketplace contains missing or duplicate Codex package names")
    if len(marketplace_by_name) != len(marketplace_entries):
        errors.append("Codex marketplace contains missing or duplicate plugin names")
    for name in sorted(catalog_by_name.keys() - marketplace_by_name.keys()):
        errors.append(f"{name}: missing from Codex marketplace")
    for name in sorted(marketplace_by_name.keys() - catalog_by_name.keys()):
        errors.append(f"{name}: not declared in apm.yml marketplace")
    for name in sorted(catalog_by_name.keys() & marketplace_by_name.keys()):
        expected = catalog_by_name[name].get("source")
        actual_source = marketplace_by_name[name].get("source")
        actual = actual_source.get("path") if isinstance(actual_source, dict) else actual_source
        if expected != actual:
            errors.append(f"{name}: Codex marketplace source {actual!r} != catalog {expected!r}")

    compatibility = (ROOT / "docs" / "codex-compatibility.md").read_text(encoding="utf-8")
    documented_events = markdown_table_ids(
        compatibility,
        "## Event parity",
        "## Package-specific adaptations",
    )
    documented_packages = markdown_table_ids(
        compatibility,
        "## Package-level differences",
        "## Validation",
    )
    if len(documented_events) != len(set(documented_events)):
        errors.append("Codex compatibility event table contains duplicate rows")
    if set(documented_events) != CLAUDE_EVENTS:
        missing = sorted(CLAUDE_EVENTS - set(documented_events))
        extra = sorted(set(documented_events) - CLAUDE_EVENTS)
        errors.append(f"Codex compatibility event table drift: missing={missing}, extra={extra}")
    if len(documented_packages) != len(set(documented_packages)):
        errors.append("Codex compatibility package table contains duplicate rows")
    unknown_differences = CODEX_DIFFERENCE_PACKAGES - all_catalog_names
    if unknown_differences:
        errors.append(
            f"Codex difference package set contains unknown packages: {sorted(unknown_differences)}"
        )
    if set(documented_packages) != CODEX_DIFFERENCE_PACKAGES:
        missing = sorted(CODEX_DIFFERENCE_PACKAGES - set(documented_packages))
        extra = sorted(set(documented_packages) - CODEX_DIFFERENCE_PACKAGES)
        errors.append(
            f"Codex compatibility difference table drift: missing={missing}, extra={extra}"
        )

    for entry in marketplace_entries:
        source = entry.get("source", {})
        rel = source.get("path") if isinstance(source, dict) else None
        if not isinstance(rel, str) or not rel.startswith("./"):
            continue
        plugin_root = ROOT / rel.removeprefix("./")
        manifest_path = plugin_root / ".codex-plugin" / "plugin.json"
        if not manifest_path.is_file():
            errors.append(f"{entry.get('name')}: missing .codex-plugin/plugin.json")
            continue
        checked_manifests += 1
        manifest = load_json(manifest_path)
        if manifest.get("name") != entry.get("name"):
            errors.append(f"{manifest_path}: name does not match marketplace entry")
        for field in ("skills", "mcpServers", "hooks"):
            value = manifest.get(field)
            if value is None:
                continue
            values = value if isinstance(value, list) else [value]
            for component in values:
                if not isinstance(component, str) or not component.startswith("./"):
                    errors.append(f"{manifest_path}: {field} path must start with ./")
                    continue
                target = plugin_root / component.removeprefix("./")
                if not target.exists():
                    errors.append(f"{manifest_path}: missing {field} target {component}")
        mcp_path = manifest.get("mcpServers")
        if isinstance(mcp_path, str):
            checked_mcp += 1
            mcp = load_json(plugin_root / mcp_path.removeprefix("./"))
            if "mcpServers" in mcp:
                errors.append(f"{manifest_path}: Codex MCP file uses Claude mcpServers wrapper")
            servers = mcp.get("mcp_servers", mcp)
            if not isinstance(servers, dict) or not servers:
                errors.append(f"{manifest_path}: Codex MCP server map is empty")

    for path in codex_hook_sources():
        checked_hooks += 1
        hook_config = load_json(path).get("hooks") or {}
        events = set(hook_config.keys())
        for event in sorted(events - SUPPORTED_EVENTS):
            errors.append(f"{path}: unsupported Codex hook event {event}")
        for groups in hook_config.values():
            for group in groups:
                handlers = group.get("hooks", [])
                if not handlers:
                    errors.append(f"{path}: empty Codex hook matcher group")
                for handler in handlers:
                    if handler.get("type") != "command":
                        errors.append(f"{path}: Codex runs only command hook handlers")
                    if handler.get("async") is True:
                        errors.append(f"{path}: Codex skips asynchronous command hooks")
                    if "if" in handler:
                        errors.append(f"{path}: Codex does not define Claude's hook if field")
                    timeout = handler.get("timeout")
                    if not isinstance(timeout, (int, float)) or not (0 < timeout <= 60):
                        errors.append(
                            f"{path}: Codex hook timeout must be explicitly bounded to 1-60s"
                        )
                    errors.extend(validate_hook_command(path, handler.get("command")))

    actual_hook_manifests = {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "packages").glob("*/.apm/hooks/*.json")
    }
    expected_hook_manifests = set(HOOK_MANIFEST_CLASSIFICATION)
    if actual_hook_manifests != expected_hook_manifests:
        errors.append(
            "hook manifest inventory drift: "
            f"missing={sorted(expected_hook_manifests - actual_hook_manifests)}, "
            f"unclassified={sorted(actual_hook_manifests - expected_hook_manifests)}"
        )
    for rel in sorted(OBSOLETE_HOOK_MANIFESTS | COLLAPSED_DUPLICATE_HOOK_MANIFESTS):
        if (ROOT / rel).exists():
            errors.append(f"{rel}: retired hook manifest must stay removed")

    for path in sorted((ROOT / "packages").glob("*/.apm/agents/*.agent.md")):
        checked_agents += 1
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---\n") or "\n---" not in text[4:]:
            continue
        frontmatter = yaml.safe_load(text.split("\n---", 1)[0][4:]) or {}
        codex = (frontmatter.get("x-agentic") or {}).get("codex") or {}
        policy = codex.get("approval_policy")
        if isinstance(policy, str) and policy not in APPROVAL_POLICIES:
            errors.append(f"{path}: invalid Codex approval_policy {policy!r}")

    print(
        "Codex config audit: "
        f"{checked_manifests} manifests, {checked_mcp} MCP files, "
        f"{checked_hooks} hook configs, {checked_agents} agents, "
        f"{len(documented_events)} Claude events, "
        f"{len(documented_packages)} package difference rows"
    )
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
