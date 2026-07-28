"""Shared pieces of the two quality hooks.

Both hooks answer "which languages does this project use, and which tools check
them", and both read a hook payload. That logic lived twice, in two shell scripts
that had drifted apart in small ways. It lives here once, and the two entry points
keep only what differs: one runs the checkers over staged files before a commit,
the other accumulates edits and suggests targeted checks.

Nothing here reaches for a subprocess or a heavyweight import at module level, so
importing it costs nothing on the calls that bail early.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Marker files that identify a language when the project has not declared one.
# Deliberately conservative: an unrecognised project gets no advice rather than
# guesses, because a wrong suggestion is worse than none.
LANGUAGE_MARKERS = {
    "go": ("go.mod",),
    "python": ("pyproject.toml",),
    "rust": ("Cargo.toml",),
    "ts": ("package.json",),
}

# Extension to language, used to decide which checks a given edit warrants.
EXTENSION_LANGUAGES = {
    ".go": "go",
    ".py": "python",
    ".pyi": "python",
    ".rs": "rust",
    ".ts": "ts",
    ".tsx": "ts",
    ".js": "ts",
    ".jsx": "ts",
    ".mjs": "ts",
    ".cjs": "ts",
}

# Filenames that imply a language without a matching extension.
FILENAME_LANGUAGES = {"Cargo.toml": "rust", "go.mod": "go"}


def read_payload() -> dict:
    """Parse the hook payload, returning an empty mapping when unreadable."""
    try:
        data = json.loads(sys.stdin.read())
    except (ValueError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def payload_command(payload: dict) -> str:
    """The shell command, accepting both the object and bare-string shapes.

    A bare string is not hypothetical: some callers send one, and the jq idiom
    `.tool_input.command // .tool_input` throws on it, which silently skipped the
    guard rather than failing loudly.
    """
    tool_input = payload.get("tool_input")
    if isinstance(tool_input, str):
        return tool_input
    if isinstance(tool_input, dict):
        command = tool_input.get("command")
        return command if isinstance(command, str) else ""
    return ""


def payload_cwd(payload: dict) -> Path:
    raw = payload.get("cwd")
    if isinstance(raw, str) and raw and Path(raw).is_dir():
        return Path(raw)
    return Path.cwd()


def find_repo_root(start: Path) -> Path | None:
    """Walk parents for a `.git` entry.

    An entry rather than a directory, because `.git` is a file in a linked
    worktree. This replaces a `git rev-parse` call that cost two orders of
    magnitude more for the same answer.
    """
    try:
        resolved = start.resolve()
    except OSError:
        return None
    for directory in (resolved, *resolved.parents):
        if (directory / ".git").exists():
            return directory
    return None


def selected_languages(root: Path) -> set[str]:
    """Languages this project wants checked.

    Three sources, most explicit first: a committed selection file, an
    environment override, then marker-file detection. The explicit sources exist
    so a polyglot repository can opt in per language instead of accepting
    whatever the markers imply.
    """
    selection = root / ".agents/hooks/quality-languages"
    if selection.is_file():
        try:
            text = selection.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        return _parse_selection(text)

    override = os.environ.get("AGENTIC_QUALITY_LANGS", "")
    if override:
        return _parse_selection(override)

    return {
        language
        for language, markers in LANGUAGE_MARKERS.items()
        if any((root / marker).is_file() for marker in markers)
    }


def _parse_selection(text: str) -> set[str]:
    return {token for token in text.replace(",", " ").split() if token}


def language_enabled(language: str, selected: set[str]) -> bool:
    """`all` enables everything; `ts` also answers for javascript and typescript."""
    if "all" in selected:
        return True
    if language == "ts":
        return bool(selected & {"ts", "javascript", "typescript"})
    return language in selected


def language_for_file(path: str) -> str | None:
    name = Path(path).name
    if name in FILENAME_LANGUAGES:
        return FILENAME_LANGUAGES[name]
    return EXTENSION_LANGUAGES.get(Path(path).suffix)


def emit_advisory(context: str) -> None:
    """Advise without blocking.

    Every finding here is a formatting or lint nit, which the agent can fix in
    place. Blocking a commit over one would cost more than the nit does.
    """
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "additionalContext": context,
            }
        },
        sys.stdout,
    )
