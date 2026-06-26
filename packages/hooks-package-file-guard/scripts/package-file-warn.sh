#!/usr/bin/env bash
# Hook: PreToolUse:Edit|Write|MultiEdit — warn when editing a dependency
# manifest directly, steering toward the package manager's add command.
# Advisory only (additionalContext), never blocks.

INPUT=$(cat)

# Only the actual file path identifies a manifest. The Edit tool's old_string is
# replacement text, not a path, so it is NOT consulted here. tool_input may be an
# object (Edit/Write carry .file_path; NotebookEdit carries .notebook_path) — the
# type-checked idiom keeps a string-form payload from throwing and bypassing the
# hook. 2>/dev/null suppresses jq parse errors on malformed stdin.
FILE_PATH=$(printf '%s' "$INPUT" | jq -r 'if (.tool_input|type)=="string" then .tool_input else (.tool_input.file_path // .tool_input.notebook_path // empty) end' 2>/dev/null)

[ -z "$FILE_PATH" ] && exit 0

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
}' 2>/dev/null

exit 0
