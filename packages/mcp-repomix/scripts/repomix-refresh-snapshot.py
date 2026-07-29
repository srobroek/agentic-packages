#!/usr/bin/env python3
"""Refresh the local Repomix snapshot cache after a branch/integration event.

`PostToolUse` on `Bash`, off the hot path. Repomix packs a whole snapshot
rather than indexing incrementally, so a pack is expensive and every gate that
suppresses one is load-bearing: subagent check, command-pattern match,
non-zero exit check, clean-tree check, gitignore check, HEAD-unchanged check,
and the atomic lockdir dedupe. Run only after successful branch/worktree
creation or integration events, and only when the worktree is clean.

The pack runs detached: this process creates the lockdir synchronously (so two
concurrent hook invocations still dedupe correctly), then re-execs itself with
a hidden `_pack` subcommand via `Popen(..., start_new_session=True)` and
returns immediately. That mirrors the self-reexec pattern already used by
`packages/mcp-serena/scripts/serena-pool.py` for its supervisor process, rather
than reaching for `multiprocessing`, which forks the whole interpreter (imports
and all) for one subprocess call this repo already knows how to background.
"""

from __future__ import annotations

import sys

# Only `sys` at module scope, per the hot-path-adjacent convention this repo
# uses even off PreToolUse: PostToolUse still runs on every Bash call, just
# without gating the tool. `re`, `json`, `os`, `subprocess` etc. live inside
# the functions that use them.

COMMAND_PATTERN = (
    r"(^|[;&|][^\S\n]*)git[^\S\n]+"
    r"(switch[^\S\n]+(-c|--create)|checkout[^\S\n]+(-b|-B)|"
    r"worktree[^\S\n]+add|merge|pull|rebase)"
    r"([^\S\n]|$)"
)

PACK_TIMEOUT_SECONDS = 180


def json_str(payload: dict, *path: str) -> str:
    """Walk a chain of dict keys, returning "" on any type/key mismatch."""
    value: object = payload
    for key in path:
        if not isinstance(value, dict):
            return ""
        value = value.get(key)
    return value if isinstance(value, str) else ""


def extract_command(payload: dict) -> str:
    tool_input = payload.get("tool_input")
    if isinstance(tool_input, str):
        return tool_input
    if isinstance(tool_input, dict):
        command = tool_input.get("command")
        return command if isinstance(command, str) else ""
    return ""


def extract_exit_code(payload: dict) -> int | None:
    """First present exit_code among the three shapes different callers send."""
    for container_key in ("tool_response", "tool_result", "result"):
        container = payload.get(container_key)
        if isinstance(container, dict) and "exit_code" in container:
            code = container["exit_code"]
            if isinstance(code, int):
                return code
            if isinstance(code, str) and code.isdigit():
                return int(code)
    return None


def repo_hash(repo_root: str) -> str:
    import hashlib

    return hashlib.md5(repo_root.encode("utf-8", "surrogateescape")).hexdigest()


