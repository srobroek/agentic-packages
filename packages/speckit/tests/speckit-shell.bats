#!/usr/bin/env bats
#
# Portability + correctness tests for the speckit shell hooks.
# Target floor: bash 3.2.57 + BSD sed/grep (stock macOS).
#
# Covered scenarios:
#   1. task-commit-check.sh + stop-gate.sh -- zero-task grep emits no error,
#      no "0\n0" double-zero from `grep -c ... || echo 0`.
#   2. task-commit-check.sh -- runs outside a git repo without aborting.
#   3. beads branch (stub bd on PATH) -- quoted bd query value, envelope- and
#      error-proof jq count, silent when all beads closed / non-spec branch.
#   4. pr-title.sh -- fires on gh pr create/edit, silent otherwise.

SCRIPTS="${BATS_TEST_DIRNAME}/../scripts"

setup() {
  TESTDIR="$(mktemp -d "${BATS_TMPDIR:-/tmp}/speckit-shell.XXXXXX")"
  BINDIR="$TESTDIR/bin"
  mkdir -p "$BINDIR"
  ORIG_PATH="$PATH"
}

teardown() {
  PATH="$ORIG_PATH"
  rm -rf "$TESTDIR"
}

# Write an executable stub onto the front of PATH.
# usage: stub <name> <body...>
stub() {
  local name="$1"; shift
  {
    printf '#!/usr/bin/env bash\n'
    printf '%s\n' "$@"
  } > "$BINDIR/$name"
  chmod +x "$BINDIR/$name"
  PATH="$BINDIR:$ORIG_PATH"
}

# Stub bd whose `where` succeeds and whose `query` replays canned JSON.
# usage: stub_bd '<json-for-query>'
# The stub records its query argv to $TESTDIR/bd-query-args for assertions.
stub_bd() {
  local query_json="$1"
  {
    printf '#!/usr/bin/env bash\n'
    printf 'case "$1" in\n'
    printf '  where) echo "%s/.beads"; exit 0;;\n' "$TESTDIR"
    printf '  query) printf "%%s\\n" "$2" > "%s/bd-query-args"; cat "%s/bd-query-out";;\n' "$TESTDIR" "$TESTDIR"
    printf '  *) exit 0;;\n'
    printf 'esac\n'
  } > "$BINDIR/bd"
  chmod +x "$BINDIR/bd"
  printf '%s' "$query_json" > "$TESTDIR/bd-query-out"
  PATH="$BINDIR:$ORIG_PATH"
}

# ---------------------------------------------------------------------------
# 1. zero-task grep: no error, no double-zero (legacy tasks.md fallback)
# ---------------------------------------------------------------------------

@test "task-commit-check.sh: zero-task tasks.md produces no grep error" {
  spec="012-empty-spec"
  mkdir -p "$TESTDIR/specs/$spec/.specify" "$TESTDIR/.specify"
  : > "$TESTDIR/specs/$spec/tasks.md"   # empty: zero checked, zero unchecked
  stub git \
    'case "$1 $2" in' \
    '  "branch --show-current") echo "'"$spec"'";;' \
    '  "log -1") echo "some commit #5";;' \
    '  *) exit 0;;' \
    'esac'
  # No bd on stub PATH is not guaranteed (host may have bd); mask it so the
  # legacy fallback path is exercised deterministically.
  stub bd 'exit 1'
  cd "$TESTDIR"
  run bash "$SCRIPTS/speckit-task-commit-check.sh" <<<'{"tool_input":{"command":"git commit -m x"}}'
  [ "$status" -eq 0 ]
  # Must not leak the "integer expression expected" error that a "0\n0" value triggers.
  echo "$output" | grep -qi "integer expression" && return 1
  [ -z "${output//[[:space:]]/}" ] || echo "$output" | jq -e '.' >/dev/null
}

@test "stop-gate.sh: zero-task tasks.md produces no grep/integer error" {
  spec="012-empty-spec"
  mkdir -p "$TESTDIR/specs/$spec" "$TESTDIR/.specify"
  : > "$TESTDIR/specs/$spec/tasks.md"
  stub git \
    'case "$1 $2" in' \
    '  "branch --show-current") echo "'"$spec"'";;' \
    '  *) exit 0;;' \
    'esac'
  stub bd 'exit 1'
  cd "$TESTDIR"
  run bash "$SCRIPTS/speckit-stop-gate.sh"
  [ "$status" -eq 0 ]
  echo "$output" | grep -qi "integer expression" && return 1
  return 0
}

