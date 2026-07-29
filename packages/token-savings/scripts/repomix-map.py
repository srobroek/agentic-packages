#!/usr/bin/env python3
"""Maintain a cheap repository structure map, and tell the agent it exists.

THE PROBLEM THIS SOLVES is CONTEXT, not time. A full pack is not a thing an
agent can read: a 4,107-file repository packs to 10,365,403 tokens, roughly ten
context windows, while the `--no-files` map of the same tree is 31,299. That
331x is the entire point.

`--compress` does not close that gap. Measured repository-wide it removes 21%
(10,365,403 -> 8,166,829 tokens), against the 70% its documentation claims,
because it extracts Tree-sitter signatures from code and markdown and JSON are
untouched. It also REGRESSES on comment-dense files: doc comments duplicate
around the elision markers.

A PACK IS CHEAP, which is the opposite of what this script used to assume. Its
header claimed "a pack is expensive and every gate that suppresses one is
load-bearing", and the cost-avoidance machinery that premise bought -- a
detached re-exec, a lockdir, a 120-second timeout -- has been removed. Measured
with repomix 1.17.0: a full pack of 4,107 files is 1.65s and of 1,269 files
1.30s, and the `--no-files` map is 1.26s to 3.18s depending on the tree, so the
map is sometimes SLOWER than the pack it replaces. repomix also has no cache
(two identical runs: 2.27s then 2.49s), so nothing is amortised by deferring.

The HEAD-marker gate stays, because skipping genuinely redundant work is still
right, and it is one file read. What is gone is the machinery that treated two
seconds as something to engineer around.

`repomix --no-files` emits the directory tree and metadata with no file
contents. Same repository: 6,093 tokens instead of 1,022,188, a 168x
reduction. THAT is small enough to hand an agent at session start, and it
answers the question a fresh session actually asks -- "what is in this
repository and where" -- without reading a single file.

So this script maintains the MAP, not the pack, and injects it only when it
fits a token budget. On the 4,124-file repository the map is still ~31k tokens,
which is not free context; over budget it injects a pointer to the file instead
of the file, because a 31k-token unconditional injection would cost more than
the exploration it saves.

Two entry points, both fail-open:

  refresh   rebuild the map when HEAD moved (SessionStart, and after merges)
  inject    emit additionalContext naming the map, within budget
  forget    delete this checkout's map (Worktrunk `post-remove`)

Never blocks a session. Missing repomix, an unwritable path, a pack timeout, or
any exception exits 0 with no output.
"""

from __future__ import annotations

import sys

# Only `sys` at module scope: `inject` runs on every SessionStart, and the
# repository's hook contract puts the per-call budget ahead of tidy imports.

# A pack is 1.3 to 3.2 seconds measured on repomix 1.17.0, so this bounds only a
# pathological tree. A 120-second timeout on a 2-second operation could not fire
# for the reason it was written.
PACK_TIMEOUT_SECONDS = 30

# Above this, the map is referenced rather than inlined. 6k fits comfortably in
# a session preamble; the ~31k a large repository produces does not, and paying
# it on every session would exceed the exploration it saves.
DEFAULT_BUDGET_TOKENS = 8000

# repomix reports tokens with a real tokenizer, but the map file is read from
# disk here, so estimate from bytes. 3.5 bytes/token is deliberately
# conservative for XML-ish text (an under-estimate would blow the budget).
BYTES_PER_TOKEN = 3.5

MAP_BASENAME = "repomix-map.xml"

