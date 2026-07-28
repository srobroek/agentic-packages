#!/usr/bin/env bats
#
# Coverage for the beads guard:
#   - beads-gh-issue-guard.sh    PreToolUse:Bash, denies mutating `gh issue`
#
# beads-subagent-reminder.py (SubagentStart advisory) was ported to Python;
# its cases live in tests/test_beads_subagent_reminder.py.
#
# The guard denies, which makes its negative cases the ones that matter: a
# read-only `gh issue list` is legitimate, a mention inside a quoted commit
# message is not a command, and a repository with no beads workspace is none of
# this hook's business. A deny that fires on correct work costs more than the
# convention it protects.
#
# `bd` and `jq` are stubbed on PATH so these tests describe the guard's logic
# rather than the machine's beads state.
#
# Portability floor: bash 3.2.57 + BSD userland.
# Run: bats packages/beads/tests/beads-hooks.bats

setup() {
  S="${BATS_TEST_DIRNAME}/../scripts"
  GUARD="$S/beads-gh-issue-guard.sh"
  command -v jq >/dev/null 2>&1 || skip "jq not available"

  # A workspace directory the guard will accept as beads-enabled.
  WORK="$BATS_TEST_TMPDIR/work"
  mkdir -p "$WORK/.beads"

  # Stub `bd` so `bd -C <dir> where` succeeds, which is the guard's gate.
  STUB="$BATS_TEST_TMPDIR/bin"
  mkdir -p "$STUB"
  printf '#!/bin/sh\nexit 0\n' >"$STUB/bd"
  chmod +x "$STUB/bd"
  PATH="$STUB:$PATH"
}

# guard <command> -> sets $output/$status
guard() {
  output="$(jq -cn --arg c "$1" --arg d "$WORK" '{cwd:$d,tool_input:{command:$c}}' \
    | /bin/bash "$GUARD" 2>&1)" && status=0 || status=$?
}

decision() {
  [ -z "$output" ] && { printf 'allow'; return; }
  printf '%s' "$output" | jq -r '.hookSpecificOutput.permissionDecision // "allow"'
}

# --- parse floor -------------------------------------------------------------

@test "scripts parse under /bin/bash" {
  run /bin/bash -n "$GUARD"; [ "$status" -eq 0 ]
}

# --- mutating gh issue is denied --------------------------------------------

@test "gh issue create is denied" {
  guard 'gh issue create --title x --body y'
  [ "$(decision)" = "deny" ]
}

@test "gh issue close is denied" {
  guard 'gh issue close 42'
  [ "$(decision)" = "deny" ]
}

@test "gh issue comment is denied" {
  guard 'gh issue comment 42 --body hi'
  [ "$(decision)" = "deny" ]
}

@test "the denial names the bd replacement, so the agent can self-correct" {
  guard 'gh issue create --title x'
  printf '%s' "$output" | jq -r '.hookSpecificOutput.permissionDecisionReason' \
    | grep -q 'bd create'
}

@test "a mutating gh issue behind a wrapper is still denied" {
  guard 'env FOO=1 gh issue close 42'
  [ "$(decision)" = "deny" ]
}

@test "a mutating gh issue inside command substitution is denied" {
  guard 'x=$(gh issue create --title y)'
  [ "$(decision)" = "deny" ]
}

@test "a mutating gh issue after a separator is denied" {
  guard 'git status && gh issue close 7'
  [ "$(decision)" = "deny" ]
}

# --- what must stay allowed -------------------------------------------------

@test "read-only gh issue list is allowed" {
  guard 'gh issue list --state open'
  [ "$(decision)" = "allow" ]
}

@test "read-only gh issue view is allowed" {
  guard 'gh issue view 42'
  [ "$(decision)" = "allow" ]
}

@test "gh pr commands are not gh issue commands" {
  guard 'gh pr create --title x --body y'
  [ "$(decision)" = "allow" ]
}

@test "a quoted mention in a commit message does not trip the guard" {
  guard "git commit -m 'do not gh issue close 42 by hand'"
  [ "$(decision)" = "allow" ]
}

@test "a double-quoted mention does not trip the guard" {
  guard 'git commit -m "gh issue create is banned here"'
  [ "$(decision)" = "allow" ]
}

@test "an unrelated command is silent" {
  guard 'ls -la'
  [ "$(decision)" = "allow" ]
  [ -z "$output" ]
}

# --- fail open --------------------------------------------------------------

@test "no beads workspace -> allow (bd where fails)" {
  printf '#!/bin/sh\nexit 1\n' >"$BATS_TEST_TMPDIR/bin/bd"
  chmod +x "$BATS_TEST_TMPDIR/bin/bd"
  guard 'gh issue create --title x'
  [ "$(decision)" = "allow" ]
}

@test "bd absent -> allow" {
  rm -f "$BATS_TEST_TMPDIR/bin/bd"
  guard 'gh issue create --title x'
  [ "$(decision)" = "allow" ]
}

@test "empty payload -> allow, exit 0" {
  output="$(printf '' | /bin/bash "$GUARD" 2>&1)" && status=0 || status=$?
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "malformed payload -> allow, exit 0" {
  output="$(printf 'not json {' | /bin/bash "$GUARD" 2>&1)" && status=0 || status=$?
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "string-form tool_input is read, not dropped" {
  output="$(jq -cn --arg c 'gh issue create --title x' --arg d "$WORK" \
    '{cwd:$d,tool_input:$c}' | /bin/bash "$GUARD" 2>&1)" && status=0 || status=$?
  [ "$status" -eq 0 ]
  [ "$(decision)" = "deny" ]
}

@test "never emits ask" {
  for c in 'gh issue create --title x' 'gh issue list' 'ls'; do
    guard "$c"
    [ "$(decision)" != "ask" ]
  done
}

# --- subagent reminder ------------------------------------------------------

@test "subagent reminder exits 0 on an empty payload" {
  output="$(printf '' | /bin/bash "$REMINDER" 2>&1)" && status=0 || status=$?
  [ "$status" -eq 0 ]
}

@test "subagent reminder exits 0 on malformed JSON" {
  output="$(printf '{oops' | /bin/bash "$REMINDER" 2>&1)" && status=0 || status=$?
  [ "$status" -eq 0 ]
}
