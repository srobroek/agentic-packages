#!/usr/bin/env bash
# chezmoi-guard.sh — PreToolUse hook. Denies direct edits / shell mutations of a
# file that chezmoi ACTUALLY manages, steering changes to the chezmoi source.
#
# Management is decided by EXACT membership in `chezmoi managed` (cached, 60s TTL),
# which is equivalent to `chezmoi source-path <file>` succeeding but ~500x faster
# (~0.4ms grep vs ~220ms CLI spawn; the hook runs on every write-shaped tool call).
#
# IMPORTANT: exact membership only — NO parent-directory prefix walk. The old walk
# over-blocked: `chezmoi managed` lists managed *targets* (and symlinks like
# ~/.config/agentic-tools itself), so walking parents flagged every file living
# beneath a managed dir — including the plain git-committed files in the
# external-managed/ tree, which are NOT managed targets (you edit them at source).
# Exact membership matches what source-path would confirm, without that false block.
#
# When chezmoi is NOT installed the hook is a clean ALLOW (exit 0): membership is
# undecidable, so it never blocks.
set -euo pipefail

payload="$(cat)"
[[ -z "$payload" ]] && exit 0

# tool_input may be an object ({command|file_path: "..."}) OR a bare string. The
# naive `.tool_input.command // .tool_input` form THROWS on a string input (jq
# cannot index a string), which silently bypasses the guard. Branch on type.
#
# A bare-string tool_input is ambiguous (some tools pass the file path, some pass
# a command), so we feed it to BOTH checks: file_path catches a bare managed path,
# command catches a managed write verb/redirect. Neither check denies unless an
# exact managed write target is found, so applying both is safe.
command="$(printf '%s' "$payload" | jq -r 'if (.tool_input|type)=="string" then .tool_input else (.tool_input.command // empty) end' 2>/dev/null || true)"
file_path="$(printf '%s' "$payload" | jq -r 'if (.tool_input|type)=="string" then .tool_input else (.tool_input.file_path // .tool_input.path // empty) end' 2>/dev/null || true)"

deny() {
  jq -cn --arg reason "$1" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: $reason
    }
  }'
  exit 0
}

# Per-user cache path (not a shared/predictable global TMPDIR file) so a multi-user
# host cannot let one user poison or pre-create another's membership list.
CACHE_FILE="${TMPDIR:-/tmp}/chezmoi-managed-cache.$(id -u)"
CACHE_TTL=60

ensure_cache() {
  command -v chezmoi >/dev/null 2>&1 || return 1
  if [[ -f "$CACHE_FILE" ]]; then
    local age
    age=$(( $(date +%s) - $(stat -f %m "$CACHE_FILE" 2>/dev/null || stat -c %Y "$CACHE_FILE" 2>/dev/null || echo 0) ))
    (( age <= CACHE_TTL )) && return 0
  fi
  chezmoi managed --path-style=absolute --include=files,symlinks 2>/dev/null > "$CACHE_FILE.new" \
    && mv "$CACHE_FILE.new" "$CACHE_FILE"
}

