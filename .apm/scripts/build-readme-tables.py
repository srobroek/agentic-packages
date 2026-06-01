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


def bundles_table() -> str:
    packages = load("packages")
    rows = [
        [f"`{p['name']}`", p.get("description", "") or "_(meta-bundle)_"]
        for p in sorted(packages, key=lambda p: p["name"])
        if not p["name"].startswith("mcp-")
    ]
    return render_table(["Bundle", "Description"], rows)


def mcp_table() -> str:
    packages = load("packages")
    rows = [
        [f"`{p['name']}`", p.get("description", "")]
        for p in sorted(packages, key=lambda p: p["name"])
        if p["name"].startswith("mcp-")
    ]
    return render_table(["MCP Package", "Description"], rows)


def agents_table() -> str:
    agents = load("agents")
    rows = [
        [f"`{a['name']}`", a.get("description", "")]
        for a in sorted(agents, key=lambda a: a["name"])
    ]
    return render_table(["Agent", "Description"], rows)


def skills_table() -> str:
    skills = load("skills")
    rows = [
        [f"`{s['name']}`", s.get("description", "")]
        for s in sorted(skills, key=lambda s: s["name"])
    ]
    return render_table(["Skill", "Description"], rows)


SECTIONS = {
    "bundles": bundles_table,
    "mcp": mcp_table,
    "agents": agents_table,
    "skills": skills_table,
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
