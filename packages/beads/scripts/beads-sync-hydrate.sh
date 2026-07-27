#!/usr/bin/env bash
set -euo pipefail

# beads-sync-hydrate.sh — SessionStart hook (Claude + Codex).
#
# Bring the local beads database up to date before an agent touches beads,
# preferring bd's native Dolt sync and falling back to JSONL only when that is
# unavailable. Paired with beads-sync-stage.sh, which handles the commit side.
#
# ORDER OF PREFERENCE -- native first, always:
#   1. `bd dolt pull` when a Dolt remote exists and custom.dolt-auto-pull is on.
#      This is the real sync path: it moves Dolt commits, not merely issue rows.
#   2. `bd import` of .beads/issues.jsonl, and only when that file differs from
#      what this database would export. Identical content means the file has
#      nothing to give, so importing would be wasted work at every session start.
# A successful pull does not skip step 2: a peer without push access may have
# committed JSONL the Dolt remote has never seen, so the file can still be ahead.
#
# This hook only receives. Publishing is beads-sync-push.sh, which runs after the
# agent's commit -- at session start there is nothing new to send.
#
# Self-gating: fail open (exit 0) whenever state cannot be determined. A sync
# hook must never be the reason a session cannot start.
#
# Portability floor: bash 3.2.57 + BSD userland. No PCRE, no \b.

# Longest a session start may wait on the network: `bd dolt pull` against an
# unreachable remote does not always fail fast.
PULL_TIMEOUT="${BEADS_SYNC_PULL_TIMEOUT:-60}"

cwd="$PWD"
payload="$(cat 2>/dev/null || true)"
if [ -n "$payload" ] && command -v jq >/dev/null 2>&1; then
  parsed="$(printf '%s' "$payload" | jq -r '.cwd // empty' 2>/dev/null || true)"
  [ -n "$parsed" ] && [ -d "$parsed" ] && cwd="$parsed"
fi

command -v bd >/dev/null 2>&1 || exit 0
command -v jq >/dev/null 2>&1 || exit 0
bd -C "$cwd" where >/dev/null 2>&1 || exit 0

beads_dir="$(bd -C "$cwd" where 2>/dev/null | head -1 || true)"
[ -n "$beads_dir" ] && [ -d "$beads_dir" ] || exit 0

# shellcheck source=beads-sync-lib.sh
. "$(dirname "$0")/beads-sync-lib.sh"

notes=""
add_note() { if [ -z "$notes" ]; then notes="$1"; else notes="$notes $1"; fi; }

# --- 1. native Dolt pull ----------------------------------------------------

if beads_has_dolt_remote "$cwd" && beads_opt "$cwd" custom.dolt-auto-pull; then
  if ! beads_bounded "$PULL_TIMEOUT" env BD_NO_PAGER=1 BD_NON_INTERACTIVE=1 \
       bd -C "$cwd" dolt pull >/dev/null 2>&1; then
    # Non-fatal: the remote may be empty (nothing pushed yet) or unreachable.
    # The JSONL step below is the fallback for exactly these.
    add_note "bd dolt pull did not complete (remote empty, unreachable, or blocked); using JSONL if present."
  fi
fi

# --- 2. JSONL fallback, only when the file actually differs -------------------

source_file="${beads_dir%/}/issues.jsonl"
if beads_opt "$cwd" custom.jsonl-git-sync && [ -s "$source_file" ]; then
  # Compare against a fresh export instead of timestamps. bd exposes no
  # database-wide commit time (`bd history` needs an issue id; `bd vc status`
  # gives a hash with no date), and file mtime is unreliable after a checkout --
  # git sets it to clone time regardless of content age. Byte comparison is exact
  # and cheap, and bd's export is deterministic, so identical output means
  # identical state.
  probe="${source_file}.hydrate-probe.$$"
  differs=1
  if BD_NO_PAGER=1 BD_NON_INTERACTIVE=1 \
       bd -C "$cwd" export --all > "$probe" 2>/dev/null && [ -s "$probe" ]; then
    cmp -s "$probe" "$source_file" && differs=0
  fi
  rm -f "$probe"

  if [ "$differs" = 1 ]; then
    # The union merge driver leaves duplicate ids in the file on concurrent
    # edits; that is deliberate. Git moves bytes, the importer decides which row
    # wins by updated_at.
    out="$(
      BD_JSON_ENVELOPE=1 BD_NO_PAGER=1 BD_NON_INTERACTIVE=1 \
        bd -C "$cwd" import --json "$source_file" 2>/dev/null || true
    )"
    if [ -n "$out" ]; then
      stale="$(
        printf '%s' "$out" |
          jq -r '((.data // {}).stale_skipped_ids // [])
                 | if length == 0 then empty else join(", ") end' 2>/dev/null || true
      )"
      # Report a stale skip only. Routine hydration is not worth a line in every
      # session: `created` counts rows processed, not rows changed. A stale skip
      # is different -- the committed file is BEHIND this database, so the next
      # export overwrites whatever a peer committed.
      if [ -n "$stale" ]; then
        add_note "issues.jsonl is BEHIND this database (stale rows: ${stale}); local state kept. Commit a fresh export before pulling peer changes."
      fi
    fi
  fi
fi

[ -n "$notes" ] || exit 0
jq -n --arg ctx "beads sync: ${notes}" '{
  hookSpecificOutput: {
    hookEventName: "SessionStart",
    additionalContext: $ctx
  }
}'
exit 0
