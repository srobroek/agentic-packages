#!/usr/bin/env bash
# Hook: PostToolUse — check Python lint after edit
INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
[ -z "$FILE" ] && exit 0

if command -v ruff >/dev/null 2>&1; then
    WARNINGS=$(ruff check "$FILE" --no-fix 2>&1 | head -10)
    if [ -n "$WARNINGS" ]; then
        echo "Python lint issues in $FILE. Run 'ruff check --fix $FILE' to auto-fix:" >&2
        echo "$WARNINGS" >&2
    fi
fi
exit 0
