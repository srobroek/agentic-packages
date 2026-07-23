#!/usr/bin/env python3
"""Purge stale Claude hook wiring left behind by APM upgrades and retirements.

Two gaps in `apm` leave dead entries in the Claude hook config:

1. `apm prune` removes a retired package's directory and deployed files but
   never unmerges its entries from ~/.claude/settings.json or the
   ~/.claude/apm-hooks.json ownership sidecar (only `apm uninstall` does).
2. The hook integrator only adds/updates merged entries; when a package
   upgrade drops a script (e.g. hooks-git-workflow v2 dropping
   test-state-tracker.sh), the old entry keeps pointing at a file that no
   longer exists.

This script is the Claude-side counterpart of sanitize-codex-hooks.py: it
drops hook handlers whose command path no longer exists, removes emptied
groups/events, and (with --prune-stale) deletes top-level entries in
~/.claude/hooks/ that no surviving handler references.

~/.claude/settings.json is typically a chezmoi-managed symlink; all writes
resolve the symlink first and replace the real target atomically so the
symlink itself is never clobbered.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from pathlib import Path


OBSOLETE_COMMAND_SUFFIXES = {
    "/agent-coder/scripts/coder-delegation-reminder.sh",
    # Retired srobroek-agentic scripts superseded by APM packages:
    # worktree-create/cleanup moved to hooks-worktree; branch-check dropped.
    "/srobroek-agentic/scripts/worktree-create.sh",
    "/srobroek-agentic/scripts/worktree-cleanup.sh",
    "/srobroek-agentic/scripts/branch-check.sh",
}


def runtime_semantics(value: object) -> object:
    """Remove APM ownership metadata before comparing runtime behavior."""
    if isinstance(value, dict):
        return {
            key: runtime_semantics(item)
            for key, item in value.items()
            if not key.startswith("_apm_")
        }
    if isinstance(value, list):
        return [runtime_semantics(item) for item in value]
    return value


def command_script_path(command: str) -> Path | None:
    """Return the script path of a command handler, or None if not path-like.

    Hook commands are single script invocations in practice; we take the
    first whitespace-delimited token and only treat it as checkable when it
    is an absolute or ~-prefixed path. Inline commands (echo, env-prefixed
    invocations) are never flagged.
    """
    token = command.strip().split()[0] if command.strip() else ""
    if token.startswith("~"):
        return Path(token).expanduser()
    if token.startswith("/"):
        return Path(token)
    return None


def handler_is_stale(handler: dict) -> bool:
    if handler.get("type") != "command":
        return False
    command = handler.get("command")
    if not isinstance(command, str):
        return False
    token = command.strip().split()[0] if command.strip() else ""
    if any(token.endswith(suffix) for suffix in OBSOLETE_COMMAND_SUFFIXES):
        return True
    script = command_script_path(command)
    return script is not None and not script.is_file()


def clean_events(events: dict) -> int:
    """Drop stale handlers from an events dict in place; return removals."""
    removed = 0
    for event in list(events.keys()):
        groups = events[event]
        if not isinstance(groups, list):
            continue
        clean_groups = []
        for group in groups:
            handlers = group.get("hooks", [])
            kept = [h for h in handlers if not handler_is_stale(h)]
            removed += len(handlers) - len(kept)
            if kept:
                clean_group = dict(group)
                clean_group["hooks"] = kept
                clean_groups.append(clean_group)
        if clean_groups:
            events[event] = clean_groups
        else:
            del events[event]
    return removed


def deduplicate_groups(events: dict) -> int:
    """Deduplicate hook groups, preferring the APM-owned copy."""
    removed = 0
    for event, groups in list(events.items()):
        if not isinstance(groups, list):
            continue
        clean_groups: list[dict] = []
        seen_groups: dict[str, int] = {}
        for group in groups:
            group_key = json.dumps(
                runtime_semantics(group),
                sort_keys=True,
                separators=(",", ":"),
            )
            if group_key in seen_groups:
                removed += 1
                existing_index = seen_groups[group_key]
                existing_group = clean_groups[existing_index]
                if not existing_group.get("_apm_source") and group.get(
                    "_apm_source"
                ):
                    clean_groups[existing_index] = group
                continue
            seen_groups[group_key] = len(clean_groups)
            clean_groups.append(group)
        events[event] = clean_groups
    return removed


def referenced_hook_entries(events_dicts: list[dict], hooks_dir: Path) -> set[str]:
    """Return top-level hooks-dir entry names referenced by any handler."""
    hooks_dir = hooks_dir.expanduser().resolve()
    referenced: set[str] = set()
    for events in events_dicts:
        for groups in events.values():
            if not isinstance(groups, list):
                continue
            for group in groups:
                for handler in group.get("hooks", []):
                    command = handler.get("command")
                    if not isinstance(command, str):
                        continue
                    script = command_script_path(command)
                    if script is None:
                        continue
                    try:
                        rel = script.resolve().relative_to(hooks_dir)
                    except ValueError:
                        continue
                    if rel.parts:
                        referenced.add(rel.parts[0])
    return referenced


def prune_stale_entries(
    events_dicts: list[dict],
    hooks_dir: Path,
    *,
    check: bool = False,
) -> list[Path]:
    """Remove unreferenced top-level entries from the hooks directory."""
    hooks_dir = hooks_dir.expanduser().resolve()
    if not hooks_dir.is_dir():
        return []

    referenced = referenced_hook_entries(events_dicts, hooks_dir)
    stale = sorted(
        (entry for entry in hooks_dir.iterdir() if entry.name not in referenced),
        key=lambda entry: entry.name,
    )
    if check:
        return stale

    for entry in stale:
        if entry.is_dir() and not entry.is_symlink():
            shutil.rmtree(entry)
        else:
            entry.unlink()
    return stale


def atomic_write_json(path: Path, data: dict) -> None:
    """Replace *path*'s real target atomically, preserving any symlink."""
    real = path.resolve()
    real.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(dir=real.parent, prefix=f".{real.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
            handle.write("\n")
        os.replace(temp_name, real)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--settings",
        type=Path,
        default=Path.home() / ".claude" / "settings.json",
    )
    parser.add_argument(
        "--sidecar",
        type=Path,
        default=Path.home() / ".claude" / "apm-hooks.json",
        help="APM hook-ownership sidecar (events at top level)",
    )
    parser.add_argument(
        "--hooks-dir",
        type=Path,
        default=Path.home() / ".claude" / "hooks",
    )
    parser.add_argument("--check", action="store_true")
    parser.add_argument(
        "--prune-stale",
        action="store_true",
        help="remove unreferenced entries from the hooks directory",
    )
    args = parser.parse_args()

    counts = {
        "settings_handlers_removed": 0,
        "sidecar_handlers_removed": 0,
        "settings_duplicate_groups_removed": 0,
        "sidecar_duplicate_groups_removed": 0,
    }
    events_dicts: list[dict] = []

    settings = None
    if args.settings.is_file():
        settings = json.loads(args.settings.read_text(encoding="utf-8"))
        settings_events = settings.get("hooks", {})
        counts["settings_handlers_removed"] = clean_events(settings_events)
        counts["settings_duplicate_groups_removed"] = deduplicate_groups(
            settings_events
        )
        events_dicts.append(settings_events)
    else:
        print(f"Claude hooks sanitizer: {args.settings} does not exist")

    sidecar = None
    if args.sidecar.is_file():
        sidecar = json.loads(args.sidecar.read_text(encoding="utf-8"))
        counts["sidecar_handlers_removed"] = clean_events(sidecar)
        counts["sidecar_duplicate_groups_removed"] = deduplicate_groups(sidecar)
        events_dicts.append(sidecar)

    if not events_dicts:
        return 0

    stale = (
        prune_stale_entries(events_dicts, args.hooks_dir, check=True)
        if args.prune_stale
        else []
    )
    changed = any(counts.values()) or bool(stale)

    if not args.check:
        if settings is not None and (
            counts["settings_handlers_removed"]
            or counts["settings_duplicate_groups_removed"]
        ):
            atomic_write_json(args.settings, settings)
        if sidecar is not None and (
            counts["sidecar_handlers_removed"]
            or counts["sidecar_duplicate_groups_removed"]
        ):
            atomic_write_json(args.sidecar, sidecar)
        if args.prune_stale:
            prune_stale_entries(events_dicts, args.hooks_dir)

    counts["stale_entries_removed"] = len(stale)
    summary = ", ".join(f"{key}={value}" for key, value in counts.items())
    print(f"Claude hooks sanitizer: changed={changed}, {summary}")
    return 1 if args.check and changed else 0


if __name__ == "__main__":
    raise SystemExit(main())
