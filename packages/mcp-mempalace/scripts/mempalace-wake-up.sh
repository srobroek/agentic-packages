#!/usr/bin/env bash
# SessionStart hook: inject MemPalace wake-up context (relevant prior
# cross-session memory) into the session as additionalContext.
#
# Portability floor: bash 3.2.57 + BSD coreutils (stock macOS).
# Never blocks a session start; any failure exits 0 with no output.
set -euo pipefail

# mempalace is optional tooling — if it isn't installed, stay silent.
command -v mempalace >/dev/null 2>&1 || exit 0

# Scope wake-up to this repo's wing (basename of the git repo root, matching
# how the mining script derives the wing). Fall back to a global wake-up when
# not inside a git repo.
repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [ -n "$repo_root" ]; then
  wing="$(basename "$repo_root")"
  ctx="$(mempalace wake-up --wing "$wing" 2>/dev/null || true)"
else
  ctx="$(mempalace wake-up 2>/dev/null || true)"
fi

# No palace / no content yet -> nothing useful to inject. mempalace prints an
# "L1 — No palace found" line for empty stores; suppress that noise so an
# unseeded project adds zero tokens.
[ -n "$ctx" ] || exit 0
case "$ctx" in
  *"No palace found"*) exit 0 ;;
esac

jq -n --arg ctx "$ctx" '{
  hookSpecificOutput: {
    hookEventName: "SessionStart",
    additionalContext: $ctx
  }
}'
