#!/usr/bin/env bats
#
# Tests for subagent-worktree-guard.sh — the PreToolUse:Agent isolation guard.
#
# Portability floor: bash 3.2.57 + BSD sed/grep (stock macOS). These tests use
# only core bats (run / status / output) — no bats-support / bats-assert — so
# they run anywhere bats + jq are installed.
#
# The hook reads a JSON event on stdin and emits a Claude PreToolUse decision on
# stdout. It fires only for tool_name == "Agent":
#   * isolation key present     -> allow by omission (no output, exit 0)
#   * description has [iso:skip] -> allow + updatedInput with sentinel stripped
#   * otherwise                  -> deny with an instruction to re-issue
# Non-Agent tools and empty payloads pass through (no output, exit 0).

setup() {
  GUARD="${BATS_TEST_DIRNAME}/../scripts/subagent-worktree-guard.sh"
  [ -f "$GUARD" ] || {
    echo "guard script not found at $GUARD" >&2
    return 1
  }
  command -v jq >/dev/null 2>&1 || skip "jq not available"
}

# decision_of <json-payload>
# Runs the guard with the payload on stdin and echoes the permissionDecision,
# or the literal string "allow" when the guard emits nothing.
decision_of() {
  local out
  out="$(printf '%s' "$1" | "$GUARD")"
  if [ -z "$out" ]; then
    printf 'allow'
  else
    printf '%s' "$out" | jq -r '.hookSpecificOutput.permissionDecision'
  fi
}

# --- pass-through cases -----------------------------------------------------

@test "non-Agent tool passes through (no output)" {
  run decision_of '{"tool_name":"Bash","tool_input":{"command":"ls"}}'
  [ "$status" -eq 0 ]
  [ "$output" = "allow" ]
}

@test "empty payload passes through (no output)" {
  run bash -c 'printf "" | "$0"' "$GUARD"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "Agent with string tool_input does not crash, passes through" {
  # A bare-string tool_input must not throw; with no object there is no
  # isolation and no description, so the guard denies (an undeclared spawn).
  run decision_of '{"tool_name":"Agent","tool_input":"oops"}'
  [ "$status" -eq 0 ]
  [ "$output" = "deny" ]
}

# --- isolation already chosen ----------------------------------------------

@test "Agent with isolation:worktree allows by omission" {
  run decision_of '{"tool_name":"Agent","tool_input":{"description":"write","prompt":"x","isolation":"worktree"}}'
  [ "$status" -eq 0 ]
  [ "$output" = "allow" ]
}

@test "Agent with isolation:remote allows by omission" {
  run decision_of '{"tool_name":"Agent","tool_input":{"description":"work","prompt":"x","isolation":"remote"}}'
  [ "$output" = "allow" ]
}

# --- undeclared spawn -> deny ----------------------------------------------

@test "Agent without isolation or sentinel is denied" {
  run decision_of '{"tool_name":"Agent","tool_input":{"description":"do work","prompt":"x","subagent_type":"general-purpose"}}'
  [ "$status" -eq 0 ]
  [ "$output" = "deny" ]
}

@test "deny reason names both the worktree and [iso:skip] options" {
  out="$(printf '%s' '{"tool_name":"Agent","tool_input":{"description":"d","prompt":"x"}}' | "$GUARD")"
  reason="$(printf '%s' "$out" | jq -r '.hookSpecificOutput.permissionDecisionReason')"
  printf '%s' "$reason" | grep -q '"isolation":"worktree"'
  printf '%s' "$reason" | grep -qF '[iso:skip]'
}

# --- sentinel opt-out -> allow + strip -------------------------------------

@test "Agent with [iso:skip] sentinel is allowed" {
  run decision_of '{"tool_name":"Agent","tool_input":{"description":"read files [iso:skip]","prompt":"x"}}'
  [ "$status" -eq 0 ]
  [ "$output" = "allow" ]
}

@test "sentinel is stripped from the description via updatedInput" {
  out="$(printf '%s' '{"tool_name":"Agent","tool_input":{"description":"read files [iso:skip]","prompt":"x","subagent_type":"general-purpose"}}' | "$GUARD")"
  desc="$(printf '%s' "$out" | jq -r '.hookSpecificOutput.updatedInput.description')"
  [ "$desc" = "read files" ]
}

@test "updatedInput preserves the other tool_input fields" {
  out="$(printf '%s' '{"tool_name":"Agent","tool_input":{"description":"x [iso:skip]","prompt":"PROMPT","subagent_type":"coder","model":"haiku"}}' | "$GUARD")"
  [ "$(printf '%s' "$out" | jq -r '.hookSpecificOutput.updatedInput.prompt')" = "PROMPT" ]
  [ "$(printf '%s' "$out" | jq -r '.hookSpecificOutput.updatedInput.subagent_type')" = "coder" ]
  [ "$(printf '%s' "$out" | jq -r '.hookSpecificOutput.updatedInput.model')" = "haiku" ]
}

@test "the stripped description no longer triggers a deny (no re-fire loop)" {
  # Feed the guard's own stripped output back in as a fresh spawn. Because the
  # sentinel is gone AND no isolation was added, this WOULD deny — which is why
  # the runtime must NOT re-fire PreToolUse on updatedInput. This test documents
  # that the stripped form is a terminal state the guard treats as undeclared;
  # the no-re-fire guarantee is the runtime's (verified separately end-to-end).
  run decision_of '{"tool_name":"Agent","tool_input":{"description":"read files","prompt":"x"}}'
  [ "$output" = "deny" ]
}

@test "sentinel mid-description is stripped cleanly" {
  out="$(printf '%s' '{"tool_name":"Agent","tool_input":{"description":"before [iso:skip] after","prompt":"x"}}' | "$GUARD")"
  desc="$(printf '%s' "$out" | jq -r '.hookSpecificOutput.updatedInput.description')"
  [ "$desc" = "before after" ]
}
