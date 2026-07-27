#!/usr/bin/env bash
set -euo pipefail

# beads-maintenance-check.sh — SessionStart hook (Claude + Codex).
#
# Report when the beads database has grown enough to be worth trimming. REPORTS
# ONLY: every command it names is destructive and irreversible, so the decision
# stays with the operator.
#
# WHY REPORTING RATHER THAN DOING: `bd prune` deletes closed beads, `bd purge`
# deletes closed wisps, and `bd flatten` discards ALL Dolt commit history. None is
# recoverable. A hook that ran them on a threshold would eventually delete work
# somebody still wanted, and the failure would be silent and permanent. A hook
# that mentions them once per session costs a line of text.
#
# WHAT ACTUALLY GROWS -- measured on a real repo, 207 open beads at 311 MB:
#     bd export --all payload      2.8 MB
#     .dolt/noms/                  199 MB   every historical row version
#     .dolt/git-remote-cache/       96 MB   local mirror of the remote
# The beads were 1% of it. 4354 Dolt commits were the other 99%, because each
# create/update/comment/close writes one and nothing is collected by default.
#
# So COMMIT COUNT is the signal, not bead count. On that same repo `bd prune
# --older-than 90d` matched nothing at all (every closed bead was recent) while
# 4354 commits sat underneath -- a prune-based threshold would have stayed silent
# through the entire problem.
#
# Self-gating: fail open (exit 0) whenever state cannot be determined. Never let a
# maintenance notice stop a session from starting.
#
# Portability floor: bash 3.2.57 + BSD userland. No PCRE, no \b.

# Commit count that warrants mentioning. Deliberately high: this fires once per
# session and a false alarm trains people to ignore it.
THRESHOLD="${BEADS_MAINTENANCE_COMMIT_THRESHOLD:-2000}"

cwd="$PWD"
payload="$(cat 2>/dev/null || true)"
if [ -n "$payload" ] && command -v jq >/dev/null 2>&1; then
  parsed="$(printf '%s' "$payload" | jq -r '.cwd // empty' 2>/dev/null || true)"
  [ -n "$parsed" ] && [ -d "$parsed" ] && cwd="$parsed"
fi

command -v bd >/dev/null 2>&1 || exit 0
command -v jq >/dev/null 2>&1 || exit 0
bd -C "$cwd" where >/dev/null 2>&1 || exit 0

# Opt-in, like the sync hooks: a repo that does not want maintenance nagging says
# nothing and gets nothing.
case "$(bd -C "$cwd" config get custom.maintenance-check 2>/dev/null || true)" in
  true|1|yes|on) ;;
  *) exit 0 ;;
esac

# `bd flatten --dry-run --json` reports commit_count and changes nothing. It is
# the only machine-readable size signal bd exposes: `bd status --json` returns an
# empty summary, and `bd vc status` gives a hash with no counts.
commits="$(
  BD_JSON_ENVELOPE=1 BD_NO_PAGER=1 BD_NON_INTERACTIVE=1 \
    bd -C "$cwd" flatten --dry-run --json 2>/dev/null |
    jq -r '(.data // .) | .commit_count // empty' 2>/dev/null || true
)"
case "$commits" in
  ''|*[!0-9]*) exit 0 ;;
esac
[ "$commits" -ge "$THRESHOLD" ] || exit 0

# Count what is actually reclaimable, so the notice names real numbers rather than
# sending someone to read three --help pages. Both are dry runs.
#
# Field names verified against live output, not guessed: prune reports
# `prune_count` and purge reports `purged_count`. Reading a wrong key would have
# silently reported 0 reclaimable and made the notice useless.
prunable="$(
  BD_JSON_ENVELOPE=1 BD_NO_PAGER=1 BD_NON_INTERACTIVE=1 \
    bd -C "$cwd" prune --older-than 90d --dry-run --json 2>/dev/null |
    jq -r '(.data // .) | .prune_count // empty' 2>/dev/null || true
)"
case "$prunable" in ''|*[!0-9]*) prunable=0 ;; esac

purgeable="$(
  BD_JSON_ENVELOPE=1 BD_NO_PAGER=1 BD_NON_INTERACTIVE=1 \
    bd -C "$cwd" purge --older-than 30d --dry-run --json 2>/dev/null |
    jq -r '(.data // .) | .purged_count // empty' 2>/dev/null || true
)"
case "$purgeable" in ''|*[!0-9]*) purgeable=0 ;; esac

msg="beads maintenance: ${commits} Dolt commits (threshold ${THRESHOLD})."
if [ "$purgeable" -gt 0 ]; then
  msg="${msg} ${purgeable} closed wisp(s) older than 30d -- 'bd purge --older-than 30d --force' is the safe first step; wisps have no value once closed."
fi
if [ "$prunable" -gt 0 ]; then
  msg="${msg} ${prunable} closed bead(s) older than 90d could go with 'bd prune --older-than 90d --force'."
fi
msg="${msg} Deleting rows does NOT shrink storage on its own -- commit history is the bulk, and only 'bd flatten --force' reclaims it, which discards ALL history irreversibly. Review with --dry-run first; none of this is automatic."

jq -n --arg ctx "$msg" '{
  hookSpecificOutput: {
    hookEventName: "SessionStart",
    additionalContext: $ctx
  }
}'
exit 0
