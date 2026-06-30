#!/usr/bin/env bash
set -euo pipefail

# precommit-gate.sh — PreToolUse:Bash hook (Claude + Codex).
#
# Ensures the `pre-commit` FRAMEWORK actually runs when a repo opts into it. A
# committed .pre-commit-config.yaml is useless if the contributor never ran
# `pre-commit install` (git does not auto-wire .git/hooks on clone), or if the
# command uses --no-verify (which skips the hooks). This guard closes both gaps
# for our agent.
#
# Decision model (Claude-native PreToolUse contract; Codex honors non-zero too):
#   - warn (exit 0 + additionalContext JSON) when the repo HAS a
#     .pre-commit-config.yaml AND either (a) the relevant git hook is not
#     installed, or (b) the command passes --no-verify / -n.
#   - allow (exit 0) otherwise. Crucially, SILENT in any repo without a
#     .pre-commit-config.yaml, so it adds no friction to ad-hoc/other repos.
#
# This is Tier-D hygiene enforcement, NOT a security control: whenever we
# cannot determine state (no jq, not a git repo, redirected git dir), we FAIL
# OPEN (allow). The real secret enforcement is the pre-push hook itself.
#
# Portability floor: bash 3.2.57 + BSD grep. No PCRE, no \b.

payload="$(cat 2>/dev/null || true)"
[ -z "$payload" ] && exit 0

# No jq -> cannot parse safely -> fail open.
command -v jq >/dev/null 2>&1 || exit 0

# tool_input may be an object {command:"..."} OR a bare string. The naive
# '.tool_input.command // .tool_input' THROWS on a string and bypasses the hook;
# type-check first so both shapes are read.
cmd="$(
  printf '%s' "$payload" | jq -r '
    if (.tool_input|type)=="string" then .tool_input
    else (.tool_input.command // empty) end
  ' 2>/dev/null || true
)"
[ -z "$cmd" ] || [ "$cmd" = "null" ] && exit 0

# Working dir the command runs in (Claude + Codex send .cwd); fall back to $PWD.
cwd="$(printf '%s' "$payload" | jq -r '.cwd // empty' 2>/dev/null || true)"
[ -n "$cwd" ] && [ "$cwd" != "null" ] && [ -d "$cwd" ] || cwd="$PWD"

# Which git operation is this? Anchored to command position (start, or after a
# real ; & | separator) so a `git commit` mentioned inside a quoted argument of
# some other command does not trip the gate. Detect commit vs push.
is_commit=0
is_push=0
if printf '%s' "$cmd" | grep -Eq '(^|[;&|][[:space:]]*)git([[:space:]][^;&|]*)?[[:space:]]+commit($|[[:space:]])'; then
  is_commit=1
fi
if printf '%s' "$cmd" | grep -Eq '(^|[;&|][[:space:]]*)git([[:space:]][^;&|]*)?[[:space:]]+push($|[[:space:]])'; then
  is_push=1
fi
[ "$is_commit" -eq 1 ] || [ "$is_push" -eq 1 ] || exit 0

# Strip quoted values from a command string, leaving only bare tokens.
# Quoted content is replaced by a single space so token boundaries are
# preserved. This prevents flag-like text inside -m 'message' from being
# mistaken for real flags (issues #4, #5).
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

# Extract the git commit/push segment from the command string. Scoped to the
# git invocation only (up to the next shell separator) so flags in subsequent
# commands (rg -n, sort -n, head -n) don't contaminate the flag checks.
git_seg="$(printf '%s' "$cmd" | grep -Eo '(^|[;&|][[:space:]]*)git[[:space:]][^;&|]*' | grep -E '[[:space:]](commit|push)([[:space:]]|$)' | head -n 1)"
# Fail open: if extraction fails, fall back to the whole command string.
[ -n "$git_seg" ] || git_seg="$cmd"

# Produce a quote-stripped version of the git segment for flag scanning.
# Text inside -m 'message' (e.g. '-C', '--no-verify', '-n') must not be
# mistaken for real flags (issues #4, #5).
git_seg_stripped="$(strip_quoted "$git_seg")"

# If git is redirected to another repo (-C / --git-dir / --work-tree), $cwd is
# not the repo being acted on; we cannot reliably check its hooks -> fail open.
# Scoped to the stripped segment so a commit message containing ' -C '
# does not falsely trigger fail-open (issue #4).
case " $git_seg_stripped " in *" -C "*) exit 0 ;; esac
if printf '%s' "$git_seg_stripped" | grep -Eq '(^|[[:space:]])(--git-dir|--work-tree)([[:space:]=])'; then
  exit 0
