#!/usr/bin/env python3
"""PostToolUse:Read -- say so when `Read` silently dropped part of the file.

THE DEFECT. `Read` on a file past its token cap returns a prefix and says nothing.
Measured on a 118,893-byte, 4,001-line file: the result carried lines 1-2,860, no
`<persisted-output>` block, no notice, nothing naming what was missing. Asked
afterwards, the model reported reading all 4,001 lines, because from inside the
transcript that is exactly what the result looks like. This is a silent-loss
defect, the same class as rtk returning 10 of 25 commits unmarked.

WHAT MAKES THE FIX POSSIBLE. The hook payload carries what the result withholds.
`tool_response.file` holds `numLines`, `totalLines`, `startLine`, and
`truncatedByTokenCap`, and that last flag is `True` on a truncated read and absent
on a complete one -- verified against both in one session. So the hook does not
guess from a size heuristic; it reads the runtime's own verdict.

WHY `additionalContext` AND NOT `updatedToolOutput`. Rewriting the result would
mean re-emitting `{type, file:{...}}` with content the model still needs, for no
gain -- the content is not the problem, the missing NOTICE is. `additionalContext`
appends the notice and leaves the prefix intact. Nothing is hidden and nothing is
substituted, so a wrong guess here cannot lose data.

Verified end-to-end: without this hook, asked whether it saw the whole file, the
model answered that it had read all 4,001 lines. With it, the same prompt returned
"No. The Read tool displayed lines 1-2,860 only", naming the 1,141 dropped lines.

Cross-tool: Claude only. `additionalContext` on `PostToolUse` is the one field
Codex also accepts, but Codex has no `Read` tool of this shape, so the manifest
ships this for Claude.

Fails open on every path: a payload that does not parse, lacks the flag, or lacks
line counts exits silently and the result is untouched.
"""

from __future__ import annotations

import json
import sys


def build_notice(start: int, seen: int, total: int) -> str:
    dropped = total - seen
    return (
        f"[token-savings] INCOMPLETE READ. This result carries lines {start}-{seen} "
        f"of {total}; {dropped} lines were dropped to fit a token cap, and the "
        f"result itself gives no sign of it. Do not treat what you have as the "
        f"whole file. Continue with `offset={seen + 1}`, or search the rest with "
        f"`rg <pattern> <path>` instead of reading it."
    )


def main() -> int:
    try:
        payload = json.loads(sys.stdin.buffer.read() or b"{}")
    except (ValueError, TypeError):
        return 0
    if not isinstance(payload, dict):
        return 0

    response = payload.get("tool_response")
    if not isinstance(response, dict):
        return 0
    file_block = response.get("file")
    if not isinstance(file_block, dict):
        return 0

    # The runtime's own flag, not a size heuristic. Absent on a complete read.
    if file_block.get("truncatedByTokenCap") is not True:
        return 0

    seen = file_block.get("numLines")
    total = file_block.get("totalLines")
    start = file_block.get("startLine")
    if not isinstance(seen, int) or not isinstance(total, int):
        return 0
    if not isinstance(start, int):
        start = 1
    # Nothing to report if the counts do not describe a real shortfall.
    if total <= seen:
        return 0

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": build_notice(start, seen, total),
                }
            }
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:
        raise SystemExit(0)
