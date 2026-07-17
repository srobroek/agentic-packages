#!/usr/bin/env bash
#
# hooks-portability-ci: a CI gate that runs shipped hook scripts through the
# real failure modes the Phase-1/Phase-2 audits found. For every hook script it
# checks three things:
#
#   1. bash 3.2 parse        -- `/bin/bash -n` (the stock macOS floor). `;;&`
#                               fallthrough is a *parse* error on 3.2 and is
#                               caught here. `mapfile`/`readarray` are bash-4
#                               builtins that PARSE fine on 3.2 but fail at
#                               runtime (exit 127), so they are caught by a
#                               separate grep below rather than by `-n`.
#   2. GNU-only sed/grep     -- BSD sed/grep (stock macOS) reject GNU extensions
#                               such as `\b` word boundaries and `+?`/`*?` lazy
#                               quantifiers. We grep the source for these and
#                               flag them.
#   3. string-form payload   -- A PreToolUse hook must tolerate a tool_input that
#                               is a bare STRING (the historical bypass that
#                               crashed jq with "Cannot index string ..."). We
#                               feed each script {"tool_input":"<cmd>"} on stdin
#                               and assert it does not crash.
#
# Portability floor: bash 3.2.57 + BSD sed/grep/awk (stock macOS). No bash-4
# constructs (mapfile/readarray/associative arrays/`;;&`) are used here.
#
# Usage: portability-check.sh [dir]   (dir defaults to "packages")
#
# Exit status:
#   0  every discovered hook script passed every check
#   1  at least one script failed at least one check
#   2  usage / environment error (missing dir, missing jq)

set -uo pipefail

# --- arguments / environment ----------------------------------------------

ROOT="${1:-packages}"

if [ ! -d "$ROOT" ]; then
  printf 'error: directory not found: %s\n' "$ROOT" >&2
  exit 2
fi

# jq is required for the string-form payload check. If it is absent we cannot
# meaningfully assert the "no Cannot index string" behaviour, so fail loud
# rather than silently skipping a check in CI.
if ! command -v jq >/dev/null 2>&1; then
  printf 'error: jq is required for the string-form payload check\n' >&2
  exit 2
fi

# Pick the strictest available bash for the parse check. Stock macOS /bin/bash
# is 3.2.57, which is the real portability floor; fall back to PATH bash on
# Linux CI so the gate still runs there.
pick_bash() {
  if [ -x /bin/bash ] && /bin/bash --version 2>/dev/null | head -1 | grep -q 'version 3\.2'; then
    printf '/bin/bash'
  else
    printf 'bash'
  fi
}
FLOOR_BASH="$(pick_bash)"

# Run a command with a wall-clock bound and explicit stdin file so a script that
# blocks on stdin (or otherwise hangs) cannot wedge CI. The explicit redirect is
# required for the pure-bash background fallback: without it, non-interactive
# bash connects an asynchronous command's stdin to /dev/null. Prefer coreutils
# `timeout`/`gtimeout` when present; otherwise use the watchdog. Returns the
# command's status, or 124 on timeout.
PROBE_TIMEOUT="${PORTABILITY_PROBE_TIMEOUT:-5}"
run_bounded() {
  input_file="$1"
  shift
  if command -v timeout >/dev/null 2>&1; then
    timeout "$PROBE_TIMEOUT" "$@" <"$input_file"
    return $?
  fi
  if command -v gtimeout >/dev/null 2>&1; then
    gtimeout "$PROBE_TIMEOUT" "$@" <"$input_file"
    return $?
  fi
  # Pure-bash watchdog: run the command in the background, sleep-kill it if it
  # outlives the bound. bash 3.2 compatible.
  "$@" <"$input_file" &
  cmd_pid=$!
  ( sleep "$PROBE_TIMEOUT"; kill -TERM "$cmd_pid" 2>/dev/null ) \
    </dev/null >/dev/null 2>&1 &
  watch_pid=$!
  wait "$cmd_pid" 2>/dev/null
  cmd_st=$?
  kill -TERM "$watch_pid" 2>/dev/null
  wait "$watch_pid" 2>/dev/null || true
  return "$cmd_st"
}

# --- state -----------------------------------------------------------------

# bash 3.2 has no associative arrays; keep simple indexed arrays of report
# lines and always guard their expansion (set -u + empty array is fatal on 3.2).
fail_lines=()
checked=0
failed=0