# BOTH an allowlist and a blocklist, because measured against a full pack they cut
# different things and compose better than either alone:
#
#   default                        1,299,332 / 10,365,403 tokens
#   --ignore only                       -21.1% / -33.5%
#   --include code+md only              -14.9% / -28.3%
#   --include code only                 -61.2% / -59.0%   (drops ALL prose)
#   --include + --ignore                -29.2% / -39.7%   <- shipped
#
# `--include` alone on code extensions is the biggest single cut, but it discards
# every README, spec, and ADR -- the files that explain WHY the code is shaped as
# it is, which is most of what a fresh session needs. So the allowlist admits
# prose and config, and the blocklist then removes the generated and duplicated
# members of those same extensions (a lockfile is `.yaml`, a CHANGELOG is `.md`).
#
# An allowlist alone would also silently drop a language nobody thought to list.
# Pairing them means a new extension shows up as noise to be measured, rather than
# as a file that vanished.
#
# See `.apm/skills/token-savings/references/repomix-ignores.md` for the numbers.
DEFAULT_INCLUDES = ",".join(
    (
        "**/*.rs",
        "**/*.ts",
        "**/*.tsx",
        "**/*.js",
        "**/*.jsx",
        "**/*.py",
        "**/*.go",
        "**/*.sh",
        "**/*.toml",
        "**/*.sql",
        "**/*.md",
        "**/*.yaml",
        "**/*.yml",
    )
)
DEFAULT_IGNORES = ",".join(
    (
        "**/CHANGELOG.md",
        "**/*.lock",
        "**/*.lock.yaml",
        "**/*.lock.json",
        "**/pnpm-lock.yaml",
        "**/Cargo.lock",
        "**/uv.lock",
        "**/package-lock.json",
        "**/poetry.lock",
        "**/.claude-plugin/marketplace.json",
        "**/.agents/plugins/marketplace.json",
        "**/assets/seed/**",
        "**/fixtures/**",
        "**/testdata/**",
        "**/*.snap",
        "**/messages/*.json",
        "**/locales/**",
        "**/i18n/**",
        "**/bindings/index.ts",
        "**/*.generated.*",
        "**/generated/**",
        "**/.agents/skills/**",
        "**/.specify/extensions/**",
        # Index dumps from code-graph tools, which write into the tree without
        # gitignoring themselves. Running the tuning sweep on a repository where
        # graphify had been used found `graphify-out/` was 38% of the whole pack.
        "**/graphify-out/**",
        "**/.serena/**",
        "**/repomix.xml",
        "**/local-*.txt",
        "**/*.min.js",
        "**/*.min.css",
        "**/*.map",
    )
)


def repo_root(start: str) -> str | None:
    """Walk parents for a `.git` entry, in process.

    Two orders of magnitude cheaper than spawning `git rev-parse`, per the hook
    contract. `.git` is treated as an ENTRY rather than a directory so linked
    worktrees, where it is a file, still resolve.
    """
    import os

    path = os.path.realpath(start)
    while True:
        if os.path.exists(os.path.join(path, ".git")):
            return path
        parent = os.path.dirname(path)
        if parent == path:
            return None
        path = parent


def state_dir() -> str:
    import os

    base = os.environ.get("XDG_STATE_HOME") or os.path.join(
        os.path.expanduser("~"), ".local", "state"
    )
    return os.path.join(base, "agentic-tools", "token-savings")


def map_paths(root: str) -> tuple[str, str]:
    """Return (map_path, head_marker_path).

    The map lives OUTSIDE the repository, keyed by a hash of the root. Writing
    it into the working tree is what stalled the existing `repomix.xml` hook:
    that hook refuses unless the output is gitignored, and it is not gitignored
    in any local repository, so it has never produced a snapshot anywhere. A
    path under XDG state has no such dependency and cannot dirty a tree.
    """
    import hashlib
    import os

    digest = hashlib.sha256(root.encode("utf-8", "surrogateescape")).hexdigest()[:16]
    directory = state_dir()
    return (
        os.path.join(directory, f"{digest}-{MAP_BASENAME}"),
        os.path.join(directory, f"{digest}.head"),
    )


