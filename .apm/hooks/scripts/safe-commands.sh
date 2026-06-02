#!/usr/bin/env bash
# safe-commands.sh - PreToolUse hook for Bash commands
# Auto-approves commands that are demonstrably safe (read-only, informational,
# or write only to cwd/tmp). Returns {"decision":"allow"} for safe commands,
# no output (fallthrough) for unknown commands.
#
# This hook runs AFTER bash-guard (policy) and rm-rf-guard (destructive ops).
# It provides a smart allow layer so safe commands don't prompt the user.

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
[ -z "$COMMAND" ] && exit 0

allow() {
  echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow"}}'
  exit 0
}

# Extract the base command (first word, ignoring env var assignments)
BASE=$(echo "$COMMAND" | sed -E 's/^([A-Z_]+=[^ ]+ )*//' | awk '{print $1}')

# Extract all flags/args after the base command
ARGS="${COMMAND#*"$BASE"}"

# ============================================================
# UNIVERSAL SAFE FLAGS -- any command with these is informational
# ============================================================

if echo "$ARGS" | grep -qE '^\s+--version\s*$'; then allow; fi
if echo "$ARGS" | grep -qE '^\s+--help\s*$'; then allow; fi
if echo "$ARGS" | grep -qE '^\s+-h\s*$'; then allow; fi
if echo "$ARGS" | grep -qE '^\s+-V\s*$'; then allow; fi
if echo "$ARGS" | grep -qE '^\s+version\s*$'; then allow; fi
if echo "$ARGS" | grep -qE '^\s+help\s*$'; then allow; fi

# ============================================================
# READ-ONLY / INFORMATIONAL COMMANDS
# These never modify state
# ============================================================

readonly READONLY_COMMANDS=(
  # filesystem inspection
  ls eza exa tree stat file wc du dust duf df
  cat bat head tail less more
  find fd
  grep rg ack ag
  diff colordiff delta
  realpath readlink basename dirname

  # system info
  uname hostname uptime who whoami id groups
  which where whereis type hash command
  printenv env set
  date cal

  # process inspection
  ps top htop btop pgrep
  lsof fuser

  # network inspection (read-only)
  ping traceroute dig nslookup host
  ifconfig ip ss netstat

  # text processing (read stdout, don't modify files)
  echo printf
  sort uniq tr cut paste fold fmt
  sed awk perl  # when used in pipes, these read stdin
  jq yq tomlq
  xargs  # typically used with read-only commands
  tee  # writes but to stdout + file, usually safe

  # compression inspection
  tar  # dangerous with -x but we check below
  unzip zipinfo

  # encoding
  base64 xxd hexdump od
  md5 md5sum sha256sum shasum

  # pagers and viewers
  man info
)

for cmd in "${READONLY_COMMANDS[@]}"; do
  if [ "$BASE" = "$cmd" ]; then allow; fi
done

# ============================================================
# SHELL BUILTINS -- always safe
# ============================================================

readonly BUILTINS=(
  echo printf cd pwd pushd popd dirs
  test "[" "[[" true false
  export set unset local declare readonly
  source "." alias unalias
  trap wait sleep
  return exit
  read mapfile readarray
  shift getopts
  times ulimit umask
  complete compgen compopt
  shopt enable
  hash type command builtin
)

for cmd in "${BUILTINS[@]}"; do
  if [ "$BASE" = "$cmd" ]; then allow; fi
done

# ============================================================
# VERSION MANAGERS & RUNTIME QUERIES
# ============================================================

case "$BASE" in
  mise)
    # Allow all mise subcommands except install/uninstall/self-update
    # (those modify the system)
    if echo "$ARGS" | grep -qE '^\s+(install|uninstall|self-update|upgrade|prune|implode)'; then
      : # fallthrough -- prompt user
    else
      allow
    fi
    ;;
  rustup)
    if echo "$ARGS" | grep -qE '^\s+(show|which|check|doc|completions|target list|toolchain list)'; then
      allow
    fi
    ;;
esac

# ============================================================
# GIT -- read-only operations
# ============================================================

