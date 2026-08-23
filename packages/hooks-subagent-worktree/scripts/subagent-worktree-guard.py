#!/usr/bin/env python3
"""PreToolUse:Agent advisory -- non-blocking guidance on subagent worktree
isolation and stale-worktree cleanup. This hook NEVER denies a spawn (that
was the old behavior, which guessed wrong too often and blocked legitimate
work). It only injects short reminders so the parent chooses isolation
deliberately and reaps dead worktrees.

Behavior (tool_name == "Agent"):
  * isolation already declared (isolation key present) -> silent about
    isolation (the parent already chose), but a stale-worktree notice is
    still emitted when the repo has lingering agent worktrees.
  * otherwise -> emit a non-blocking isolation advisory (plus the stale
    notice when applicable) via hookSpecificOutput.additionalContext and
    exit 0. Always allows.

Non-Agent tools and empty payloads pass straight through.

Claude-only (the Agent spawn tool is Claude-specific); the Codex variant is a
no-op.
"""

from __future__ import annotations

import sys

ADVICE = (
    'Subagent isolation (advisory, non-blocking): if this subagent WRITES '
    'files AND runs in parallel with other writers, pass isolation:"worktree" '
    "so they do not collide on a shared tree -- Claude branches it from your "
    "current HEAD (worktree.baseRef=head) as worktree-<name>. A read-only, "
    "different-repo, or lone-writer subagent needs no isolation. If you DO run "
    "it in a worktree, instruct it to COMMIT its work before finishing: the "
    "worktree branch persists, but uncommitted changes there can be lost when "
    "the worktree is cleaned up. Afterward the worktree is yours to reap: once "
    "the branch is merged or harvested AND confirmed clean (git status "
    "--porcelain prints nothing -- never discard uncommitted work), delete its "
    "build artifacts and remove it (rm -rf <worktree>/target; git worktree "
    "remove <worktree>) -- dead worktrees accumulate compiled output and fill "
    "the disk."
)


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


def stale_notice(cwd: str) -> str:
    """Non-blocking notice naming linked agent worktrees (worktree-* branch).

    Cheap: one `git worktree list` per spawn.
    """
    import subprocess

    result = subprocess.run(
        ["git", "-C", cwd, "worktree", "list", "--porcelain"],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    if result.returncode != 0:
        return ""

    stale: list[str] = []
    path = None
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            path = line[len("worktree ") :]
        elif line.startswith("branch refs/heads/worktree-") and path:
            stale.append(path)
            if len(stale) >= 10:
                break

    if not stale:
        return ""

    stale_list = " ".join(stale) + " "
    return (
        "Stale worktree notice: this repo has linked agent worktrees: "
        f"{stale_list}-- review whether each is still in use. For every "
        "finished one, first CONFIRM IT IS CLEAN: git -C <path> status "
        "--porcelain prints nothing and the branch is merged or harvested. "
        "Never discard uncommitted work to force a removal -- commit, stash, "
        "or escalate instead. Once confirmed clean, delete build artifacts "
        "(rm -rf <path>/target and similar gitignored output) then remove: "
        "git worktree remove <path>; git worktree prune. Dead worktrees "
        "accumulate compiled output and fill the disk."
    )


def emit(context: str) -> None:
    import json

    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": context,
            }
        },
        sys.stdout,
    )


def main() -> int:
    raw = _read_stdin_text()
    if not raw.strip():
        return 0

    import json

    try:
        payload = json.loads(raw)
    except ValueError:
        return 0
    if not isinstance(payload, dict):
        return 0

    if payload.get("tool_name") != "Agent":
        return 0

    tool_input = payload.get("tool_input")
    has_isolation = isinstance(tool_input, dict) and "isolation" in tool_input

    cwd = payload.get("cwd")
    notice = ""
    if isinstance(cwd, str) and cwd:
        import subprocess

        try:
            notice = stale_notice(cwd)
        except (OSError, subprocess.TimeoutExpired):
            notice = ""

    if has_isolation:
        if notice:
            emit(notice)
        return 0

    context = ADVICE if not notice else f"{ADVICE}\n\n{notice}"
    emit(context)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:
        # Fail open: an advisory failure must never block a spawn.
        raise SystemExit(0)