fi

# Resolve the repo. Not a git work tree -> nothing to gate -> allow.
root="$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null || true)"
[ -n "$root" ] || exit 0

# No pre-commit config in this repo -> the repo has not opted in -> stay SILENT.
config=""
for f in .pre-commit-config.yaml .pre-commit-config.yml; do
  if [ -f "$root/$f" ]; then config="$f"; break; fi
done
[ -n "$config" ] || exit 0

# Accumulate advisory notes; emit a single JSON object at the end.
notes=""
note() { if [ -n "$notes" ]; then notes="$notes"$'\n'"- $1"; else notes="- $1"; fi; }

# (a) --no-verify / -n skips the framework entirely. Warn so the configured
#     hooks are not silently bypassed. -n is git commit's short form for it;
#     match a standalone -n token (not bundled, to avoid e.g. a future -no).
#     Scoped to the STRIPPED segment so '-n' or '--no-verify' appearing only
#     inside a quoted commit message is not mistaken for the real flag (issue #5).
#     When --no-verify is used the hook-installed check is moot (hooks are
#     bypassed regardless) so we skip it and emit one advisory only.
noverify=0
if printf '%s' "$git_seg_stripped" | grep -Eq '(^|[[:space:]])--no-verify([[:space:]]|$)' \
  || printf '%s' "$git_seg_stripped" | grep -Eq '(^|[[:space:]])-n([[:space:]]|$)'; then
  noverify=1
  note "this git command uses --no-verify, which skips the configured pre-commit hooks for this commit"
fi

if [ "$noverify" -eq 0 ]; then
  # (b) The relevant git hook must be installed. Resolve the hooks dir (honor a
  #     custom core.hooksPath; default <gitdir>/hooks). A pre-commit-managed hook
  #     file contains the marker string 'generated by pre-commit' — a bare sample
  #     or unrelated hook does not count.
  git_common="$(git -C "$cwd" rev-parse --git-common-dir 2>/dev/null || true)"
  [ -n "$git_common" ] || git_common="$(git -C "$cwd" rev-parse --git-dir 2>/dev/null || true)"
  [ -n "$git_common" ] || exit 0   # cannot locate git dir -> fail open
  case "$git_common" in /*) : ;; *) git_common="$root/$git_common" ;; esac

  hooks_dir="$(git -C "$cwd" config --get core.hooksPath 2>/dev/null || true)"
  if [ -n "$hooks_dir" ]; then
    case "$hooks_dir" in /*) : ;; *) hooks_dir="$root/$hooks_dir" ;; esac
    # If core.hooksPath points OUTSIDE this repo, a centralized/global hooks
    # manager (e.g. a corporate git wrapper) owns the hooks. pre-commit's per-repo
    # `install` does not take effect there in the normal way, and we cannot reason
    # about a foreign manager — fail open rather than block on a setup we don't
    # control.
    case "$hooks_dir/" in
      "$root"/*) : ;;          # inside the repo -> trust it
      *) exit 0 ;;             # outside the repo -> fail open
    esac
  else
    hooks_dir="$git_common/hooks"
  fi

  # Which hook file backs this operation.
  hook_file=""
  if [ "$is_commit" -eq 1 ]; then hook_file="$hooks_dir/pre-commit"; fi
  if [ "$is_push" -eq 1 ]; then hook_file="$hooks_dir/pre-push"; fi

  # Installed == file exists AND is the pre-commit FRAMEWORK's generated hook. The
  # framework writes a distinctive marker comment ('generated by pre-commit') into
  # the hook; match THAT, not a bare 'pre-commit' substring (a corporate wrapper
  # or the .sample files mention 'pre-commit' too).
  if [ ! -f "$hook_file" ] || ! grep -q 'generated by pre-commit' "$hook_file" 2>/dev/null; then
    if [ "$is_commit" -eq 1 ]; then
      note "the git pre-commit hook is not installed, so the configured commit-stage checks will not run"
    else
      note "the git pre-push hook is not installed, so the configured pre-push checks will not run"
    fi
  fi
fi

# Emit at most one advisory JSON object, then exit 0 unconditionally.
if [ -n "$notes" ]; then
  jq -cn --arg ctx "$(printf 'pre-commit framework advisory (non-blocking):\n%s\nFix once: pre-commit install -t pre-commit -t pre-push' "$notes")" \
    '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"allow",additionalContext:$ctx}}' 2>/dev/null || true
fi
exit 0
