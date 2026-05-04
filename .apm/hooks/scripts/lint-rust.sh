#!/usr/bin/env bash
# Hook: PostToolUse — check Rust formatting after edit
INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
[ -z "$FILE" ] && exit 0

WARNINGS=$(cargo fmt --check 2>&1 | grep "^Diff in" | head -10)
if [ -n "$WARNINGS" ]; then
    echo "Rust format issues detected. Run 'cargo fmt' to auto-fix:" >&2
    echo "$WARNINGS" >&2
fi
exit 0
