#!/usr/bin/env python3
"""Pre-commit + CI check: deliberately duplicated scripts stay byte-identical.

Constitution principle I forbids one package reaching into another's internals
at runtime, and a skill script resolves paths relative to its own installed
directory. So a capability two skills both need is duplicated rather than
shared. The duplication is a decision; the DRIFT is a defect, and a comment
saying "keep both identical" enforces nothing.

Each entry in TWIN_SETS lists paths that must hold identical bytes. Exit 0 when
every set agrees, 1 on any drift or missing member.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

TWIN_SETS: list[tuple[str, list[str]]] = [
    (
        "skill dependency detector",
        [
            "packages/whats-new/.apm/skills/whats-new/scripts/detect.py",
            "packages/dep-update/.apm/skills/dep-update/scripts/detect.py",
        ],
    ),
    (
        "skill dependency detector tests",
        [
            "packages/whats-new/tests/test_whats_new_detect.py",
            "packages/dep-update/tests/test_dep_update_detect.py",
        ],
    ),
    (
        "skill dependency detector fuzz harnesses",
        [
            "packages/whats-new/tests/test_whats_new_detect_fuzz.py",
            "packages/dep-update/tests/test_dep_update_detect_fuzz.py",
        ],
    ),
    (
        "bot review probe",
        [
            "packages/pr-shepherd/.apm/skills/pr-shepherd/scripts/bot-review-probe.py",
            "packages/orchestrate/.apm/skills/orchestrate/scripts/bot-review-probe.py",
        ],
    ),
    (
        "bot review probe tests",
        [
            "packages/pr-shepherd/.apm/skills/pr-shepherd/scripts/_test_bot_review_probe.py",
            "packages/orchestrate/.apm/skills/orchestrate/scripts/_test_bot_review_probe.py",
        ],
    ),
]


def check_set(root: Path, label: str, members: list[str]) -> list[str]:
    problems: list[str] = []
    contents: dict[str, bytes] = {}
    for rel in members:
        path = root / rel
        if not path.is_file():
            problems.append(f"{label}: missing twin member {rel}")
            continue
        contents[rel] = path.read_bytes()

    if len(contents) < 2:
        return problems

    reference_rel, reference = next(iter(contents.items()))
    for rel, body in contents.items():
        if body != reference:
            problems.append(
                f"{label}: {rel} differs from {reference_rel}; "
                f"copy one over the other so the twins stay byte-identical"
            )
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="root of an agentic-packages checkout",
    )
    # Accept pre-commit's staged-file args; the check is whole-set by nature, so
    # they are ignored rather than used to narrow it.
    parser.add_argument("files", nargs="*", type=Path)
    args = parser.parse_args()

    problems: list[str] = []
    for label, members in TWIN_SETS:
        problems.extend(check_set(args.repo_root, label, members))

    if problems:
        print(f"check-twin-scripts: {len(problems)} problem(s):")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    total = sum(len(members) for _, members in TWIN_SETS)
    print(
        f"check-twin-scripts: {len(TWIN_SETS)} twin set(s), "
        f"{total} file(s), all identical"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