def run_pack(repo_root: str, output_path: str, head_marker: str, lock_dir: str) -> None:
    """Run inside the detached child: pack, then write the marker on success only.

    Do NOT pre-write the marker before packing: a premature write makes a later
    invocation believe a (possibly failed) pack succeeded.
    """
    import shutil
    import subprocess

    try:
        timeout_bin = None
        for candidate in ("timeout", "gtimeout"):
            if shutil.which(candidate):
                timeout_bin = candidate
                break

        # The directory is POSITIONAL. repomix 1.11.1 rejects `--directory` with
        # "error: unknown option", so every pack this hook attempted exited
        # non-zero and wrote nothing -- silently, because the pack runs detached
        # with output discarded and the HEAD marker is only written on success.
        cmd = (
            [timeout_bin, str(PACK_TIMEOUT_SECONDS)] if timeout_bin else []
        ) + ["repomix", "--style", "xml", "--output", output_path, repo_root]

        completed = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=PACK_TIMEOUT_SECONDS + 10,
            check=False,
        )
        if completed.returncode == 0:
            head_sha = subprocess.run(
                ["git", "-C", repo_root, "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            ).stdout.strip()
            if head_sha:
                with open(head_marker, "w", encoding="utf-8") as handle:
                    handle.write(head_sha + "\n")
    except Exception:  # noqa: BLE001 - fail open, never surface a pack error
        pass
    finally:
        try:
            import os

            os.rmdir(lock_dir)
        except OSError:
            pass


def main() -> int:
    raw = sys.stdin.read()
    if not raw.strip():
        return 0

    import json

    try:
        payload = json.loads(raw)
    except (ValueError, TypeError):
        return 0
    if not isinstance(payload, dict):
        return 0

    agent_id = json_str(payload, "agent_id")
    if agent_id:
        return 0

    command = extract_command(payload)
    if not command:
        return 0

    import re

    if not re.search(COMMAND_PATTERN, command):
        return 0

    exit_code = extract_exit_code(payload)
    if exit_code is not None and exit_code != 0:
        return 0

    import shutil

    if shutil.which("repomix") is None:
        return 0

    import os

    cwd = json_str(payload, "cwd")
    if not cwd or not os.path.isdir(cwd):
        cwd = os.getcwd()

    import subprocess

    toplevel = subprocess.run(
        ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    repo_root = toplevel.stdout.strip()
    if not repo_root:
        return 0
    git_entry = os.path.join(repo_root, ".git")
    if not os.path.isdir(git_entry) and not os.path.isfile(git_entry):
        return 0

    head_result = subprocess.run(
        ["git", "-C", repo_root, "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    head_sha = head_result.stdout.strip()
    if not head_sha:
        return 0

    # Avoid packing conflicted, partially merged, or locally dirty snapshots.
    status_result = subprocess.run(
        ["git", "-C", repo_root, "status", "--porcelain=v1"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if status_result.stdout.strip():
        return 0

    output_rel = "repomix.xml"
    ignore_check = subprocess.run(
        ["git", "-C", repo_root, "check-ignore", "-q", output_rel],
        timeout=10,
        check=False,
    )
    if ignore_check.returncode != 0:
        return 0

    state_root = os.path.join(
        os.environ.get("XDG_STATE_HOME") or os.path.join(os.path.expanduser("~"), ".local", "state"),
        "agentic-tools",
        "repomix",
    )
    try:
        os.makedirs(state_root, exist_ok=True)
    except OSError:
        return 0

    digest = repo_hash(repo_root)
    head_marker = os.path.join(state_root, f"{digest}.sha")
    try:
        with open(head_marker, encoding="utf-8") as handle:
            last_head = handle.read().strip()
    except OSError:
        last_head = ""
    if last_head == head_sha:
        return 0

    # Dedupe concurrent packs with an atomic lockdir: mkdir succeeds for exactly
    # one racer, others bail. Created synchronously (before detaching) so two
    # concurrent hook invocations still see each other's lock.
    lock_dir = os.path.join(state_root, f"{digest}.lock")
    try:
        os.mkdir(lock_dir)
    except OSError:
        return 0

    output_path = os.path.join(repo_root, output_rel)

    import subprocess

    subprocess.Popen(
        [sys.executable, os.path.realpath(__file__), "_pack", repo_root, output_path, head_marker, lock_dir],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
    )
    # Deliberately not waited on: the hook must return immediately. The child
    # outlives this process and cleans up its own lockdir.

    return 0


def _pack_entrypoint(argv: list[str]) -> int:
    """Hidden subcommand the detached child runs: `_pack <repo_root> <output_path> <head_marker> <lock_dir>`.

    `run_pack` already cleans up its own lockdir in a `finally`, mirroring the
    bash `trap 'rmdir ...' EXIT` on the backgrounded subshell; this wrapper adds
    no extra path, it just unpacks argv.
    """
    repo_root, output_path, head_marker, lock_dir = argv
    run_pack(repo_root, output_path, head_marker, lock_dir)
    return 0


if __name__ == "__main__":
    try:
        if len(sys.argv) > 1 and sys.argv[1] == "_pack":
            raise SystemExit(_pack_entrypoint(sys.argv[2:]))
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:
        raise SystemExit(0)