@test "scripts: no 'grep -c ... || echo' double-zero idiom remains in code" {
  run bash -c '
    for f in "$@"; do
      grep -vE "^[[:space:]]*#" "$f" | grep -nE "grep -c.*\|\| *echo" && exit 0
    done
    exit 1
  ' _ "$SCRIPTS/speckit-task-commit-check.sh" "$SCRIPTS/speckit-stop-gate.sh"
  [ "$status" -ne 0 ]
}

# ---------------------------------------------------------------------------
# 2. task-commit-check.sh: outside a git repo, no abort under set -e
# ---------------------------------------------------------------------------

@test "task-commit-check.sh: non-repo invocation does not abort" {
  mkdir -p "$TESTDIR/.specify"
  # git stub that fails like a real git outside a repo (exit 128).
  stub git \
    'echo "fatal: not a git repository" >&2' \
    'exit 128'
  stub bd 'exit 1'
  cd "$TESTDIR"
  run bash "$SCRIPTS/speckit-task-commit-check.sh" <<<'{"tool_input":{"command":"git commit -m x"}}'
  # set -e + git exit 128 previously aborted (status 128/1). Must be clean 0.
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# 3. beads branch: quoted bd query value, envelope/error-proof jq count
# ---------------------------------------------------------------------------

@test "stop-gate.sh: beads branch reports open bead count" {
  spec="003-test-feat"
  mkdir -p "$TESTDIR/.specify"
  stub git \
    'case "$1 $2" in' \
    '  "branch --show-current") echo "'"$spec"'";;' \
    '  *) exit 0;;' \
    'esac'
  stub_bd '[{"id":"bd-1","status":"open"},{"id":"bd-2","status":"in_progress"}]'
  cd "$TESTDIR"
  run bash "$SCRIPTS/speckit-stop-gate.sh"
  [ "$status" -eq 0 ]
  echo "$output" | jq -e '.systemMessage | test("2 open beads")'
  # The query value must be quoted with the wildcard inside the quotes
  # (bd 1.1.0 parses unquoted hyphenated values as an error).
  grep -qF 'spec_id="003-test-feat*"' "$TESTDIR/bd-query-args"
}

@test "stop-gate.sh: beads branch silent when all beads closed" {
  spec="003-test-feat"
  mkdir -p "$TESTDIR/.specify"
  stub git \
    'case "$1 $2" in' \
    '  "branch --show-current") echo "'"$spec"'";;' \
    '  *) exit 0;;' \
    'esac'
  stub_bd '[]'
  cd "$TESTDIR"
  run bash "$SCRIPTS/speckit-stop-gate.sh"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "stop-gate.sh: bd error object counts as zero, not two" {
  spec="003-test-feat"
  mkdir -p "$TESTDIR/.specify"
  stub git \
    'case "$1 $2" in' \
    '  "branch --show-current") echo "'"$spec"'";;' \
    '  *) exit 0;;' \
    'esac'
  # bd parse errors emit an {error,schema_version} OBJECT; bare `jq length`
  # counts its 2 keys and fabricates "2 open beads".
  stub_bd '{"error":"parsing query: expected digit at position 12","schema_version":1}'
  cd "$TESTDIR"
  run bash "$SCRIPTS/speckit-stop-gate.sh"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "stop-gate.sh: BD_JSON_ENVELOPE=1 exported does not change the count" {
  spec="003-test-feat"
  mkdir -p "$TESTDIR/.specify"
  stub git \
    'case "$1 $2" in' \
    '  "branch --show-current") echo "'"$spec"'";;' \
    '  *) exit 0;;' \
    'esac'
  # Stub honors the env override: plain array when BD_JSON_ENVELOPE is empty
  # (the script must prefix BD_JSON_ENVELOPE=), envelope object otherwise.
  {
    printf '#!/usr/bin/env bash\n'
    printf 'case "$1" in\n'
    printf '  where) exit 0;;\n'
    printf '  query)\n'
    printf '    if [ -n "${BD_JSON_ENVELOPE:-}" ]; then\n'
    printf '      echo "{\\"data\\":[{\\"id\\":\\"bd-1\\"}]}"\n'
    printf '    else\n'
    printf '      echo "[{\\"id\\":\\"bd-1\\"}]"\n'
    printf '    fi;;\n'
    printf '  *) exit 0;;\n'
    printf 'esac\n'
  } > "$BINDIR/bd"
  chmod +x "$BINDIR/bd"
  PATH="$BINDIR:$ORIG_PATH"
  cd "$TESTDIR"
  BD_JSON_ENVELOPE=1 run bash "$SCRIPTS/speckit-stop-gate.sh"
  [ "$status" -eq 0 ]
  echo "$output" | jq -e '.systemMessage | test("1 open beads")'
}

@test "task-commit-check.sh: beads branch reports open bead count" {
  spec="003-test-feat"
  mkdir -p "$TESTDIR/.specify"
  stub git \
    'case "$1 $2" in' \
    '  "branch --show-current") echo "'"$spec"'";;' \
    '  "log -1") echo "feat: something";;' \
    '  *) exit 0;;' \
    'esac'
  stub_bd '[{"id":"bd-1","status":"open"}]'
  cd "$TESTDIR"
  run bash "$SCRIPTS/speckit-task-commit-check.sh" <<<'{"tool_input":{"command":"git commit -m x"}}'
  [ "$status" -eq 0 ]
  echo "$output" | jq -e '.hookSpecificOutput.additionalContext | test("1 open beads")'
  grep -qF 'spec_id="003-test-feat*"' "$TESTDIR/bd-query-args"
}

@test "task-commit-check.sh: beads branch silent when all beads closed" {
  spec="003-test-feat"
  mkdir -p "$TESTDIR/.specify"
  stub git \
    'case "$1 $2" in' \
    '  "branch --show-current") echo "'"$spec"'";;' \
    '  "log -1") echo "feat: something";;' \
    '  *) exit 0;;' \
    'esac'
  stub_bd '[]'
  cd "$TESTDIR"
  run bash "$SCRIPTS/speckit-task-commit-check.sh" <<<'{"tool_input":{"command":"git commit -m x"}}'
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "task-commit-check.sh: non-spec branch skips the bd query entirely" {
  mkdir -p "$TESTDIR/.specify"
  stub git \
    'case "$1 $2" in' \
    '  "branch --show-current") echo "main";;' \
    '  "log -1") echo "feat: something";;' \
    '  *) exit 0;;' \
    'esac'
  stub_bd '[{"id":"bd-1","status":"open"}]'
  cd "$TESTDIR"
  run bash "$SCRIPTS/speckit-task-commit-check.sh" <<<'{"tool_input":{"command":"git commit -m x"}}'
  [ "$status" -eq 0 ]
  [ -z "$output" ]
  # The [[ -n $active_spec ]] guard must short-circuit before bd query runs.
  [ ! -f "$TESTDIR/bd-query-args" ]
}

# ---------------------------------------------------------------------------
# 4. pr-title.sh: PR title/body guidance advisory
# ---------------------------------------------------------------------------

@test "pr-title.sh: gh pr create emits title guidance" {
  mkdir -p "$TESTDIR/.specify"
  cd "$TESTDIR"
  run bash "$SCRIPTS/speckit-pr-title.sh" <<<'{"tool_input":{"command":"gh pr create --fill"}}'
  [ "$status" -eq 0 ]
  echo "$output" | jq -e '.hookSpecificOutput.hookEventName == "PreToolUse"'
  echo "$output" | jq -e '.hookSpecificOutput.additionalContext | test("CHANGELOG ENTRY")'
}

@test "pr-title.sh: gh pr edit emits title guidance" {
  mkdir -p "$TESTDIR/.specify"
  cd "$TESTDIR"
  run bash "$SCRIPTS/speckit-pr-title.sh" <<<'{"tool_input":{"command":"gh pr edit 5 --title \"feat: x\""}}'
  [ "$status" -eq 0 ]
  echo "$output" | jq -e '.hookSpecificOutput.additionalContext | test("CHANGELOG ENTRY")'
}

@test "pr-title.sh: gh pr list stays silent" {
  mkdir -p "$TESTDIR/.specify"
  cd "$TESTDIR"
  run bash "$SCRIPTS/speckit-pr-title.sh" <<<'{"tool_input":{"command":"gh pr list"}}'
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "pr-title.sh: non-speckit project stays silent" {
  cd "$TESTDIR"   # no .specify
  run bash "$SCRIPTS/speckit-pr-title.sh" <<<'{"tool_input":{"command":"gh pr create --fill"}}'
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}
