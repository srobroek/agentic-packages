#!/usr/bin/env python3
"""Repair generated AGENTS.md and CLAUDE.md context links after distributed APM compilation."""

from __future__ import annotations

import os
import re
from pathlib import Path


ROOT = Path.cwd()
PACKAGE_ROOT_CANDIDATES = (
    ROOT / "apm_modules" / "srobroek" / "agentic-packages" / "packages",
    ROOT / "apm_modules" / "_local",
    ROOT / "apm_modules" / "_local" / "agentic-packages" / "packages",
)
PACKAGE_ROOT = next((path for path in PACKAGE_ROOT_CANDIDATES if path.exists()), PACKAGE_ROOT_CANDIDATES[0])

MARKDOWN_LINK = re.compile(r"\]\(([^)\n]+\.context\.md)\)")

TARGET_NAMES = ("AGENTS.md", "CLAUDE.md")

LANGUAGE_HINTS = (
    ("language-typescript", ("TypeScript", "JavaScript", "ts,tsx", "js,jsx")),
    ("language-python", ("Python",)),
    ("language-go", ("Go ", "Go modules", "Golang")),
    ("language-rust", ("Rust", "Cargo")),
    ("language-terraform", ("Terraform", "HCL", "IaC")),
)


def iter_agents_files() -> list[Path]:
    files: list[Path] = []
    for name in TARGET_NAMES:
        for path in ROOT.rglob(name):
            parts = set(path.parts)
            if {".git", "node_modules", "apm_modules"} & parts:
                continue
            files.append(path)
    return sorted(files)


def context_suffix(raw_target: str) -> str | None:
    target = raw_target.split("#", 1)[0]
    marker = ".apm/context/"
    if marker in target:
        return target.split(marker, 1)[1]

    normalized = target
    while normalized.startswith("../"):
        normalized = normalized[3:]
    if normalized.startswith("context/"):
        return normalized[len("context/") :]

    return None


def choose_package(suffix: str, surrounding_text: str) -> str:
    if suffix.startswith("languages/") or suffix.startswith("toolchain-defaults/"):
        for package, hints in LANGUAGE_HINTS:
            if any(hint in surrounding_text for hint in hints):
                if (PACKAGE_ROOT / package / ".apm" / "context" / suffix).exists():
                    return package

    for package in ("core", "speckit"):
        if (PACKAGE_ROOT / package / ".apm" / "context" / suffix).exists():
            return package

    return "core"


def repair_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    changed = False

    def replace(match: re.Match[str]) -> str:
        nonlocal changed

        suffix = context_suffix(match.group(1))
        if suffix is None:
            return match.group(0)

        start = text.rfind("\n## ", 0, match.start())
        if start == -1:
            start = 0
        end = text.find("\n## ", match.end())
        if end == -1:
            end = len(text)
        package = choose_package(suffix, text[start:end])
        target = PACKAGE_ROOT / package / ".apm" / "context" / suffix
        relative = os.path.relpath(target, path.parent).replace(os.sep, "/")
        changed = changed or relative != match.group(1)
        return f"]({relative})"

    updated = MARKDOWN_LINK.sub(replace, text)
    if changed:
        path.write_text(updated, encoding="utf-8")
    return changed


def main() -> int:
    changed = [str(path) for path in iter_agents_files() if repair_file(path)]
    if changed:
        print(f"repaired context links in {len(changed)} context file(s)")
        for path in changed:
            print(f"- {path}")
    else:
        print("no context links needed repair")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
