#!/usr/bin/env python3
"""Remove generated SpecKit constitution blocks from agent steering files."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path.cwd()
TARGET_NAMES = {"AGENTS.md", "CLAUDE.md", "GEMINI.md"}
BEGIN = "<!-- SPEC-KIT CONSTITUTION: BEGIN -->"
END = "<!-- SPEC-KIT CONSTITUTION: END -->"
BLOCK_RE = re.compile(
    rf"\n?{re.escape(BEGIN)}.*?{re.escape(END)}\n?",
    flags=re.DOTALL,
)


def candidate_files() -> list[Path]:
    ignored_parts = {
        ".git",
        "apm_modules",
        "node_modules",
        "target",
        ".venv",
        "venv",
    }
    files: list[Path] = []
    for path in ROOT.rglob("*.md"):
        if path.name not in TARGET_NAMES:
            continue
        if any(part in ignored_parts for part in path.parts):
            continue
        files.append(path)
    return sorted(files)


def strip_file(path: Path) -> bool:
    original = path.read_text(encoding="utf-8")
    stripped = BLOCK_RE.sub("\n", original)
    stripped = re.sub(r"\n{3,}", "\n\n", stripped)
    if stripped == original:
        return False
    path.write_text(stripped, encoding="utf-8")
    return True


def main() -> int:
    changed = [path for path in candidate_files() if strip_file(path)]
    if changed:
        for path in changed:
            print(f"stripped constitution block from {path}")
    else:
        print("no SpecKit constitution blocks found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
