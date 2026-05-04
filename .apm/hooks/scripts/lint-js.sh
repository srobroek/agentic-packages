#!/usr/bin/env bash
# Hook: PostToolUse — check JS/TS lint after edit
INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
[ -z "$FILE" ] && exit 0

if command -v npx >/dev/null 2>&1; then
    WARNINGS=$(npx biome check "$FILE" 2>&1 | head -10)
    if [ -n "$WARNINGS" ] && ! echo "$WARNINGS" | grep -q "No files were processed"; then
        echo "JS/TS lint issues in $FILE. Run 'npx biome check --fix $FILE' to auto-fix:" >&2
        echo "$WARNINGS" >&2
    fi
fi
exit 0
