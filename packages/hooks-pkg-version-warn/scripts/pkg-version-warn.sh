#!/usr/bin/env bash
# PreToolUse hook: warn to use latest compatible version when installing packages
# Triggers on package install/add commands.
# Advisory only (additionalContext), never blocks.

INPUT=$(cat)
# tool_input may be a string OR an object. The naive `.tool_input.command //
# .tool_input` throws on a string; the type-checked form is safe.
COMMAND=$(echo "$INPUT" | jq -r 'if (.tool_input|type)=="string" then .tool_input else (.tool_input.command // empty) end' 2>/dev/null)

[ -z "$COMMAND" ] && exit 0

# Anchor to the leading command token so a substring such as
# `echo pip install ...` or `grep "npm install"` does not trip the advisory.
# Strip leading whitespace, then read the first two whitespace-separated
# tokens (verb + subcommand, e.g. "pnpm add", "uv pip install").
TRIMMED="${COMMAND#"${COMMAND%%[![:space:]]*}"}"
read -r TOK1 TOK2 TOK3 _REST <<EOF
$TRIMMED
EOF
HEAD="$TOK1 $TOK2"
HEAD3="$TOK1 $TOK2 $TOK3"

case "$HEAD3" in
  "uv pip install")
    MSG="Ensure you're installing the latest compatible version. Use: uv add <pkg> (defaults to latest) or check PyPI first."
    HEAD="" ;; # already matched, skip the two-token check below
esac

if [ -n "$HEAD" ]; then
  case "$HEAD" in
    "pnpm add"|"pnpm install"|"npm install"|"npm add"|"yarn add")
      MSG="Ensure you're installing the latest compatible version. Use: pnpm add <pkg>@latest or check npm for the current version first." ;;
    "uv add"|"pip install")
      MSG="Ensure you're installing the latest compatible version. Use: uv add <pkg> (defaults to latest) or check PyPI first." ;;
    "cargo add")
      exit 0 ;; # cargo add fetches latest by default, no warning needed
    "go get")
      MSG="Ensure you're installing the latest compatible version. Use: go get <pkg>@latest" ;;
    "gem install"|"bundle add")
      MSG="Ensure you're installing the latest compatible version. Check rubygems.org for the current version." ;;
    "composer require")
      MSG="Ensure you're installing the latest compatible version. Composer defaults to latest constraint." ;;
    *)
      exit 0 ;;
  esac
fi

[ -z "${MSG:-}" ] && exit 0

jq -n --arg msg "PACKAGE VERSION: $MSG" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    additionalContext: $msg
  }
}' 2>/dev/null
exit 0
