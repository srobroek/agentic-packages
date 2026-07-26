#!/usr/bin/env python3
"""Pre-commit + CI check: every APM instruction primitive declares `applyTo`.

apm-cli treats an instruction with no `applyTo` frontmatter as "global" and
folds it into BOTH deploy targets: it is rendered into the user-scope root
context file (e.g. `~/.claude/CLAUDE.md`) AND deployed as an unconditional
rule (e.g. `~/.claude/rules/<pkg>.md`) -- so the same guidance loads twice in
every session. There is no dial to pick one target; the only lever is
`applyTo` itself, and the filter is a plain truthiness check on the frontmatter
field (`not instr.apply_to`), not an inspection of what the glob matches.

An `applyTo: "**/*"` (or any other non-empty pattern) opts an instruction out
of the CLAUDE.md path while keeping it as a `.claude/rules/` entry with a
`paths:` frontmatter block -- the fix for always-loaded guidance that still
wants a single home.

This check flags every `*.instructions.md` under `packages/*/.apm/instructions/`
that has no `applyTo:` key in its frontmatter. Vendored copies under a
package's own `apm_modules/` (gitignored dependency checkouts) are skipped --
they are not source.

Exit 0 when clean, 1 when any instruction is missing `applyTo`.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

FRONTMATTER_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
APPLY_TO_RE = re.compile(r"^applyTo\s*:", re.MULTILINE)


def find_instruction_files(packages_dir: Path) -> list[Path]:
    return sorted(
        p
        for p in packages_dir.glob("*/.apm/instructions/*.instructions.md")
        if "apm_modules" not in p.parts
    )


def missing_apply_to(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if not match:
        # No frontmatter at all -- also invalid, treat as missing applyTo.
        return True
    return not APPLY_TO_RE.search(match.group(1))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--packages-dir",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "packages",
        help="packages/ directory of an agentic-packages checkout",
    )
    # Accept pre-commit's staged-file args without requiring them; when given,
    # only those files are checked (still filtered to *.instructions.md).
    parser.add_argument("files", nargs="*", type=Path)
    args = parser.parse_args()

    if args.files:
        candidates = [
            f for f in args.files if f.name.endswith(".instructions.md") and "apm_modules" not in f.parts
        ]
    else:
        if not args.packages_dir.is_dir():
            print(f"check-instructions-apply-to: packages dir not found: {args.packages_dir}")
            return 2
        candidates = find_instruction_files(args.packages_dir)

    problems = [str(f) for f in candidates if f.is_file() and missing_apply_to(f)]

    if problems:
        print(f"check-instructions-apply-to: {len(problems)} instruction(s) missing 'applyTo':")
        for p in problems:
            print(f"  - {p}")
        print(
            "\nAdd 'applyTo: \"<glob>\"' to the frontmatter (use \"**/*\" for "
            "always-loaded guidance) so the instruction deploys to exactly one "
            "target instead of both CLAUDE.md and .claude/rules/."
        )
        return 1

    print(f"check-instructions-apply-to: all {len(candidates)} instruction(s) declare 'applyTo'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
