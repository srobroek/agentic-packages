#!/usr/bin/env python3
"""PreToolUse deny gate: never READ a repomix pack, only search it.

A full pack of a 4,107-file repository is 6,349,248 tokens across 26 MB. Reading
it is not a large read, it is roughly six context windows, so it cannot succeed:
the tool truncates or the session dies. The pack exists to be SEARCHED, where it
is genuinely good -- one file instead of a tree walk, measured at 0.023s to list
every path under a directory against 0.126s for the equivalent `rg` over the
live tree, and faithful (16 unique symbol matches in the pack against 16 live).

So this denies the read and names the search instead. It is the one place a deny
is right rather than an advisory: an advisory the model declines to follow costs
the whole context window, and the correction is mechanical.

Covers the ways a pack gets read:

  Read tool           on a pack path
  Bash                cat / bat / head -<huge> / less / more / open
  MCP file readers    a `file_path`/`path` argument naming a pack

Deliberately NOT denied:

  rg / grep / awk / sed on a pack   -- the intended use
  head / tail with a small count    -- sampling the shape is reasonable
  wc                                -- a size check
  a pack under the size threshold   -- a tiny repository's pack is readable

THE ESCAPE HATCH. Sometimes the whole pack IS what you want: a human opening it
in an editor, or an agent genuinely needing to page through it. Set
`TOKEN_SAVINGS_ALLOW_PACK_READ=1` and the guard steps aside for that call. A deny
with no override is a guard that gets deleted the first time it is wrong, so the
override exists to keep the default strict.

The denial message names it, because a denial the model cannot act on is just a
wall.

Fails open: an unparseable payload, a missing file, or any exception allows.
"""

from __future__ import annotations

import sys

# Only `sys` at module scope: this runs on every Read and Bash call.

# Filenames that are repomix output. `repomix-output.*` are its defaults when
# `--output` is omitted; the rest are the conventional names.
PACK_NAMES = (
    "repomix-output.xml",
    "repomix-output.md",
    "repomix-output.txt",
    "repomix-full.xml",
    "repomix.xml",
    "repomix.md",
    "repomix.json",
    "repomix.txt",
)

# Below this a pack is small enough to read. A tiny repository packs to a few
# thousand tokens and denying that would be obstructive. 400 KB is roughly 100k
# tokens: already large, still recoverable.
READABLE_BYTES = 400_000

# Readers that pull a whole file into context.
WHOLE_FILE_READERS = ("cat", "bat", "less", "more", "open", "nl")

# A line-count flag small enough that the caller is sampling, not slurping.
SAMPLE_LIMIT = 200


def pack_paths_in(text: str) -> list[str]:
    """Pack filenames mentioned in a string, cheapest test first."""
    return [name for name in PACK_NAMES if name in text]


def resolve(root: str, name: str, text: str) -> str | None:
    """Find the pack on disk so its size can gate the decision."""
    import os
    import re

    # Prefer an explicit path from the command, so a pack outside the repository
    # is still measured.
    match = re.search(r"(\S*" + re.escape(name) + r")", text)
    if match:
        candidate = os.path.expanduser(match.group(1))
        if os.path.isabs(candidate) and os.path.exists(candidate):
            return candidate
        joined = os.path.join(root, candidate)
        if os.path.exists(joined):
            return joined
    joined = os.path.join(root, name)
    return joined if os.path.exists(joined) else None


def repo_root(start: str) -> str:
    import os

    path = os.path.realpath(start)
    while True:
        if os.path.exists(os.path.join(path, ".git")):
            return path
        parent = os.path.dirname(path)
        if parent == path:
            return os.path.realpath(start)
        path = parent


