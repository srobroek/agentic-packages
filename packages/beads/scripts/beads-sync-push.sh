#!/usr/bin/env bash
set -euo pipefail

# beads-sync-push.sh — PostToolUse:Bash hook (Claude + Codex).
#
# Publish bead state after the agent commits, so it does not sit unshared on one
# machine. Runs on PostToolUse, not PreToolUse: before the commit there is nothing
# to push, and a hook that pushed pre-commit would publish the previous state and
# leave the new commit behind.
#
# Two independent paths, each gated on what is actually available:
#   1. `bd dolt push` when a Dolt remote exists, custom.dolt-auto-push is on, and
#      a probe confirms a direct push goes through. This is the real sync path.
#   2. Nothing else. The JSONL file rides the agent's own `git push`, so this hook
#      has no second path to run -- beads-sync-stage.sh already put the file in
#      the commit.
#
# WHY AUTO-PUSH IS ACCEPTABLE HERE, when the SYNC rule is otherwise cautious:
# what moves is bead state -- task records, not source. A Dolt push writes only
# `refs/dolt/blobstore/`, touches no branch, and is additive. Still opt-in and
# still bounded.
#
# CHECK BEFORE PUSHING. beads_push_permitted probes with `git push --dry-run`,
# which runs the same pre-push path while transferring nothing. When a host push
# will not go through, this hook uses `custom.bd-push-command` if one is set, and
# otherwise says what the options are.
#
# Self-gating: fail open (exit 0) whenever state cannot be determined.
#
# Portability floor: bash 3.2.57 + BSD grep. No PCRE, no \b.

PUSH_TIMEOUT="${BEADS_SYNC_PUSH_TIMEOUT:-90}"
PROBE_TIMEOUT="${BEADS_SYNC_PROBE_TIMEOUT:-30}"

payload="$(cat 2>/dev/null || true)"
[ -z "$payload" ] && exit 0
command -v jq >/dev/null 2>&1 || exit 0

case "$payload" in
  *"git"*commit*) ;;
  *) exit 0 ;;
esac

cwd=""
cmd=""
{
  IFS= read -r cwd || true
  cmd="$(cat)"
} < <(
  printf '%s' "$payload" | jq -j '
    (.cwd // "") + "\n" +
    (if (.tool_input|type)=="string" then .tool_input
     else (.tool_input.command // "") end)
  ' 2>/dev/null
)
[ -z "$cmd" ] || [ "$cmd" = "null" ] && exit 0
[ -n "$cwd" ] && [ "$cwd" != "null" ] && [ -d "$cwd" ] || cwd="$PWD"

# shellcheck source=beads-sync-lib.sh
. "$(dirname "$0")/beads-sync-lib.sh"

strip_quoted() {
  printf '%s' "$1" | awk '
  { s=$0; n=length(s); out=""; i=1
    while(i<=n){
      c=substr(s,i,1)
      if(c=="\x27"){i++;while(i<=n&&substr(s,i,1)!="\x27"){i++};i++;out=out " ";continue}
      if(c=="\""){i++;while(i<=n){c=substr(s,i,1);if(c=="\""){i++;break}
        if(c=="\\"){i++;if(i<=n)i++;continue};i++};out=out " ";continue}
      out=out c;i++
    }
    print out
  }'
}

stripped="$(strip_quoted "$cmd")"
printf '%s' "$stripped" |
  grep -Eq "(^|[[:space:];&|(\`])git([[:space:]]+(-[^[:space:]]*|[^-[:space:]][^[:space:]]*=[^[:space:]]*|[^[:space:]]*/[^[:space:]]*))*[[:space:]]+commit([[:space:]]|$)" ||
  exit 0

command -v bd >/dev/null 2>&1 || exit 0
bd -C "$cwd" where >/dev/null 2>&1 || exit 0
beads_opt "$cwd" custom.dolt-auto-push || exit 0
beads_has_dolt_remote "$cwd" || exit 0

note=""

# A push needs a Dolt commit to carry. Auto-commit policy may be 'off' or
# 'batch', in which case writes sit in the working set until something commits
# them -- so commit first, and treat "nothing to commit" as fine.
BD_NO_PAGER=1 BD_NON_INTERACTIVE=1 \
  bd -C "$cwd" dolt commit -m "beads: state at $(git -C "$cwd" rev-parse --short HEAD 2>/dev/null || echo commit)" \
  >/dev/null 2>&1 || true

set +e
beads_push_permitted "$cwd" "$PROBE_TIMEOUT"
verdict=$?
set -e

# A host that cannot push directly may still have a wrapper that runs bd somewhere
# with network access (a container, a jump host). Ask for one by name rather than
# hardcoding a tool: custom.bd-push-command names the executable, which must
# accept the same argv as bd.
#
# The indirection is the extension point, and it is load-bearing: a machine-local
# APM package cannot remove or replace a hook entry this package installs -- APM
# merges each package's hooks/hooks.json and records provenance per entry, so a
# local package can only ADD. If this hook hardcoded `bd`, a host that needs a
# wrapper would have no way to redirect it.
runner=""
configured="$(bd -C "$cwd" config get custom.bd-push-command 2>/dev/null || true)"
case "$configured" in
  ""|*"not set"*) : ;;
  *) command -v "$configured" >/dev/null 2>&1 && runner="$configured" ;;
esac

case "$verdict" in
  0)
    # A direct push works, so prefer plain bd even when a wrapper is configured:
    # no reason to pay a wrapper's startup cost when the direct path is available.
    if ! beads_bounded "$PUSH_TIMEOUT" env BD_NO_PAGER=1 BD_NON_INTERACTIVE=1 \
         bd -C "$cwd" dolt push >/dev/null 2>&1; then
      note="bd dolt push did not complete (remote empty, or auth unavailable to Dolt). Bead state is committed locally but not published; run 'bd dolt push' to see the error."
    fi
    ;;
  1)
    # A direct push will not go through. Use the configured wrapper if there is one.
    if [ -n "$runner" ]; then
      if ! beads_bounded "$PUSH_TIMEOUT" env BD_NO_PAGER=1 BD_NON_INTERACTIVE=1 \
           "$runner" dolt push >/dev/null 2>&1; then
        note="a direct push did not go through and '${runner} dolt push' also failed. Bead state is committed locally but not published; run '${runner} dolt push' to see the error."
      fi
    else
      note="'bd dolt push' cannot publish bead state from this host. Set custom.bd-push-command to a wrapper that can reach the remote (bd config set custom.bd-push-command dbd), or use the JSONL path (bd config set custom.jsonl-git-sync true)."
    fi
    ;;
  *)
    # No verdict: unreachable host, timeout, no origin. Transient, so stay quiet
    # rather than telling the operator to change their sync strategy because the
    # network was down. Skipping the push is the safe default -- nothing is lost,
    # the next commit tries again.
    ;;
esac

[ -n "$note" ] || exit 0
jq -n --arg ctx "beads sync: ${note}" '{
  hookSpecificOutput: {
    hookEventName: "PostToolUse",
    additionalContext: $ctx
  }
}'
exit 0
