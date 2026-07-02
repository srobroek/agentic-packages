#!/usr/bin/env bash
# chezmoi-guard.sh — PreToolUse hook. Warns (non-blocking) when a direct edit or
# shell mutation targets a file that chezmoi ACTUALLY manages, steering changes to
# the chezmoi source. The hook emits permissionDecision:"allow" with an
# additionalContext advisory — the operation proceeds; chezmoi apply will overwrite
# the target, so the source-of-truth is unaffected and recovery is trivial.
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
# undecidable, so it never warns.
set -euo pipefail

payload="$(cat)"
[[ -z "$payload" ]] && exit 0

# Cheap bail: when chezmoi is NOT installed the guard is a guaranteed no-op
# (membership is undecidable -> clean ALLOW), so skip both jq spawns up front.
command -v chezmoi >/dev/null 2>&1 || exit 0

# tool_input may be an object ({command|file_path: "..."}) OR a bare string. The
# naive `.tool_input.command // .tool_input` form THROWS on a string input (jq
# cannot index a string), which silently bypasses the guard. Branch on type.
#
# A bare-string tool_input is ambiguous (some tools pass the file path, some pass
# a command), so we feed it to BOTH checks: file_path catches a bare managed path,
# command catches a managed write verb/redirect. Neither check denies unless an
# exact managed write target is found, so applying both is safe.
# ONE jq spawn yields both fields via a merged parse. file_path goes FIRST (a
# path has no newline, so the line-based split is safe) and cmd LAST via $(cat),
# because a multi-line command WOULD otherwise bleed into the file_path field.
file_path=""
cmd=""
{
  IFS= read -r file_path || true
  cmd="$(cat)"
} < <(
  printf '%s' "$payload" | jq -j '
    (if (.tool_input|type)=="string" then .tool_input else (.tool_input.file_path // .tool_input.path // "") end) + "\n" +
    (if (.tool_input|type)=="string" then .tool_input else (.tool_input.command // "") end)
  ' 2>/dev/null
)

warn() {
  jq -cn --arg ctx "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"allow",additionalContext:$ctx}}' 2>/dev/null || true
  exit 0
}

# Per-user cache path (not a shared/predictable global TMPDIR file) so a multi-user
# host cannot let one user poison or pre-create another's membership list.
CACHE_FILE="${TMPDIR:-/tmp}/chezmoi-managed-cache.$(id -u)"
CACHE_TTL=60

ensure_cache() {
  command -v chezmoi >/dev/null 2>&1 || return 1
  if [[ -f "$CACHE_FILE" ]]; then
    local age mtime
    # mtime via GNU stat (-c %Y) or BSD/macOS stat (-f %m); each emits a bare
    # number on success. Guard the result so a non-numeric/empty value (either
    # stat variant rejecting the other's flag) can never feed `set -u` arithmetic.
    mtime="$(stat -c %Y "$CACHE_FILE" 2>/dev/null || stat -f %m "$CACHE_FILE" 2>/dev/null || true)"
    [[ "$mtime" =~ ^[0-9]+$ ]] || mtime=0
    age=$(( $(date +%s) - mtime ))
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
    warn "heads-up: '$file_path' is chezmoi-managed; a direct edit here will be overwritten on the next 'chezmoi apply'. Edit the source instead: chezmoi edit '$file_path' (source: chezmoi source-path '$file_path'). Proceeding."
  fi
fi

# --- Shell commands that mutate files ------------------------------------------
[[ -z "$cmd" || "$cmd" == "null" ]] && exit 0

# Only warn when a chezmoi-managed file is an actual WRITE TARGET. A managed path
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
done < <(printf '%s' "$cmd" | grep -oE '[0-9]*>>?[[:space:]]*("[^"]*"|'\''[^'\'']*'\''|[^[:space:]|&;<>]+)' || true)

# (b) In-place / destructive verbs whose path operands ARE the target
#     (rm, touch, chmod, chown, tee, ln, sed -i, perl -pi). Scan dotfile operands
#     ONLY in segments whose first word is one of those verbs, to avoid flagging a
#     read-only managed reference in a compound command like:
#       chmod /tmp/foo && diff ~/.config/MANAGED /tmp/foo
#     Split on shell separators (||, &&, |, ;, &) into segments; for each segment
#     check whether its first word is an in-place verb, then collect dotfile tokens
#     from that segment only, first stripping `< token` input-redirect sources so a
#     read source (e.g. `sed -i s/x/y/ file < ~/.config/MANAGED`) is not flagged.
while IFS= read -r segment; do
  # Trim leading whitespace, then peel leading wrappers and NAME=value env-
  # assignments so the REAL verb (rm/tee/chmod/...) becomes first_word even when
  # the command is prefixed with e.g. `sudo rm`, `env rm`, `time tee`,
  # `FOO=bar rm`, or `sudo -u root tee`. Bash 3.2 / BSD-safe: uses only case
  # globbing and parameter expansion, no ERE/grep.
  trimmed="${segment#"${segment%%[! ]*}"}"
  # Strip loop: peel one token at a time while it looks like a wrapper or
  # NAME=value assignment; stop when the leading token is neither.
  while :; do
    first_word="${trimmed%% *}"
    case "$first_word" in
      # NAME=value env assignment — strip this token (first_word already has it)
      # and any leading whitespace before the next token.
      *=*)
        trimmed="${trimmed#"$first_word"}"
        trimmed="${trimmed#"${trimmed%%[! ]*}"}"
        continue
        ;;
      # Known wrappers; each may be followed by option tokens ("-u root",
      # "--preserve-env", etc.) — strip the wrapper word and any immediately
      # following option-flag tokens (words starting with -).
      sudo|doas|env|time|nice|command|exec|xargs|stdbuf|nohup|setsid|ionice)
        trimmed="${trimmed#"$first_word"}"
        trimmed="${trimmed#"${trimmed%%[! ]*}"}"
        # Consume option tokens (words starting with '-') and their value args
        # (the single word immediately following a -* option, which may be a
        # username, group, etc. — e.g. `-u root` for sudo).
        while :; do
          next="${trimmed%% *}"
          case "$next" in
            -*)
              trimmed="${trimmed#"$next"}"
              trimmed="${trimmed#"${trimmed%%[! ]*}"}"
              # The token after a -flag is its value argument — consume it too,
              # unless the following token itself starts with '-' (another flag).
              val="${trimmed%% *}"
              case "$val" in
                -*|'') : ;;  # another flag or empty — don't consume
                *) trimmed="${trimmed#"$val"}"; trimmed="${trimmed#"${trimmed%%[! ]*}"}"; ;;
              esac
              ;;
            *) break ;;
          esac
        done
        continue
        ;;
    esac
    break
  done
  first_word="${trimmed%% *}"
  case "$first_word" in
    rm|touch|chmod|chown|tee|ln|sed|perl) : ;;
    *) continue ;;
  esac
  # For sed/perl require the -i / -pi flag to be present in this segment
  case "$first_word" in
    sed)  printf '%s' "$segment" | grep -qE -- '-i' || continue ;;
    perl) printf '%s' "$segment" | grep -qE -- '-pi' || continue ;;
  esac
  # Strip `< token` input-redirect sources so they are not mistaken for write targets
  seg_write="$(printf '%s' "$segment" | sed -E 's/<[[:space:]]*("[^"]*"|'\''[^'\'']*'\''|[^[:space:]|&;<>]+)//g')"
  while IFS= read -r tok; do
    [[ -n "$tok" ]] && targets+=("$tok")
  done < <(printf '%s' "$seg_write" | grep -oE "$dotfile_re" || true)
