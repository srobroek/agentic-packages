#!/usr/bin/env bats
#
# Coverage for the package-investigate PreToolUse nudge hook. Asserts the
# add/install path emits the deep-investigation context, update/remove emits the
# lighter review, unrelated commands stay silent, and malformed stdin never
# crashes. Also asserts the script PARSES under /bin/bash (macOS bash 3.2.57).
#
# Run: bats packages/hooks-package-investigate/tests/package-investigate.bats

setup() {
  SCRIPTS="${BATS_TEST_DIRNAME}/../scripts"
  HOOK="${SCRIPTS}/package-investigate.sh"
}

# --- helpers ---------------------------------------------------------------

# Build a Claude/Codex-style PreToolUse payload with an object tool_input.
mk_obj() {
  # $1 = command string
  jq -cn --arg cmd "$1" '{tool_input: {command: $cmd}}'
}

# Build a payload where tool_input is a bare STRING (the historical bypass).
mk_str() {
  # $1 = command string
  jq -cn --arg cmd "$1" '{tool_input: $cmd}'
}

# Run the hook with the given stdin payload; capture stdout into $output, the
# exit status into $status, and the additionalContext into $ctx (empty when the
# hook stays silent / allows with no output).
run_hook() {
  payload="$1"
  output="$(printf '%s' "$payload" | /bin/bash "$HOOK")"
  status=$?
  ctx="$(printf '%s' "$output" | jq -r '.hookSpecificOutput.additionalContext // empty' 2>/dev/null || true)"
}

# --- parse / portability floor --------------------------------------------

@test "package-investigate.sh parses under /bin/bash (no bash-4 syntax)" {
  run /bin/bash -n "$HOOK"
  [ "$status" -eq 0 ]
}

# --- add / install -> deep investigation nudge -----------------------------

@test "pnpm add foo -> investigate nudge" {
  run_hook "$(mk_obj "pnpm add foo")"
  [ "$status" -eq 0 ]
  [[ "$ctx" == *"Before adding this dependency"* ]]
}

@test "npm install left-pad -> investigate nudge" {
  run_hook "$(mk_obj "npm install left-pad")"
  [[ "$ctx" == *"Before adding this dependency"* ]]
}

@test "pip install requests -> investigate nudge" {
  run_hook "$(mk_obj "pip install requests")"
  [[ "$ctx" == *"Before adding this dependency"* ]]
}

@test "cargo add serde -> investigate nudge" {
  run_hook "$(mk_obj "cargo add serde")"
  [[ "$ctx" == *"Before adding this dependency"* ]]
}

@test "go get example.com/pkg -> investigate nudge" {
  run_hook "$(mk_obj "go get example.com/pkg")"
  [[ "$ctx" == *"Before adding this dependency"* ]]
}

@test "add after && separator -> investigate nudge" {
  run_hook "$(mk_obj "cd app && pnpm add foo")"
  [[ "$ctx" == *"Before adding this dependency"* ]]
}

# --- update / upgrade / remove -> lighter review ---------------------------

@test "npm remove bar -> lighter review" {
  run_hook "$(mk_obj "npm remove bar")"
  [ "$status" -eq 0 ]
  [[ "$ctx" == *"Dependency change (update/upgrade/remove)"* ]]
}

@test "pnpm update -> lighter review" {
  run_hook "$(mk_obj "pnpm update")"
  [[ "$ctx" == *"Dependency change (update/upgrade/remove)"* ]]
}

@test "cargo update -> lighter review" {
  run_hook "$(mk_obj "cargo update")"
  [[ "$ctx" == *"Dependency change (update/upgrade/remove)"* ]]
}

@test "go mod tidy -> lighter review" {
  run_hook "$(mk_obj "go mod tidy")"
  [[ "$ctx" == *"Dependency change (update/upgrade/remove)"* ]]
}

# --- unrelated commands stay silent ----------------------------------------

@test "ls -> allow, no output" {
  run_hook "$(mk_obj "ls")"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
  [ -z "$ctx" ]
}

@test "quoted 'pnpm add' inside echo is not at command position -> silent" {
  run_hook "$(mk_obj "echo 'run pnpm add later'")"
  [ "$status" -eq 0 ]
  [ -z "$ctx" ]
}

# --- string-form tool_input still gates (no bypass) ------------------------

@test "STRING-form tool_input pnpm add -> investigate nudge" {
  run_hook "$(mk_str "pnpm add foo")"
  [[ "$ctx" == *"Before adding this dependency"* ]]
}

# --- malformed stdin never crashes -----------------------------------------

@test "empty stdin -> exit 0, no output" {
  run_hook ""
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "invalid JSON stdin -> exit 0, no crash" {
  run_hook "this is not json {"
  [ "$status" -eq 0 ]
  [ -z "$ctx" ]
}

@test "tool_input absent -> exit 0, no output" {
  run_hook '{"foo":"bar"}'
  [ "$status" -eq 0 ]
  [ -z "$ctx" ]
}
