#!/usr/bin/env bats
#
# Portability and correctness tests for the SpecKit PR-title hook.
# Target floor: bash 3.2.57 + BSD userland (stock macOS).

SCRIPTS="${BATS_TEST_DIRNAME}/../scripts"

setup() {
  TESTDIR="$(mktemp -d "${BATS_TMPDIR:-/tmp}/speckit-shell.XXXXXX")"
}

teardown() {
  rm -rf "$TESTDIR"
}

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
  cd "$TESTDIR"
  run bash "$SCRIPTS/speckit-pr-title.sh" <<<'{"tool_input":{"command":"gh pr create --fill"}}'
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}
