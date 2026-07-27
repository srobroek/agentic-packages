#!/usr/bin/env bash
set -euo pipefail

# beads-sync-push.sh — SessionEnd hook (Claude + Codex).
#
# Publish bead state once, at the end of a session, so it does not sit unshared on
# one machine.
#
# WHY SESSIONEND AND NOT PER-COMMIT: an incremental push costs ~12s, of which ~8s
# is process/container startup rather than data transfer (measured against a
# 311 MB, 4354-commit database: 12.2s incremental, 8.1s for a no-op invocation).
# That cost is fixed per invocation, so pushing after every commit made a
# ten-commit session pay two minutes for what one push covers. Dolt pushes are
# additive and idempotent, so a single push at the end loses nothing.
#
# WHY DETACHED: even 12s of session teardown is time the user waits on a network
# round trip they do not care about, and the FIRST push of a database that has
# never synced uploads its whole history -- measured at over 550s on that same
# repo. Blocking a session on that is indefensible, so this starts the push and
# returns immediately.
#
# HOW FAILURES STAY VISIBLE: a detached process cannot report to the session that
# spawned it, and a silently failing push is the worst outcome here -- bead state
# would look shared while sitting on one machine. So the push writes its outcome to
# .beads/last-push.log and beads-sync-hydrate.sh reports a failure it finds there
# at the next session start. Nothing blocks, nothing is lost.
#
# Self-gating: fail open (exit 0) whenever state cannot be determined.
#
# Portability floor: bash 3.2.57 + BSD userland. No PCRE, no \b.

# Bound on the detached push. Generous because a first push uploads accumulated
# history: 90s was too low in practice and reported "did not complete" on a push
# that was simply still running.
PUSH_TIMEOUT="${BEADS_SYNC_PUSH_TIMEOUT:-600}"
PROBE_TIMEOUT="${BEADS_SYNC_PROBE_TIMEOUT:-30}"

cwd="$PWD"
payload="$(cat 2>/dev/null || true)"
if [ -n "$payload" ] && command -v jq >/dev/null 2>&1; then
  parsed="$(printf '%s' "$payload" | jq -r '.cwd // empty' 2>/dev/null || true)"
  [ -n "$parsed" ] && [ -d "$parsed" ] && cwd="$parsed"
fi

command -v bd >/dev/null 2>&1 || exit 0
bd -C "$cwd" where >/dev/null 2>&1 || exit 0

# shellcheck source=beads-sync-lib.sh
. "$(dirname "$0")/beads-sync-lib.sh"

beads_opt "$cwd" custom.dolt-auto-push || exit 0
beads_has_dolt_remote "$cwd" || exit 0

beads_dir="$(bd -C "$cwd" where 2>/dev/null | head -1 || true)"
[ -n "$beads_dir" ] && [ -d "$beads_dir" ] || exit 0
log="${beads_dir%/}/last-push.log"

# A push needs a Dolt commit to carry. Auto-commit policy may be 'off' or 'batch',
# in which case writes sit in the working set until something commits them -- so
# commit first, and treat "nothing to commit" as fine. Cheap and local, so it stays
# in the foreground where a failure is still visible.
BD_NO_PAGER=1 BD_NON_INTERACTIVE=1 \
  bd -C "$cwd" dolt commit -m "beads: session state" >/dev/null 2>&1 || true

# A host that cannot push directly may still have a wrapper that runs bd somewhere
# with network access. Ask for one by name rather than hardcoding a tool:
# custom.bd-push-command names an executable that must accept bd's argv.
#
# The indirection is load-bearing: APM merges each package's hooks/hooks.json and
# records provenance per entry, so a machine-local package can ADD hooks but never
# remove or replace this one. Hardcoding `bd` would leave a host that needs a
# wrapper no way to redirect it.
runner="bd"
configured="$(bd -C "$cwd" config get custom.bd-push-command 2>/dev/null || true)"
case "$configured" in
  ""|*"not set"*) : ;;
  *) command -v "$configured" >/dev/null 2>&1 && runner="$configured" ;;
esac

# Probe policy in the FOREGROUND: it is bounded and cheap, and its verdict decides
# whether a detached push is worth starting at all. Spawning a background push that
# will be refused, just to log the refusal for the next session, is worse than
# recording it now.
set +e
beads_push_permitted "$cwd" "$PROBE_TIMEOUT"
verdict=$?
set -e

case "$verdict" in
  0) : ;;
  1)
    # A direct push will not go through. With no wrapper configured there is
    # nothing to detach, so record why and stop.
    if [ "$runner" = "bd" ]; then
      printf 'failed: a direct push does not go through from this host, and custom.bd-push-command is not set. Set it to a wrapper that can reach the remote, or use the JSONL path.\n' \
        > "$log" 2>/dev/null || true
      exit 0
    fi
    ;;
  *)
    # No verdict: unreachable, timed out, or no origin. Transient -- skip quietly
    # and let the next session try. State is committed locally, so nothing is lost.
    exit 0
    ;;
esac

# Detach. setsid where available so the push outlives the session's process group;
# nohup otherwise. The inner script appends its own verdict line, so the log always
# ends in something the hydrate hook can classify.
detach() {
  if command -v setsid >/dev/null 2>&1; then
    setsid "$@" >/dev/null 2>&1 &
  else
    nohup "$@" >/dev/null 2>&1 &
  fi
}

printf 'started: %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || echo unknown)" \
  > "$log" 2>/dev/null || true

detach /bin/sh -c '
  log="$1"; runner="$2"; cwd="$3"; to="$4"
  if command -v timeout >/dev/null 2>&1; then bound="timeout $to"
  elif command -v gtimeout >/dev/null 2>&1; then bound="gtimeout $to"
  else bound=""
  fi
  if BD_NO_PAGER=1 BD_NON_INTERACTIVE=1 $bound "$runner" -C "$cwd" dolt push >>"$log" 2>&1; then
    printf "ok: push complete\n" >> "$log"
  else
    printf "failed: %s dolt push exited non-zero (output above)\n" "$runner" >> "$log"
  fi
' _ "$log" "$runner" "$cwd" "$PUSH_TIMEOUT"

exit 0