def is_search(command: str) -> bool:
    """Does this command SEARCH the pack rather than read it?

    Checked before the reader test, because `rg pattern repomix.xml` and
    `cat repomix.xml | rg pattern` are both searches and only the second has a
    reader in it.
    """
    import re

    # A large `head`/`tail` count is a slurp wearing a sampler's clothes, so test
    # it BEFORE the searcher list -- `head -100000 pack | rg x` would otherwise
    # pass on the `rg` alone.
    match = re.search(r"(^|[\s;&|])(head|tail)\s+-n?\s*(\d+)", command)
    if match and int(match.group(3)) > SAMPLE_LIMIT:
        return False

    if re.search(r"(^|[\s;&|])(rg|grep|egrep|fgrep|ag|ack|awk|sed|wc|jq|xmllint)(\s|$)", command):
        return True
    if match:
        return True
    return False


def deny(name: str, size: int, how: str) -> None:
    import json

    tokens = size // 4
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        f"`{name}` is a repomix pack: {size:,} bytes, roughly {tokens:,} tokens. "
                        f"{how} would not fit in context. Search it instead:\n"
                        f"  rg '<pattern>' {name}\n"
                        f"  rg -o 'path=\"[^\"]*<name>[^\"]*\"' {name}   # locate a file\n"
                        f"  awk '/<file path=\"<path>\">/,/<\\/file>/' {name}   # one file's contents\n"
                        f"To read one source file, read that file rather than the pack. "
                        f"If you genuinely need the whole pack, rerun with "
                        f"TOKEN_SAVINGS_ALLOW_PACK_READ=1."
                    ),
                }
            }
        )
    )


def main() -> int:
    import os

    # Explicit override: the caller has decided the whole pack is what they want.
    if os.environ.get("TOKEN_SAVINGS_ALLOW_PACK_READ", "").strip() not in ("", "0", "false"):
        return 0

    raw = sys.stdin.buffer.read()
    # Cheap bail: no pack name in the payload means nothing to guard.
    if not any(name.encode() in raw for name in PACK_NAMES):
        return 0

    import json

    try:
        payload = json.loads(raw)
    except (ValueError, TypeError):
        return 0
    if not isinstance(payload, dict):
        return 0

    cwd = payload.get("cwd")
    root = repo_root(cwd if isinstance(cwd, str) and os.path.isdir(cwd) else os.getcwd())

    tool = payload.get("tool_name")
    tool_input = payload.get("tool_input")
    if isinstance(tool_input, str):
        haystack, command = tool_input, tool_input
    elif isinstance(tool_input, dict):
        command = tool_input.get("command")
        command = command if isinstance(command, str) else ""
        # MCP readers and the Read tool name the file in a path-ish field.
        fields = [
            tool_input.get(key)
            for key in ("file_path", "path", "filePath", "target_file", "notebook_path")
        ]
        haystack = " ".join([command] + [f for f in fields if isinstance(f, str)])
    else:
        return 0
    if not haystack:
        return 0

    names = pack_paths_in(haystack)
    if not names:
        return 0
    name = names[0]

    # A search is the intended use, whatever the tool.
    if command and is_search(command):
        return 0

    path = resolve(root, name, haystack)
    if path is None:
        return 0
    try:
        size = os.path.getsize(path)
    except OSError:
        return 0
    if size < READABLE_BYTES:
        return 0

    if tool == "Read" or (isinstance(tool, str) and tool.startswith("mcp__")):
        deny(name, size, "Reading it")
        return 0

    import re

    if command and re.search(
        r"(^|[\s;&|])(" + "|".join(WHOLE_FILE_READERS) + r")(\s|$)", command
    ):
        deny(name, size, "That command")
        return 0

    # A `head`/`tail` count above the sample limit reads most of the pack even
    # though neither is in WHOLE_FILE_READERS.
    oversized = re.search(r"(^|[\s;&|])(head|tail)\s+-n?\s*(\d+)", command or "")
    if oversized and int(oversized.group(3)) > SAMPLE_LIMIT:
        deny(name, size, f"Reading {oversized.group(3)} lines")
        return 0

    # A bare `head`/`tail` with no count defaults to 10 lines: a sample, allowed.
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:
        raise SystemExit(0)
