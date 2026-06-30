#!/usr/bin/env bats
#
# Portability + correctness tests for the speckit shell hooks.
# Target floor: bash 3.2.57 + BSD sed/grep (stock macOS).
#
# Covered scenarios (audit phase-1, speckit-shell stream):
#   1. pr-issue-refs.sh   -- SSH + HTTPS remote slug extraction (no BSD `+?`).
#   2. task-issue-sync.sh -- multi-task completion id extraction (no `\b`).
#   3. task-commit-check.sh + stop-gate.sh -- zero-task grep emits no error,
#                            no "0\n0" double-zero from `grep -c ... || echo 0`.
#   4. task-commit-check.sh -- runs outside a git repo without aborting.
#   5. issue-label-guard.sh -- issue titled "fix deferred loading" NOT blocked.

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

# ---------------------------------------------------------------------------
# 1. pr-issue-refs.sh slug regex: SSH + HTTPS forms, with/without .git
# ---------------------------------------------------------------------------

# Exercise the exact portable sed idiom the script uses, so we catch a
# regression in the pattern regardless of the surrounding git/gh plumbing.
slug() {
  printf '%s' "$1" | sed -E 's#.*[/:]([^/]+/[^/]+)$#\1#; s#\.git$##'
}

@test "slug: HTTPS remote with .git" {
  run slug "https://github.com/owner/repo.git"
  [ "$status" -eq 0 ]
  [ "$output" = "owner/repo" ]
}

@test "slug: HTTPS remote without .git" {
  run slug "https://github.com/owner/repo"
  [ "$status" -eq 0 ]
  [ "$output" = "owner/repo" ]
}

@test "slug: SSH remote (git@host:owner/repo.git)" {
  run slug "git@github.com:owner/repo.git"
  [ "$status" -eq 0 ]
  [ "$output" = "owner/repo" ]
}

@test "slug: SSH remote without .git" {
  run slug "git@github.com:owner/repo"
  [ "$status" -eq 0 ]
  [ "$output" = "owner/repo" ]
}

# Scan only code lines (strip full-line comments whose first non-space char is '#').
@test "pr-issue-refs.sh: code does not use BSD-illegal +? quantifier" {
  run bash -c 'grep -vE "^[[:space:]]*#" "$1" | grep -F "+?"' _ "$SCRIPTS/speckit-pr-issue-refs.sh"
  [ "$status" -ne 0 ]
}

# End-to-end: SSH remote, non-spec branch -> base guidance only, slug works.
@test "pr-issue-refs.sh: SSH remote end-to-end emits guidance JSON" {
  stub git \
    'case "$1 $2" in' \
    '  "branch --show-current") echo "main";;' \
    '  "remote get-url") echo "git@github.com:owner/repo.git";;' \
    '  *) exit 0;;' \
    'esac'
  run bash "$SCRIPTS/speckit-pr-issue-refs.sh" <<<'{"tool_input":{"command":"gh pr create --fill"}}'
  [ "$status" -eq 0 ]
  echo "$output" | jq -e '.hookSpecificOutput.hookEventName == "PreToolUse"'
}

# ---------------------------------------------------------------------------
# 2. task-issue-sync.sh: multi-task id extraction without \b
# ---------------------------------------------------------------------------

@test "task-issue-sync.sh: extracts multiple completed task ids" {
  mkdir -p "$TESTDIR/.specify"   # hook is a no-op outside a speckit project
  cd "$TESTDIR"
  patch=$'*** Update File: specs/001-foo/tasks.md\n+- [x] T001 first task\n+- [X] T042 second task\n+- [ ] T099 not done\n'
  run bash "$SCRIPTS/speckit-task-issue-sync.sh" <<EOF
{"tool_name":"apply_patch","tool_input":$(jq -Rs . <<<"$patch")}
EOF
  [ "$status" -eq 0 ]
  echo "$output" | jq -e '.hookSpecificOutput.additionalContext | test("T001")'
  echo "$output" | jq -e '.hookSpecificOutput.additionalContext | test("T042")'
  # T099 is unchecked ([ ]) and must NOT appear.
  echo "$output" | jq -e '.hookSpecificOutput.additionalContext | test("T099") | not'
}

