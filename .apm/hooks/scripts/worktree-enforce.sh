#!/usr/bin/env bash
# BLOCKING PreToolUse hook: enforce worktree for code edits (exit 2 = block)
set -euo pipefail

file_path=$(echo "$CLAUDE_TOOL_USE_INPUT" | jq -r '.file_path // empty')
[[ -z "$file_path" ]] && exit 0

# Already in worktree
[[ "$file_path" == /tmp/* ]] && exit 0

# Exempt: .claude/, specs/, .specify/, research/, docs/
[[ "$file_path" == */.claude/* ]] && exit 0
[[ "$file_path" == */specs/* ]] && exit 0
[[ "$file_path" == */.specify/* ]] && exit 0
[[ "$file_path" == */research/* ]] && exit 0
[[ "$file_path" == */docs/* ]] && exit 0

# Exempt: CLAUDE.md in project root (no subdirectory separators after last /)
basename=$(basename "$file_path")
[[ "$basename" == "CLAUDE.md" ]] && { parent=$(dirname "$file_path"); [[ ! "$parent" == */src* ]] && exit 0; }

# Exempt: .md files not inside source directories
if [[ "$basename" == *.md ]]; then
  case "$file_path" in
    */src/*|*/crates/*|*/frontend/src/*|*/lib/*|*/cmd/*|*/internal/*|*/pkg/*) ;; # source dirs -- not exempt
    *) exit 0 ;;
  esac
fi

# If we reach here, it's a code edit outside /tmp/ worktree -- block
echo "BLOCKED: Code edits must happen in a worktree. Use EnterWorktree first." >&2
exit 2
