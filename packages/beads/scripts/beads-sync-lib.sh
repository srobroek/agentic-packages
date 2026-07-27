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
# Dolt network operations against a blocked or unreachable remote do not fail fast.
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

# beads_push_permitted <cwd> <timeout> -> 0 when a push to this repo's git remote
# would be permitted, 1 when a policy guard refuses it.
#
# Asks the guard instead of guessing: `git push --dry-run` runs the same pre-push
# checks as a real push but transfers nothing and mutates no remote, so it is a
# safe probe. The ref is deliberately a name that does not exist -- with
# --dry-run nothing is created either way, and using a real branch could report a
# non-fast-forward that has nothing to do with policy.
#
# Detects the refusal by its message rather than by exit status: a dry-run exits
# non-zero for many ordinary reasons (no upstream, unreachable network, nothing
# to push), so status alone cannot separate "policy says no" from "try later".
#
# Returns 2, not 1, when the probe could not reach a verdict -- an unresolvable
# host, a timeout, no origin. That distinction matters: a refusal is permanent and
# the operator should switch to JSONL, while an unreachable remote is transient
# and retrying later is right. Collapsing them would tell someone to change their
# whole sync strategy because their wifi dropped.
#
# NOTE git resolves the remote host BEFORE running pre-push hooks, so an
# unreachable URL never reaches the guard and cannot produce a verdict either way.
#
# NEVER attempt to work around a refusal. If the guard says no, the JSONL path is
# the sanctioned alternative and the operator can request an exemption.
beads_push_permitted() {
  _cwd="$1"; _to="${2:-30}"
  git -C "$_cwd" rev-parse --git-dir >/dev/null 2>&1 || return 2
  git -C "$_cwd" remote get-url origin >/dev/null 2>&1 || return 2

  _out="$(
    beads_bounded "$_to" git -C "$_cwd" push --dry-run origin \
      "HEAD:refs/heads/beads-sync-policy-probe" 2>&1 || true
  )"
  case "$_out" in
    *"blocked your push"*|*"Code Defender"*|*"unapproved"*|\
    *"not currently on the allow list"*)
      return 1 ;;
    *"Could not resolve host"*|*"unable to access"*|*"Connection refused"*|\
    *"Could not read from remote"*|*"timed out"*|*"terminated"*)
      return 2 ;;
  esac
  return 0
}
