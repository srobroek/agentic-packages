#!/usr/bin/env bash
set -euo pipefail

# beads-jsonl-export.sh — PreToolUse:Bash hook (Claude + Codex).
#
# Refresh .beads/issues.jsonl and stage it when the agent is about to commit, so
# bead state travels with the branch as a reviewable text file. This is the
# transport half of the JSONL sync path; beads-jsonl-import.sh is the other half.
#
# WHY THIS EXISTS: `bd dolt push` is the native sync path and stays the default
# (see the SYNC section of beads.context.md). It writes Dolt table files under
# refs/dolt/blobstore/, which some environments block outright -- corporate
# push guards reject the unapproved-remote push, and it needs credentials Dolt
# cannot prompt for. Where that path is unavailable, JSONL over ordinary git
# works: the file is tracked, diffable, and rides whatever push wrapper the repo
# already uses. Opt in per repo with `bd config set custom.jsonl-git-sync true`.
#
# NOT a substitute for `bd dolt push` where that works. Export carries issue
# records only -- no Dolt branches, no commit history, no non-issue tables.
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

# Strip quoted values from a command string, leaving only bare tokens, so a
# `git commit` mentioned inside -m '...' or an echo cannot trigger a stage the
# user never asked for. Copied from beads-gh-issue-guard.sh, which took it from
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
# forms are what dgit and CI actually use, so matching only `-flag` shapes missed
# them. Stopping at the first token that is neither a flag nor a flag value keeps
# `git log --format=%s commit` from counting as a commit.
stripped="$(strip_quoted "$cmd")"
printf '%s' "$stripped" |
  grep -Eq "(^|[[:space:];&|(\`])git([[:space:]]+(-[^[:space:]]*|[^-[:space:]][^[:space:]]*=[^[:space:]]*|[^[:space:]]*/[^[:space:]]*))*[[:space:]]+commit([[:space:]]|$)" ||
  exit 0

command -v bd >/dev/null 2>&1 || exit 0
bd -C "$cwd" where >/dev/null 2>&1 || exit 0

# Opt-in per repo. Absent or false: this hook does nothing, so installing the
# package cannot start committing bead state in a repo that syncs via Dolt.
enabled="$(bd -C "$cwd" config get custom.jsonl-git-sync 2>/dev/null || true)"
case "$enabled" in
  true|1|yes|on) ;;
  *) exit 0 ;;
esac

# Resolve the repo root: .beads/ may sit above $cwd, and git add needs a path
# that exists relative to where we run it.
beads_dir="$(bd -C "$cwd" where 2>/dev/null | head -1 || true)"
[ -n "$beads_dir" ] && [ -d "$beads_dir" ] || exit 0
target="${beads_dir%/}/issues.jsonl"

# --all so memories and infrastructure beads travel too. Write to a temp file
# first: a failed export must not truncate a good committed file.
tmp="${target}.hook-tmp.$$"
if ! BD_NO_PAGER=1 BD_NON_INTERACTIVE=1 bd -C "$cwd" export --all > "$tmp" 2>/dev/null; then
  rm -f "$tmp"
  exit 0
fi
# An empty export means something went wrong; a real workspace has beads.
if [ ! -s "$tmp" ]; then
  rm -f "$tmp"
  exit 0
fi
mv -f "$tmp" "$target"

# Stage it so the agent's own `git commit` picks it up. Never commit here: that
# would create a commit the agent did not ask for.
#
# `git add` on an ignored path exits non-zero without staging, and a stealth
# `bd init` writes `.beads/` into .git/info/exclude -- so the whole sync can look
# healthy while nothing is ever committed. Say so rather than failing silently;
# this is the one case worth a message, because it is unfixable from inside the
# hook and invisible from the outside.
if ! git -C "$cwd" add -- "$target" >/dev/null 2>&1; then
  if command -v jq >/dev/null 2>&1 &&
     git -C "$cwd" check-ignore -q -- "$target" >/dev/null 2>&1; then
    jq -n --arg reason "custom.jsonl-git-sync is on, but $target is git-ignored, so bead state will never be committed. A stealth 'bd init' excludes .beads/ via .git/info/exclude. Un-ignore the file (or drop the pattern) before relying on JSONL sync." '{
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        additionalContext: $reason
      }
    }'
  fi
  exit 0
fi
exit 0
