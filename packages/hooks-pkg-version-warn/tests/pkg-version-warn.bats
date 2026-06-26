#!/usr/bin/env bats
# Tests for pkg-version-warn.sh — advisory package-version hook.
#
# The hook is advisory only: it must always exit 0 and never block.
# Focus areas:
#   1. A real install command (pnpm add foo) emits a PACKAGE VERSION advisory.
#   2. A non-install command (echo hello) emits nothing.
#   3. The leading-token anchor: a substring like `echo "pip install ..."`
#      must NOT trip the advisory.
#   4. String-form tool_input is handled (no "Cannot index string" throw).
#   5. Malformed / empty stdin must not crash and must exit 0 with no jq leak.
#   6. `cargo add` is intentionally silent.
#   7. The three-token `uv pip install` form is handled.

setup() {
  HOOK="${BATS_TEST_DIRNAME}/../scripts/pkg-version-warn.sh"
}

# --- 1. Real install command emits an advisory ----------------------------

@test "pnpm add foo emits a PACKAGE VERSION advisory" {
  run bash -c 'printf "%s" '\''{"tool_input":{"command":"pnpm add foo"}}'\'' | bash "$1"' _ "$HOOK"
  [ "$status" -eq 0 ]
  ctx="$(printf '%s' "$output" | jq -r '.hookSpecificOutput.additionalContext')"
  [[ "$ctx" == *"PACKAGE VERSION"* ]]
  [[ "$ctx" == *"latest compatible version"* ]]
}

@test "output is valid PreToolUse json when an advisory fires" {
  run bash -c 'printf "%s" '\''{"tool_input":{"command":"go get example.com/x"}}'\'' | bash "$1"' _ "$HOOK"
  [ "$status" -eq 0 ]
  printf '%s' "$output" | jq -e '.hookSpecificOutput.hookEventName == "PreToolUse"'
}

@test "pip install emits an advisory" {
  run bash -c 'printf "%s" '\''{"tool_input":{"command":"pip install requests"}}'\'' | bash "$1"' _ "$HOOK"
  [ "$status" -eq 0 ]
  ctx="$(printf '%s' "$output" | jq -r '.hookSpecificOutput.additionalContext')"
  [[ "$ctx" == *"PACKAGE VERSION"* ]]
}

# --- 2. Non-install command emits nothing ---------------------------------

@test "echo hello emits no output and exits 0" {
  run bash -c 'printf "%s" '\''{"tool_input":{"command":"echo hello"}}'\'' | bash "$1" 2>&1' _ "$HOOK"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

# --- 3. Leading-token anchor: substrings do not trip the advisory ---------

@test "echo with quoted pip install substring does not trip the advisory" {
  run bash -c 'printf "%s" '\''{"tool_input":{"command":"echo \"pip install requests\""}}'\'' | bash "$1" 2>&1' _ "$HOOK"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
  [[ "$output" != *"PACKAGE VERSION"* ]]
}

@test "grep for npm install substring does not trip the advisory" {
  run bash -c 'printf "%s" '\''{"tool_input":{"command":"grep \"npm install\" log.txt"}}'\'' | bash "$1" 2>&1' _ "$HOOK"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

# --- 4. String-form tool_input is handled ---------------------------------

@test "string-form tool_input does not throw and still advises" {
  run bash -c 'printf "%s" '\''{"tool_input":"npm install lodash"}'\'' | bash "$1" 2>&1' _ "$HOOK"
  [ "$status" -eq 0 ]
  [[ "$output" != *"Cannot index string"* ]]
  [[ "$output" != *"jq:"* ]]
  ctx="$(printf '%s' "$output" | jq -r '.hookSpecificOutput.additionalContext')"
  [[ "$ctx" == *"PACKAGE VERSION"* ]]
}

# --- 5. Malformed / empty stdin: no crash, no jq leak, exit 0 -------------

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

# --- 6. cargo add is intentionally silent ---------------------------------

@test "cargo add emits no output (fetches latest by default)" {
  run bash -c 'printf "%s" '\''{"tool_input":{"command":"cargo add serde"}}'\'' | bash "$1" 2>&1' _ "$HOOK"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

# --- 7. Three-token uv pip install form -----------------------------------

@test "uv pip install is handled via the three-token branch" {
  run bash -c 'printf "%s" '\''{"tool_input":{"command":"uv pip install ruff"}}'\'' | bash "$1"' _ "$HOOK"
  [ "$status" -eq 0 ]
  ctx="$(printf '%s' "$output" | jq -r '.hookSpecificOutput.additionalContext')"
  [[ "$ctx" == *"PyPI"* ]]
}

@test "leading whitespace before the command is tolerated" {
  run bash -c 'printf "%s" '\''{"tool_input":{"command":"   composer require monolog/monolog"}}'\'' | bash "$1"' _ "$HOOK"
  [ "$status" -eq 0 ]
  ctx="$(printf '%s' "$output" | jq -r '.hookSpecificOutput.additionalContext')"
  [[ "$ctx" == *"Composer"* ]]
}