done < <(printf '%s\n' "$cmd" | tr -s '|&;' '\n' || true)

# (c) cp / mv: the destination is the last argument — check only that, so a
#     managed file used as a read SOURCE (`cp managed /tmp/x`) is not blocked.
#     Strip any trailing redirections FIRST (`cp src managed >/dev/null` would
#     otherwise make $NF the redirect token `/dev/null` and miss the real managed
#     destination). Drop every `[fd]>|>>  target` segment, then take the last arg.
if printf '%s' "$cmd" | grep -Eq '(^|[[:space:]])(cp|mv)([[:space:]]|$)'; then
  # Drop fd-dups (`2>&1`) first, then `[fd]>|>> target` redirects, so neither the
  # dup nor a redirect target can be mistaken for the cp/mv destination.
  cp_mv="$(printf '%s' "$cmd" | sed -E 's/[[:space:]][0-9]*>&[0-9-]+//g; s/[[:space:]][0-9]*>>?[[:space:]]*("[^"]*"|'\''[^'\'']*'\''|[^[:space:]|&;<>]+)//g')"
  targets+=("$(unquote "$(printf '%s' "$cp_mv" | awk '{print $NF}')")")
fi

# Decision is always chezmoi's: warn if a write-target is an exact managed entry.
for tok in ${targets[@]+"${targets[@]}"}; do
  [[ -z "$tok" ]] && continue
  abs="$(normalize_path "$tok")"
  if is_chezmoi_managed "$abs"; then
    warn "heads-up: shell write targets chezmoi-managed file '$tok'; it will be overwritten on the next 'chezmoi apply'. Edit the source instead (chezmoi source-path '$tok'). Proceeding."
  fi
done

exit 0
