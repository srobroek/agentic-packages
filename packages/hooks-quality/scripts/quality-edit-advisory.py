#!/usr/bin/env python3
"""PostToolUse advisory: suggest targeted checks once edits accumulate.

Nagging after every edit would be ignored, so this counts edited files and
changed lines across a session and speaks only when the change is large enough to
be worth checking, then stays quiet for a cooldown period. State lives under the
temporary directory, keyed by repository, so two projects never share a counter.

Thresholds are tunable: AGENTIC_QUALITY_ADVISORY_LINES (120),
AGENTIC_QUALITY_ADVISORY_FILES (5), AGENTIC_QUALITY_ADVISORY_COOLDOWN_SECONDS
(300).
"""

from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_common import (  # noqa: E402
    emit_advisory,
    find_repo_root,
    language_enabled,
    language_for_file,
    payload_cwd,
    read_payload,
    selected_languages,
)

# Codex sends the whole patch in tool_input.command; these are the file headers.
PATCH_FILE = re.compile(r"^\*\*\* (?:Update|Add) File: (.*)$", re.MULTILINE)

# Suggested check per language, in the order they are reported.
SUGGESTIONS = {
    "go": "gofmt -l {files} && go vet ./...",
    "python": "ruff check {files} && ruff format --check {files}",
    "rust": "cargo fmt --all -- --check && cargo clippy",
    "ts": "biome check {files}",
}


def edited_files(payload: dict) -> list[str]:
    """Every file this tool call touched, across the shapes the tools use."""
    tool_input = payload.get("tool_input")
    if isinstance(tool_input, dict):
        for key in ("file_path", "path"):
            value = tool_input.get(key)
            if isinstance(value, str) and value:
                return [value]
        command = tool_input.get("command")
        if isinstance(command, str) and command:
            return PATCH_FILE.findall(command)
    elif isinstance(tool_input, str) and tool_input:
        return PATCH_FILE.findall(tool_input) or [tool_input]
    return []


def changed_line_count(payload: dict) -> int:
    """Rough size of this edit, used only to decide when to speak."""
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return 1
    command = tool_input.get("command")
    if isinstance(command, str) and command:
        return sum(
            1
            for line in command.splitlines()
            if line[:1] in "+-" and line[1:2] not in "+-"
        )
    for key in ("new_string", "content"):
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            return len(value.splitlines()) or 1
    return 1


def state_dir(root: Path) -> Path:
    """Per-repository state directory.

    Keyed by a hash of the path so sibling checkouts of the same project, and two
    unrelated projects, keep separate counters.
    """
    import hashlib

    digest = hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:16]
    return Path(os.environ.get("TMPDIR", "/tmp")) / f"agentic-quality-advisory-{digest}"


def read_int(path: Path) -> int:
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return 0


def env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, ""))
    except ValueError:
        return default


def main() -> int:
    payload = read_payload()
    if not payload:
        return 0

    files = [f for f in edited_files(payload) if f]
    if not files:
        return 0

    root = find_repo_root(payload_cwd(payload))
    if root is None:
        return 0
    selected = selected_languages(root)
    if not selected:
        return 0

    directory = state_dir(root)
    try:
        directory.mkdir(parents=True, exist_ok=True)
        files_state = directory / "files"
        lines_state = directory / "lines"
        last_advice = directory / "last-advice"

        known = set()
        if files_state.is_file():
            known = {
                line
                for line in files_state.read_text(encoding="utf-8", errors="replace").splitlines()
                if line.strip()
            }
        known.update(files)
        files_state.write_text("\n".join(sorted(known)) + "\n", encoding="utf-8")

        total_lines = read_int(lines_state) + changed_line_count(payload)
        lines_state.write_text(f"{total_lines}\n", encoding="utf-8")
        last = read_int(last_advice)
    except OSError:
        return 0  # state is a convenience, never a reason to fail

    line_threshold = env_int("AGENTIC_QUALITY_ADVISORY_LINES", 120)
    file_threshold = env_int("AGENTIC_QUALITY_ADVISORY_FILES", 5)
    cooldown = env_int("AGENTIC_QUALITY_ADVISORY_COOLDOWN_SECONDS", 300)

    now = int(time.time())
    if now - last < cooldown:
        return 0
    if total_lines < line_threshold and len(known) < file_threshold:
        return 0

    # Only suggest checks for languages actually present in the edited set, so a
    # Python-only change never mentions cargo.
    by_language: dict[str, list[str]] = {}
    for path in sorted(known):
        language = language_for_file(path)
        if language and language_enabled(language, selected):
            by_language.setdefault(language, []).append(path)
    if not by_language:
        return 0

    suggestions = [
        SUGGESTIONS[language].format(files=" ".join(paths[:8]))
        for language, paths in by_language.items()
        if language in SUGGESTIONS
    ]
    if not suggestions:
        return 0

    preview = sorted(known)
    shown = ", ".join(preview[:10])
    if len(preview) > 10:
        shown += f", +{len(preview) - 10} more"

    try:
        last_advice.write_text(f"{now}\n", encoding="utf-8")
    except OSError:
        pass

    # The "QUALITY ADVISORY" prefix is the stable marker callers and tests key
    # on, so it stays exactly as it was.
    emit_advisory(
        f"QUALITY ADVISORY: {len(preview)} file(s) and approximately {total_lines} "
        f"changed line(s) in {', '.join(sorted(by_language))}. Before committing, "
        f"run checks on the edited files only where practical. Suggested targeted "
        f"checks: " + "; ".join(suggestions) + f". Files: {shown}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:
        # Fail open: an advisory must never disturb the edit that triggered it.
        raise SystemExit(0)
