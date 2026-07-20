#!/usr/bin/env bash
# Backfill: mine this repo's historical Claude Code / Codex session transcripts
# into MemPalace, filed under a wing named for the repo. Idempotent per file:
# a transcript already filed is skipped on re-run.
#
# Run this ONCE per repo to ingest pre-existing transcripts, and only when no
# other session is active in the repo. WARNING — do not run mid-session as a
# save point: the miner has no mtime re-check for conversations, so a transcript
# mined while still growing is frozen at that snapshot and everything appended
# afterwards is never ingested. Ongoing capture is handled automatically by the
# SessionEnd hook (mempalace-auto-mine.sh), which mines each session's complete
# transcript when it ends.
#
# Portability floor: bash 3.2.57 + BSD coreutils (stock macOS).
set -euo pipefail

command -v mempalace >/dev/null 2>&1 || {
  echo "mempalace not installed; skipping mine (install: uv tool install mempalace)" >&2
  exit 0
}

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
[ -n "$repo_root" ] || {
  echo "not inside a git repo; skipping mine" >&2
  exit 0
}
wing="$(basename "$repo_root")"

# Claude Code stores per-project session JSONL under ~/.claude/projects/<slug>,
# where <slug> is the project path with '/' replaced by '-'.
cc_slug="$(printf '%s' "$repo_root" | sed 's#/#-#g')"
cc_dir="$HOME/.claude/projects/$cc_slug"

mined_any=0
if [ -d "$cc_dir" ]; then
  echo "Mining Claude Code sessions for wing '$wing' from $cc_dir" >&2
  mempalace mine "$cc_dir" --mode convos --wing "$wing" || true
  mined_any=1
fi

# Codex stores sessions under ~/.codex/sessions (flat, not per-project). Mining
# the whole dir into this wing would mix other projects, so only mine it when a
# project-scoped subdir exists. Left as a documented extension point.
codex_dir="$HOME/.codex/sessions/$cc_slug"
if [ -d "$codex_dir" ]; then
  echo "Mining Codex sessions for wing '$wing' from $codex_dir" >&2
  mempalace mine "$codex_dir" --mode convos --wing "$wing" || true
  mined_any=1
fi

[ "$mined_any" -eq 1 ] || echo "No session transcript dir found for wing '$wing'; nothing mined." >&2
