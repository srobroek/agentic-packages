#!/usr/bin/env python3
"""Worktree lifecycle hooks: WorktreeCreate and WorktreeRemove.

Merged from two shell scripts (worktree-create.sh, worktree-cleanup.sh) per
the hook contract's fold-narrow-guards-together rule: both bind lifecycle
events in this one package, so answering "which event fired" once and
dispatching is nearly free, whereas two separate scripts would each pay a
process startup and payload parse. Self-filters on hook_event_name since
Codex has no per-event manifest routing analogue.

These are lifecycle events (rare -- one worktree create/remove per spawn),
not the PreToolUse hot path, so the perf rules that gate module-scope
imports elsewhere do not apply with the same weight here; imports are kept
function-local anyway for consistency with the rest of the package family
and because most invocations still bail before needing json/subprocess.

WorktreeCreate: create worktrees in /tmp to prevent nesting. Keeps
worktrees outside the repo tree, which eliminates nesting bugs entirely.
Prints the created path on success and exits 0; exits 1 (with a stderr
message) when the request cannot be honored.

WorktreeRemove: clean up the worktree directory and branch after removal.
Only ever touches a LINKED worktree, never the main repo, and never
discards uncommitted work without stashing it first.
"""

from __future__ import annotations

import sys


def git_common_dir(cwd: str) -> str | None:
    import subprocess

    result = subprocess.run(
        ["git", "-C", cwd, "rev-parse", "--git-common-dir"],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    output = result.stdout.strip()
    return output if result.returncode == 0 and output else None


def repo_root_from_common_dir(cwd: str, git_common: str) -> str:
    """The main worktree root, from its shared .git dir.

    Physical (symlink-resolved), matching `git rev-parse --show-toplevel`: on
    macOS /tmp -> /private/tmp and /var -> /private/var are symlinks, so a
    logical root would never equal TOPLEVEL and the main-repo guard would
    silently fail.
    """
    import os

    common_abs = git_common if os.path.isabs(git_common) else os.path.join(cwd, git_common)
    return os.path.realpath(os.path.join(common_abs, ".."))


def sanitize_name(name: str) -> str | None:
    """Collapse whitespace to dashes, strip leading/trailing dashes.

    The name flows into both the worktree path and the branch name, so an
    unsanitized value could escape the managed /tmp/claude-worktrees tree
    (path traversal) or inject git-ref metacharacters. Collapsing whitespace
    first stops a multi-line payload from smuggling a second path component
    through; stripping leading dashes defangs a leading-dash name (e.g.
    "-rf"), which git could otherwise treat as an option flag.

    Returns None when the name still contains `..` or `/` after sanitizing --
    that cannot be safely rewritten without surprising the caller.
    """
    import re

    collapsed = re.sub(r"[\n\r\t ]+", "-", name)
    collapsed = re.sub(r"-+", "-", collapsed)
    collapsed = collapsed.strip("-")
    if ".." in collapsed or "/" in collapsed:
        return None
    return collapsed


def worktree_create(payload: dict) -> int:
    import os

    cwd = payload.get("cwd") or ""
    if not cwd:
        return 1

    name = payload.get("worktree_name") or f"worktree-{os.getpid()}"
    ref = payload.get("git_ref") or "HEAD"

    sanitized = sanitize_name(name)
    if sanitized is None:
        print(f"BLOCKED: unsafe worktree name ({name}). Refusing to create.", file=sys.stderr)
        return 1
    name = sanitized or f"worktree-{os.getpid()}"

    # GUARD: reject if CWD is inside a managed worktree path -- prevents nesting.
    if "/claude-worktrees/" in cwd or "/.claude/worktrees/" in cwd:
        print(f"BLOCKED: CWD is inside a worktree ({cwd}). Refusing to nest.", file=sys.stderr)
        return 1

    git_common = git_common_dir(cwd)
    repo_root = repo_root_from_common_dir(cwd, git_common) if git_common else cwd

    repo_name = os.path.basename(repo_root)
    worktree_path = f"/tmp/claude-worktrees/{repo_name}/{name}"
    branch_name = f"worktree-{name}"

    os.makedirs(os.path.dirname(worktree_path), exist_ok=True)

    import subprocess

    # Hooks disabled (core.hooksPath=/dev/null) to avoid post-checkout hook
    # failures in /tmp.
    created = subprocess.run(
        [
            "git", "-C", repo_root,
            "-c", "core.hooksPath=/dev/null",
            "worktree", "add", worktree_path, "-b", branch_name, ref,
        ],
        capture_output=True,
        timeout=30,
        check=False,
    )
    if created.returncode == 0:
        print(worktree_path)
        return 0

    # Fallback: try without -b (branch may already exist).
    fallback = subprocess.run(
        [
            "git", "-C", repo_root,
            "-c", "core.hooksPath=/dev/null",
            "worktree", "add", worktree_path, ref,
        ],
        capture_output=True,
        timeout=30,
        check=False,
    )
    if fallback.returncode == 0:
        print(worktree_path)
        return 0
    return 1


def worktree_remove(payload: dict) -> int:
    import subprocess

    cwd = payload.get("cwd") or ""
    if not cwd:
        return 0

    git_common = git_common_dir(cwd)
    if not git_common:
        return 0
    repo_root = repo_root_from_common_dir(cwd, git_common)

    # SAFETY: only operate on a LINKED worktree. If TOPLEVEL equals REPO_ROOT,
    # CWD is the main repo itself -- stashing/removing here would discard the
    # user's real WIP, so bail out without touching anything.
    toplevel_result = subprocess.run(
        ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    toplevel = toplevel_result.stdout.strip()
    if not toplevel:
        return 0
    if toplevel == repo_root:
        return 0

    branch_result = subprocess.run(
        ["git", "-C", cwd, "branch", "--show-current"],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    branch = branch_result.stdout.strip()

    # Only a managed /tmp/claude-worktrees worktree gets force-removed (any
    # residual untracked/modified state there is disposable); unmanaged paths
    # keep git's own safety net.
    managed = toplevel.startswith("/tmp/claude-worktrees/") or toplevel.startswith(
        "/private/tmp/claude-worktrees/"
    )

    # Stash uncommitted changes (including untracked files via -u) so nothing
    # is silently lost before the worktree directory is removed.
    status = subprocess.run(
        ["git", "-C", cwd, "status", "--porcelain"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if status.stdout.strip():
        subprocess.run(
            ["git", "-C", cwd, "stash", "-u"],
            capture_output=True,
            timeout=30,
            check=False,
        )

    remove_cmd = ["git", "-C", repo_root, "worktree", "remove"]
    if managed:
        remove_cmd.append("--force")
    remove_cmd.append(toplevel)
    subprocess.run(remove_cmd, capture_output=True, timeout=30, check=False)

    # Reclaim disk even when removal was refused (e.g. locked or unmanaged
    # tree): build artifacts are reproducible, so a stranded worktree must not
    # keep holding them. Only delete directories git itself marks as ignored,
    # so no real work is ever touched.
    import os
    import shutil

    if os.path.isdir(toplevel):
        for artifact_dir in ("target", "node_modules", "dist", ".venv"):
            candidate = os.path.join(toplevel, artifact_dir)
            if not os.path.isdir(candidate):
                continue
            ignored = subprocess.run(
                ["git", "-C", toplevel, "check-ignore", "-q", artifact_dir],
                capture_output=True,
                timeout=10,
                check=False,
            )
            if ignored.returncode == 0:
                shutil.rmtree(candidate, ignore_errors=True)

    # Delete worktree branch (recoverable; -d refuses unmerged work).
    if branch.startswith("worktree-"):
        subprocess.run(
            ["git", "-C", repo_root, "branch", "-d", branch],
            capture_output=True,
            timeout=10,
            check=False,
        )

    return 0


def main() -> int:
    raw = sys.stdin.read()

    import json

    try:
        payload = json.loads(raw) if raw.strip() else {}
    except ValueError:
        # WorktreeCreate must signal failure on unparsable input (the shell
        # original relied on jq emitting an empty CWD, which also exits 1);
        # WorktreeRemove is a no-op on anything it cannot read.
        payload = None

    event = payload.get("hook_event_name") if isinstance(payload, dict) else None

    if payload is None:
        return 1

    if event == "WorktreeCreate":
        return worktree_create(payload)
    if event == "WorktreeRemove":
        return worktree_remove(payload)

    # hook_event_name is not always present in test/manual invocations; fall
    # back to field shape (worktree_name/git_ref only appear on create).
    if "worktree_name" in payload or "git_ref" in payload:
        return worktree_create(payload)
    return worktree_remove(payload)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:
        # Fail open on cleanup (never wedge on a lifecycle event); create
        # already returns 1 explicitly on any recognized bad input, so an
        # unexpected crash here still surfaces as failure rather than a
        # silent success.
        raise SystemExit(1)
