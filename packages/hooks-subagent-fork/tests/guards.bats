#!/usr/bin/env bats
#
# Tests for subagent-fork-guard.sh — the PreToolUse:Agent fork_turns deny gate
# — and subagent-fork-inject.sh — the SubagentStart discipline digest.
#
# Portability floor: bash 3.2.57 + BSD sed/grep (stock macOS). Core bats only.
#
# Guard contract (Codex-shaped spawns: payload has task_name/agent_type/
# fork_turns/fork_context; Claude spawns pass through untouched):
#   * fork_turns omitted on a Codex spawn        -> deny (omitted == "all")
#   * fork_turns "none" / number <= max          -> allow (no output)
#   * fork_turns "all"                           -> deny + corrected format
#   * numeric fork_turns > max (default 3)       -> deny + corrected format
#   * SUBAGENT_FORK_GUARD_MAX overrides the cap; junk override falls back to 3
#   * Claude spawn shapes, non-spawn tools, malformed stdin, missing jq
#     -> allow (fail-open / out of scope)

setup() {
  GUARD="${BATS_TEST_DIRNAME}/../scripts/subagent-fork-guard.sh"
  INJECT="${BATS_TEST_DIRNAME}/../scripts/subagent-fork-inject.sh"
  [ -f "$GUARD" ] || { echo "guard script not found at $GUARD" >&2; return 1; }
  [ -f "$INJECT" ] || { echo "inject script not found at $INJECT" >&2; return 1; }
  command -v jq >/dev/null 2>&1 || skip "jq not available"
}

run_guard() {
  payload="$1"; shift
  if [ "$#" -gt 0 ]; then
    output="$(printf '%s' "$payload" | env "$@" bash "$GUARD")"
  else
    output="$(printf '%s' "$payload" | bash "$GUARD")"
  fi
  status=$?
  decision="$(printf '%s' "$output" | jq -r '.hookSpecificOutput.permissionDecision // empty' 2>/dev/null || true)"
  reason="$(printf '%s' "$output" | jq -r '.hookSpecificOutput.permissionDecisionReason // empty' 2>/dev/null || true)"
}

# --- allow ------------------------------------------------------------------

@test "Claude spawn shape (no codex fields) -> allow" {
  run_guard '{"tool_name":"Agent","tool_input":{"subagent_type":"coder","prompt":"do x","model":"sonnet"}}'
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "fork_turns omitted on codex spawn -> deny (defaults to all upstream)" {
  run_guard '{"tool_name":"Agent","tool_input":{"task_name":"code-reviewer"}}'
  [ "$status" -eq 0 ]
  [ "$decision" = "deny" ]
  printf '%s' "$reason" | grep -q 'omitted'
  printf '%s' "$reason" | grep -q 'fork_turns="none"'
}

@test "fork_turns none -> allow" {
  run_guard '{"tool_name":"Agent","tool_input":{"task_name":"code-reviewer","fork_turns":"none"}}'
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "fork_turns 2 (numeric json) -> allow" {
  run_guard '{"tool_name":"Agent","tool_input":{"task_name":"x","fork_turns":2}}'
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "fork_turns 3 string at cap -> allow" {
  run_guard '{"tool_name":"Agent","tool_input":{"task_name":"x","fork_turns":"3"}}'
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "non-spawn tool -> allow even with fork_turns all" {
  run_guard '{"tool_name":"Bash","tool_input":{"command":"echo fork_turns=all"}}'
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

# --- deny -------------------------------------------------------------------

@test "fork_turns all -> deny with corrected format" {
  run_guard '{"tool_name":"Agent","tool_input":{"task_name":"code-reviewer","fork_turns":"all"}}'
  [ "$status" -eq 0 ]
  [ "$decision" = "deny" ]
  printf '%s' "$reason" | grep -q 'fork_turns="none"'
  printf '%s' "$reason" | grep -q 'spawn_agent(task_name="code-reviewer", fork_turns="none")'
}

@test "fork_turns 4 (> default 3) -> deny" {
  run_guard '{"tool_name":"Agent","tool_input":{"task_name":"x","fork_turns":4}}'
  [ "$decision" = "deny" ]
}

@test "fork_turns 100 string -> deny" {
  run_guard '{"tool_name":"Agent","tool_input":{"task_name":"x","fork_turns":"100"}}'
  [ "$decision" = "deny" ]
}

@test "Task tool alias also guarded" {
  run_guard '{"tool_name":"Task","tool_input":{"task_name":"x","fork_turns":"all"}}'
  [ "$decision" = "deny" ]
}

# --- override ---------------------------------------------------------------

@test "SUBAGENT_FORK_GUARD_MAX=10 allows 8" {
  run_guard '{"tool_name":"Agent","tool_input":{"task_name":"x","fork_turns":8}}' SUBAGENT_FORK_GUARD_MAX=10
  [ -z "$output" ]
}

@test "SUBAGENT_FORK_GUARD_MAX=1 denies 2" {
  run_guard '{"tool_name":"Agent","tool_input":{"task_name":"x","fork_turns":2}}' SUBAGENT_FORK_GUARD_MAX=1
  [ "$decision" = "deny" ]
}

@test "junk SUBAGENT_FORK_GUARD_MAX falls back to 3: denies 4" {
  run_guard '{"tool_name":"Agent","tool_input":{"task_name":"x","fork_turns":4}}' SUBAGENT_FORK_GUARD_MAX=banana
  [ "$decision" = "deny" ]
}

# --- fail-open --------------------------------------------------------------

@test "empty stdin -> allow" {
  run_guard ''
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "malformed json -> allow" {
  run_guard '{not json'
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "tool_input as bare string -> allow (no crash)" {
  run_guard '{"tool_name":"Agent","tool_input":"spawn something"}'
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

# --- inject -----------------------------------------------------------------

@test "inject: subagent gets fork_turns discipline" {
  output="$(printf '%s' '{"agent_id":"abc123","agent_type":"coder"}' | bash "$INJECT")"
  ctx="$(printf '%s' "$output" | jq -r '.hookSpecificOutput.additionalContext')"
  printf '%s' "$ctx" | grep -q 'fork_turns="none"'
  printf '%s' "$ctx" | grep -q 'spawn_agent(task_name="code-reviewer", fork_turns="none")'
}

@test "inject: non-subagent (no agent_id) -> no output" {
  output="$(printf '%s' '{"session_id":"s1"}' | bash "$INJECT")"
  [ -z "$output" ]
}
