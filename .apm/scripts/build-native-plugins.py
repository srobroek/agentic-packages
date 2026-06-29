#!/usr/bin/env python3
"""Generate committed native plugin layout for every native-capable package.

The marketplace `source: ./packages/<name>` entries are consumed by THREE native
loaders -- Claude `/plugin install`, Codex `plugin add`, and APM `apm install`.
All three require a native plugin layout (`.claude-plugin/plugin.json` + top-level
`skills/`/`agents/`/`.mcp.json`/`hooks/hooks.json`), NOT APM's `.apm/` source
layout. APM's own `apm pack` only writes the catalog + a repo-root plugin.json; it
never materialises per-package native layout. This generator fills that gap.

It is the native-layout analogue of render-docs.py: driven by the single
`build_inventory.build_context()` walk, idempotent, and supports `--check` for a
CI staleness gate. Generated files are committed (like the marketplace block) so a
fresh clone resolves marketplace sources with no build step.

What it emits, per package classification:

* skill  -> `skills/<name>/` (copied from `.apm/skills/<name>/`) + plugin.json
* agent  -> `agents/<n>.md` (from `.apm/agents/<n>.agent.md`) + plugin.json
* mcp    -> `.mcp.json` (from the apm.yml `dependencies.mcp` block) + plugin.json
* bundle -> plugin.json with a `dependencies` array (native plugin bundling)
* hooks / mixed packages with hooks -> `hooks/hooks.json` ONLY when the package's
  claude and codex hook variants are byte-identical (otherwise a universal
  `hooks.json` leaks Claude hooks into the Codex `apm install` -- see the spec).
  The per-target `.apm/hooks/*-{claude,codex}-hooks.json` files stay authoritative
  for `apm install`.
* steering -> nothing (no native plugin component exists for rules/instructions).

`plugin.json` carries name/version/description/author/license, plus
`dependencies` for bundles. Component dirs are auto-discovered by all three
loaders, so no path-override keys are written.

stdlib + PyYAML only (PyYAML already a CI dep via apm-cli).
"""

from __future__ import annotations

import argparse
import filecmp
import importlib.util
import json
import re
import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
PACKAGES_DIR = ROOT / "packages"
APM_YML = ROOT / "apm.yml"

# Native component dirs/files this generator owns at a package root. Any of these
# present-but-unexpected is pruned so the tree never drifts from the source.
_GENERATED_DIRS = ("skills", "agents", "hooks")
_GENERATED_FILES = (".mcp.json",)

# A first-party dependency reference -> the member package name (for bundles).
_FIRST_PARTY = re.compile(r"srobroek/agentic-packages/packages/([\w-]+)(?:#(.+))?$")


