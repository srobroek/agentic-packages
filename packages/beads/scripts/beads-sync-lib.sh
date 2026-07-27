#!/usr/bin/env bash
# beads-sync-lib.sh — shared helpers for the beads sync hooks. Sourced, not run.
#
# Portability floor: bash 3.2.57 + BSD userland. No PCRE, no \b.

# beads_opt <cwd> <config-key> -> 0 when the key is truthy
beads_opt() {
  case "$(bd -C "$1" config get "$2" 2>/dev/null || true)" in
    true|1|yes|on) return 0 ;;
    *) return 1 ;;
  esac
}

# beads_bounded <seconds> <cmd...> -> run with a wall-clock bound where possible.
# `timeout` is GNU; macOS ships it only via coreutils (as gtimeout). Degrade to
# running bare rather than skipping the work, but use a bound wherever one exists:
# Dolt network operations do not always fail fast.
beads_bounded() {
  _bt="$1"; shift
  if command -v timeout >/dev/null 2>&1; then
    timeout "$_bt" "$@"
  elif command -v gtimeout >/dev/null 2>&1; then
    gtimeout "$_bt" "$@"
  else
    "$@"
  fi
}

# beads_has_dolt_remote <cwd> -> 0 when a Dolt remote is configured
beads_has_dolt_remote() {
  case "$(bd -C "$1" dolt remote list 2>/dev/null || true)" in
    ""|*"No remotes configured"*) return 1 ;;
    *) return 0 ;;
  esac
}

# beads_push_permitted <cwd> <timeout>
#   0 = a push from here would go through
#   1 = something rejected it at pre-push time
#   2 = no answer (unreachable, timed out, no origin)
#
# Probes with `git push --dry-run`, which runs the same pre-push path as a real
# push while transferring nothing and mutating no remote.
#
# Reads the outcome from the message, not the exit status: a dry-run exits
# non-zero for many ordinary reasons (no upstream, unreachable network, nothing
# to push), so status alone cannot tell a rejection from "try later".
#
# The 1/2 split matters. A rejection is durable and calls for a different route;
# an unreachable remote is transient and calls for retrying. Collapsing them would
# advise changing a sync strategy over a dropped connection.
#
# NOTE git resolves the remote host BEFORE running pre-push hooks, so an
# unreachable URL yields no answer either way.
beads_push_permitted() {
  _cwd="$1"; _to="${2:-30}"
  git -C "$_cwd" rev-parse --git-dir >/dev/null 2>&1 || return 2
  git -C "$_cwd" remote get-url origin >/dev/null 2>&1 || return 2

  _out="$(
    beads_bounded "$_to" git -C "$_cwd" push --dry-run origin \
      "HEAD:refs/heads/beads-sync-probe" 2>&1 || true
  )"
  case "$_out" in
    *"Could not resolve host"*|*"unable to access"*|*"Connection refused"*|\
    *"Could not read from remote"*|*"timed out"*|*"terminated"*)
      return 2 ;;
    *"pre-push hook declined"*|*"blocked your push"*|*"not currently on the allow list"*)
      return 1 ;;
  esac
  return 0
}
