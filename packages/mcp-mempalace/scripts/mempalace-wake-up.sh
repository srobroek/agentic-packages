#!/usr/bin/env bash
# SessionStart hook: inject a tiny MemPalace index (what memory exists for
# this repo + how to recall it) as additionalContext.
#
# Deliberately NOT the `mempalace wake-up` L1 dump: at session start there is
# no query yet, so any content selection is unranked — L1's "importance"
# scoring is a constant for mined drawers, making the dump effectively the
# first N drawers by filing order (verbatim transcript noise). Injecting that
# costs ~800 tokens and buries the useful signal. Instead we inject a compact
# pointer: which wing this repo maps to, how much memory it holds, and an
# instruction to recall on demand with a real query (MCP mempalace_search /
# CLI `mempalace search`), where semantic + BM25 ranking actually works.
#
# Portability floor: bash 3.2.57 + BSD coreutils (stock macOS).
# Never blocks a session start; any failure exits 0 with no output.
set -euo pipefail

# Drain the hook payload before any self-gate can exit. Hook runners may still
# be writing stdin when this process starts, and an early exit gives them EPIPE.
cat >/dev/null 2>&1 || true

# mempalace is optional tooling — if it isn't installed, stay silent.
command -v mempalace >/dev/null 2>&1 || exit 0

# Scope to this repo's wing (basename of the git repo root, matching how the
# mining script derives the wing). Outside a git repo there is no wing to
# point at, so inject nothing.
repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
[ -n "$repo_root" ] || exit 0
wing="$(basename "$repo_root")"

# Pull this wing's room/drawer counts from `mempalace status`. The status
# output is grouped as "WING: <name>" followed by indented "ROOM: ..." lines;
# extract just this wing's block.
status="$(mempalace status 2>/dev/null || true)"
[ -n "$status" ] || exit 0

wing_block="$(printf '%s\n' "$status" | awk -v wing="$wing" '
  /WING:/ { in_wing = ($2 == wing) ; next }
  in_wing && /ROOM:/ { sub(/^[[:space:]]+/, ""); print "  " $0 }
')"

# No memory for this wing yet -> inject nothing (an unseeded project adds
# zero tokens).
[ -n "$wing_block" ] || exit 0

ctx="## MemPalace — cross-session memory available for this repo (wing: $wing)
$wing_block
Recall on demand with a specific query — do not guess from memory of prior
sessions when the palace can answer: use the mempalace_search MCP tool (or
\`mempalace search \"<query>\" --wing $wing\`) for prior decisions, debugging
outcomes, and gotchas from earlier sessions. Memory is verbatim history —
verify code/config facts against the live tree before acting on them."

jq -n --arg ctx "$ctx" '{
  hookSpecificOutput: {
    hookEventName: "SessionStart",
    additionalContext: $ctx
  }
}'
