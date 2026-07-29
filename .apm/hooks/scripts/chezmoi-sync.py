#!/usr/bin/env python3
"""Advise when an edit touches chezmoi-managed state (PostToolUse: Edit/Write).

ADVISORY ONLY. Performs no git operation and no `chezmoi add`: it never commits,
stages, or pushes. Automatic commit+push fought deliberate branch work and
`git add -A` swept unrelated dotfile changes into commits, so both were removed.
Its whole job is to tell the agent that an edit landed on an applied copy rather
than the source, and to show what is already pending in the chezmoi source repo.

Ported from shell, where `is_config_file` contained a dead branch: the test
`[[ "$relative" == .*//* ]]` requires a literal double slash, so the "inside a dot
directory" case never matched and files like ~/.config-adjacent dotdirs fell through
to the untracked-suggestion path. The port implements the intended single-slash test,
which is why a file under ~/.ssh/ is now recognised.

Fail open (exit 0) everywhere: this hook only ever prints advice.
"""

from __future__ import annotations

import sys

# Top-level names under $HOME that are never chezmoi-managed config.
IGNORED_TOPS = frozenset(
    {
        ".Trash",
        ".cache",
        ".npm",
        ".pnpm",
        ".bun",
        ".node_modules",
        "node_modules",
        ".DS_Store",
        ".localized",
        ".CFUserTextEncoding",
        ".zsh_history",
        ".bash_history",
        ".fish_history",
        ".python_history",
        ".lesshst",
        ".wget-hsts",
        ".viminfo",
        ".Spotlight-V100",
        ".fseventsd",
        ".TemporaryItems",
        ".cups",
        ".dropbox",
        ".gradle",
        ".m2",
        ".ivy2",
    }
)

# Prefixes under $HOME holding project checkouts, not dotfiles.
PROJECT_PREFIXES = ("personal", "work", "Projects")

# Transient files worth no advice.
IGNORED_SUFFIXES = (".lock", ".swp", ".swo", "~", ".bak", ".tmp")

# Names that look like configuration worth tracking, when untracked.
CONFIG_SUFFIXES = (".conf", ".config", ".cfg", ".ini", ".toml", ".yaml", ".yml", ".json")
CONFIG_NAMES = ("config",)
CONFIG_LITERALS = (".gitconfig", ".gitignore")


