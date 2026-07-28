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

write_codex_agent() {
  root="$1"; name="$2"; model="${3:-}"; effort="${4:-}"
  mkdir -p "$root/.codex/agents"
  {
    printf 'name = "%s"\n' "$name"
    printf 'description = "Test"\n'
    [ -z "$model" ] || printf 'model = "%s"\n' "$model"
    [ -z "$effort" ] || printf 'model_reasoning_effort = "%s"\n' "$effort"
    printf 'developer_instructions = "Work"\n'
  } > "$root/.codex/agents/$name.toml"
}

write_codex_agent_literal() {
  root="$1"; name="$2"; model="${3:-}"; effort="${4:-}"
  mkdir -p "$root/.codex/agents"
  {
    printf "name = '%s'\n" "$name"
    printf "description = 'Test'\n"
    [ -z "$model" ] || printf "model = '%s'\n" "$model"
    [ -z "$effort" ] || printf "model_reasoning_effort = '%s'\n" "$effort"
    printf "developer_instructions = 'Work'\n"
  } > "$root/.codex/agents/$name.toml"
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

# --- Codex: semantic profile resolution ------------------------------------

@test "Codex pinned project agent -> allow" {
  project="$BATS_TEST_TMPDIR/project"
  global="$BATS_TEST_TMPDIR/global"
  write_codex_agent "$project" workflow-coder gpt-5.6-luna xhigh
  payload="$(jq -cn --arg cwd "$project" '{tool_name:"Agent",cwd:$cwd,tool_input:{agent_type:"workflow-coder",task_name:"test"}}')"
  run_guard "$payload" CODEX_HOME="$global"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "Codex pinned project agent with TOML literal strings -> allow" {
  project="$BATS_TEST_TMPDIR/project"
  global="$BATS_TEST_TMPDIR/global"
  write_codex_agent_literal "$project" workflow-coder gpt-5.6-luna xhigh
  payload="$(jq -cn --arg cwd "$project" '{tool_name:"Agent",cwd:$cwd,tool_input:{agent_type:"workflow-coder",task_name:"test"}}')"
  run_guard "$payload" CODEX_HOME="$global"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "Codex pinned global agent -> allow" {
  project="$BATS_TEST_TMPDIR/project"
  global="$BATS_TEST_TMPDIR/global"
  mkdir -p "$project"
  write_codex_agent "$global" explorer gpt-5.6-luna medium
  payload="$(jq -cn --arg cwd "$project" '{tool_name:"Agent",cwd:$cwd,tool_input:{agent_type:"explorer",task_name:"test"}}')"
  run_guard "$payload" CODEX_HOME="$global/.codex"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "Codex pinned global agent with TOML literal strings -> allow" {
  project="$BATS_TEST_TMPDIR/project"
  global="$BATS_TEST_TMPDIR/global"
  mkdir -p "$project"
  write_codex_agent_literal "$global" explorer gpt-5.6-luna medium
  payload="$(jq -cn --arg cwd "$project" '{tool_name:"Agent",cwd:$cwd,tool_input:{agent_type:"explorer",task_name:"test"}}')"
  run_guard "$payload" CODEX_HOME="$global/.codex"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "Codex incomplete project profile shadows pinned global profile -> deny" {
  project="$BATS_TEST_TMPDIR/project"
  global="$BATS_TEST_TMPDIR/global"
  write_codex_agent "$project" workflow-coder
  write_codex_agent "$global" workflow-coder gpt-5.6-luna xhigh
  payload="$(jq -cn --arg cwd "$project" '{tool_name:"Agent",cwd:$cwd,tool_input:{agent_type:"workflow-coder",task_name:"test"}}')"
  run_guard "$payload" CODEX_HOME="$global/.codex"
  [ "$decision" = "deny" ]
  printf '%s' "$output" | jq -e '.hookSpecificOutput.permissionDecisionReason | test("shadows lower-precedence")' >/dev/null
}

@test "Codex unknown agent type -> deny" {
  project="$BATS_TEST_TMPDIR/project"
  mkdir -p "$project"
  payload="$(jq -cn --arg cwd "$project" '{tool_name:"Agent",cwd:$cwd,tool_input:{agent_type:"mystery",task_name:"test"}}')"
  run_guard "$payload" CODEX_HOME="$BATS_TEST_TMPDIR/empty"
  [ "$decision" = "deny" ]
  printf '%s' "$output" | jq -e '.hookSpecificOutput.permissionDecisionReason | test("no project or global custom profile")' >/dev/null
}

@test "Codex default agent, no profiles installed -> deny with create-profile guidance" {
  payload='{"tool_name":"Agent","cwd":"/tmp","tool_input":{"task_name":"test"}}'
  run_guard "$payload" CODEX_HOME="$BATS_TEST_TMPDIR/empty"
  [ "$decision" = "deny" ]
  printf '%s' "$output" | jq -e '.hookSpecificOutput.permissionDecisionReason | test("Define a project or global agent profile")' >/dev/null
}

@test "Codex default agent, profiles installed -> deny listing installed catalog" {
  project="$BATS_TEST_TMPDIR/catalog-project"
  global="$BATS_TEST_TMPDIR/catalog-global"
  write_codex_agent "$project" alpha-worker gpt-5.6-luna medium
  write_codex_agent "$project" beta-coder gpt-4o high
  write_codex_agent "$global" gamma-reviewer gpt-5.6-luna low
  payload="$(jq -cn --arg cwd "$project" '{tool_name:"Agent",cwd:$cwd,tool_input:{task_name:"test"}}')"
  run_guard "$payload" CODEX_HOME="$global/.codex"
  [ "$decision" = "deny" ]
  # Catalog names appear in the deny reason; alphabetical order.
  printf '%s' "$output" | jq -e '.hookSpecificOutput.permissionDecisionReason | test("alpha-worker")' >/dev/null
  printf '%s' "$output" | jq -e '.hookSpecificOutput.permissionDecisionReason | test("beta-coder")' >/dev/null
  printf '%s' "$output" | jq -e '.hookSpecificOutput.permissionDecisionReason | test("gamma-reviewer")' >/dev/null
  # No hardcoded legacy names should appear.
  printf '%s' "$output" | jq -e '.hookSpecificOutput.permissionDecisionReason | test("workflow-coder") | not' >/dev/null
  printf '%s' "$output" | jq -e '.hookSpecificOutput.permissionDecisionReason | test("luna-low") | not' >/dev/null
}

@test "Codex explicit ad-hoc model and effort require opt-in" {
  payload='{"tool_name":"Agent","cwd":"/tmp","tool_input":{"task_name":"test","model":"gpt-5.6-luna","reasoning_effort":"medium"}}'
  run_guard "$payload" CODEX_HOME="$BATS_TEST_TMPDIR/empty"
  [ "$decision" = "deny" ]
  run_guard "$payload" CODEX_HOME="$BATS_TEST_TMPDIR/empty" SUBAGENT_MODEL_GUARD_ALLOW_AD_HOC=1
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

# --- deny: inherit-by-default subagent_type without model ------------------

@test "general-purpose without model -> deny with routing table" {
  run_guard '{"tool_name":"Agent","tool_input":{"subagent_type":"general-purpose"}}'
  [ "$decision" = "deny" ]
  printf '%s' "$output" | jq -e '.hookSpecificOutput.permissionDecisionReason | test("sonnet")' >/dev/null
  printf '%s' "$output" | jq -e '.hookSpecificOutput.permissionDecisionReason | test("opus")' >/dev/null
}

# haiku is in the same disqualifying-rate group as sonnet (22-26% against opus at
# 6-8%, 485-cell matrix 2026-07) and no shipped agent pins it, so the routing
# message must not offer it as an option at all.
@test "deny reason does not offer haiku" {
  run_guard '{"tool_name":"Agent","tool_input":{"subagent_type":"general-purpose"}}'
  reason="$(printf '%s' "$output" | jq -r '.hookSpecificOutput.permissionDecisionReason')"
  [[ "$reason" != *haiku* ]]
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
  printf '%s' "$output" | jq -e '.hookSpecificOutput.permissionDecisionReason | test("opus")' >/dev/null
}

@test "deny reason teaches caller to re-issue with an explicit model" {
  run_guard '{"tool_name":"Agent","tool_input":{"subagent_type":"general-purpose"}}'
  printf '%s' "$output" | jq -e '.hookSpecificOutput.permissionDecisionReason | test("explicit model")' >/dev/null
}

@test "deny reason points at a task-specific agent_type first" {
  run_guard '{"tool_name":"Agent","tool_input":{"subagent_type":"general-purpose"}}'
  printf '%s' "$output" | jq -e '.hookSpecificOutput.permissionDecisionReason | test("agent_type")' >/dev/null
}

# The message is read by an agent mid-spawn, not by a human reviewing policy: it
# must carry the instruction and nothing else. Keep it short enough that the
# actionable part cannot get buried in rationale.
@test "deny reason stays terse" {
  run_guard '{"tool_name":"Agent","tool_input":{"subagent_type":"general-purpose"}}'
  reason="$(printf '%s' "$output" | jq -r '.hookSpecificOutput.permissionDecisionReason')"
  [ "$(printf '%s' "$reason" | wc -w)" -lt 60 ]
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
