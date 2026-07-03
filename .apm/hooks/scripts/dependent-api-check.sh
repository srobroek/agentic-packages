#!/usr/bin/env bash
# Hook: PreToolUse:Write,PreToolUse:Edit -- Check dependent crate/module APIs exist before writing code
# Advisory only -- reminds to verify imports compile before committing.

INPUT=$(cat)
TOOL=$(echo "$INPUT" | jq -r '.tool_name // empty')
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // empty')

[ -z "$FILE_PATH" ] && exit 0

# Only check Rust source files in GUI/CLI crates that import from core
case "$FILE_PATH" in
  */astro-up-gui/src/*.rs|*/astro-up-cli/src/*.rs) ;;
  *) exit 0 ;;
esac

# Check if the file content references astro_up_core types
CONTENT=""
if [ "$TOOL" = "Write" ]; then
  CONTENT=$(echo "$INPUT" | jq -r '.tool_input.content // empty')
elif [ "$TOOL" = "Edit" ]; then
  CONTENT=$(echo "$INPUT" | jq -r '.tool_input.new_string // empty')
fi

[ -z "$CONTENT" ] && exit 0

# Look for core crate imports
if echo "$CONTENT" | grep -qE 'astro_up_core::|use astro_up_core'; then
  # Extract the module paths being referenced
  # POSIX ERE (grep -oE), not PCRE (grep -oP): -P is a GNU-only extension that
  # stock macOS BSD grep rejects with "invalid option -- P". `\w` -> [[:alnum:]_].
  MODULES=$(echo "$CONTENT" | grep -oE 'astro_up_core::[[:alnum:]_]+(::[[:alnum:]_]+)*' | sort -u | head -5)
  if [ -n "$MODULES" ]; then
    jq -n --arg mods "$MODULES" '{
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        additionalContext: ("DEPENDENT API CHECK: This file imports from astro-up-core. Verify these exist with `cargo check` after writing:\n" + $mods)
      }
    }'
  fi
fi

exit 0
