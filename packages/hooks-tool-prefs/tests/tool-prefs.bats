#!/usr/bin/env bats
# Tests for enforce-tool-prefs.sh — advisory tool-preference hook.
#
# Focus areas (from audit phase-1 fix list):
#   1. Quote-aware segment splitting: a commit message containing a `;` and the
#      word `make` must NOT produce a spurious `make` suggestion.
#   2. Malformed stdin must not leak a jq parse error to stderr and must exit 0.
#   3. String-form tool_input must not throw (the old `.tool_input.command`
#      idiom threw "Cannot index string" and bypassed the hook).
#   4. Real command chains must still produce suggestions for each segment.
#
# The hook is advisory only: it must always exit 0 and never block.

setup() {
  HOOK="${BATS_TEST_DIRNAME}/../scripts/enforce-tool-prefs.sh"
  # Run in an isolated dir so the make-suggestion's justfile/Taskfile probes are
  # deterministic (no project files leaking in).
  TESTDIR="$(mktemp -d "${BATS_TEST_TMPDIR:-/tmp}/toolprefs.XXXXXX")"
  cd "$TESTDIR" || return 1
}

teardown() {
  [ -n "$TESTDIR" ] && rm -rf "$TESTDIR"
}

# --- 1. Quoted-metachar commit message: NO false suggestion ---------------

@test "quoted ; in commit message does not trigger a make suggestion" {
  run bash -c 'printf "%s" '\''{"tool_input":{"command":"git commit -m \"fix; make it work\""}}'\'' | bash "$1"' _ "$HOOK"
  [ "$status" -eq 0 ]
  # No suggestion at all: git is not a tracked tool, and the quoted `make`
  # must not be parsed as its own segment.
  [ -z "$output" ]
  [[ "$output" != *"make"* ]]
  [[ "$output" != *"TOOL PREFERENCE"* ]]
}

@test "single-quoted separators are not split into segments" {
  run bash -c 'printf "%s" '\''{"tool_input":{"command":"echo '\''\'\'''\''a; make b'\''\'\'''\''"}}'\'' | bash "$1"' _ "$HOOK"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "CLI tools (grep/find/ls/cat) produce no suggestion" {
  # CLI aesthetics were removed from this hook (static steering owns them);
  # only package managers, task runners, and version managers remain.
  run bash -c 'printf "%s" '\''{"tool_input":{"command":"grep x f | find . -name y && ls -la; cat file.txt"}}'\'' | bash "$1"' _ "$HOOK"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "non-Bash tool_name is ignored even with a matching command" {
  run bash -c 'printf "%s" '\''{"tool_name":"Grep","tool_input":{"command":"npm install"}}'\'' | bash "$1"' _ "$HOOK"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "explicit Bash tool_name still suggests" {
  run bash -c 'printf "%s" '\''{"tool_name":"Bash","tool_input":{"command":"npm install"}}'\'' | bash "$1"' _ "$HOOK"
  [ "$status" -eq 0 ]
  [[ "$output" == *"pnpm install"* ]]
}

# --- 2. Malformed stdin: no jq error leak, exit 0 -------------------------

@test "malformed json stdin produces no jq error and exits 0" {
  run bash -c 'printf "%s" "not valid json{{{" | bash "$1" 2>&1' _ "$HOOK"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
  [[ "$output" != *"parse error"* ]]
  [[ "$output" != *"jq:"* ]]
}

@test "empty stdin exits 0 with no output" {
  run bash -c 'printf "" | bash "$1" 2>&1' _ "$HOOK"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "valid json with empty command exits 0 with no output" {
  run bash -c 'printf "%s" '\''{"tool_input":{"command":""}}'\'' | bash "$1" 2>&1' _ "$HOOK"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

# --- 3. String-form tool_input must not throw -----------------------------

@test "string-form tool_input does not throw and still suggests" {
  run bash -c 'printf "%s" '\''{"tool_input":"pip install requests"}'\'' | bash "$1" 2>&1' _ "$HOOK"
  [ "$status" -eq 0 ]
  [[ "$output" != *"Cannot index string"* ]]
  [[ "$output" != *"jq:"* ]]
  [[ "$output" == *"uv"* ]]
}

@test "string-form tool_input with quoted metachar does not false-trigger" {
  run bash -c 'printf "%s" '\''{"tool_input":"git commit -m \"fix; make it work\""}'\'' | bash "$1" 2>&1' _ "$HOOK"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

# --- 4. Real chains still produce suggestions -----------------------------

@test "real chain suggests for each segment" {
  run bash -c 'printf "%s" '\''{"tool_input":{"command":"pip install x | npm install && make build"}}'\'' | bash "$1"' _ "$HOOK"
  [ "$status" -eq 0 ]
  ctx="$(printf '%s' "$output" | jq -r '.hookSpecificOutput.additionalContext')"
  [[ "$ctx" == *"uv"* ]]
  [[ "$ctx" == *"pnpm install"* ]]
  [[ "$ctx" == *"make"* ]]
}

@test "leading env-var assignments are stripped before base detection" {
  run bash -c 'printf "%s" '\''{"tool_input":{"command":"FOO=1 yarn add lodash"}}'\'' | bash "$1"' _ "$HOOK"
  [ "$status" -eq 0 ]
  ctx="$(printf '%s' "$output" | jq -r '.hookSpecificOutput.additionalContext')"
  [[ "$ctx" == *"pnpm"* ]]
}

@test "make suggestion prefers just when a justfile is present" {
  : > justfile
  run bash -c 'printf "%s" '\''{"tool_input":{"command":"make build"}}'\'' | bash "$1"' _ "$HOOK"
  [ "$status" -eq 0 ]
  ctx="$(printf '%s' "$output" | jq -r '.hookSpecificOutput.additionalContext')"
  [[ "$ctx" == *"just"* ]]
}

@test "output is always valid json when a suggestion fires" {
  run bash -c 'printf "%s" '\''{"tool_input":{"command":"nvm use 20"}}'\'' | bash "$1"' _ "$HOOK"
  [ "$status" -eq 0 ]
  printf '%s' "$output" | jq -e '.hookSpecificOutput.hookEventName == "PreToolUse"'
}
