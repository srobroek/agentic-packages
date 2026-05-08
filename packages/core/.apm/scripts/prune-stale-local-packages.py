#!/usr/bin/env python3
"""Remove stale local APM package installs without pruning transitive deps."""

from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path.cwd()
LOCAL_MODULES = ROOT / "apm_modules" / "_local"
LOCKFILE = ROOT / "apm.lock.yaml"


def is_local_dependency_block(block: list[str]) -> bool:
    for line in block:
        stripped = line.strip()
        if stripped in {"repo_url: _local", "- repo_url: _local"}:
            return True
        if stripped.startswith(("repo_url: _local/", "- repo_url: _local/")):
            return True
        if stripped == "host: local":
            return True
    return False


def split_top_level_dependency_blocks(lines: list[str], start: int, end: int) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] = []

    for line in lines[start:end]:
        if line.startswith("- ") and current:
            blocks.append(current)
            current = [line]
        else:
            current.append(line)

    if current:
        blocks.append(current)

    return blocks


def prune_lockfile() -> int:
    if not LOCKFILE.exists():
        return 0

    lines = LOCKFILE.read_text(encoding="utf-8").splitlines(keepends=True)
    try:
        dependencies_header = next(index for index, line in enumerate(lines) if line == "dependencies:\n")
    except StopIteration:
        return 0

    start = dependencies_header + 1
    end = next(
        (
            index
            for index in range(start, len(lines))
            if lines[index] and not lines[index].startswith((" ", "-"))
        ),
        len(lines),
    )

    blocks = split_top_level_dependency_blocks(lines, start, end)
    kept_blocks = [block for block in blocks if not is_local_dependency_block(block)]
    removed = len(blocks) - len(kept_blocks)
    if removed:
        rewritten: list[str] = []
        for block in kept_blocks:
            rewritten.extend(block)
        LOCKFILE.write_text("".join(lines[:start] + rewritten + lines[end:]), encoding="utf-8")
    return removed


def main() -> int:
    removed_modules = LOCAL_MODULES.exists()
    if removed_modules:
        shutil.rmtree(LOCAL_MODULES)
        print(f"removed {LOCAL_MODULES}")

    removed_lock_entries = prune_lockfile()
    if removed_lock_entries:
        print(f"removed {removed_lock_entries} _local lockfile entr{'y' if removed_lock_entries == 1 else 'ies'}")

    if not removed_modules and not removed_lock_entries:
        print("no stale _local APM packages found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