def current_head(root: str) -> str:
    """Read HEAD without spawning git.

    Resolves a symbolic ref through `.git/HEAD` and the ref file, falling back
    to packed-refs. Returns "" when it cannot be determined, which callers
    treat as "rebuild".
    """
    import os

    git_entry = os.path.join(root, ".git")
    if os.path.isfile(git_entry):
        # Linked worktree: `.git` is a file pointing at the real gitdir.
        try:
            with open(git_entry, encoding="utf-8") as handle:
                content = handle.read().strip()
        except OSError:
            return ""
        if not content.startswith("gitdir:"):
            return ""
        git_entry = content.split(":", 1)[1].strip()
        if not os.path.isabs(git_entry):
            git_entry = os.path.join(root, git_entry)

    head_file = os.path.join(git_entry, "HEAD")
    try:
        with open(head_file, encoding="utf-8") as handle:
            head = handle.read().strip()
    except OSError:
        return ""

    if not head.startswith("ref:"):
        return head  # detached HEAD holds the sha directly

    ref = head.split(":", 1)[1].strip()
    try:
        with open(os.path.join(git_entry, ref), encoding="utf-8") as handle:
            return handle.read().strip()
    except OSError:
        pass

    try:
        with open(os.path.join(git_entry, "packed-refs"), encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) == 2 and parts[1] == ref:
                    return parts[0]
    except OSError:
        pass
    return ""


def refresh(root: str, force: bool = False) -> int:
    """Rebuild the map when HEAD moved. Returns 0 always."""
    import os
    import subprocess

    import shutil

    if shutil.which("repomix") is None:
        return 0

    map_path, head_marker = map_paths(root)
    head = current_head(root)

    if not force and head:
        try:
            with open(head_marker, encoding="utf-8") as handle:
                if handle.read().strip() == head and os.path.exists(map_path):
                    return 0
        except OSError:
            pass

    try:
        os.makedirs(state_dir(), exist_ok=True)
    except OSError:
        return 0

    # Dedupe concurrent refreshes with an atomic lockdir: mkdir succeeds for
    # exactly one racer. Several SessionStart hooks can fire at once across
    # worktrees of the same repository.
    lock_dir = map_path + ".lock"
    try:
        os.mkdir(lock_dir)
    except OSError:
        return 0

    try:
        completed = subprocess.run(
            # The directory is POSITIONAL. repomix 1.11.1 rejects `--directory`
            # outright ("unknown option"), which is how the sibling
            # mcp-repomix refresh hook silently never packed anything.
            [
                "repomix",
                "--style",
                "xml",
                "--no-files",
                "--no-file-summary",
                "--include",
                DEFAULT_INCLUDES,
                "--ignore",
                DEFAULT_IGNORES,
                "--output",
                map_path,
                root,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=PACK_TIMEOUT_SECONDS,
            check=False,
        )
        # Write the marker only on success. A marker written before a failed
        # pack makes the next run believe a stale map is current.
        if completed.returncode == 0 and head:
            with open(head_marker, "w", encoding="utf-8") as handle:
                handle.write(head + "\n")
    except (OSError, subprocess.SubprocessError):
        pass
    finally:
        try:
            os.rmdir(lock_dir)
        except OSError:
            pass
    return 0


def forget(root: str) -> int:
    """Delete this checkout's map and marker.

    Maps are keyed by a hash of the ROOT PATH, so a removed worktree leaves one
    that nothing will ever read again. Worktrunk `post-remove` calls this. Returns
    0 even when there was nothing to remove.
    """
    import os

    for path in map_paths(root):
        try:
            os.unlink(path)
        except OSError:
            pass
    return 0


def inject(root: str, budget: int, event: str = "SessionStart") -> int:
    """Emit additionalContext describing the map.

    `event` must name the hook that invoked this, because the payload echoes it
    back in `hookEventName` and a mismatch is silently ignored. The same entry
    point serves `SessionStart` and `SubagentStart`: a SUBAGENT does not inherit
    the parent's session context, so without the SubagentStart binding it never
    learns the map exists. Verified by asking a subagent a "where is X" question
    with no steering -- it answered with five `ls`/`rg` calls and reported seeing
    "no mention anywhere in my context of a pre-built repository structure map".
    """
    import json
    import os

    map_path, _ = map_paths(root)
    try:
        size = os.path.getsize(map_path)
    except OSError:
        return 0
    if size == 0:
        return 0

    estimated = int(size / BYTES_PER_TOKEN)

    if estimated <= budget:
        try:
            with open(map_path, encoding="utf-8", errors="replace") as handle:
                body = handle.read()
        except OSError:
            return 0
        context = (
            f"Repository structure map ({estimated} est. tokens, from `repomix --no-files`). "
            f"Use it to locate files instead of exploratory listing; it has no file CONTENTS, "
            f"so read or search a file once this tells you where it is.\n\n{body}"
        )
    else:
        # Over budget: name the artifact rather than pay for it. Grepping a
        # 31k-token map costs far less than injecting it into every session.
        context = (
            f"A repository structure map is available at `{map_path}` "
            f"({estimated} est. tokens -- too large to inline). It is the directory tree "
            f"with no file contents, from `repomix --no-files`. Search it "
            f"(`rg <name> {map_path}`) to locate files instead of exploratory `ls`/`find`. "
            f"For file CONTENTS use the semantic tools or Read."
        )

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": event,
                    "additionalContext": context,
                }
            }
        )
    )
    return 0


