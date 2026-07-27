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
#      the repo's push policy permits it. This is the real sync path.
#   2. Nothing else. The JSONL file rides the agent's own `git push`, so this hook
#      has no second path to run -- beads-sync-stage.sh already put the file in
#      the commit.
#
# WHY AUTO-PUSH IS ACCEPTABLE HERE, when the SYNC rule guards it: what moves is
# bead state -- task records, not source. The rule exists so an agent does not
# publish code or force a remote's history sideways. A Dolt push writes only
# `refs/dolt/blobstore/`, touches no branch, and is additive. Still opt-in, still
# bounded, and still refuses to fight a policy guard.
#
# ASK THE GUARD, DO NOT GUESS OR CIRCUMVENT. beads_push_permitted probes with
# `git push --dry-run`, which runs the same pre-push checks while transferring
# nothing. On refusal this hook stops and says so; working around a corporate
# push guard is never the hook's business. Where push is refused, JSONL over
# ordinary git is the sanctioned route.
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

case "$verdict" in
  0)
    if ! beads_bounded "$PUSH_TIMEOUT" env BD_NO_PAGER=1 BD_NON_INTERACTIVE=1 \
         bd -C "$cwd" dolt push >/dev/null 2>&1; then
      # Report rather than swallow: a silently failed push leaves bead state on
      # one machine while everyone believes it is shared.
      note="bd dolt push did not complete although policy permits it (remote empty, or auth unavailable to Dolt). Bead state is committed locally but not published; run 'bd dolt push' to see the error."
    fi
    ;;
  1)
    # A policy guard refused. Say so once, name the sanctioned alternative, and
    # stop -- do not retry, and never attempt to work around the guard.
    note="a push policy guard refuses pushes to this remote, so 'bd dolt push' cannot publish bead state. Use the JSONL path instead (bd config set custom.jsonl-git-sync true) or request an exemption for this repo."
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
