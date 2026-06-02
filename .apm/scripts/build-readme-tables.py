#!/usr/bin/env python3
"""Generate README inventory tables from indexes/*.json.

Renders markdown tables for bundles, MCP packages, agents, and skills, then
injects each table into README.md between named HTML-comment markers:

    <!-- BEGIN:bundles -->   ... generated table ...   <!-- END:bundles -->
    <!-- BEGIN:mcp -->       ...                        <!-- END:mcp -->
    <!-- BEGIN:agents -->    ...                        <!-- END:agents -->
    <!-- BEGIN:skills -->    ...                        <!-- END:skills -->

Run after `build-agentic-indexes.py`. Idempotent: re-running with unchanged
indexes produces no diff. Pass --check to fail (exit 1) when README.md is out
of date instead of writing it -- used by CI to enforce regeneration.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INDEXES = ROOT / "indexes"
README = ROOT / "README.md"


def load(name: str) -> list[dict]:
    return json.loads((INDEXES / f"{name}.json").read_text(encoding="utf-8"))


def escape_cell(text: str) -> str:
    """Make a string safe for a single markdown table cell."""
    return text.replace("|", "\\|").replace("\n", " ").strip()


def render_table(headers: list[str], rows: list[list[str]]) -> str:
    head = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join("---" for _ in headers) + " |"
    body = "\n".join("| " + " | ".join(escape_cell(c) for c in row) + " |" for row in rows)
    return "\n".join([head, sep, body])


PACKAGES_DIR = ROOT / "packages"


def _classify(name: str) -> str:
    """Classify a package by name + on-disk shape.

    Returns one of: agent, mcp, steering, skill, bundle.
    """
    if name.startswith("agent-"):
        return "agent"
    if name.startswith("mcp-"):
        return "mcp"
    if name.startswith("steering-") or name.startswith("language-steering-"):
        return "steering"
    # A single-skill package has SKILL.md at its root.
    if (PACKAGES_DIR / name / "SKILL.md").is_file():
        return "skill"
    return "bundle"


def _rows_for(kind: str) -> list[list[str]]:
    packages = load("packages")
    return [
        [f"`{p['name']}`", p.get("description", "")]
        for p in sorted(packages, key=lambda p: p["name"])
        if _classify(p["name"]) == kind
    ]


def bundles_table() -> str:
    return render_table(["Bundle", "Description"], _rows_for("bundle"))


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