def main(argv: list[str]) -> int:
    import os

    if not argv:
        return 0
    command = argv[0]
    if command not in ("refresh", "inject", "forget"):
        return 0

    forced = "--force" in argv

    # Read cwd from the payload rather than trusting the process working
    # directory, and canonicalize it: on macOS a payload may carry `/tmp/x`
    # where git reports `/private/tmp/x`, and the two share no prefix.
    cwd = os.getcwd()
    raw = ""
    if not sys.stdin.isatty():
        try:
            raw = sys.stdin.read()
        except OSError:
            raw = ""

    # `refresh` is bound to PostToolUse:Bash, so it runs after EVERY shell
    # command. A repack is only ever warranted after an event that moved HEAD,
    # so reject the rest on the raw bytes before parsing JSON or touching the
    # filesystem. Kept a strict superset of the real trigger: it tests for the
    # verbs alone, never their arguments, so it cannot mask a case the HEAD
    # comparison would have caught. `--force` skips the filter for the
    # SessionStart and manual paths, which have no command to inspect.
    if command == "refresh" and not forced and raw:
        encoded = raw.encode("utf-8", "replace") if isinstance(raw, str) else raw
        # A bare-word filter is far too loose: measured on 3,358 real Bash calls,
        # testing for "commit"/"merge"/etc. admitted 36% of them, because those
        # words appear in bead notes, commit MESSAGES, and branch names. Only 1%
        # actually contained a HEAD-moving git verb. Requiring the literal `git `
        # first cuts the JSON-parse-plus-git-read path by a factor of 20 while
        # staying a strict superset of the structured check below.
        if b"git " not in encoded and b"git\t" not in encoded:
            return 0
        if not any(
            verb in encoded
            for verb in (b"commit", b"merge", b"rebase", b"pull", b"checkout", b"switch", b"worktree", b"reset")
        ):
            return 0

    if raw.strip():
        import json

        try:
            payload = json.loads(raw)
            if isinstance(payload, dict):
                candidate = payload.get("cwd")
                if isinstance(candidate, str) and os.path.isdir(candidate):
                    cwd = candidate
        except (ValueError, TypeError):
            pass

    root = repo_root(cwd)
    if root is None:
        return 0

    if command == "forget":
        return forget(root)

    if command == "refresh":
        return refresh(root, force=forced)

    budget = DEFAULT_BUDGET_TOKENS
    env_budget = os.environ.get("TOKEN_SAVINGS_MAP_BUDGET")
    if env_budget and env_budget.isdigit():
        budget = int(env_budget)

    # Echo back whichever event actually fired. The payload carries it, so trust
    # that over the argv, and fall back to SessionStart for a manual run.
    event = "SessionStart"
    if raw.strip():
        import json as _json

        try:
            payload = _json.loads(raw)
            if isinstance(payload, dict):
                name = payload.get("hook_event_name")
                if isinstance(name, str) and name:
                    event = name
        except (ValueError, TypeError):
            pass
    return inject(root, budget, event)


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except SystemExit:
        raise
    except BaseException:
        raise SystemExit(0)
