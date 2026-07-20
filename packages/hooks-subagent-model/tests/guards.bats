#!/usr/bin/env bats
#
# Tests for subagent-model-guard.sh — the PreToolUse:Agent model-routing deny
# gate.
#
# Portability floor: bash 3.2.57 + BSD sed/grep (stock macOS). These tests use
# only core bats (run / status / output) — no bats-support / bats-assert.
#
# Contract:
#   * `model` set                                   -> allow (no output)
#   * `subagent_type` set and NOT inherit-by-default -> allow (no output)
#   * `subagent_type` inherit-by-default, no model   -> deny + routing table
#   * `subagent_type` absent, no model               -> deny + routing table
#   * malformed / empty stdin, missing jq            -> allow (fail-open)

setup() {
  GUARD="${BATS_TEST_DIRNAME}/../scripts/subagent-model-guard.sh"
  [ -f "$GUARD" ] || { echo "guard script not found at $GUARD" >&2; return 1; }
  command -v jq >/dev/null 2>&1 || skip "jq not available"
}

# run_guard <json-payload> [env-assignment...] -> populates $output/$status and
# $decision (permissionDecision, or empty for allow/no-output).
run_guard() {
  payload="$1"; shift
  output="$(printf '%s' "$payload" | env "$@" bash "$GUARD")"
  status=$?
  decision="$(printf '%s' "$output" | jq -r '.hookSpecificOutput.permissionDecision // empty' 2>/dev/null || true)"
}

# --- allow: model explicitly set --------------------------------------------

@test "model set + general-purpose -> allow (no output)" {
  run_guard '{"tool_name":"Agent","tool_input":{"model":"haiku","subagent_type":"general-purpose"}}'
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "model set + subagent_type absent -> allow (no output)" {
  run_guard '{"tool_name":"Agent","tool_input":{"model":"sonnet"}}'
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

# --- allow: pinned (non-inherit) subagent_type ------------------------------

@test "pinned subagent_type (workflow-coder), no model -> allow (no output)" {
  run_guard '{"tool_name":"Agent","tool_input":{"subagent_type":"workflow-coder"}}'
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "pinned subagent_type (pr-reviewer), no model -> allow (no output)" {
  run_guard '{"tool_name":"Agent","tool_input":{"subagent_type":"pr-reviewer"}}'
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

# --- deny: inherit-by-default subagent_type without model ------------------

@test "general-purpose without model -> deny with routing table" {
  run_guard '{"tool_name":"Agent","tool_input":{"subagent_type":"general-purpose"}}'
  [ "$decision" = "deny" ]
  printf '%s' "$output" | jq -e '.hookSpecificOutput.permissionDecisionReason | test("haiku")' >/dev/null
  printf '%s' "$output" | jq -e '.hookSpecificOutput.permissionDecisionReason | test("sonnet")' >/dev/null
  printf '%s' "$output" | jq -e '.hookSpecificOutput.permissionDecisionReason | test("opus")' >/dev/null
}

@test "Explore without model -> deny" {
  run_guard '{"tool_name":"Agent","tool_input":{"subagent_type":"Explore"}}'
  [ "$decision" = "deny" ]
}

@test "Plan without model -> deny" {
  run_guard '{"tool_name":"Agent","tool_input":{"subagent_type":"Plan"}}'
  [ "$decision" = "deny" ]
}

@test "claude without model -> deny" {
  run_guard '{"tool_name":"Agent","tool_input":{"subagent_type":"claude"}}'
  [ "$decision" = "deny" ]
}

@test "fork without model -> deny" {
  run_guard '{"tool_name":"Agent","tool_input":{"subagent_type":"fork"}}'
  [ "$decision" = "deny" ]
}

# --- deny: subagent_type absent entirely, no model --------------------------

@test "no subagent_type, no model -> deny with routing table" {
  run_guard '{"tool_name":"Agent","tool_input":{"description":"d","prompt":"x"}}'
  [ "$decision" = "deny" ]
  printf '%s' "$output" | jq -e '.hookSpecificOutput.permissionDecisionReason | test("haiku")' >/dev/null
}

@test "deny reason teaches caller to re-issue with an explicit model" {
  run_guard '{"tool_name":"Agent","tool_input":{"subagent_type":"general-purpose"}}'
  printf '%s' "$output" | jq -e '.hookSpecificOutput.permissionDecisionReason | test("explicit model")' >/dev/null
}

@test "deny reason notes effort is not enforceable per-call" {
  run_guard '{"tool_name":"Agent","tool_input":{"subagent_type":"general-purpose"}}'
  printf '%s' "$output" | jq -e '.hookSpecificOutput.permissionDecisionReason | test("Effort is not enforceable")' >/dev/null
}

# --- env override: SUBAGENT_MODEL_GUARD_INHERIT_TYPES -----------------------

@test "env override adds a type to the inherit list -> now denied" {
  run_guard '{"tool_name":"Agent","tool_input":{"subagent_type":"workflow-coder"}}' \
    SUBAGENT_MODEL_GUARD_INHERIT_TYPES=workflow-coder
  [ "$decision" = "deny" ]
}

@test "env override shrinks the inherit list -> general-purpose now allowed" {
  run_guard '{"tool_name":"Agent","tool_input":{"subagent_type":"general-purpose"}}' \
    SUBAGENT_MODEL_GUARD_INHERIT_TYPES=Explore,Plan
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "env override with spaced list still matches (trimmed)" {
  run_guard '{"tool_name":"Agent","tool_input":{"subagent_type":"custom-thing"}}' \
    SUBAGENT_MODEL_GUARD_INHERIT_TYPES="general-purpose, custom-thing, Plan"
  [ "$decision" = "deny" ]
}

# --- fail-open: malformed / empty / non-Agent input --------------------------

@test "malformed JSON stdin -> allow, no crash" {
  run bash -c 'printf "%s" "not json {" | "$0"' "$GUARD"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "empty stdin -> allow, no output" {
  run bash -c 'printf "" | "$0"' "$GUARD"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "non-Agent tool_name -> allow, pass through" {
  run_guard '{"tool_name":"Bash","tool_input":{"command":"ls"}}'
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "tool_input as a bare string (no object) -> deny (no model/subagent_type available)" {
  run_guard '{"tool_name":"Agent","tool_input":"oops"}'
  [ "$decision" = "deny" ]
}

@test "guard parses under /bin/bash (no bash-4-only syntax)" {
  run /bin/bash -n "$GUARD"
  [ "$status" -eq 0 ]
}
