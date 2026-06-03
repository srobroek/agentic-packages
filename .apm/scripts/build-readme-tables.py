#!/usr/bin/env python3
"""Generate README inventory tables from packages/*/apm.yml.

Renders markdown tables for bundles, MCP packages, agents, skills, steering,
and hook packages, then injects each table into README.md between named
HTML-comment markers:

    <!-- BEGIN:bundles -->   ... generated table ...   <!-- END:bundles -->
    <!-- BEGIN:mcp -->       ...                        <!-- END:mcp -->
    <!-- BEGIN:agents -->    ...                        <!-- END:agents -->
    <!-- BEGIN:skills -->    ...                        <!-- END:skills -->
    <!-- BEGIN:steering -->  ...                        <!-- END:steering -->
    <!-- BEGIN:hooks -->     ...                        <!-- END:hooks -->

The bundle table additionally renders a "Includes" column parsed from each
bundle's apm.yml dependency list (first-party members by name, third-party
deps summarized as "+N external").

Run after `build-agentic-indexes.py`. Idempotent: re-running with unchanged
indexes produces no diff. Pass --check to fail (exit 1) when README.md is out
of date instead of writing it -- used by CI to enforce regeneration.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "README.md"
PACKAGES_DIR = ROOT / "packages"


def _load_manifest(name: str) -> dict:
    """Parse a package apm.yml with a real YAML loader.

    Manifests are routinely reformatted (e.g. long ``description:`` strings and
    dependency entries folded into ``>-`` block scalars), so regex scraping of
    individual lines is unreliable -- parse the document instead.
    """
    import yaml

    try:
        return yaml.safe_load((PACKAGES_DIR / name / "apm.yml").read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}


def _apm_deps(name: str) -> list[str]:
    """First-party + external apm dependency strings for a package."""
    deps = (_load_manifest(name).get("dependencies") or {}).get("apm") or []
    out = []
    for dep in deps:
        if isinstance(dep, str):
            out.append(dep)
        elif isinstance(dep, dict):
            # object form: prefer git/id locator for naming
            out.append(str(dep.get("git") or dep.get("id") or dep.get("path") or ""))
    return [d for d in out if d]


def packages() -> list[dict]:
    """Read every package straight from packages/<name>/apm.yml via YAML.

    Replaces the former indexes/packages.json intermediate -- name, description,
    and type all live in the manifest, and classification additionally inspects
    on-disk shape (SKILL.md / .apm), so no generated index is needed.
    """
    out = []
    for manifest in sorted(PACKAGES_DIR.glob("*/apm.yml")):
        name = manifest.parent.name
        d = _load_manifest(name)
        out.append({
            "name": str(d.get("name") or name),
            "description": str(d.get("description") or "").strip(),
            "type": str(d.get("type") or ""),
        })
    return sorted(out, key=lambda p: p["name"])


def escape_cell(text: str) -> str:
    """Make a string safe for a single markdown table cell."""
    return text.replace("|", "\\|").replace("\n", " ").strip()


def render_table(headers: list[str], rows: list[list[str]]) -> str:
    head = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join("---" for _ in headers) + " |"
    body = "\n".join("| " + " | ".join(escape_cell(c) for c in row) + " |" for row in rows)
    return "\n".join([head, sep, body])


def _classify(name: str) -> str:
    """Classify a package by name + on-disk shape.

    Returns one of: agent, mcp, steering, hooks, skill, bundle.
    """
    if name.startswith("agent-"):
        return "agent"
    if name.startswith("mcp-"):
        return "mcp"
    if name.startswith("steering-") or name.startswith("language-steering-"):
        return "steering"
    if name.startswith("hooks-"):
        return "hooks"
    # A skill package ships exactly one skill under .apm/skills/<skill>/ and no
    # agents. A bundle is either a pure dependency aggregator (no own primitives)
    # or a multi-primitive package like speckit (skills + agents + hooks).
    # (A skill may still declare a companion dependency, e.g. catchup -> handover,
    # so primitive presence, not the dependency list, is the deciding signal.)
    pkg = PACKAGES_DIR / name
    skills = list((pkg / ".apm" / "skills").glob("*/SKILL.md"))
    has_agents = (pkg / ".apm" / "agents").is_dir()
    if len(skills) == 1 and not has_agents:
        return "skill"
    return "bundle"


def _rows_for(kind: str) -> list[list[str]]:
    return [
        [f"`{p['name']}`", p.get("description", "")]
        for p in packages()
        if _classify(p["name"]) == kind
    ]


# --- Bundle "Includes" column: parse each bundle's apm.yml dependency list ---

# A first-party member is a virtual-subdirectory dependency on this repo's own
# packages: "srobroek/agentic-packages/packages/<name>#<ref>".
_FIRST_PARTY = re.compile(r"srobroek/agentic-packages/packages/([\w-]+)")


def _external_name(dep: str) -> str:
    """Short, readable name for a third-party dependency reference.

    e.g. ``mattpocock/skills/skills/engineering/diagnose#main`` -> ``diagnose``;
    ``wshobson/agents/plugins/context-management#main`` -> ``context-management``.
    Falls back to the path basename before any ``#ref``.
    """
    ref = dep.split("#", 1)[0].rstrip("/")
    return ref.rsplit("/", 1)[-1] if "/" in ref else ref


def _bundle_includes(name: str) -> str:
    """Render a bundle's members as an explicit list.

    First-party members (``srobroek/agentic-packages/packages/<name>#...``) are
    listed by bare name. Third-party members are listed by their short name with
    a trailing ``*`` marking them external; a footnote explains the marker.
    """
    parts: list[str] = []
    for dep in _apm_deps(name):
        fp = _FIRST_PARTY.search(dep)
        if fp:
            parts.append(f"`{fp.group(1)}`")
        else:
            parts.append(f"`{_external_name(dep)}`*")
    return ", ".join(parts)


def _bundle_summary(description: str) -> str:
    """First clause of a bundle description, before the colon-introduced list."""
    text = description.strip()
    # Bundle descriptions are written as "Short purpose: comma, list, of, parts."
    # Prefer the clause before the first colon (the "Purpose: detail" pattern).
    if ":" in text:
        head = text.split(":", 1)[0].strip()
        if head and len(head) <= 90:
            return head.rstrip(".")
    # No usable colon: take the first sentence, but only break on a period that
    # actually ends a sentence (". " or trailing ".") so dotted tokens like
    # "draw.io" don't truncate the summary mid-word.
    m = re.search(r"\.(?:\s|$)", text)
    head = text[: m.start()] if m else text
    return head.strip().rstrip(".")


def bundles_table() -> str:
    rows = []
    for p in packages():
        if _classify(p["name"]) != "bundle":
            continue
        includes = _bundle_includes(p["name"])
        if not includes:
            # No apm dependency block: a self-contained package ships its own
            # primitives under .apm/ rather than aggregating other packages.
            includes = "self-contained" if (PACKAGES_DIR / p["name"] / ".apm").is_dir() else "external packages"
        rows.append([
            f"`{p['name']}`",
            _bundle_summary(p.get("description", "")),
            includes,
        ])
    return render_table(["Bundle", "What it gives you", "Includes"], rows)


def hooks_table() -> str:
    return render_table(["Hook Package", "Description"], _rows_for("hooks"))


def mcp_table() -> str:
    return render_table(["MCP Package", "Description"], _rows_for("mcp"))


def agents_table() -> str:
    return render_table(["Agent", "Description"], _rows_for("agent"))


def skills_table() -> str:
    return render_table(["Skill", "Description"], _rows_for("skill"))


def steering_table() -> str:
    return render_table(["Steering Package", "Description"], _rows_for("steering"))


SECTIONS = {
    "bundles": bundles_table,
    "mcp": mcp_table,
    "agents": agents_table,
    "skills": skills_table,
    "steering": steering_table,
    "hooks": hooks_table,
}


def inject(text: str, marker: str, payload: str) -> str:
    begin = f"<!-- BEGIN:{marker} -->"
    end = f"<!-- END:{marker} -->"
    pattern = re.compile(
        re.escape(begin) + r".*?" + re.escape(end),
        flags=re.DOTALL,
    )
    if not pattern.search(text):
        raise SystemExit(
            f"marker pair {begin} / {end} not found in README.md -- "
            "add the markers where the table should render"
        )
    replacement = f"{begin}\n{payload}\n{end}"
    return pattern.sub(lambda _: replacement, text)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if README.md is out of date; do not write.",
    )
    args = parser.parse_args()

    original = README.read_text(encoding="utf-8")
    updated = original
    for marker, builder in SECTIONS.items():
        updated = inject(updated, marker, builder())

    if args.check:
        if updated != original:
            print("README.md inventory tables are out of date. Run:")
            print("  apm run build-readme-tables")
            return 1
        print("README.md inventory tables are up to date.")
        return 0

    if updated != original:
        README.write_text(updated, encoding="utf-8")
        print(f"updated inventory tables in {README}")
    else:
        print("README.md inventory tables already up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
