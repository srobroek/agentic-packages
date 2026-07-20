#!/usr/bin/env bash
# SessionEnd hook: mine the just-ended session's transcript into MemPalace
# automatically, so the palace stays populated without anyone remembering to
# run the mine script by hand.
#
# Design constraints (all three bit us in production):
#
# 1. Mine at SessionEnd, not Stop. MemPalace's convo miner treats transcripts
#    as immutable (no mtime re-check): a transcript mined mid-session is never
#    re-mined, so everything appended after the first mine is permanently
#    lost. Only at SessionEnd is the transcript complete.
#
# 2. Mine ONLY this session's transcript (from the hook's stdin JSON), staged
#    at a stable path — never the whole projects dir. A dir-wide mine would
#    sweep up transcripts of OTHER sessions still running concurrently
#    (worktrees, parallel agents) and freeze them per (1).
#
# 3. Run detached. SessionEnd hooks have a short budget and a cold mempalace
#    start alone exceeds it.
#
# After mining, the FTS5 index is checked and rebuilt if the mine corrupted
# it (known MemPalace/ChromaDB failure: large convo mines can leave
# `embedding_fulltext_search` with a malformed inverted index, which kills
# BM25/full-text recall until rebuilt).
#
# Historical backfill is intentionally not done here: run
# `mempalace-mine.sh` by hand once per repo to ingest pre-existing
# transcripts (safe when no other session is active in the repo).
#
# Portability floor: bash 3.2.57 + BSD coreutils (stock macOS).
# Never blocks session end; any failure exits 0 with no output.
set -euo pipefail

command -v mempalace >/dev/null 2>&1 || exit 0
command -v jq >/dev/null 2>&1 || exit 0

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
[ -n "$repo_root" ] || exit 0
wing="$(basename "$repo_root")"

# The harness hands us the ended session's transcript path on stdin.
input="$(cat 2>/dev/null || true)"
transcript="$(printf '%s' "$input" | jq -r '.transcript_path // empty' 2>/dev/null || true)"
[ -n "$transcript" ] && [ -f "$transcript" ] || exit 0
case "$transcript" in *.jsonl) ;; *) exit 0 ;; esac

# Stage the completed transcript at a per-wing path keyed by session id and
# transcript line count. The miner dedupes by source_file path with no mtime
# re-check, so the path must be stable for re-fires of the same state (idempotent)
# but distinct when the session was resumed and the transcript grew — otherwise
# the resumed session's delta would be skipped as already-mined. The prefix gets
# re-mined under the new name (bounded duplication, chosen over silent loss).
staging="$HOME/.mempalace/auto-mine/staging/$wing"
mkdir -p "$staging" 2>/dev/null || exit 0
lines="$(wc -l < "$transcript" 2>/dev/null | tr -d '[:space:]' || echo 0)"
base="$(basename "$transcript" .jsonl)"
staged="$staging/$base.$lines.jsonl"
cp "$transcript" "$staged" 2>/dev/null || exit 0

log="$HOME/.mempalace/auto-mine/$wing.log"

# Detached background worker: mine the staging dir (this transcript plus any
# leftovers from previously failed runs), delete staged files only on
# success, then self-heal the FTS5 index. nohup + disown so it survives the
# session teardown that triggered us. The miner holds a per-palace lock, so
# simultaneous SessionEnds serialize themselves; a failed (locked-out) mine
# leaves its staged file for the next run to pick up.
(
  nohup bash -c '
    wing="$1"; staging="$2"
    if mempalace mine "$staging" --mode convos --wing "$wing"; then
      find "$staging" -maxdepth 1 -name "*.jsonl" -type f -delete 2>/dev/null || true
    fi

    # FTS5 self-heal: rebuild the inverted index when the mine corrupted it.
    palace_db="$HOME/.mempalace/palace/chroma.sqlite3"
    if command -v sqlite3 >/dev/null 2>&1 && [ -f "$palace_db" ]; then
      if sqlite3 "$palace_db" "PRAGMA quick_check;" 2>/dev/null \
          | grep -q "embedding_fulltext_search"; then
        sqlite3 "$palace_db" \
          "INSERT INTO embedding_fulltext_search(embedding_fulltext_search) VALUES('"'"'rebuild'"'"');" \
          2>/dev/null || true
      fi
    fi
  ' _ "$wing" "$staging" >> "$log" 2>&1 &
  disown 2>/dev/null || true
) 2>/dev/null

exit 0
