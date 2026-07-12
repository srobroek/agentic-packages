#!/usr/bin/env bats
# Tests for the write-docs SubagentStart doc-discipline injector.
# Portability floor: bash 3.2.57 + BSD coreutils (stock macOS).
# Run with: bats packages/write-docs/tests/write-docs.bats

setup() {
  SCRIPT="${BATS_TEST_DIRNAME}/../scripts/inject-doc-discipline.sh"
}

@test "inject: subagent payload yields valid JSON" {
  run bash "$SCRIPT" <<<'{"agent_id":"a1","agent_type":"general-purpose","cwd":"/whatever"}'
  [ "$status" -eq 0 ]
  echo "$output" | jq . >/dev/null
}

@test "inject: emits a SubagentStart hookSpecificOutput" {
  run bash "$SCRIPT" <<<'{"agent_id":"a1"}'
  [ "$status" -eq 0 ]
  echo "$output" | jq -e '.hookSpecificOutput.hookEventName == "SubagentStart"' >/dev/null
  echo "$output" | jq -e '.hookSpecificOutput.additionalContext | length > 0' >/dev/null
}

@test "inject: carries the discipline header, the skill-invocation rule, and the buried-task clause" {
  run bash "$SCRIPT" <<<'{"agent_id":"a1","agent_type":"coder","cwd":"/x"}'
  [ "$status" -eq 0 ]
  ctx="$(echo "$output" | jq -r '.hookSpecificOutput.additionalContext')"
  echo "$ctx" | grep -q "DOCUMENTATION DISCIPLINE" || { echo "no discipline header"; return 1; }
  echo "$ctx" | grep -q "Invoke the write-docs skill" || { echo "no skill-invocation rule"; return 1; }
  echo "$ctx" | grep -q "one step of a larger task" || { echo "no buried-task clause"; return 1; }
}

@test "inject: self-gates on the conditional documentation lead" {
  # The digest applies conditionally (unlike the universal working-style digest),
  # so a code-only subagent can harmlessly ignore it. The lead must state that.
  run bash "$SCRIPT" <<<'{"agent_id":"a1"}'
  [ "$status" -eq 0 ]
  ctx="$(echo "$output" | jq -r '.hookSpecificOutput.additionalContext')"
  echo "$ctx" | grep -q "applies when this task includes writing or reviewing any document" \
    || { echo "no conditional gate in lead"; return 1; }
}

@test "inject: carries the core MUST rules and NOT prohibitions" {
  run bash "$SCRIPT" <<<'{"agent_id":"a1"}'
  [ "$status" -eq 0 ]
  ctx="$(echo "$output" | jq -r '.hookSpecificOutput.additionalContext')"
  for rule in "MUST State what the artifact does" "MUST One idea per sentence" "MUST Consumer docs"; do
    echo "$ctx" | grep -q "$rule" || { echo "missing rule: $rule"; return 1; }
  done
  echo "$ctx" | grep -q "NOT Status language" || { echo "missing status-language prohibition"; return 1; }
  echo "$ctx" | grep -q "NOT Slop lexicon" || { echo "missing slop-lexicon prohibition"; return 1; }
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