def chezmoi(*arguments: str) -> str:
    """Run chezmoi and return stdout, or empty on any failure."""
    import subprocess

    try:
        result = subprocess.run(
            ["chezmoi", *arguments],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def pending_advisory(source: str) -> str:
    """Read-only advisory listing uncommitted changes in the chezmoi source repo."""
    import subprocess

    try:
        inside = subprocess.run(
            ["git", "-C", source, "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        if inside.returncode != 0:
            return ""
        status = subprocess.run(
            ["git", "-C", source, "status", "--short"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    if status.returncode != 0 or not status.stdout.strip():
        return ""

    return f"""<chezmoi-commit-advisory>
Your edit changed chezmoi-managed dotfile state. This hook does NOT auto-commit
or auto-push -- you must handle it deliberately.

CHEZMOI SOURCE REPO: {source}

Uncommitted changes there right now (git status --short):
{status.stdout.rstrip()}

ACTION (when your current task is at a commit point):
  1. cd "{source}"  (or use git -C "{source}")
  2. Review: git -C "{source}" diff
  3. Stage ONLY the files you intend (never git add -A -- other unrelated
     dotfile changes may be pending, as shown above).
  4. Commit on an appropriate branch, then push deliberately (dgit for github.com).
Do this yourself; nothing is committed or pushed automatically.
</chezmoi-commit-advisory>"""


def is_config_path(relative) -> bool:
    """Whether a $HOME-relative path is plausibly chezmoi-managed configuration."""
    parts = relative.parts
    if not parts:
        return False
    # Anything under ~/.config.
    if parts[0] == ".config":
        return True
    # A dotfile directly in $HOME.
    if len(parts) == 1 and parts[0].startswith("."):
        return True
    # Inside a dot directory in $HOME. The shell version tested for a literal `//`
    # here, so this branch never fired and ~/.ssh/config was never recognised.
    return len(parts) > 1 and parts[0].startswith(".")


def is_ignored(path, relative, source: str) -> bool:
    """Whether the path is known-uninteresting."""
    text = str(path)
    if source and text.startswith(source):
        return True
    parts = relative.parts
    if not parts:
        return True
    if parts[0] in IGNORED_TOPS:
        return True
    if parts[0] == ".local":
        return True
    if parts[0] == ".cargo" and len(parts) > 1 and parts[1] in ("registry", "git"):
        return True
    return text.endswith(IGNORED_SUFFIXES)


def looks_like_config(name: str) -> bool:
    """Whether an untracked file's name suggests it is configuration."""
    if name in CONFIG_LITERALS or name in CONFIG_NAMES:
        return True
    if name.endswith(CONFIG_SUFFIXES):
        return True
    if name.startswith("settings"):
        return True
    # .zshrc, .profile, .env and friends.
    return name.startswith(".") and (
        name.endswith("rc") or name.endswith("profile") or name.endswith("env")
    )


def main() -> int:
    payload = sys.stdin.read()
    if not payload:
        return 0

    import json

    try:
        data = json.loads(payload)
    except (ValueError, TypeError):
        return 0
    if not isinstance(data, dict):
        return 0

    tool_input = data.get("tool_input")
    raw = tool_input.get("file_path") if isinstance(tool_input, dict) else None
    if not isinstance(raw, str) or not raw:
        return 0

    from pathlib import Path

    path = Path(raw)
    if not path.is_file():
        return 0
    try:
        path = path.resolve()
    except OSError:
        return 0

    home = Path.home()
    try:
        relative = path.relative_to(home)
    except ValueError:
        # Outside $HOME entirely.
        return 0

    # Project checkouts under $HOME are not dotfile state.
    if relative.parts and relative.parts[0] in PROJECT_PREFIXES:
        return 0

    source = chezmoi("source-path")
    if not source:
        return 0

    text = str(path)
    # A direct edit to the source: advise on committing, nothing else.
    if text.startswith(source) or text.startswith(str(home / ".local/share/chezmoi/")):
        advisory = pending_advisory(source)
        if advisory:
            print(advisory)
        return 0

    if not is_config_path(relative) or is_ignored(path, relative, source):
        return 0

    source_path = chezmoi("source-path", text)
    if source_path and Path(source_path).is_file():
        if source_path.endswith(".tmpl"):
            print(
                f"""<chezmoi-template-warning>
STOP: This file is managed by chezmoi as a template.

TARGET_FILE: {text}
TEMPLATE_FILE: {source_path}

ACTION REQUIRED:
1. Your changes to {text} will be OVERWRITTEN by chezmoi
2. Instead, edit the template: {source_path}
3. Apply the same logical changes to the template file
4. After editing the template, run: chezmoi apply --include={text}

Do NOT continue editing the target file. Edit the template file instead.
</chezmoi-template-warning>"""
            )
            return 0

        print(
            f"""<chezmoi-readd-advisory>
This file is tracked by chezmoi; you edited the APPLIED target, not the source.

TARGET_FILE: {text}
SOURCE_FILE: {source_path}

To fold your change back into the source of truth (nothing is done for you):
  chezmoi re-add "{text}"      # or edit {source_path} directly
Then review/commit/push the chezmoi source repo deliberately (see below if pending)."""
        )
        advisory = pending_advisory(source)
        if advisory:
            print(advisory)
        return 0

    if looks_like_config(path.name):
        print(f"Config file not tracked by chezmoi: {text}")
        print(f'   To add: chezmoi add "{text}"')
    return 0


if __name__ == "__main__":
    sys.exit(main())
