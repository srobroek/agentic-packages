#!/usr/bin/env python3
"""CI check: validate Claude hook wiring in settings profiles against package sources.

The live-machine sanitizer (sanitize-claude-hooks.py) can only run where
~/.claude exists. This is its CI counterpart: given one or more committed
settings profiles (chezmoi's external-managed/claude/settings.*.json) and an
agentic-packages checkout, it flags hook entries that reference:

- a package directory (~/.claude/hooks/<pkg>/...) with no matching
  packages/<pkg>/ in the checkout — the retired-package class of staleness
  that `apm prune` leaves behind, or
- a script inside an existing package (~/.claude/hooks/<pkg>/scripts/<f>)
  that the package source no longer ships — the dropped-on-upgrade class.

Loose single-file entries directly under hooks/ (e.g. dgit-push-guard.sh,
cbm-* helpers) are machine-local, not APM-deployed; they are skipped.

Caveat: the checkout is usually `main`, which can be ahead of the released
versions a machine has installed. A script removed on main but still present
in the latest release reports stale here slightly early — acceptable for a
gate whose purpose is catching wiring that will break on the next update.

Exit 0 when clean, 1 when stale wiring is found.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

# ~/.claude/hooks/<rest> in either ~-form or any absolute $HOME form.
HOOKS_REF_RE = re.compile(r"(?:~|/[^\s\"']*?)/\.claude/hooks/([^\s\"']+)")


def hook_commands(settings: dict) -> list[str]:
    commands: list[str] = []
    for groups in (settings.get("hooks") or {}).values():
        if not isinstance(groups, list):
            continue
        for group in groups:
            for handler in group.get("hooks", []):
                command = handler.get("command")
                if isinstance(command, str):
                    commands.append(command)
    return commands


def check_profile(profile: Path, packages_dir: Path) -> list[str]:
    settings = json.loads(profile.read_text(encoding="utf-8"))
    problems: list[str] = []
    for command in hook_commands(settings):
        match = HOOKS_REF_RE.search(command)
        if not match:
            continue
        parts = Path(match.group(1)).parts
        if len(parts) < 2:
            continue  # loose machine-local script, not an APM package deploy
        pkg = parts[0]
        pkg_dir = packages_dir / pkg
        if not pkg_dir.is_dir():
            problems.append(f"{profile.name}: no package source for '{pkg}' ({command})")
            continue
        # Installed layout hooks/<pkg>/<rel> mirrors the package source layout.
        rel = Path(*parts[1:])
        if not (pkg_dir / rel).is_file():
            problems.append(f"{profile.name}: '{pkg}' no longer ships '{rel}' ({command})")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--packages-dir",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "packages",
        help="packages/ directory of an agentic-packages checkout",
    )
    parser.add_argument("profiles", nargs="+", type=Path)
    args = parser.parse_args()

    if not args.packages_dir.is_dir():
        print(f"check-hook-wiring: packages dir not found: {args.packages_dir}")
        return 2

    problems: list[str] = []
    for profile in args.profiles:
        if not profile.is_file():
            print(f"check-hook-wiring: skipping missing profile {profile}")
            continue
        problems.extend(check_profile(profile, args.packages_dir))

    if problems:
        print(f"check-hook-wiring: {len(problems)} stale hook reference(s):")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("check-hook-wiring: all hook references resolve to package sources")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
