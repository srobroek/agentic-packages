#!/usr/bin/env bash
# Hook: PreToolUse:Bash — Suggest preferred tools over deprecated ones
# Advisory only (additionalContext), does NOT block.

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
[ -z "$COMMAND" ] && exit 0

# Suggest for every command in a pipeline/chain, not only the first word:
# split on |, ||, &&, ; and inspect each segment's base command.
SEGMENTS=$(echo "$COMMAND" | awk '{gsub(/\|\||&&|;|\|/, "\n"); print}')

suggest_for() {
  local base="$1" segment="$2"
  case "$base" in
    # CLI replacements
    grep)   echo "Prefer rg (ripgrep) over grep for faster, more ergonomic search." ;;
    find)   echo "Prefer fd over find for faster file discovery." ;;
    ls)     echo "Prefer eza over ls for better output." ;;
    cat)
      # cat is fine for piping; only suggest bat for viewing
      if ! echo "$COMMAND" | grep -qE '\|'; then
        echo "Prefer bat over cat for syntax-highlighted viewing."
      fi
      ;;

    # Package managers
    npm)
      case "$(echo "$segment" | awk '{print $2}')" in
        install) echo "Use pnpm install instead of npm install (project default). Override in the project context file (CLAUDE.md/AGENTS.md) if this project requires npm." ;;
        run)     echo "Use pnpm run instead of npm run (project default). Override in the project context file (CLAUDE.md/AGENTS.md) if this project requires npm." ;;
        *)       echo "Use pnpm instead of npm (project default). Override in the project context file (CLAUDE.md/AGENTS.md) if this project requires npm." ;;
      esac
      ;;
    yarn)   echo "Use pnpm instead of yarn (project default). Override in the project context file (CLAUDE.md/AGENTS.md) if this project requires yarn." ;;
    pip|pip3)
      case "$(echo "$segment" | awk '{print $2}')" in
        install) echo "Use uv pip install or uv add instead of $base install (project default)." ;;
        *)       echo "Use uv pip instead of $base (project default)." ;;
      esac
      ;;
    poetry) echo "Use uv instead of poetry (project default)." ;;
    conda)  echo "Use uv instead of conda (project default)." ;;

    # Task runners
    make)
      if [ -f "justfile" ] || [ -f "Justfile" ]; then
        echo "Prefer just over make (justfile found in project)."
      elif [ -f "Taskfile.yml" ] || [ -f "Taskfile.yaml" ]; then
        echo "Prefer task over make (Taskfile found in project)."
      else
        echo "Prefer just or task (go-task) over make."
      fi
      ;;

    # Version managers
    nvm)    echo "Use mise instead of nvm for version management." ;;
    pyenv)  echo "Use mise instead of pyenv for version management." ;;
    rbenv)  echo "Use mise instead of rbenv for version management." ;;
    asdf)   echo "Use mise instead of asdf for version management." ;;
  esac
}

SUGGESTIONS=""
SEEN=" "
while IFS= read -r SEGMENT; do
  STRIPPED=$(echo "$SEGMENT" | sed -E 's/^[[:space:]]*([A-Za-z_][A-Za-z0-9_]*=[^ ]+[[:space:]]+)*//')
  BASE=$(echo "$STRIPPED" | awk '{print $1}')
  [ -z "$BASE" ] && continue
  case "$SEEN" in *" $BASE "*) continue ;; esac
  SEEN="$SEEN$BASE "
  S=$(suggest_for "$BASE" "$STRIPPED")
  [ -n "$S" ] && SUGGESTIONS="${SUGGESTIONS:+$SUGGESTIONS }$S"
done <<EOF
$SEGMENTS
EOF

if [ -n "$SUGGESTIONS" ]; then
  jq -n --arg msg "TOOL PREFERENCE: $SUGGESTIONS" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      additionalContext: $msg
    }
  }'
fi

exit 0
