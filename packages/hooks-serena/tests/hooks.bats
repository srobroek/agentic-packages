#!/usr/bin/env bats

setup() {
  command -v jq >/dev/null 2>&1 || skip "jq not available"
  ROOT="$(cd "${BATS_TEST_DIRNAME}/.." && pwd -P)"
  CLAUDE="$ROOT/.apm/hooks/hooks-serena-claude-hooks.json"
  CODEX="$ROOT/.apm/hooks/hooks-serena-codex-hooks.json"
}

@test "Claude hook contract matches Serena documentation" {
  run jq -e '
    (.hooks | keys) == ["PreToolUse", "SessionEnd", "SessionStart"] and
    .hooks.PreToolUse == [{matcher:"", hooks:[{type:"command", command:"serena-hooks remind --client=claude-code"}]}] and
    .hooks.SessionStart == [{matcher:"", hooks:[{type:"command", command:"serena-hooks activate --client=claude-code"}]}] and
    .hooks.SessionEnd == [{matcher:"", hooks:[{type:"command", command:"serena-hooks cleanup --client=claude-code"}]}]
  ' "$CLAUDE"
  [ "$status" -eq 0 ]
}

@test "Codex hook contract matches Serena documentation" {
  run jq -e '
    (.hooks | keys) == ["PreToolUse", "SessionStart", "Stop"] and
    .hooks.PreToolUse == [{matcher:"Bash", hooks:[{type:"command", command:"serena-hooks remind --client=codex", timeout:30}]}] and
    .hooks.SessionStart == [{matcher:"startup|resume", hooks:[{type:"command", command:"serena-hooks activate --client=codex", timeout:30}]}] and
    .hooks.Stop == [{hooks:[{type:"command", command:"serena-hooks cleanup --client=codex", timeout:30}]}]
  ' "$CODEX"
  [ "$status" -eq 0 ]
}

@test "hook commands delegate stdin directly to Serena CLI" {
  run jq -er '
    [.hooks[][] | .hooks[] | .command] |
    all(test("^serena-hooks (remind|activate|cleanup) --client=(claude-code|codex)$"))
  ' "$CLAUDE"
  [ "$status" -eq 0 ]

  run jq -er '
    [.hooks[][] | .hooks[] | .command] |
    all(test("^serena-hooks (remind|activate|cleanup) --client=(claude-code|codex)$"))
  ' "$CODEX"
  [ "$status" -eq 0 ]
}
