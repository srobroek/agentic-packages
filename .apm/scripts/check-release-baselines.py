#!/usr/bin/env python3
"""Reject release manifest baselines that do not match published package tags."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "release-please-config.json"
MANIFEST = ROOT / ".release-please-manifest.json"
FIRST_RELEASE_SENTINEL = "0.0.0"
STABLE_VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def _current_branch() -> str:
    github_head = os.environ.get("GITHUB_HEAD_REF", "")
    if github_head:
        return github_head
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _component_versions(component: str) -> dict[str, tuple[int, int, int]]:
    result = subprocess.run(
        ["git", "tag", "--list", f"{component}--v*"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    prefix = f"{component}--v"
    versions = {}
    for tag in result.stdout.splitlines():
        version = tag.removeprefix(prefix)
        match = STABLE_VERSION.fullmatch(version)
        if match:
            versions[version] = tuple(map(int, match.groups()))
    return versions


def check_release_baselines() -> list[str]:
    branch = _current_branch()
    if branch == "release-please--branches--main":
        print(f"release baseline check skipped on release branch {branch}")
        return []

    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    errors = []
    for path, version in manifest.items():
        package_config = config["packages"].get(path)
        if not package_config:
            errors.append(f"{path}: missing release-please package configuration")
            continue
        component = package_config["component"]
        versions = _component_versions(component)
        if version == FIRST_RELEASE_SENTINEL:
            if versions:
                latest = max(versions, key=versions.get)
                errors.append(
                    f"{path}: first-release sentinel has published tag {component}--v{latest}"
                )
            continue
        if not STABLE_VERSION.fullmatch(version):
            errors.append(f"{path}: unsupported baseline version {version!r}")
            continue
        expected_tag = f"{component}--v{version}"
        if version not in versions:
            errors.append(f"{path}: baseline {version} has no tag {expected_tag}")
            continue
        latest = max(versions, key=versions.get)
        if version != latest:
            errors.append(f"{path}: baseline {version} is behind latest tag {component}--v{latest}")
    return errors


def main() -> int:
    errors = check_release_baselines()
    if errors:
        for error in errors:
            print(f"release baseline error: {error}")
        return 1
    print("release baselines match published tags and first-release sentinels")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
