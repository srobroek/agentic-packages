#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6"]
# ///
"""Pre-commit + CI check: every primitive's YAML frontmatter parses and its
`permissionMode` names a real mode.

APM reads each primitive's frontmatter to decide where it deploys and what it
declares. A frontmatter block that does not parse is skipped with a warning on
stderr during `apm install` and the primitive silently does not deploy -- the
install still reports success, so the failure surfaces as an absent rule or skill
rather than as an error.

Six files were in that state when this check was written, across three packages,
and every one failed for the same reason: an unquoted colon-space inside a scalar
value. YAML reads `description: Rules for X: code economy` as a nested mapping and
rejects it, because `X: code economy` cannot be a value and a key at once.

`permissionMode` fails the same way: an unrecognised value is not an error, the
agent just runs under whatever mode it inherits, so `acceptEdit` or `accept-edits`
would deploy and every other gate would stay green.

Exit 0 when every block parses and every declared mode is legal, 1 otherwise.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]

# https://code.claude.com/docs/en/sub-agents.md -- the field is optional and
# accepts the same set as the CLI's --permission-mode and settings.json
# permissions.defaultMode. `manual` is an alias for `default` and needs Claude
# Code v2.1.200+.
PERMISSION_MODES = frozenset(
    {"default", "manual", "acceptEdits", "auto", "dontAsk", "bypassPermissions", "plan"}
)


def frontmatter(text: str) -> str | None:
    """Return the frontmatter block, or None when the file carries none.

    Splitting on the fence rather than scanning line by line keeps a `---` inside
    the body from being mistaken for the closing fence: only the first two count.
    """
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    return parts[1]


def findings(root: Path) -> list[tuple[Path, str]]:
    out: list[tuple[Path, str]] = []
    for path in sorted((root / "packages").glob("*/.apm/**/*.md")):
        if "apm_modules" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            out.append((path, f"unreadable: {exc}"))
            continue
        block = frontmatter(text)
        if block is None:
            continue
        try:
            parsed = yaml.safe_load(block)
        except yaml.YAMLError as exc:
            # The first line of a YAML error names the construct; the rest is a
            # position dump that repeats the file name this check already prints.
            reason = str(exc).split("\n")[0]
            out.append((path, reason))
            continue
        if parsed is not None and not isinstance(parsed, dict):
            out.append((path, f"frontmatter is {type(parsed).__name__}, not a mapping"))
            continue
        if isinstance(parsed, dict) and "permissionMode" in parsed:
            mode = parsed["permissionMode"]
            if mode not in PERMISSION_MODES:
                out.append(
                    (
                        path,
                        f"permissionMode: {mode!r} is not a permission mode; "
                        f"allowed: {', '.join(sorted(PERMISSION_MODES))}",
                    )
                )
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)

    bad = findings(args.root)
    if bad:
        print("check-frontmatter-parses: bad frontmatter", file=sys.stderr)
        for path, reason in bad:
            rel = path.relative_to(args.root) if path.is_relative_to(args.root) else path
            print(f"  {rel}: {reason}", file=sys.stderr)
        print(
            "\nA value containing ': ' must be quoted. APM skips a primitive whose "
            "frontmatter does not parse, and the install still reports success; an "
            "unrecognised permissionMode deploys and the agent inherits a mode instead.",
            file=sys.stderr,
        )
        return 1

    count = sum(1 for _ in (args.root / "packages").glob("*/.apm/**/*.md"))
    print(f"check-frontmatter-parses: {count} primitive file(s), 0 finding(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