def _load_inventory():
    spec = importlib.util.spec_from_file_location(
        "build_inventory", Path(__file__).with_name("build_inventory.py")
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def _author_license(root_manifest: dict) -> tuple[dict | None, str | None]:
    """Repo-level author/license, used when a package omits its own."""
    author = root_manifest.get("author")
    author_obj = {"name": str(author)} if isinstance(author, str) else author
    return author_obj, root_manifest.get("license")


# --------------------------------------------------------------------------- #
# plugin.json
# --------------------------------------------------------------------------- #

def _plugin_manifest(
    pkg: dict, manifest: dict, defaults: tuple, deps: list[dict] | None, has_skills: bool = False
) -> dict:
    author_default, license_default = defaults
    out: dict = {"name": pkg["name"]}
    if pkg.get("version"):
        out["version"] = str(pkg["version"])
    if pkg.get("description"):
        out["description"] = pkg["description"]
    author = manifest.get("author")
    author = {"name": str(author)} if isinstance(author, str) else (author or author_default)
    if author:
        out["author"] = author
    lic = manifest.get("license") or license_default
    if lic:
        out["license"] = str(lic)
    # Reference skills in place rather than copying them (avoids duplicating
    # any test_*.py the skill ships, which breaks pytest collection).
    if has_skills:
        out["skills"] = "./.apm/skills"
    if deps:
        out["dependencies"] = deps
    return out


# --------------------------------------------------------------------------- #
# bundle dependencies
# --------------------------------------------------------------------------- #

def _bundle_dependencies(deps: list[str]) -> list[dict]:
    """Map a bundle's first-party apm deps to native plugin `dependencies`.

    Only first-party members (this repo's own packages) are emitted -- they
    resolve within the same generated marketplace. External members (e.g.
    `wshobson/*`) need a cross-marketplace allowlist and are intentionally NOT
    auto-added here (a native install would fail to resolve them otherwise).

    Entries use the object form ``{git, path}`` (no ``ref``) so they keep
    tracking whatever version the marketplace provides while remaining a valid
    APM dependency reference. A bare ``{name: ...}`` object is rejected by
    apm's ``DependencyReference.parse_from_dict`` ("Object-style dependency
    must have a 'git', 'path', or 'registry' field"), which broke transitive
    resolution for every bundle.
    """
    out: list[dict] = []
    for dep in deps:
        m = _FIRST_PARTY.search(dep)
        if m:
            out.append(
                {"git": "srobroek/agentic-packages", "path": f"packages/{m.group(1)}"}
            )
    return out


# --------------------------------------------------------------------------- #
# mcp -> .mcp.json
# --------------------------------------------------------------------------- #

def _mcp_json(manifest: dict) -> dict | None:
    """Build a Claude/Codex `.mcp.json` from the apm.yml `dependencies.mcp` block."""
    servers = (manifest.get("dependencies") or {}).get("mcp") or []
    if not servers:
        return None
    out: dict = {}
    for s in servers:
        if not isinstance(s, dict) or not s.get("name"):
            continue
        name = str(s["name"])
        entry: dict = {}
        transport = s.get("transport", "stdio")
        if s.get("command"):
            entry["command"] = str(s["command"])
            if s.get("args"):
                entry["args"] = list(s["args"])
            if s.get("env"):
                entry["env"] = dict(s["env"])
        elif s.get("url"):
            # http/sse server
            entry["type"] = transport if transport in ("http", "sse") else "http"
            entry["url"] = str(s["url"])
        else:
            continue
        out[name] = entry
    return {"mcpServers": out} if out else None


# --------------------------------------------------------------------------- #
# hooks: emit hooks/hooks.json only when claude == codex variant
# --------------------------------------------------------------------------- #

def _unified_hook(pkg_dir: Path) -> Path | None:
    """Return the claude hook file IFF claude and codex variants are identical.

    A universal root `hooks/hooks.json` is routed to EVERY target by `apm
    install`; if the variants differ it would leak Claude-only hooks into Codex.
    Only when they are byte-identical is a single native hooks.json safe.
    """
    hooks_dir = pkg_dir / ".apm" / "hooks"
    if not hooks_dir.is_dir():
        return None
    claude = sorted(hooks_dir.glob("*-claude-hooks.json")) or sorted(hooks_dir.glob("claude-hooks.json"))
    codex = sorted(hooks_dir.glob("*-codex-hooks.json")) or sorted(hooks_dir.glob("codex-hooks.json"))
    if not claude:
        return None
    if codex and not filecmp.cmp(claude[0], codex[0], shallow=False):
        return None  # variants differ -> do NOT emit a universal hooks.json
    return claude[0]


# --------------------------------------------------------------------------- #
# planning: compute the desired native tree for one package
# --------------------------------------------------------------------------- #

def _plan_package(pkg: dict, manifest: dict, defaults: tuple) -> dict[str, object] | None:
    """Return {relpath: content} for the native files a package should have.

    Content is bytes for copied files, str for generated JSON. Directory copies
    are represented as (src_dir, "<dir-copy>"). Returns None for steering (no
    native layout).
    """
    cls = pkg["classification"]
    if cls == "steering":
        return None

    pkg_dir = PACKAGES_DIR / pkg["dirname"]
    plan: dict[str, object] = {}

    # Skills are REFERENCED in place via a plugin.json `skills` override pointing
    # at .apm/skills -- NOT copied. All three native loaders (Claude /plugin,
    # Codex plugin add, apm install) honor the override. Copying would duplicate
    # any test_*.py the skill ships, and pytest's collector aborts on two modules
    # with the same basename. Multi-primitive bundles (e.g. speckit) surface their
    # skills the same way.
    skills_src = pkg_dir / ".apm" / "skills"
    has_skills = skills_src.is_dir() and any(skills_src.rglob("SKILL.md"))

    # Agents MUST be materialised at native agents/*.md: a plugin.json `agents`
    # override into .apm/ does not load (verified). Agents are .md only (no test
    # files), so copying carries no pytest-collision risk.
    agents_src = pkg_dir / ".apm" / "agents"
    if agents_src.is_dir():
        for f in sorted(agents_src.glob("*.agent.md")):
            plan[f"agents/{f.name[:-len('.agent.md')]}.md"] = f.read_bytes()
        for f in sorted(agents_src.glob("*.md")):
            if not f.name.endswith(".agent.md"):
                plan[f"agents/{f.name}"] = f.read_bytes()

    # MCP servers declared in the apm.yml dependencies.mcp block -> .mcp.json.
    mcp = _mcp_json(manifest)
    if mcp is not None:
        plan[".mcp.json"] = json.dumps(mcp, indent=2, ensure_ascii=False) + "\n"

    # Native plugin dependencies = this package's first-party apm members. Emit
    # them whenever they exist, independent of doc-classification: a skill-led
    # package (e.g. speckit) may still aggregate a first-party member, and it must
    # keep that wiring in its native plugin.json. Pure aggregators ("bundle") are
    # the common case but not the only one. _bundle_dependencies returns [] (->
    # None) when there are no first-party deps, so this is a no-op for standalone
    # packages like sniff.
    deps = _bundle_dependencies(pkg["deps"]) or None

    # Hooks (for hooks-* packages AND mixed packages that ship .apm/hooks).
    unified = _unified_hook(pkg_dir)
    if unified is not None:
        plan["hooks/hooks.json"] = unified.read_text(encoding="utf-8")

    # Every native-capable package gets a manifest. ensure_ascii=False so non-ASCII
    # (e.g. em-dashes in descriptions) is written as raw UTF-8, matching how
    # `apm pack` writes plugin.json/marketplace.json -- otherwise the CI staleness
    # gate sees drift when apm pack rewrites a manifest this generator also wrote.
    plan[".claude-plugin/plugin.json"] = (
        json.dumps(_plugin_manifest(pkg, manifest, defaults, deps, has_skills), indent=2, ensure_ascii=False) + "\n"
    )
    return plan


# --------------------------------------------------------------------------- #
# apply / check
# --------------------------------------------------------------------------- #

def _materialize(pkg_dir: Path, plan: dict[str, object], check: bool) -> list[str]:
    """Write (or diff) the planned native files. Returns list of stale relpaths."""
    stale: list[str] = []

    # 1. Prune previously-generated dirs/files no longer in the plan. A plan key
    #    is either a DIRCOPY root (no slash, e.g. "skills") or a nested file
    #    (e.g. "agents/coder.md", "hooks/hooks.json") -- both contribute their
    #    top-level segment to the set of dirs that should exist.
    planned_dirs = {rel.split("/", 1)[0] for rel in plan}
    for d in _GENERATED_DIRS:
        target = pkg_dir / d
        wanted = d in planned_dirs
        if target.exists() and not wanted:
            if check:
                stale.append(f"{pkg_dir.name}/{d} (should be removed)")
            else:
                shutil.rmtree(target)
    for f in _GENERATED_FILES:
        target = pkg_dir / f
        if target.exists() and f not in plan:
            if check:
                stale.append(f"{pkg_dir.name}/{f} (should be removed)")
            else:
                target.unlink()

    # 2. Write/diff each planned entry.
    for rel, content in plan.items():
        if isinstance(content, tuple) and content[0] == "DIRCOPY":
            src = content[1]
            dst = pkg_dir / rel
            stale += _sync_dir(src, dst, rel, pkg_dir.name, check)
            continue
        target = pkg_dir / rel
        data = content if isinstance(content, bytes) else content.encode("utf-8")
        if target.exists() and target.read_bytes() == data:
            continue
        if check:
            stale.append(f"{pkg_dir.name}/{rel}")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    return stale


def _sync_dir(src: Path, dst: Path, rel: str, pkg: str, check: bool) -> list[str]:
    """Mirror src -> dst exactly (content + membership). Returns stale relpaths."""
    stale: list[str] = []
    src_files = {p.relative_to(src) for p in src.rglob("*") if p.is_file()}
    dst_files = {p.relative_to(dst) for p in dst.rglob("*") if p.is_file()} if dst.exists() else set()

    for r in sorted(src_files):
        s, d = src / r, dst / r
        data = s.read_bytes()
        if d.exists() and d.read_bytes() == data:
            continue
        if check:
            stale.append(f"{pkg}/{rel}/{r}")
        else:
            d.parent.mkdir(parents=True, exist_ok=True)
            d.write_bytes(data)
    for r in sorted(dst_files - src_files):
        if check:
            stale.append(f"{pkg}/{rel}/{r} (should be removed)")
        else:
            (dst / r).unlink()
    return stale


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Diff vs committed; exit 1 on drift.")
    args = parser.parse_args(argv)

    inv = _load_inventory()
    ctx = inv.build_context()
    root_manifest = yaml.safe_load(APM_YML.read_text(encoding="utf-8")) or {}
    defaults = _author_license(root_manifest)

    all_stale: list[str] = []
    n_written = 0
    for pkg in ctx["packages"]:
        pkg_dir = PACKAGES_DIR / pkg["dirname"]
        manifest = yaml.safe_load((pkg_dir / "apm.yml").read_text(encoding="utf-8")) or {}
        plan = _plan_package(pkg, manifest, defaults)
        if plan is None:
            # steering: ensure no stray generated native layout exists
            plan = {}
        stale = _materialize(pkg_dir, plan, args.check)
        if stale:
            all_stale.extend(stale)
        elif not args.check and plan:
            n_written += 1

    if args.check:
        if all_stale:
            print("Native plugin layout out of date:")
            for s in sorted(all_stale)[:40]:
                print(f"  {s}")
            if len(all_stale) > 40:
                print(f"  ... and {len(all_stale) - 40} more")
            print("Run: apm run build-native-plugins")
            return 1
        print("Native plugin layout is up to date.")
        return 0

    print(f"generated native plugin layout for {n_written} package(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
