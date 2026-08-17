"""Language detection and payload reading for the quality advisory.

Answers two questions: which languages this project wants checked, and which of
them the pre-commit framework already checks on its own. The second is what keeps
the advisory from repeating a gate that runs without it.

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

# Checkers that, if the pre-commit framework already runs them, make this hook's
# advice for that language redundant. Matched per language rather than
# wholesale: a repository whose pre-commit runs rustfmt has said nothing about
# Python, so Python advice should still be given.
PRECOMMIT_CHECKERS = {
    "go": ("gofmt", "gofumpt", "goimports", "golangci-lint", "go-vet"),
    "python": ("ruff", "black", "isort", "flake8", "pyupgrade"),
    "rust": ("rustfmt", "cargo-fmt", "clippy", "cargo-clippy"),
    "ts": ("biome", "prettier", "eslint", "oxlint", "dprint"),
}


def _read_stdin_text() -> str:
    """Read the payload as bytes and decode leniently.

    `sys.stdin.read()` raises UnicodeDecodeError on one undecodable byte anywhere in
    the payload -- including in a field the guard never looks at -- and the fail-open
    wrapper then swallowed the error, so a stray byte turned a decision into silence.
    Reproduced on the attribution guard: it denied a valid payload and went silent
    with the same payload plus one bad byte.

    Falls back to a plain read when stdin has no buffer, which is how the tests inject
    a StringIO.
    """
    buffer = getattr(sys.stdin, "buffer", None)
    if buffer is None:
        return sys.stdin.read()
    return buffer.read().decode("utf-8", "replace")


def read_payload() -> dict:
    """Parse the hook payload, returning an empty mapping when unreadable."""
    try:
        data = json.loads(_read_stdin_text())
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


def precommit_covered_languages(root: Path) -> set[str]:
    """Languages whose checks the pre-commit framework already runs.

    Two things must both hold before a language counts as covered: the framework
    hook is actually installed, and the config names a checker for that language.
    A config alone proves nothing, because nobody may have run the install, and an
    installed hook alone proves nothing either -- a config full of whitespace and
    YAML checks says nothing about whether Python is formatted.

    Returns an empty set whenever either signal is missing, so the advisory speaks
    rather than assuming coverage it cannot see.
    """
    config = next(
        (
            root / name
            for name in (".pre-commit-config.yaml", ".pre-commit-config.yml")
            if (root / name).is_file()
        ),
        None,
    )
    if config is None or not _framework_hook_installed(root):
        return set()

    try:
        text = config.read_text(encoding="utf-8", errors="replace").lower()
    except OSError:
        return set()

    return {
        language
        for language, checkers in PRECOMMIT_CHECKERS.items()
        if any(checker in text for checker in checkers)
    }


def _framework_hook_installed(root: Path) -> bool:
    """True when a pre-commit-generated hook sits inside this repository.

    The hooks directory is resolved through git so a custom core.hooksPath is
    honoured. A path outside the repository belongs to some other manager, which
    this cannot reason about, so it does not count.
    """
    import subprocess

    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--git-path", "hooks"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if result.returncode != 0:
        return False

    hooks = Path(result.stdout.strip())
    if not hooks.is_absolute():
        hooks = root / hooks
    try:
        if not hooks.resolve().is_relative_to(root.resolve()):
            return False
        return "generated by pre-commit" in (hooks / "pre-commit").read_text(
            encoding="utf-8", errors="replace"
        )
    except (OSError, ValueError):
        return False


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
