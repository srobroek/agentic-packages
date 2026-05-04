#!/usr/bin/env bash
# Hook: PostToolUse — check Go formatting after edit
INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
[ -z "$FILE" ] && exit 0

if command -v gofmt >/dev/null 2>&1; then
    WARNINGS=$(gofmt -l "$FILE" 2>&1)
    if [ -n "$WARNINGS" ]; then
        echo "Go format issues in $FILE. Run 'gofmt -w $FILE' to auto-fix:" >&2
    fi
fi
exit 0