add_fail() { fail_lines[${#fail_lines[@]}]="$1"; }

# Record a per-script failure: $1 = script path, $2 = check name, $3 = detail.
fail() {
  failed=$((failed + 1))
  add_fail "FAIL [$2] $1"
  add_fail "       $3"
}

# --- discovery -------------------------------------------------------------

# Find shipped hook scripts: any *.sh living under a */scripts/ directory or a
# */hooks/ path within the tree. We exclude tests/ (bats files are dev-only and
# are themselves the harness, not shipped runtime) and the gate's own script
# (it references `tool_input` in its source, so the string-payload probe would
# otherwise re-invoke the gate and recurse). bash 3.2 has no `mapfile`, so
# collect into an array via a while-read loop over a NUL-delimited find.
self="${BASH_SOURCE[0]:-$0}"
self_base="$(basename "$self")"
scripts=()
while IFS= read -r -d '' f; do
  [ "$(basename "$f")" = "$self_base" ] && continue
  scripts[${#scripts[@]}]="$f"
done < <(
  find "$ROOT" \
    -type f \
    -name '*.sh' \
    \( -path '*/scripts/*' -o -path '*/hooks/*' -o -path '*/hooks' \) \
    ! -path '*/tests/*' \
    -print0 2>/dev/null | sort -z
)

if [ "${#scripts[@]}" -eq 0 ]; then
  printf 'no hook scripts found under %s/ (looked under */scripts/ and */hooks)\n' "$ROOT"
  exit 0
fi

# Temp file holding the string-form payload fed to each probed script, plus the
# scratch file for parse-check stderr. Bats can provide a writable per-test
# directory even when the host TMPDIR is unavailable to a sandboxed process.
make_temp() {
  temp_name="$1"
  for temp_dir in "${TMPDIR:-}" "${BATS_TEST_TMPDIR:-}" /tmp; do
    [ -n "$temp_dir" ] || continue
    temp_path="$(mktemp "${temp_dir%/}/${temp_name}.XXXXXX" 2>/dev/null)" || continue
    printf '%s' "$temp_path"
    return 0
  done
  return 1
}

probe_in="$(make_temp portability-probe)" || {
  printf 'error: unable to create portability probe temp file\n' >&2
  exit 2
}
parse_err="$(make_temp portability-parse)" || {
  rm -f "$probe_in"
  printf 'error: unable to create portability parse temp file\n' >&2
  exit 2
}
trap 'rm -f "$probe_in" "$parse_err"' EXIT INT TERM

# --- checks ----------------------------------------------------------------

# 1) bash 3.2 parse + bash-4 runtime builtins.
#
# `bash -n` catches `;;&` and other 3.2 parse errors. `mapfile`/`readarray`
# parse fine on 3.2 but explode at runtime, so grep for a word-boundary-ish
# usage (BSD-grep-safe: we use a leading-context character class, not `\b`).
check_parse() {
  script="$1"
  if ! "$FLOOR_BASH" -n "$script" 2>"$parse_err"; then
    detail="$(head -3 "$parse_err" 2>/dev/null | tr '\n' ' ')"
    fail "$script" "bash32-parse" "${detail:-parse error under $FLOOR_BASH}"
    return 1
  fi
  # mapfile/readarray are bash-4 only. Match as a command (start of line or
  # after whitespace/;/&/|) so we do not flag the word inside a comment string
  # like "no mapfile here". Use a POSIX ERE the BSD grep accepts.
  if grep -nE '(^|[[:space:]]|[;&|])(mapfile|readarray)([[:space:]]|$)' "$script" \
      | grep -vE '^[[:space:]]*[0-9]+:[[:space:]]*#' >/dev/null 2>&1; then
    hit="$(grep -nE '(^|[[:space:]]|[;&|])(mapfile|readarray)([[:space:]]|$)' "$script" \
            | grep -vE '^[[:space:]]*[0-9]+:[[:space:]]*#' | head -1)"
    fail "$script" "bash4-builtin" "uses mapfile/readarray (bash-4, exit 127 on bash 3.2): ${hit}"
    return 1
  fi
  return 0
}

# 2) GNU-only sed/grep constructs that BSD sed/grep reject.
#
# Only lines that actually invoke sed/grep are considered, and comment lines are
# stripped first so a remark like "# BSD sed has no +?" is not flagged. Flagged:
#   - `\b` word boundary in *sed*  (BSD sed treats `\b` literally; GNU-only).
#     Note: BSD `grep` does support `\b`, so we scope this to sed per the audit.
#   - `+?` / `*?` lazy quantifiers in sed/grep (PCRE/GNU; not BSD ERE).
check_gnuism() {
  script="$1"
  rc=0
  # Lines invoking sed or grep, with their line numbers, excluding comment-only
  # lines (`grep -n` prefixes "N:", so a comment line reads "N:   # ...").
  tooling="$(
    grep -nE '(^|[[:space:]]|[;&|(])(sed|grep)([[:space:]])' "$script" 2>/dev/null \
      | grep -vE '^[0-9]+:[[:space:]]*#' || true
  )"
  if [ -z "$tooling" ]; then
    return 0
  fi
  # `\b` word boundary on a line invoking sed (BSD sed does not support it).
  sed_lines="$(printf '%s\n' "$tooling" | grep -E '(^|[[:space:]]|[;&|(])sed([[:space:]])' || true)"
  if [ -n "$sed_lines" ] && printf '%s\n' "$sed_lines" | grep -F '\b' >/dev/null 2>&1; then
    hit="$(printf '%s\n' "$sed_lines" | grep -F '\b' | head -1)"
    fail "$script" "gnu-sed-grep" "GNU \\b word boundary in sed (BSD sed treats it literally): ${hit}"
    rc=1
  fi
  # Lazy quantifiers `+?` or `*?` inside a sed/grep invocation.
  if printf '%s\n' "$tooling" | grep -E '[+*]\?' >/dev/null 2>&1; then
    hit="$(printf '%s\n' "$tooling" | grep -E '[+*]\?' | head -1)"
    fail "$script" "gnu-sed-grep" "GNU/PCRE lazy quantifier (+?/*?) in sed/grep (not BSD ERE): ${hit}"
    rc=1
  fi
  return "$rc"
}

# 3) string-form tool_input payload must not crash the script.
#
# Many guards index .tool_input.command; if tool_input is a bare string, a naive
# jq filter dies with "Cannot index string with ...". A correct guard treats the
# string itself as the command. We feed both an object and a string form and
# assert: no jq "Cannot index string" on stderr, and no unexpected hard crash.
#
# Scripts that do not read stdin (no `tool_input` reference at all) are skipped:
# they are not PreToolUse-shaped and the payload check does not apply.
check_string_payload() {
  script="$1"
  if ! grep -q 'tool_input' "$script" 2>/dev/null; then
    return 0
  fi
  # Feed the payload from a file (closed stdin) and bound the run so a hook that
  # blocks on stdin cannot hang the gate. Capture stderr only.
  printf '%s' '{"tool_input":"echo portability probe"}' > "$probe_in"
  err="$(run_bounded "$probe_in" "$FLOOR_BASH" "$script" 2>&1 >/dev/null)"
  st=$?
  if [ "$st" -eq 124 ]; then
    fail "$script" "string-payload" "timed out (${PROBE_TIMEOUT}s) reading string-form tool_input (blocks on stdin?)"
    return 1
  fi
  # A guard may legitimately exit 0 (allow) or, for a deliberately matched
  # payload, emit a decision. The failure signal is a jq type crash or an
  # unexpected non-0/2 status accompanied by an index error.
  if printf '%s' "$err" | grep -qiE 'cannot index (string|number|boolean)'; then
    fail "$script" "string-payload" "crashes on string-form tool_input: ${err}"
    return 1
  fi
  # Status 2 from set -e/pipefail blowups (not a deliberate deny) combined with
  # an error on stderr is also a crash. A clean status 0 with no stderr passes.
  if [ "$st" -ne 0 ] && [ -n "$err" ] \
      && printf '%s' "$err" | grep -qiE 'jq: error|unexpected|syntax error|bad substitution'; then
    fail "$script" "string-payload" "errors on string-form tool_input (status ${st}): ${err}"
    return 1
  fi
  return 0
}

# --- run -------------------------------------------------------------------

printf 'portability-check: %s script(s) under %s/ (floor bash: %s)\n' \
  "${#scripts[@]}" "$ROOT" "$FLOOR_BASH"
printf -- '----------------------------------------------------------------\n'

i=0
while [ "$i" -lt "${#scripts[@]}" ]; do
  script="${scripts[$i]}"
  i=$((i + 1))
  checked=$((checked + 1))
  check_parse "$script" || true
  check_gnuism "$script" || true
  check_string_payload "$script" || true
done

# --- report ----------------------------------------------------------------

printf -- '----------------------------------------------------------------\n'
if [ "${#fail_lines[@]}" -gt 0 ]; then
  j=0
  while [ "$j" -lt "${#fail_lines[@]}" ]; do
    printf '%s\n' "${fail_lines[$j]}"
    j=$((j + 1))
  done
  printf -- '----------------------------------------------------------------\n'
fi

printf 'checked %s script(s); %s failing check(s)\n' "$checked" "$failed"

if [ "$failed" -gt 0 ]; then
  exit 1
fi
exit 0
