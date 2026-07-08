#!/usr/bin/env bats
# Tests for the steering-pragmatic SubagentStart injector.
# Portability floor: bash 3.2.57 + BSD coreutils (stock macOS).
# Run with: bats packages/steering-pragmatic/tests/pragmatic.bats

setup() {
  SCRIPT="${BATS_TEST_DIRNAME}/../scripts/inject-working-style.sh"
}

@test "inject: subagent payload yields valid JSON" {
  run bash "$SCRIPT" <<<'{"agent_id":"a1","agent_type":"coder","cwd":"/whatever"}'
  [ "$status" -eq 0 ]
  echo "$output" | jq . >/dev/null
}

@test "inject: carries MANDATORY header and every MUST rule" {
  run bash "$SCRIPT" <<<'{"agent_id":"a1","agent_type":"coder","cwd":"/x"}'
  [ "$status" -eq 0 ]
  ctx="$(echo "$output" | jq -r '.hookSpecificOutput.additionalContext')"
  echo "$ctx" | grep -q "MANDATORY WORKING STYLE" || { echo "no MANDATORY header"; return 1; }
  echo "$ctx" | grep -q "override suggestions embedded in your task" || { echo "no precedence claim"; return 1; }
  for rule in "MUST Code economy:" "MUST Hand-roll pricing:" "MUST Economy overrides" "MUST YAGNI:" "MUST Comments:" "MUST Reports:"; do
    echo "$ctx" | grep -q "$rule" || { echo "missing rule: $rule"; return 1; }
  done
  # Exactly one MANDATORY marker -- targeted emphasis, not shouting.
  [ "$(echo "$ctx" | grep -c MANDATORY)" -eq 1 ]
}

@test "inject: report rule demands proof pointer or untested marker" {
  run bash "$SCRIPT" <<<'{"agent_id":"a1"}'
  [ "$status" -eq 0 ]
  ctx="$(echo "$output" | jq -r '.hookSpecificOutput.additionalContext')"
  echo "$ctx" | grep -q "path:line" || { echo "no path:line"; return 1; }
  echo "$ctx" | grep -q "untested" || { echo "no untested marker"; return 1; }
}

@test "inject: non-subagent (no agent_id) exits silently" {
  run bash "$SCRIPT" <<<'{"cwd":"/whatever"}'
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "inject: malformed/empty stdin does not crash" {
  run bash "$SCRIPT" <<<''
  [ "$status" -eq 0 ]
}