# Resolve ~ and relative paths to an absolute path, then canonicalize `.`/`..`
# LEXICALLY (no filesystem access — the target may not exist yet, and BSD
# `realpath` lacks `-m` and fails on missing paths). Canonicalization is required
# so a `..`-equivalent path (e.g. ~/.claude/../.claude/CLAUDE.md) cannot dodge the
# exact-membership test, whose entries are already canonical absolute paths.
normalize_path() {
  local p="$1"
  p="${p/#\~/$HOME}"
  case "$p" in
    /*) : ;;
    *)  p="$PWD/$p" ;;
  esac
  # Lexically collapse `.` and `..`. Segments are pushed/popped on a newline-
  # delimited stack so segments that contain spaces are preserved intact.
  local seg stack="" out=""
  local oldifs="$IFS"
  IFS='/'
  # word-splitting on '/' is intentional here
  # shellcheck disable=SC2086
  set -- $p
  IFS="$oldifs"
  for seg in "$@"; do
    case "$seg" in
      ''|.) continue ;;
      ..)   stack="${stack%$'\n'*}" ;;
      *)    stack="$stack"$'\n'"$seg" ;;
    esac
  done
  IFS=$'\n'
  for seg in $stack; do
    out="$out/$seg"
  done
  IFS="$oldifs"
  [[ -z "$out" ]] && out="/"
  printf '%s' "$out"
}

# Managed iff the resolved path is an EXACT entry in the managed list.
is_chezmoi_managed() {
  ensure_cache || return 1
  grep -qxF "$1" "$CACHE_FILE" 2>/dev/null
}

# --- Direct Edit/Write/MultiEdit of a file -------------------------------------
# Object-form Edit/Write/MultiEdit sets file_path and leaves command empty. A
# bare-string tool_input sets BOTH (see above); the membership check below catches
# a bare managed path, then control falls through to the command block so a string
# like `echo x > managed` is still inspected as a write. We never short-circuit
# past the command block while a command is present.
if [[ -n "$file_path" && "$file_path" != "null" ]]; then
  abs_path="$(normalize_path "$file_path")"
  if is_chezmoi_managed "$abs_path"; then
    deny "refusing direct edits to chezmoi-managed file '$file_path'; edit the chezmoi source instead (chezmoi source-path '$file_path')"
  fi
fi

# --- Shell commands that mutate files ------------------------------------------
[[ -z "$command" || "$command" == "null" ]] && exit 0

# Only deny when a chezmoi-managed file is an actual WRITE TARGET. A managed path
# that merely appears as a READ argument (cat/diff/ls/grep/readlink ...) must pass,
# even alongside an unrelated redirect like `>/dev/null`. So we collect the precise
# set of write-target tokens — never "every dotfile path in the command" — and
# check only those. This is what prevents read-only commands that reference a
# managed path from being blocked.
#
# LIMITATION (spaces in managed paths): the dotfile regex below matches an
# unquoted path token and stops at the first space, so a write target that is a
# QUOTED path containing a space (e.g. `tee "~/.config/a b/c"`) is not detected by
# branch (b). Redirect targets (a) and the cp/mv destination (c) are matched by
# whole token / last-arg and DO handle a quoted segment once unquoted below. Paths
# with spaces are rare in dotfile trees; the direct-Edit path (file_path) is
# unaffected and remains the primary guard.
dotfile_re='(~|'"$HOME"'|/Users/[^/]+)?/?\.(claude|codex|config)/[^ >"'\'']+'
targets=()

# Strip one layer of surrounding single/double quotes from a token, so a quoted
# write target (`>"~/.config/x"`, `mv a '~/.config/x'`) normalizes to the bare
# path before the membership test.
unquote() {
  local t="$1"
  case "$t" in
    \"*\") t="${t#\"}"; t="${t%\"}" ;;
    \'*\') t="${t#\'}"; t="${t%\'}" ;;
  esac
  printf '%s' "$t"
}

# (a) Redirect targets: the token after `>` / `>>`. Skip /dev/* sinks (e.g.
#     `>/dev/null`, `2>/dev/null`) — discarding output is never a managed write.
#     `2>&1`-style fd dups produce no file token and are naturally ignored.
while IFS= read -r rt; do
  rt="$(printf '%s' "$rt" | sed -E 's/^[0-9]*>>?[[:space:]]*//')"
  rt="$(unquote "$rt")"
  [[ -z "$rt" ]] && continue
  case "$rt" in /dev/*) continue ;; esac
  targets+=("$rt")
done < <(printf '%s' "$command" | grep -oE '[0-9]*>>?[[:space:]]*("[^"]*"|'\''[^'\'']*'\''|[^[:space:]|&;<>]+)' || true)

# (b) In-place / destructive verbs whose path operands ARE the target
#     (rm, touch, chmod, chown, tee, ln, sed -i, perl -pi). Scan dotfile operands.
if printf '%s' "$command" | grep -Eq '(^|[[:space:]])(rm|touch|chmod|chown|tee|ln)([[:space:]]|$)|(^|[[:space:]])sed[[:space:]].*-i|(^|[[:space:]])perl[[:space:]].*-pi'; then
  while IFS= read -r tok; do
    [[ -n "$tok" ]] && targets+=("$tok")
  done < <(printf '%s' "$command" | grep -oE "$dotfile_re" || true)
fi

# (c) cp / mv: the destination is the last argument — check only that, so a
#     managed file used as a read SOURCE (`cp managed /tmp/x`) is not blocked.
if printf '%s' "$command" | grep -Eq '(^|[[:space:]])(cp|mv)([[:space:]]|$)'; then
  targets+=("$(unquote "$(printf '%s' "$command" | awk '{print $NF}')")")
fi

# Decision is always chezmoi's: deny iff a write-target is an exact managed entry.
for tok in ${targets[@]+"${targets[@]}"}; do
  [[ -z "$tok" ]] && continue
  abs="$(normalize_path "$tok")"
  if is_chezmoi_managed "$abs"; then
    deny "refusing shell write to chezmoi-managed file '$tok'; edit the chezmoi source instead (chezmoi source-path '$tok')"
  fi
done

exit 0
