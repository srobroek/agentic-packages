#!/usr/bin/env python3
"""Generate the ``marketplace.packages`` block in apm.yml from packages/*/apm.yml.

Each package's own ``apm.yml`` is the single source of truth for its ``name``,
``category``, and ``tags``. As of apm >= 0.21 (upstream fix microsoft/apm#1725),
``apm pack`` automatically inherits ``description`` and ``version`` from each local
subpath package's own ``apm.yml`` into the generated marketplace.json -- so this
script no longer needs to emit them into the root ``apm.yml`` marketplace block.

``category`` and ``tags`` are curation, not derived metadata. They are taken from
the package manifest when the package declares them (``category:`` / ``tags:`` /
``keywords:``), otherwise preserved from the existing marketplace block. A package
with no curation in either place is emitted without those fields and reported.

Only the top-level ``marketplace:`` block is rewritten; the static sub-blocks
(``owner``, ``outputs``, ``versioning``, ``build``) are preserved, and the rest of
apm.yml is left byte-for-byte unchanged. Entries are sorted by name (deterministic).

Pass --check to exit 1 when apm.yml is out of date instead of writing it -- used by
CI to enforce regeneration.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
APM_YML = ROOT / "apm.yml"
PACKAGES_DIR = ROOT / "packages"

# Per-entry key order in the rendered block.
_ENTRY_ORDER = ("name", "source", "category", "tags")


def _load(path: Path) -> dict:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise SystemExit(f"cannot parse {path}: {exc}")


def _existing_curation(marketplace: dict) -> dict[str, dict]:
    """Map package name -> {category, tags} from the current marketplace block."""
    out: dict[str, dict] = {}
    for entry in marketplace.get("packages") or []:
        if isinstance(entry, dict) and entry.get("name"):
            out[str(entry["name"])] = {
                "category": entry.get("category"),
                "tags": list(entry.get("tags") or []),
            }
    return out


def _package_tags(pkg: dict) -> list[str]:
    """A package's own tags (``tags`` plus ``keywords``, deduplicated, order-stable)."""
    tags: list[str] = []
    for key in ("tags", "keywords"):
        for t in pkg.get(key) or []:
            if t not in tags:
                tags.append(str(t))
    return tags


def build_entries(marketplace: dict) -> tuple[list[dict], list[str]]:
    """Build the new packages list from packages/*/apm.yml. Returns (entries, warnings)."""
    curation = _existing_curation(marketplace)
    entries: list[dict] = []
    warnings: list[str] = []

    found: set[str] = set()
    for manifest in sorted(PACKAGES_DIR.glob("*/apm.yml")):
        dirname = manifest.parent.name
        pkg = _load(manifest)
        name = str(pkg.get("name") or dirname)
        found.add(name)

        entry: dict = {"name": name, "source": f"./packages/{dirname}"}

        category = pkg.get("category") or curation.get(name, {}).get("category")
        if category:
            entry["category"] = str(category)

        tags = _package_tags(pkg) or curation.get(name, {}).get("tags") or []
        if tags:
            entry["tags"] = list(tags)

        if name not in curation and not entry.get("tags"):
            warnings.append(f"{name}: new package with no tags (add tags: to its apm.yml)")

        entries.append({k: entry[k] for k in _ENTRY_ORDER if k in entry})

    for stale in sorted(set(curation) - found):
        warnings.append(f"{stale}: in marketplace block but no packages/ dir -- dropped")

    entries.sort(key=lambda e: e["name"])
    return entries, warnings


class _IndentDumper(yaml.Dumper):
    """Indent block sequences under their key (``key:`` then ``  - item``),
    matching the hand-authored apm.yml style instead of PyYAML's indentless default."""

    def increase_indent(self, flow=False, indentless=False):  # noqa: ARG002
        return super().increase_indent(flow, False)


def render_block(marketplace: dict, entries: list[dict]) -> str:
    """Render the full ``marketplace:`` block as YAML text (2-space indented)."""
    # Preserve original key order; replace only ``packages``.
    block: dict = {}
    for key in marketplace:
        block[key] = entries if key == "packages" else marketplace[key]
    if "packages" not in block:
        block["packages"] = entries

    dumped = yaml.dump(
        block,
        Dumper=_IndentDumper,
        sort_keys=False,
        default_flow_style=False,
        width=10**9,
        allow_unicode=True,
        indent=2,
    )
    indented = "".join(("  " + line if line.strip() else line) for line in dumped.splitlines(keepends=True))
    return "marketplace:\n" + indented


def regenerate(text: str) -> tuple[str, list[str]]:
    """Return (new_apm_yml_text, warnings)."""
    data = yaml.safe_load(text) or {}
    marketplace = data.get("marketplace")
    if not isinstance(marketplace, dict):
        raise SystemExit("apm.yml has no 'marketplace:' block to generate")

    entries, warnings = build_entries(marketplace)
    block_text = render_block(marketplace, entries)

    lines = text.splitlines(keepends=True)
    start = next((i for i, ln in enumerate(lines) if ln.rstrip("\n") == "marketplace:"), None)
    if start is None:
        raise SystemExit("could not locate the 'marketplace:' line in apm.yml")
    # marketplace is the last top-level key; find the next col-0 key if any.
    end = len(lines)
    for i in range(start + 1, len(lines)):
        ln = lines[i]
        if ln[:1].strip() and not ln.startswith(("#", " ", "\t")):
            end = i
            break

    head = "".join(lines[:start])
    tail = "".join(lines[end:])
    new_text = head + block_text
    if not new_text.endswith("\n"):
        new_text += "\n"
    new_text += tail
    return new_text, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Exit 1 if apm.yml is out of date; do not write.")
    args = parser.parse_args()

    original = APM_YML.read_text(encoding="utf-8")
    updated, warnings = regenerate(original)

    for w in warnings:
        print(f"[warn] {w}", file=sys.stderr)

    if updated == original:
        if args.check:
            print("marketplace block is up to date.")
        return 0

    if args.check:
        print("apm.yml marketplace block is out of date. Run: apm run build-marketplace-block")
        return 1

    APM_YML.write_text(updated, encoding="utf-8")
    print(f"regenerated marketplace block: {len(yaml.safe_load(updated)['marketplace']['packages'])} packages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
