#!/usr/bin/env python3
"""Normalize installed Codex hooks to the released Codex hook contract."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import tempfile
from pathlib import Path

SUPPORTED_EVENTS = {
    "SessionStart",
    "SubagentStart",
    "PreToolUse",
    "PermissionRequest",
    "PostToolUse",
    "PreCompact",
    "PostCompact",
    "UserPromptSubmit",
    "SubagentStop",
    "Stop",
}
OBSOLETE_COMMAND_SUFFIXES = {
    "/agent-builder/scripts/coder-delegation-reminder.sh",
}
CODEX_UNAVAILABLE_PACKAGES = {
    "hooks-subagent-model",
    "hooks-subagent-worktree",
    "hooks-worktree",
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


def command_script_path(command: str, working_dir: Path | None = None) -> Path | None:
    """Return a checkable hook script path, resolving relative paths."""
    token = command.strip().split()[0] if command.strip() else ""
    if token.startswith("~"):
        return Path(token).expanduser()
    if token.startswith("/"):
        return Path(token)
    if working_dir is not None and "/" in token:
        return working_dir / token
    return None


def handler_is_stale(handler: dict, working_dir: Path | None = None) -> bool:
    if handler.get("type") != "command":
        return False
    command = handler.get("command")
    if not isinstance(command, str):
        return False
    script = command_script_path(command, working_dir)
    return script is not None and not script.is_file()


def sanitize(config: dict, working_dir: Path | None = None) -> tuple[dict, dict[str, int]]:
    source_hooks = config.get("hooks", {})
    clean_hooks: dict[str, list[dict]] = {}
    counts = {
        "events_removed": 0,
        "handlers_removed": 0,
        "duplicate_groups_removed": 0,
        "async_converted": 0,
        "if_removed": 0,
        "timeouts_added": 0,
    }

    for event, groups in source_hooks.items():
        if event not in SUPPORTED_EVENTS:
            counts["events_removed"] += 1
            continue

        clean_groups: list[dict] = []
        seen_groups: dict[str, int] = {}
        for group in groups:
            clean_handlers: list[dict] = []
            for handler in group.get("hooks", []):
                command = handler.get("command", "")
                command_token = command.strip().split()[0] if command.strip() else ""
                if (
                    handler.get("type") != "command"
                    or handler_is_stale(handler, working_dir)
                    or any(command_token.endswith(suffix) for suffix in OBSOLETE_COMMAND_SUFFIXES)
                    or any(f"/{package}/" in command for package in CODEX_UNAVAILABLE_PACKAGES)
                ):
                    counts["handlers_removed"] += 1
                    continue

                clean_handler = dict(handler)
                if clean_handler.pop("async", None) is not None:
                    counts["async_converted"] += 1
                if clean_handler.pop("if", None) is not None:
                    counts["if_removed"] += 1
                timeout = clean_handler.get("timeout")
                if not isinstance(timeout, (int, float)) or not 0 < timeout <= 60:
                    clean_handler["timeout"] = 30
                    counts["timeouts_added"] += 1
                clean_handlers.append(clean_handler)

            if clean_handlers:
                clean_group = dict(group)
                clean_group["hooks"] = clean_handlers
                group_key = json.dumps(
                    runtime_semantics(clean_group),
                    sort_keys=True,
                    separators=(",", ":"),
                )
                if group_key in seen_groups:
                    counts["duplicate_groups_removed"] += 1
                    existing_index = seen_groups[group_key]
                    existing_group = clean_groups[existing_index]
                    if not existing_group.get("_apm_source") and clean_group.get("_apm_source"):
                        clean_groups[existing_index] = clean_group
                    continue
                seen_groups[group_key] = len(clean_groups)
                clean_groups.append(clean_group)

        if clean_groups:
            clean_hooks[event] = clean_groups

    clean_config = dict(config)
    clean_config["hooks"] = clean_hooks
    return clean_config, counts


def referenced_hook_entries(config: dict, hooks_dir: Path) -> set[str]:
    """Return top-level hook-dir entries referenced by command handlers."""
    pattern = re.compile(re.escape(str(hooks_dir.expanduser().resolve())) + r"/([^/\s\"']+)")
    referenced: set[str] = set()
    for groups in (config.get("hooks") or {}).values():
        for group in groups:
            for handler in group.get("hooks", []):
                command = handler.get("command")
                if not isinstance(command, str):
                    continue
                referenced.update(pattern.findall(command))
    return referenced


def prune_stale_entries(
    config: dict,
    hooks_dir: Path,
    *,
    check: bool = False,
) -> list[Path]:
    """Remove unreferenced top-level entries from a generated hook directory."""
    hooks_dir = hooks_dir.expanduser().resolve()
    if not hooks_dir.is_dir():
        return []

    referenced = referenced_hook_entries(config, hooks_dir)
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=Path.home() / ".codex" / "hooks.json",
    )
    parser.add_argument("--check", action="store_true")
    parser.add_argument(
        "--prune-stale",
        action="store_true",
        help="remove unreferenced entries from the sibling hooks directory",
    )
    parser.add_argument(
        "--hooks-dir",
        type=Path,
        help="override the hooks directory used by --prune-stale",
    )
    args = parser.parse_args()

    if not args.path.is_file():
        print(f"Codex hooks sanitizer: {args.path} does not exist")
        return 0

    original = json.loads(args.path.read_text(encoding="utf-8"))
    working_dir = args.path.expanduser().resolve().parent.parent
    clean, counts = sanitize(original, working_dir)
    config_changed = clean != original
    hooks_dir = args.hooks_dir or args.path.parent / "hooks"
    stale = prune_stale_entries(clean, hooks_dir, check=True) if args.prune_stale else []
    changed = config_changed or bool(stale)

    if config_changed and not args.check:
        args.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            dir=args.path.parent,
            prefix=f".{args.path.name}.",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(clean, handle, indent=2)
                handle.write("\n")
            os.replace(temp_name, args.path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    if args.prune_stale and not args.check:
        prune_stale_entries(clean, hooks_dir)
    counts["stale_entries_removed"] = len(stale)
    summary = ", ".join(f"{key}={value}" for key, value in counts.items())
    print(f"Codex hooks sanitizer: changed={changed}, {summary}")
    return 1 if args.check and changed else 0


if __name__ == "__main__":
    raise SystemExit(main())
