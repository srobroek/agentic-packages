#!/usr/bin/env python3
"""PreToolUse:apply_patch|Write|Edit|NotebookEdit -- deny an edit to a generated
ADR file and name the bead to edit instead.

A banner inside the file cannot prevent the edit it warns about. The agent has
already decided to write by the time it reads the file, the write succeeds, and
the renderer destroys the edit on the next commit -- silently, because
regeneration is not a conflict. This moves the warning to the moment of the write
and makes it actionable: the message carries the `bd` command for the bead that
owns the file.

`deny` rather than `allow` + advisory, which the hook contract reserves for
catastrophic or unrecoverable operations. This qualifies on the second count: the
edit is lost with no reflog, no conflict, and no diff to recover from, since the
renderer overwrites rather than merges. The denial is also self-correcting -- an
agent reads the bead id and retries against the bead -- so it does not stall
autonomous work, which is what the ban on `ask` exists to protect.

Scoped as narrowly as the harm: only files under an ADR directory that carry the
generated marker. A hand-written ADR in a repository that does not use this
renderer has no marker and is untouched.

Fails open on an unparsable payload, a missing file, or any exception.
"""

from __future__ import annotations

import sys

# Only `sys` at module scope: this runs on every Write and Edit the agent makes,
# and the hook contract puts a per-call budget ahead of tidy imports.

# The renderer's first line. Matching the marker rather than the path alone is
# what keeps a hand-authored ADR editable: no marker, no denial.
MARKER = "Generated from a beads decision bead"

# Only paths inside an ADR directory are candidates. A file elsewhere that
# happens to contain the marker string -- this script, its tests, the package
# documentation -- must stay editable.
ADR_PATH_HINTS = ("docs/adr/", "doc/adr/")


def allow() -> None:
    """Emit nothing and exit 0. The call proceeds untouched."""
    raise SystemExit(0)


def deny(reason: str) -> None:
    import json

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    raise SystemExit(0)


def target_path(tool_input: dict) -> str:
    """Extract a written path from the file-writing tool payload."""
    for key in ("file_path", "notebook_path", "path"):
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def target_paths(tool: str, tool_input: dict) -> list[str]:
    """Extract every written path, including Codex's whole-patch payload."""
    if tool == "apply_patch":
        command = tool_input.get("command") or tool_input.get("patch")
        if isinstance(command, str):
            paths = []
            prefixes = (
                "*** Update File: ",
                "*** Add File: ",
                "*** Delete File: ",
                "*** Move to: ",
            )
            for line in command.splitlines():
                for prefix in prefixes:
                    if line.startswith(prefix):
                        path = line[len(prefix) :].strip()
                        if path:
                            paths.append(path)
                        break
            return paths
        return []
    path = target_path(tool_input)
    return [path] if path else []


def bead_id_from(text: str) -> str:
    """Read the bead id out of the generated banner's `bd show <id>` line."""
    import re

    match = re.search(r"bd show (\S+)", text)
    if match:
        return match.group(1).rstrip("-")
    match = re.search(r"^bead:\s*(\S+)\s*$", text, flags=re.MULTILINE)
    return match.group(1) if match else ""


def main() -> None:
    import json

    try:
        payload = json.load(sys.stdin)
    except Exception:  # noqa: BLE001
        allow()

    tool = payload.get("tool_name") or payload.get("tool") or ""
    if tool not in ("Write", "Edit", "MultiEdit", "NotebookEdit", "apply_patch"):
        allow()

    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        allow()

    paths = target_paths(tool, tool_input)
    if not paths:
        allow()

    from pathlib import Path

    for path in paths:
        # Normalize separators before matching, so a Windows-style payload is
        # judged the same as a POSIX one.
        normalized = path.replace("\\", "/")
        if not any(hint in normalized for hint in ADR_PATH_HINTS):
            continue

        try:
            existing = Path(path)
            if not existing.is_file():
                # A NEW file under docs/adr/ is not judged here. The renderer
                # owns the numbering, so a hand-created file collides on the
                # next run rather than being silently lost, and the pre-commit
                # gate reports it.
                continue
            # Read only the head: the marker is on line one, and an ADR can be
            # long.
            head = existing.read_text(encoding="utf-8", errors="replace")[:4096]
        except Exception:  # noqa: BLE001
            continue

        if MARKER not in head:
            continue

        bead = bead_id_from(head)
        where = f"`bd show {bead}`" if bead else "its decision bead"
        edit_cmd = (
            f"bd update {bead} --notes '...'"
            if bead
            else "bd update <bead-id> --notes '...'"
        )

        deny(
            f"{normalized} is generated from a beads decision bead and is overwritten "
            f"on the next commit, so an edit here is lost with nothing to recover "
            f"from. Edit the record instead: {where}, then {edit_cmd} (or "
            f"`bd update {bead or '<bead-id>'} -d '...'` to change a MADR section). "
            f"The render-adrs pre-commit hook rewrites this file from the bead. To "
            f"replace the decision rather than correct it, use "
            f"`bd supersede {bead or '<old>'} --with <new>`."
        )

    allow()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001
        # Fail open: a guard defect must not block a write.
        sys.exit(0)
