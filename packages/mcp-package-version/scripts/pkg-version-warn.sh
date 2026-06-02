#!/usr/bin/env bash
# PreToolUse hook: warn to use latest compatible version when installing packages
# Triggers on package install/add commands

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)

[ -z "$COMMAND" ] && exit 0

case "$COMMAND" in
  *"pnpm add"*|*"pnpm install"*|*"npm install"*|*"npm add"*|*"yarn add"*)
    echo "PACKAGE VERSION: Ensure you're installing the latest compatible version. Use: pnpm add <pkg>@latest or check npm for the current version first." ;;
  *"uv add"*|*"uv pip install"*|*"pip install"*)
    echo "PACKAGE VERSION: Ensure you're installing the latest compatible version. Use: uv add <pkg> (defaults to latest) or check PyPI first." ;;
  *"cargo add"*)
    ;; # cargo add fetches latest by default, no warning needed
  *"go get"*)
    echo "PACKAGE VERSION: Ensure you're installing the latest compatible version. Use: go get <pkg>@latest" ;;
  *"gem install"*|*"bundle add"*)
    echo "PACKAGE VERSION: Ensure you're installing the latest compatible version. Check rubygems.org for the current version." ;;
  *"composer require"*)
    echo "PACKAGE VERSION: Ensure you're installing the latest compatible version. Composer defaults to latest constraint." ;;
esac

exit 0