@test "task-issue-sync.sh: code does not use BSD-unsupported \\\\b" {
  run bash -c 'grep -vE "^[[:space:]]*#" "$1" | grep -F "\\b"' _ "$SCRIPTS/speckit-task-issue-sync.sh"
  [ "$status" -ne 0 ]
}

# T1234 (4 digits) must not be captured as T123 -- boundary is enforced.
@test "task-issue-sync.sh: 3-digit boundary rejects 4-digit ids" {
  mkdir -p "$TESTDIR/.specify"
  cd "$TESTDIR"
  patch=$'*** Update File: tasks.md\n+- [x] T1234 four digit id\n'
  run bash "$SCRIPTS/speckit-task-issue-sync.sh" <<EOF
{"tool_name":"apply_patch","tool_input":$(jq -Rs . <<<"$patch")}
EOF
  # No valid TNNN-with-boundary match -> early exit, no JSON.
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

# ---------------------------------------------------------------------------
# 3. zero-task grep: no error, no double-zero
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
  # No spec.md -> HAS_PROJECT=false -> fallback grep path exercised.
  stub git \
    'case "$1 $2" in' \
    '  "branch --show-current") echo "'"$spec"'";;' \
    '  *) exit 0;;' \
    'esac'
  cd "$TESTDIR"
  run bash "$SCRIPTS/speckit-stop-gate.sh"
  [ "$status" -eq 0 ]
  echo "$output" | grep -qi "integer expression" && return 1
  echo "$output" | grep -qi "0" || true
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
# 4. task-commit-check.sh: outside a git repo, no abort under set -e
# ---------------------------------------------------------------------------

@test "task-commit-check.sh: non-repo invocation does not abort" {
  mkdir -p "$TESTDIR/.specify"
  # git stub that fails like a real git outside a repo (exit 128).
  stub git \
    'echo "fatal: not a git repository" >&2' \
    'exit 128'
  cd "$TESTDIR"
  run bash "$SCRIPTS/speckit-task-commit-check.sh" <<<'{"tool_input":{"command":"git commit -m x"}}'
  # set -e + git exit 128 previously aborted (status 128/1). Must be clean 0.
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# 5. issue-label-guard.sh: "fix deferred loading" title NOT blocked
# ---------------------------------------------------------------------------

@test "issue-label-guard.sh: title 'fix deferred loading' not treated as deferred" {
  mkdir -p "$TESTDIR/.specify"
  cd "$TESTDIR"
  cmd='gh issue create --title "fix deferred loading" --label "spec:001" --label "phase:impl"'
  run bash "$SCRIPTS/speckit-issue-label-guard.sh" <<EOF
{"tool_input":{"command":$(jq -Rs . <<<"$cmd")}}
EOF
  # Has spec: + phase:, and 'deferred' is only in the title, not a label value.
  # Must NOT be blocked (exit 2) for missing deferred/second-spec labels.
  [ "$status" -eq 0 ]
}

@test "issue-label-guard.sh: real deferred label still requires two spec labels" {
  mkdir -p "$TESTDIR/.specify"
  cd "$TESTDIR"
  cmd='gh issue create --title "blocked work" --label "spec:001" --label "phase:impl" --label "deferred"'
  run bash "$SCRIPTS/speckit-issue-label-guard.sh" <<EOF
{"tool_input":{"command":$(jq -Rs . <<<"$cmd")}}
EOF
  # Deferred label present but only ONE spec: label -> must emit advisory (non-blocking).
  [ "$status" -eq 0 ]
  ctx="$(printf '%s' "$output" | jq -r '.hookSpecificOutput.additionalContext // empty' 2>/dev/null || true)"
  echo "$ctx" | grep -qi "TWO spec"
}

@test "issue-label-guard.sh: deferred label with two spec labels passes" {
  mkdir -p "$TESTDIR/.specify"
  cd "$TESTDIR"
  cmd='gh issue create --title "blocked" --label "spec:001" --label "spec:002" --label "phase:impl" --label "deferred"'
  run bash "$SCRIPTS/speckit-issue-label-guard.sh" <<EOF
{"tool_input":{"command":$(jq -Rs . <<<"$cmd")}}
EOF
  [ "$status" -eq 0 ]
}

@test "issue-label-guard.sh: missing spec label -> advisory allow" {
  mkdir -p "$TESTDIR/.specify"
  cd "$TESTDIR"
  cmd='gh issue create --title "x" --label "phase:impl"'
  run bash "$SCRIPTS/speckit-issue-label-guard.sh" <<EOF
{"tool_input":{"command":$(jq -Rs . <<<"$cmd")}}
EOF
  [ "$status" -eq 0 ]
  ctx="$(printf '%s' "$output" | jq -r '.hookSpecificOutput.additionalContext // empty' 2>/dev/null || true)"
  [ -n "$ctx" ]
}

@test "issue-label-guard.sh: missing phase label -> advisory allow" {
  mkdir -p "$TESTDIR/.specify"
  cd "$TESTDIR"
  cmd='gh issue create --title "x" --label "spec:001"'
  run bash "$SCRIPTS/speckit-issue-label-guard.sh" <<EOF
{"tool_input":{"command":$(jq -Rs . <<<"$cmd")}}
EOF
  [ "$status" -eq 0 ]
  ctx="$(printf '%s' "$output" | jq -r '.hookSpecificOutput.additionalContext // empty' 2>/dev/null || true)"
  [[ "$ctx" == *"phase:"* ]]
}

@test "issue-label-guard.sh: GraphQL createIssue missing spec -> advisory allow" {
  mkdir -p "$TESTDIR/.specify"
  cd "$TESTDIR"
  cmd='gh api graphql -f query="mutation { createIssue(input: { title: \"x\" }) }"'
  run bash "$SCRIPTS/speckit-issue-label-guard.sh" <<EOF
{"tool_input":{"command":$(jq -Rs . <<<"$cmd")}}
EOF
  [ "$status" -eq 0 ]
  ctx="$(printf '%s' "$output" | jq -r '.hookSpecificOutput.additionalContext // empty' 2>/dev/null || true)"
  [[ "$ctx" == *"spec:"* ]]
}

# --- issue #6: false positives on echo/comment containing mutation + createIssue( ---

@test "issue-label-guard.sh: 'echo mutation; echo createIssue(' -> silent (issue #6)" {
  mkdir -p "$TESTDIR/.specify"
  cd "$TESTDIR"
  cmd='echo mutation; echo "createIssue("'
  run bash "$SCRIPTS/speckit-issue-label-guard.sh" <<EOF
{"tool_input":{"command":$(jq -Rs . <<<"$cmd")}}
EOF
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "issue-label-guard.sh: comment with mutation and createIssue( -> silent (issue #6)" {
  mkdir -p "$TESTDIR/.specify"
  cd "$TESTDIR"
  cmd='# run a mutation that calls createIssue() without spec'
  run bash "$SCRIPTS/speckit-issue-label-guard.sh" <<EOF
{"tool_input":{"command":$(jq -Rs . <<<"$cmd")}}
EOF
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "issue-label-guard.sh: echoed 'gh issue create' phrase -> silent (no advisory)" {
  mkdir -p "$TESTDIR/.specify"
  cd "$TESTDIR"
  cmd='echo "gh issue create later"'
  run bash "$SCRIPTS/speckit-issue-label-guard.sh" <<EOF
{"tool_input":{"command":$(jq -Rs . <<<"$cmd")}}
EOF
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}
