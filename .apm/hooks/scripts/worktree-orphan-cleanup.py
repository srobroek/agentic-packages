#!/usr/bin/env python3
"""Delete build artifacts from worktrees whose owning session is gone.

Naming convention: /tmp/claude-worktrees/<repo>/worktree-<pid>. A worktree is
orphaned when that pid is no longer running. Only build output is removed -- the
worktree directory itself is left to `git worktree prune`, so nothing a human might
still want is destroyed here.

Ported from shell, where cleanup used `rm -r` on globbed paths and
`find ... -name __pycache__ -exec rm -r {} +`. Two things made that riskier than it
reads: the `for nm in "$worktree"/*/node_modules` glob expands to a LITERAL
unmatched pattern when nothing matches (the `[ -d ]` guard caught it, but only by
luck of ordering), and `find -exec rm -r` follows into any symlink named
`__pycache__`, so a planted link could delete outside the worktree. `shutil.rmtree`
does not traverse symlinks, and every path is verified to sit inside the worktree
before deletion.

Fail open (exit 0) throughout, and skip in subagents so concurrent agents do not
race on the same directories.
"""

from __future__ import annotations

import sys

# Where the pre-Worktrunk session hooks placed worktrees. /private/tmp is the same
# directory on macOS via symlink; resolving both and de-duplicating avoids the
# shell version's `break`-after-first-iteration trick, which silently skipped the
# second base whenever the first existed but was empty.
BASES = ("/tmp/claude-worktrees", "/private/tmp/claude-worktrees")


def prune(directory) -> None:
    """Remove a directory tree, never following a symlink out of it."""
    import shutil

    if directory.is_symlink() or not directory.is_dir():
        return
    shutil.rmtree(directory, ignore_errors=True)


def run(command: list[str], cwd=None) -> None:
    """Run a cleanup command, ignoring failure."""
    import subprocess

    try:
        subprocess.run(
            command,
            cwd=cwd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=300,
        )
    except (OSError, subprocess.SubprocessError):
        return


def alive(pid: int) -> bool:
    """Whether a process with this pid exists."""
    import os

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Exists, owned by someone else. Treat as alive: not ours to clean up.
        return True
    except OSError:
        return True
    return True


def clean(worktree) -> None:
    """Remove build output from one orphaned worktree."""
    if (worktree / "Cargo.toml").is_file():
        run(["cargo", "clean", "--manifest-path", str(worktree / "Cargo.toml")])

    # Node, top level and one level of workspace nesting.
    prune(worktree / "node_modules")
    for child in worktree.iterdir() if worktree.is_dir() else []:
        if child.is_dir() and not child.is_symlink():
            prune(child / "node_modules")

    prune(worktree / ".venv")
    # rglob does not follow symlinked directories, and the containment check below
    # rejects anything that resolves outside the worktree regardless.
    root = worktree.resolve()
    for cache in worktree.rglob("__pycache__"):
        try:
            if cache.resolve().is_relative_to(root):
                prune(cache)
        except OSError:
            continue

    if (worktree / "go.mod").is_file():
        run(["go", "clean", "-cache"], cwd=str(worktree))

    if (worktree / "bin").is_dir() and (worktree / "obj").is_dir():
        prune(worktree / "bin")
        prune(worktree / "obj")

    gradle = (worktree / "build.gradle").is_file() or (worktree / "build.gradle.kts").is_file()
    if gradle:
        prune(worktree / "build")

    if (worktree / "pom.xml").is_file():
        prune(worktree / "target")

    if (worktree / "Package.swift").is_file():
        prune(worktree / ".build")


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

    if data.get("agent_id"):
        return 0

    from pathlib import Path

    seen: set[Path] = set()
    for base in BASES:
        directory = Path(base)
        if not directory.is_dir():
            continue
        try:
            resolved = directory.resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)

        for worktree in sorted(resolved.glob("*/worktree-*")):
            if not worktree.is_dir() or worktree.is_symlink():
                continue
            suffix = worktree.name[len("worktree-") :]
            if not suffix.isdigit():
                continue
            if alive(int(suffix)):
                continue
            clean(worktree)
    return 0


if __name__ == "__main__":
    sys.exit(main())
