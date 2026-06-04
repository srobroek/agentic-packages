#!/usr/bin/env bash
# Hook: PreToolUse:Bash — Suggest preferred tools over deprecated ones
# Advisory only (additionalContext), does NOT block.

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
[ -z "$COMMAND" ] && exit 0

# Extract base command
BASE=$(echo "$COMMAND" | sed -E 's/^([A-Z_]+=[^ ]+ )*//' | awk '{print $1}')

SUGGEST=""

case "$BASE" in
  # CLI replacements
  grep)   SUGGEST="Prefer rg (ripgrep) over grep for faster, more ergonomic search." ;;
  find)   SUGGEST="Prefer fd over find for faster file discovery." ;;
  ls)     SUGGEST="Prefer eza over ls for better output." ;;
  cat)
    # cat is fine for piping; only suggest bat for viewing
    if ! echo "$COMMAND" | grep -qE '\|'; then
      SUGGEST="Prefer bat over cat for syntax-highlighted viewing."
    fi
    ;;

  # Package managers
  npm)
    SUBCMD=$(echo "$COMMAND" | awk '{print $2}')
    case "$SUBCMD" in
      install) SUGGEST="Use pnpm install instead of npm install (project default). Override in project CLAUDE.md if this project requires npm." ;;
      run)     SUGGEST="Use pnpm run instead of npm run (project default). Override in project CLAUDE.md if this project requires npm." ;;
      *)       SUGGEST="Use pnpm instead of npm (project default). Override in project CLAUDE.md if this project requires npm." ;;
    esac
    ;;
  yarn)   SUGGEST="Use pnpm instead of yarn (project default). Override in project CLAUDE.md if this project requires yarn." ;;
  pip)
    SUBCMD=$(echo "$COMMAND" | awk '{print $2}')
    case "$SUBCMD" in
      install) SUGGEST="Use uv pip install or uv add instead of pip install (project default)." ;;
      *)       SUGGEST="Use uv pip instead of pip (project default)." ;;
    esac
    ;;
  pip3)
    SUBCMD=$(echo "$COMMAND" | awk '{print $2}')
    case "$SUBCMD" in
      install) SUGGEST="Use uv pip install or uv add instead of pip3 install (project default)." ;;
      *)       SUGGEST="Use uv pip instead of pip3 (project default)." ;;
    esac
    ;;
  poetry) SUGGEST="Use uv instead of poetry (project default)." ;;
  conda)  SUGGEST="Use uv instead of conda (project default)." ;;

  # Task runners
  make)
    # Check if justfile or Taskfile exists
    if [ -f "justfile" ] || [ -f "Justfile" ]; then
      SUGGEST="Prefer just over make (justfile found in project)."
    elif [ -f "Taskfile.yml" ] || [ -f "Taskfile.yaml" ]; then
      SUGGEST="Prefer task over make (Taskfile found in project)."
    else
      SUGGEST="Prefer just or task (go-task) over make."
    fi
    ;;

  # Version managers
  nvm)    SUGGEST="Use mise instead of nvm for version management." ;;
  pyenv)  SUGGEST="Use mise instead of pyenv for version management." ;;
  rbenv)  SUGGEST="Use mise instead of rbenv for version management." ;;
  asdf)   SUGGEST="Use mise instead of asdf for version management." ;;
esac

if [ -n "$SUGGEST" ]; then
  jq -n --arg msg "TOOL PREFERENCE: $SUGGEST" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      additionalContext: $msg
    }
  }'
fi

exit 0
