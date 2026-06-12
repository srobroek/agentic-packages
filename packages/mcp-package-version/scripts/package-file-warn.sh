#!/usr/bin/env bash
# PreToolUse hook: warn when editing package files directly
# Suggests using native package commands instead.
# Advisory only (additionalContext), never blocks.

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.old_string // empty' 2>/dev/null)

# If no file path found, try to extract from arguments
if [ -z "$FILE_PATH" ]; then
  exit 0
fi

BASENAME=$(basename "$FILE_PATH" 2>/dev/null)

case "$BASENAME" in
  package.json)
    MSG="Editing package.json directly. Consider using native commands instead: pnpm add <pkg>, pnpm remove <pkg>. Ensure you install the latest compatible version." ;;
  Cargo.toml)
    MSG="Editing Cargo.toml directly. Consider using native commands instead: cargo add <crate>, cargo remove <crate>. cargo add fetches the latest compatible version automatically." ;;
  go.mod)
    MSG="Editing go.mod directly. Consider using native commands instead: go get <pkg>@latest, go mod tidy." ;;
  pyproject.toml)
    MSG="Editing pyproject.toml directly. Consider using native commands instead: uv add <pkg>, uv remove <pkg>." ;;
  Gemfile)
    MSG="Editing Gemfile directly. Consider using native commands instead: bundle add <gem>." ;;
  composer.json)
    MSG="Editing composer.json directly. Consider using native commands instead: composer require <pkg>." ;;
  *)
    exit 0 ;;
esac

jq -n --arg msg "PACKAGE FILE EDIT: $MSG" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    additionalContext: $msg
  }
}'
exit 0
