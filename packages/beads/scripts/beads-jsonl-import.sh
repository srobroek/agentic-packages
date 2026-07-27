#!/usr/bin/env bash
set -euo pipefail

# beads-jsonl-import.sh — SessionStart hook (Claude + Codex).
#
# Hydrate the local beads database from .beads/issues.jsonl before an agent
# touches beads, so a session that starts after `git pull` sees the state its
# peers committed. The receiving half of the JSONL sync path;
# beads-jsonl-export.sh writes and stages the file.
#
# WHY THIS IS SAFE -- bd's importer is upsert-only with a staleness guard, all
# verified against a live database rather than read off the docs:
#   - A row rewrites a local issue only when its updated_at is strictly newer.
#     Older rows are skipped and reported (stale_skipped_ids), so pulling an old
#     file cannot revert newer local work.
#   - Equal timestamps keep every local column (updated_at has second
#     granularity, so a tie can be two distinct same-second edits).
#   - Comments, labels, and dependencies MERGE rather than replace, so two
#     agents commenting on one bead both survive.
#   - Local issues absent from the file are left alone. Import never deletes.
# Restoring an older snapshot needs an explicit --allow-stale, which this hook
# never passes.
#
# Self-gating: fail open (exit 0) whenever state cannot be determined -- no bd,
# no beads workspace, no file, opt-in unset. A sync hook must never be the
# reason a session cannot start.
#
# Portability floor: bash 3.2.57 + BSD grep. No PCRE, no \b.

cwd="$PWD"
payload="$(cat 2>/dev/null || true)"
if [ -n "$payload" ] && command -v jq >/dev/null 2>&1; then
  parsed="$(printf '%s' "$payload" | jq -r '.cwd // empty' 2>/dev/null || true)"
  [ -n "$parsed" ] && [ -d "$parsed" ] && cwd="$parsed"
fi

command -v bd >/dev/null 2>&1 || exit 0
bd -C "$cwd" where >/dev/null 2>&1 || exit 0

# Same opt-in as the export half: absent means this repo syncs some other way.
enabled="$(bd -C "$cwd" config get custom.jsonl-git-sync 2>/dev/null || true)"
case "$enabled" in
  true|1|yes|on) ;;
  *) exit 0 ;;
esac

beads_dir="$(bd -C "$cwd" where 2>/dev/null | head -1 || true)"
[ -n "$beads_dir" ] && [ -d "$beads_dir" ] || exit 0
source_file="${beads_dir%/}/issues.jsonl"
[ -s "$source_file" ] || exit 0

# The union merge driver (see the repo's .gitattributes) resolves concurrent
# edits by keeping BOTH rows for a bead, leaving a file with duplicate ids. That
# is deliberate: git handles transport, and the importer below resolves which
# row wins by updated_at. So a duplicate id here is expected, not corruption.
# BD_JSON_ENVELOPE per the JSON DETERMINISM rule: read .data, not prose. The
# human output is not usable for gating -- it reports "Imported N issues" even
# when every row was already present and nothing changed.
out="$(
  BD_JSON_ENVELOPE=1 BD_NO_PAGER=1 BD_NON_INTERACTIVE=1 \
    bd -C "$cwd" import --json "$source_file" 2>/dev/null || true
)"
[ -n "$out" ] || exit 0
command -v jq >/dev/null 2>&1 || exit 0

# Report ONLY a stale skip. Routine hydration is not worth a line in every
# session: `created` counts rows processed, not rows changed, so it reads "1 row
# applied" even when the file exactly matches the database -- gating on it would
# annotate every single session start with a no-op.
#
# A stale skip is different: it means the committed file is BEHIND this database,
# so the next export will overwrite what a peer committed. That is a real
# divergence and the one thing the agent has to know about.
summary="$(
  printf '%s' "$out" | jq -r '
    ((.data // {}).stale_skipped_ids // []) as $s
    | if ($s | length) == 0 then empty
      else "beads: .beads/issues.jsonl is BEHIND this database -- \($s | length) row(s) "
           + "skipped as stale (\($s | join(", "))). Local state was kept. Commit a fresh "
           + "export before pulling peer changes, or those rows will be overwritten."
      end
  ' 2>/dev/null || true
)"
[ -n "$summary" ] || exit 0

jq -n --arg ctx "$summary" '{
  hookSpecificOutput: {
    hookEventName: "SessionStart",
    additionalContext: $ctx
  }
}'
exit 0
