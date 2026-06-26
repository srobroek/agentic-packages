#!/usr/bin/env bats
#
# Coverage for hooks-close-keywords:
#   - normalize-closes.sh   the shared rewrite engine (stdin -> stdout)
#   - commit-msg-rewrite.sh the pre-commit commit-msg entrypoint (rewrite a file)
#   - pr-close-guard.sh     the PreToolUse gh-pr guard (deny + corrected body)
#
# Portability floor: bash 3.2.57 + BSD userland.
# Run: bats packages/hooks-close-keywords/tests/close-keywords.bats

setup() {
  S="${BATS_TEST_DIRNAME}/../scripts"
  NORM="$S/normalize-closes.sh"
  MSG="$S/commit-msg-rewrite.sh"
  PRG="$S/pr-close-guard.sh"
  command -v jq >/dev/null 2>&1 || skip "jq not available"
}

# norm <text> -> echoes normalized text
norm() { printf '%s' "$1" | /bin/bash "$NORM"; }

# --- parse / portability floor ---------------------------------------------

@test "scripts parse under /bin/bash" {
  run /bin/bash -n "$NORM"; [ "$status" -eq 0 ]
  run /bin/bash -n "$MSG"; [ "$status" -eq 0 ]
  run /bin/bash -n "$PRG"; [ "$status" -eq 0 ]
}

# --- engine: distribution ---------------------------------------------------

@test "comma list: Closes #1, #2, #3 -> each gets the keyword" {
  [ "$(norm 'Closes #1, #2, #3')" = "Closes #1, closes #2, closes #3" ]
}

@test "'and' separator: Fixes #1, #2 and #3" {
  [ "$(norm 'Fixes #1, #2 and #3')" = "Fixes #1, fixes #2 and fixes #3" ]
}

@test "trailing ', and': Resolves #1, #2, and #3" {
  [ "$(norm 'Resolves #1, #2, and #3')" = "Resolves #1, resolves #2, and resolves #3" ]
}

@test "distributed keyword is lowercased; first keeps case" {
  [ "$(norm 'FIXES #1, #2')" = "FIXES #1, fixes #2" ]
}

# --- engine: idempotence & non-targets -------------------------------------

@test "idempotent: already-correct list is unchanged" {
  in='Closes #1, closes #2, closes #3'
  [ "$(norm "$in")" = "$in" ]
}

@test "single ref is unchanged" {
  [ "$(norm 'Closes #42')" = "Closes #42" ]
}

@test "bare references with NO keyword are left alone" {
  [ "$(norm 'See #1, #2 for context')" = "See #1, #2 for context" ]
}

@test "unrelated later #N (not contiguous) is not distributed" {
  [ "$(norm 'Fixes #5, #6. Also see #99 later')" = "Fixes #5, fixes #6. Also see #99 later" ]
}

@test "non-keyword word starting with a keyword (closet) is not matched" {
  [ "$(norm 'closet #1, #2')" = "closet #1, #2" ]
}

# --- engine: ref forms ------------------------------------------------------

@test "cross-repo and GH- refs: owner/repo#12, #13, GH-14" {
  [ "$(norm 'Resolves owner/repo#12, #13, GH-14')" = "Resolves owner/repo#12, resolves #13, resolves GH-14" ]
}

@test "list ends when a separator is not followed by a ref" {
  [ "$(norm 'Closes #1, #2 and then some prose')" = "Closes #1, closes #2 and then some prose" ]
}

# --- commit-msg-rewrite.sh --------------------------------------------------

@test "commit-msg: rewrites the message file in place" {
  f="$(mktemp "${BATS_TEST_TMPDIR}/msg.XXXXXX")"
  printf 'feat: x\n\nCloses #1, #2, #3\n' >"$f"
  run /bin/bash "$MSG" "$f"
  [ "$status" -eq 0 ]
  grep -q 'Closes #1, closes #2, closes #3' "$f"
}

@test "commit-msg: leaves a clean message untouched" {
  f="$(mktemp "${BATS_TEST_TMPDIR}/msg.XXXXXX")"
  printf 'fix: y\n\nCloses #7\n' >"$f"
  before="$(cat "$f")"
  run /bin/bash "$MSG" "$f"
  [ "$status" -eq 0 ]
  [ "$(cat "$f")" = "$before" ]
}

@test "commit-msg: missing file arg -> exit 0, no crash" {
  run /bin/bash "$MSG"
  [ "$status" -eq 0 ]
}

# --- pr-close-guard.sh ------------------------------------------------------

# pr <command> -> sets $status/$output from the guard
pr() {
  output="$(jq -cn --arg c "$1" '{tool_input:{command:$c}}' | /bin/bash "$PRG" 2>&1)" && status=0 || status=$?
}
# Empty hook output == allow (jq's // does not fire on empty stdin, so guard it).
decision() {
  [ -z "$output" ] && { printf 'allow'; return; }
  printf '%s' "$output" | jq -r '.hookSpecificOutput.permissionDecision // "allow"'
}

@test "pr guard: malformed --body (double-quoted) -> deny with corrected body" {
  pr 'gh pr create --title t --body "Closes #1, #2, #3"'
  [ "$(decision)" = "deny" ]
  printf '%s' "$output" | jq -r '.hookSpecificOutput.permissionDecisionReason' | grep -q 'Closes #1, closes #2, closes #3'
}

@test "pr guard: --body= inline form on gh pr edit -> deny" {
  pr 'gh pr edit 5 --body="Fixes #1, #2"'
  [ "$(decision)" = "deny" ]
}

@test "pr guard: already-correct body -> allow" {
  pr 'gh pr create --body "Closes #1, closes #2"'
  [ "$(decision)" = "allow" ]
}

@test "pr guard: body with no close keyword -> allow" {
  pr 'gh pr create --body "Just a normal PR description, see #5"'
  [ "$(decision)" = "allow" ]
}

@test "pr guard: not a gh pr command -> allow (silent)" {
  pr 'echo "Closes #1, #2"'
  [ "$(decision)" = "allow" ]
  [ -z "$output" ]
}

@test "pr guard: gh pr create with no inline body -> allow" {
  pr 'gh pr create --title t --fill'
  [ "$(decision)" = "allow" ]
}

@test "pr guard: empty stdin -> allow" {
  output="$(printf '' | /bin/bash "$PRG" 2>&1)" && status=0 || status=$?
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}
