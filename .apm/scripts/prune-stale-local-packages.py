#!/usr/bin/env python3
"""Remove stale local APM package installs without pruning transitive deps."""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml


ROOT = Path.cwd()
LOCAL_MODULES = ROOT / "apm_modules" / "_local"
LOCKFILE = ROOT / "apm.lock.yaml"


def is_local_dependency(entry: object) -> bool:
    if not isinstance(entry, dict):
        return False
    repo_url = str(entry.get("repo_url", ""))
    host = str(entry.get("host", ""))
    return repo_url == "_local" or repo_url.startswith("_local/") or host == "local"


def prune_lockfile() -> int:
    if not LOCKFILE.exists():
        return 0
    data = yaml.safe_load(LOCKFILE.read_text(encoding="utf-8")) or {}
    dependencies = data.get("dependencies")
    if not isinstance(dependencies, list):
        return 0
    kept = [entry for entry in dependencies if not is_local_dependency(entry)]
    removed = len(dependencies) - len(kept)
    if removed:
        data["dependencies"] = kept
        LOCKFILE.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
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
