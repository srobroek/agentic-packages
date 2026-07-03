#!/usr/bin/env bats
#
# Tests for subagent-worktree-guard.sh — the PreToolUse:Agent isolation advisory.
#
# Portability floor: bash 3.2.57 + BSD sed/grep (stock macOS). These tests use
# only core bats (run / status / output) — no bats-support / bats-assert.
#
# The hook reads a JSON event on stdin and, for tool_name == "Agent", emits a
# non-blocking advisory. It NEVER denies. Contract:
#   * isolation key present  -> silent (parent already chose), no output, exit 0
#   * otherwise (Agent)      -> emit additionalContext advisory, exit 0
#   * non-Agent / empty       -> pass through, no output, exit 0

setup() {
  GUARD="${BATS_TEST_DIRNAME}/../scripts/subagent-worktree-guard.sh"
  [ -f "$GUARD" ] || { echo "guard script not found at $GUARD" >&2; return 1; }
  command -v jq >/dev/null 2>&1 || skip "jq not available"
}

# ctx_of <json-payload> -> the additionalContext string, or empty if no output
ctx_of() {
  printf '%s' "$1" | "$GUARD" | jq -r '.hookSpecificOutput.additionalContext // empty' 2>/dev/null
}

# --- pass-through (no output) ----------------------------------------------

@test "non-Agent tool passes through silently" {
  run bash -c 'printf "%s" "$1" | "$0"' "$GUARD" '{"tool_name":"Bash","tool_input":{"command":"ls"}}'
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "empty payload passes through silently" {
  run bash -c 'printf "" | "$0"' "$GUARD"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

# --- never denies ----------------------------------------------------------

@test "never emits a deny decision" {
  out="$(printf '%s' '{"tool_name":"Agent","tool_input":{"description":"do work","prompt":"x"}}' | "$GUARD")"
  # permissionDecision must be absent (advisory uses additionalContext only)
  decision="$(printf '%s' "$out" | jq -r '.hookSpecificOutput.permissionDecision // "none"')"
  [ "$decision" = "none" ]
}

@test "Agent with string tool_input does not crash" {
  run bash -c 'printf "%s" "$1" | "$0"' "$GUARD" '{"tool_name":"Agent","tool_input":"oops"}'
  [ "$status" -eq 0 ]
}

# --- isolation already chosen -> silent ------------------------------------

@test "Agent with isolation:worktree is silent" {
  [ -z "$(ctx_of '{"tool_name":"Agent","tool_input":{"description":"w","prompt":"x","isolation":"worktree"}}')" ]
}

@test "Agent with isolation:remote is silent" {
  [ -z "$(ctx_of '{"tool_name":"Agent","tool_input":{"description":"w","prompt":"x","isolation":"remote"}}')" ]
}

# --- undeclared spawn -> advisory ------------------------------------------

@test "Agent without isolation gets an advisory" {
  ctx="$(ctx_of '{"tool_name":"Agent","tool_input":{"description":"do work","prompt":"x","subagent_type":"general-purpose"}}')"
  [ -n "$ctx" ]
}

@test "advisory mentions worktree isolation, parallel, and committing" {
  ctx="$(ctx_of '{"tool_name":"Agent","tool_input":{"description":"d","prompt":"x"}}')"
  printf '%s' "$ctx" | grep -qi 'worktree'
  printf '%s' "$ctx" | grep -qi 'commit'
  printf '%s' "$ctx" | grep -qi 'parallel'
}

@test "advisory exits 0 (non-blocking)" {
  run bash -c 'printf "%s" "$1" | "$0"' "$GUARD" '{"tool_name":"Agent","tool_input":{"description":"d","prompt":"x"}}'
  [ "$status" -eq 0 ]
}
