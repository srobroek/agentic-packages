#!/usr/bin/env python3
"""Generate release-please config + manifest from the packages/ set.

Per-package versioning: one release-please component per packages/<name>, each
tracking its own apm.yml `version:` line via the yaml ($.version) extra-file updater, tagged
{name}-v{version}. Run at build time so adding/removing a package keeps the
release-please config in sync.

Outputs (committed):
  release-please-config.json
  .release-please-manifest.json

Pass --check to fail (exit 1) if the committed files are out of date.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGES = ROOT / "packages"
CONFIG = ROOT / "release-please-config.json"
MANIFEST = ROOT / ".release-please-manifest.json"

# Each package tracks its own apm.yml `version:` via the yaml extra-file
# updater (jsonpath $.version). The yaml updater rewrites the value in place
# from the manifest by JSONPath, so the version line needs no release-please
# annotation comment.
CHANGELOG_SECTIONS = [
    {"type": "feat", "section": "Features"},
    {"type": "fix", "section": "Bug Fixes"},
    {"type": "perf", "section": "Performance"},
    {"type": "refactor", "section": "Refactors"},
    {"type": "docs", "section": "Documentation"},
    {"type": "chore", "section": "Chores", "hidden": True},
    {"type": "test", "section": "Tests", "hidden": True},
    {"type": "ci", "section": "CI/CD", "hidden": True},
]


def _package_dirs() -> list[str]:
    out = []
    for d in sorted(PACKAGES.iterdir()):
        if d.is_dir() and (d / "apm.yml").is_file():
            out.append(d.name)
    return out


def _read_version(pkg: str) -> str:
    text = (PACKAGES / pkg / "apm.yml").read_text(encoding="utf-8")
    m = re.search(r"^version:\s*(\S+)", text, re.M)
    return m.group(1) if m else "0.1.0"


def build_config(pkgs: list[str]) -> dict:
    packages = {}
    for p in pkgs:
        packages[f"packages/{p}"] = {
            "release-type": "simple",
            "component": p,
            "changelog-path": "CHANGELOG.md",
            "extra-files": [
                {
                    "type": "yaml",
                    "path": "apm.yml",
                    "jsonpath": "$.version",
                }
            ],
        }
    return {
        "$schema": "https://raw.githubusercontent.com/googleapis/release-please/main/schemas/config.json",
        "separate-pull-requests": True,
        "tag-separator": "-",
        "include-component-in-tag": True,
        "changelog-sections": CHANGELOG_SECTIONS,
        "packages": packages,
    }


def build_manifest(pkgs: list[str]) -> dict:
    return {f"packages/{p}": _read_version(p) for p in pkgs}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if out of date.")
    args = parser.parse_args()

    pkgs = _package_dirs()
    config = build_config(pkgs)
    manifest = build_manifest(pkgs)
    config_text = json.dumps(config, indent=2) + "\n"
    manifest_text = json.dumps(manifest, indent=2) + "\n"

    if args.check:
        stale = []
        if not CONFIG.exists() or CONFIG.read_text() != config_text:
            stale.append("release-please-config.json")
        if not MANIFEST.exists() or MANIFEST.read_text() != manifest_text:
            stale.append(".release-please-manifest.json")
        if stale:
            print("release-please config out of date:", ", ".join(stale))
            print("Run: apm run build-release-please")
            return 1
        print("release-please config up to date.")
        return 0

    CONFIG.write_text(config_text, encoding="utf-8")
    MANIFEST.write_text(manifest_text, encoding="utf-8")
    print(f"wrote release-please config + manifest for {len(pkgs)} packages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
