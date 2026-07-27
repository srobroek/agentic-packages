#!/usr/bin/env bash
set -euo pipefail

# beads-sync-stage.sh — PreToolUse:Bash hook (Claude + Codex).
#
# Keep .beads/issues.jsonl current and staged when the agent commits, so bead
# state travels with the branch in repos that cannot use Dolt sync. The commit
# half of the pair; beads-sync-hydrate.sh handles session start.
#
# WHY THIS EXISTS AT ALL -- bd already has most of it natively:
#   `bd config set export.auto true` exports after every write command, throttled
#   by export.interval. Prefer that; this hook does not duplicate it.
# Two gaps keep the hook necessary:
#   1. `export.git-add: true` does not stage the file (verified: the export lands
#      and shows as modified in git status, but never enters the index), so the
#      commit would not carry it.
#   2. Auto-export is throttled, so the file can lag the database by up to
#      export.interval at the moment of commit.
# This hook closes both: refresh, then stage. It never commits -- the agent's own
# commit carries the file.
#
# NATIVE SYNC WINS. When a Dolt remote is configured and reachable, `bd dolt
# push` is the sync path and JSONL is redundant: it carries issue rows only, not
# Dolt branches or history. So this stays off unless the repo opts in with
# custom.jsonl-git-sync, which is how a repo declares Dolt sync unavailable.
#
# Self-gating: matcher is Bash with no `if` filter. Fail open (exit 0) whenever
# state cannot be determined: no jq, no bd, no beads workspace, opt-in unset.
#
# Portability floor: bash 3.2.57 + BSD grep. No PCRE, no \b.

payload="$(cat 2>/dev/null || true)"
[ -z "$payload" ] && exit 0
command -v jq >/dev/null 2>&1 || exit 0

# Cheap pre-jq bail: only `git commit` is of interest.
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

# Strip quoted values, leaving only bare tokens, so a `git commit` mentioned
# inside -m '...' or an echo cannot trigger a stage nobody asked for. Copied from
# beads-gh-issue-guard.sh, which took it from
# packages/hooks-precommit-gate/scripts/precommit-gate.sh (its issues #4/#5 fix).
# Handles single-quoted (no escapes) and double-quoted (backslash escapes).
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

# Match a real `git commit` in the QUOTE-STRIPPED command. Anchor on a non-word
# class rather than strict command position, so command substitution, subshells,
# and wrapper prefixes (`time git ...`, `env FOO=1 git ...`) still match.
#
# The middle group swallows git's global options INCLUDING their separate values
# (`git -c k=v commit`, `git -C path commit`, `git --no-pager commit`) -- those
# are the forms dgit and CI actually use, so matching only `-flag` shapes missed
# them entirely. Stopping at the first token that is neither a flag nor a flag
# value keeps `git log --format=%s commit` from counting as a commit.
stripped="$(strip_quoted "$cmd")"
printf '%s' "$stripped" |
  grep -Eq "(^|[[:space:];&|(\`])git([[:space:]]+(-[^[:space:]]*|[^-[:space:]][^[:space:]]*=[^[:space:]]*|[^[:space:]]*/[^[:space:]]*))*[[:space:]]+commit([[:space:]]|$)" ||
  exit 0

command -v bd >/dev/null 2>&1 || exit 0
bd -C "$cwd" where >/dev/null 2>&1 || exit 0

# Opt-in per repo: this is how a repo declares that Dolt sync is unavailable to
# it. Absent, the hook does nothing, so installing the package cannot start
# committing bead state in a repo that syncs natively.
case "$(bd -C "$cwd" config get custom.jsonl-git-sync 2>/dev/null || true)" in
  true|1|yes|on) ;;
  *) exit 0 ;;
esac

beads_dir="$(bd -C "$cwd" where 2>/dev/null | head -1 || true)"
[ -n "$beads_dir" ] && [ -d "$beads_dir" ] || exit 0
target="${beads_dir%/}/issues.jsonl"

# --all so memories and infrastructure beads travel too. Write to a temp file
# first: a failed export must not truncate a good committed file.
tmp="${target}.hook-tmp.$$"
if ! BD_NO_PAGER=1 BD_NON_INTERACTIVE=1 \
     bd -C "$cwd" export --all > "$tmp" 2>/dev/null; then
  rm -f "$tmp"
  exit 0
fi
# An empty export means something went wrong; a real workspace has beads.
if [ ! -s "$tmp" ]; then
  rm -f "$tmp"
  exit 0
fi
# Skip the write when nothing changed, so an unrelated commit does not carry a
# spurious one-line diff. bd's export is deterministic, so equal bytes mean
# equal state.
if cmp -s "$tmp" "$target" 2>/dev/null; then
  rm -f "$tmp"
  exit 0
fi
mv -f "$tmp" "$target"

# Stage it so the agent's own `git commit` picks it up. Never commit here: that
# would create a commit the agent did not ask for.
#
# `git add` on an ignored path exits non-zero WITHOUT staging, and a stealth
# `bd init` writes `.beads/` into .git/info/exclude -- so the whole sync can look
# healthy while nothing is ever committed. Say so rather than failing silently:
# it is unfixable from inside the hook and invisible from the outside.
if ! git -C "$cwd" add -- "$target" >/dev/null 2>&1; then
  if git -C "$cwd" check-ignore -q -- "$target" >/dev/null 2>&1; then
    jq -n --arg reason "custom.jsonl-git-sync is on, but $target is git-ignored, so bead state will never be committed. A stealth 'bd init' excludes .beads/ via .git/info/exclude. Un-ignore the file (or drop that pattern) before relying on JSONL sync." '{
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        additionalContext: $reason
      }
    }'
  fi
  exit 0
fi
exit 0