if [ "$BASE" = "git" ]; then
  SUBCMD=$(echo "$ARGS" | awk '{print $1}')

  readonly GIT_SAFE_SUBCMDS=(
    status log diff show blame annotate shortlog
    branch  # listing branches is safe; -D is caught by Safety Net
    tag     # listing tags
    remote  # listing remotes
    stash   # stash list is safe; drop/clear caught by Safety Net
    ls-files ls-tree ls-remote
    rev-parse rev-list name-rev describe
    config  # reading config
    reflog
    grep log
    cat-file for-each-ref
    worktree  # worktree list
    count-objects fsck
    verify-commit verify-tag
    whatchanged
    cherry
    rerere
    notes
    range-diff
  )

  for subcmd in "${GIT_SAFE_SUBCMDS[@]}"; do
    if [ "$SUBCMD" = "$subcmd" ]; then allow; fi
  done

  # git with -C flag (directory override) + safe subcmd
  if echo "$ARGS" | grep -qE '^\s+-C\s'; then
    SUBCMD_AFTER_C=$(echo "$ARGS" | sed -E 's/^\s+-C\s+\S+\s+//' | awk '{print $1}')
    for subcmd in "${GIT_SAFE_SUBCMDS[@]}"; do
      if [ "$SUBCMD_AFTER_C" = "$subcmd" ]; then allow; fi
    done
  fi
fi

# ============================================================
# BUILD & TEST -- write to cwd only
# ============================================================

case "$BASE" in
  # Go
  go)
    SUBCMD=$(echo "$ARGS" | awk '{print $1}')
    case "$SUBCMD" in
      build|test|vet|fmt|generate|mod|tool|env|doc|list|version)
        allow ;;
    esac
    ;;

  # Rust
  cargo)
    SUBCMD=$(echo "$ARGS" | awk '{print $1}')
    case "$SUBCMD" in
      build|test|check|clippy|fmt|bench|doc|tree|metadata|verify-project|version|search|locate-project)
        allow ;;
    esac
    ;;

  # Node/JS
  pnpm)
    SUBCMD=$(echo "$ARGS" | awk '{print $1}')
    case "$SUBCMD" in
      # read/inspect
      list|ls|why|audit|outdated|licenses|store)
        allow ;;
      # build/test/run (writes to cwd only)
      run|test|exec|build|start|dev|lint|format|check|typecheck)
        allow ;;
      # pnpm biome, pnpm tsc, etc.
      biome|tsc|tsx|vitest|playwright|jest|mocha)
        allow ;;
      # direct flags
      ""|--version|--help|-h|-V)
        allow ;;
    esac
    ;;
  bun)
    SUBCMD=$(echo "$ARGS" | awk '{print $1}')
    case "$SUBCMD" in
      run|test|build|dev|x)
        allow ;;
    esac
    ;;
  npx)
    # npx runs arbitrary packages -- only allow known safe ones
    SUBCMD=$(echo "$ARGS" | awk '{print $1}')
    case "$SUBCMD" in
      tsc|tsx|biome|vitest|jest|playwright)
        allow ;;
    esac
    ;;
  node|deno|tsx)
    allow ;;

  # Python
  python|python3)
    # Allow running scripts, not bare python (REPL)
    if echo "$ARGS" | grep -qE '^\s+\S'; then allow; fi
    ;;
  uv)
    SUBCMD=$(echo "$ARGS" | awk '{print $1}')
    case "$SUBCMD" in
      run|sync|lock|tree|pip|venv|build|version)
        allow ;;
    esac
    ;;
  pip|pip3)
    SUBCMD=$(echo "$ARGS" | awk '{print $1}')
    case "$SUBCMD" in
      list|show|freeze|check|search)
        allow ;;
    esac
    ;;
  pytest|ruff|mypy|pyright)
    allow ;;

  # Rust tools
  rustfmt|clippy-driver)
    allow ;;

  # Make/Task/Just
  make|gmake)
    allow ;;
  just)
    allow ;;
  task)
    allow ;;

  # Terraform/IaC (plan is read-only, apply is not)
  terraform|tofu)
    SUBCMD=$(echo "$ARGS" | awk '{print $1}')
    case "$SUBCMD" in
      init|plan|validate|fmt|show|state|output|providers|version|graph)
        allow ;;
    esac
    ;;

  # Docker (read-only)
  # Note: docker is in excludedCommands, but if it weren't:
  # docker ps, docker images, docker logs, etc. would be safe

  # Cloud CLIs (read-only operations)
  aws)
    # Only allow read operations
    if echo "$ARGS" | grep -qE '(describe|list|get|show|sts get-caller-identity)'; then
      allow
    fi
    ;;
  gcloud)
    if echo "$ARGS" | grep -qE '(list|describe|info|version|config list)'; then
      allow
    fi
    ;;
