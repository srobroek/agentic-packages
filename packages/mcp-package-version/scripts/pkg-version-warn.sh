#!/usr/bin/env bash
# PreToolUse hook: warn to use latest compatible version when installing packages
# Triggers on package install/add commands.
# Advisory only (additionalContext), never blocks.

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)

[ -z "$COMMAND" ] && exit 0

case "$COMMAND" in
  *"pnpm add"*|*"pnpm install"*|*"npm install"*|*"npm add"*|*"yarn add"*)
    MSG="Ensure you're installing the latest compatible version. Use: pnpm add <pkg>@latest or check npm for the current version first." ;;
  *"uv add"*|*"uv pip install"*|*"pip install"*)
    MSG="Ensure you're installing the latest compatible version. Use: uv add <pkg> (defaults to latest) or check PyPI first." ;;
  *"cargo add"*)
    exit 0 ;; # cargo add fetches latest by default, no warning needed
  *"go get"*)
    MSG="Ensure you're installing the latest compatible version. Use: go get <pkg>@latest" ;;
  *"gem install"*|*"bundle add"*)
    MSG="Ensure you're installing the latest compatible version. Check rubygems.org for the current version." ;;
  *"composer require"*)
    MSG="Ensure you're installing the latest compatible version. Composer defaults to latest constraint." ;;
  *)
    exit 0 ;;
esac

jq -n --arg msg "PACKAGE VERSION: $MSG" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    additionalContext: $msg
  }
}'
exit 0