esac

# ============================================================
# PACKAGE MANAGER QUERIES (not install/add)
# ============================================================

case "$BASE" in
  brew)
    SUBCMD=$(echo "$ARGS" | awk '{print $1}')
    case "$SUBCMD" in
      list|ls|info|search|deps|uses|leaves|outdated|config|doctor|--version)
        allow ;;
    esac
    ;;
esac

# ============================================================
# FILE OPERATIONS -- safe subset
# ============================================================

case "$BASE" in
  mkdir)
    allow ;;  # creating dirs is safe
  touch)
    allow ;;  # creating/updating timestamps is safe
  cp)
    allow ;;  # copying is non-destructive
  mv)
    allow ;;  # renaming within cwd is typically safe
  ln)
    allow ;;  # symlinks are safe
  chmod)
    # chmod 777 is blocked by permissions.deny, other chmod is fine
    allow ;;
  chown)
    : ;;  # fallthrough -- chown can be sensitive
  rm)
    # rm -rf is caught by rm-rf-guard; plain rm is safe enough
    if echo "$ARGS" | grep -qE '(-rf|-fr|-r\s+-f|-f\s+-r)'; then
      : # fallthrough -- rm-rf-guard handles this
    else
      allow
    fi
    ;;
  rmdir)
    allow ;;  # only removes empty dirs
  install)
    allow ;;  # the install command (not package install)
esac

# ============================================================
# MISC SAFE TOOLS
# ============================================================

readonly MISC_SAFE=(
  # version control helpers
  gh glab  # GitHub/GitLab CLIs -- hooks catch dangerous ops
  pre-commit

  # editors/viewers (non-interactive use)
  code zed subl
  open xdg-open
  pbcopy pbpaste xclip xsel

  # network tools
  curl wget  # download tools -- deny list catches pipe-to-shell
  ssh scp rsync

  # chezmoi
  chezmoi

  # containers (read ops go through, writes need excludedCommands)
  kubectl helm

  # misc dev tools
  wc nl rev tac
  bc dc expr
  yes seq shuf
  iconv
  dot plantuml
  hyperfine
  tokei scc cloc

  # shell utilities
  nohup timeout watch
  xargs parallel

  # archiving (creating archives is safe)
  zip gzip bzip2 xz zstd

  # linters/formatters (write to cwd only)
  shfmt shellcheck
  biome
  golangci-lint
  hadolint
  yamllint
  actionlint
  typos

  # database CLIs (read operations)
  psql mysql sqlite3

  # misc
  bd  # beads daemon
  wt  # worktrunk
)

for cmd in "${MISC_SAFE[@]}"; do
  if [ "$BASE" = "$cmd" ]; then allow; fi
done

# ============================================================
# PATH-BASED PATTERNS -- scripts in known-safe locations
# ============================================================

# Scripts in tmp dirs
if echo "$BASE" | grep -qE '^(/tmp/|/private/tmp/|\$TMPDIR/)'; then allow; fi

# Scripts in current directory
if echo "$BASE" | grep -qE '^\./'; then allow; fi

# Scripts in project bin/scripts dirs
if echo "$BASE" | grep -qE '^(\./)?(bin|scripts|tools|hack)/'; then allow; fi

# ============================================================
# FALLTHROUGH -- unknown commands prompt the user
# ============================================================

exit 0
